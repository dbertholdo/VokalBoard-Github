from fastapi import APIRouter, Request, Form, BackgroundTasks, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse

from app.database import fetch_all, fetch_one, execute, execute_returning
from app.auth import get_current_user
from app.render import render
from app.csrf import verify_csrf
from app.notifications import notify_matching_users
from app.badges import check_and_notify_new_badges
from app.urgency import ListingNotEligible, UrgencyUnavailable, get_urgency_status, mark_listing_urgent
from app.locations import COUNTRY_OPTIONS, STATE_OPTIONS, get_city_options
from app.richtext import html_to_excerpt
from app.highlights import get_weekly_highlights
from app.retention_rules import availability_valid
from app.vacancies import get_vacancies, parse_vacancies_form, set_vacancies
from app.fees import fee_valid, format_fee, CURRENCIES, DEFAULT_CURRENCY
from app.compatibility import FEE_COMPATIBILITY_ORDER_SQL, RATING_JOIN_SQL, viewer_location_params
from app.mascot_moments import profile_incomplete
from app.i18n import translate
from app.listing_pdf import ListingFlyerDocument, render_listing_flyer_pdf
from datetime import date
from sqlalchemy.exc import IntegrityError


def _persist_listing(query, params, returning=False):
    try:
        return execute_returning(query, params) if returning else execute(query, params)
    except IntegrityError as exc:
        reason = getattr(getattr(exc.orig, 'diag', None), 'message_primary', '')
        if reason in ('availability_limit', 'availability_invalid'):
            raise HTTPException(status_code=400, detail=reason) from exc
        raise


def _valid_event_date(value):
    try:
        date.fromisoformat(value)
        return True
    except (ValueError, TypeError):
        return False

router = APIRouter()

LISTING_TYPE_KEYS = [
    "seeking_singer",
    "seeking_conductor",
    "singer_available",
    "conductor_available",
]

ENSEMBLE_TYPE_KEYS = ["solo", "choir", "both"]

# "event_status" is calculated right in the SQL (CASE), it isn't
# stored in the database — this way it changes on its own as days go
# by, with no need for any job/routine to keep it up to date.
#   upcoming (green)  -> event more than 7 days in the future
#   soon     (yellow) -> event within the next 7 days
#   past     (red)    -> event already happened
#   NULL               -> listing with no event date (e.g. availability)
EVENT_STATUS_SQL = """
    CASE
        WHEN l.event_date IS NULL THEN NULL
        WHEN l.event_date < CURRENT_DATE THEN 'past'
        WHEN l.event_date <= CURRENT_DATE + INTERVAL '7 days' THEN 'soon'
        ELSE 'upcoming'
    END AS event_status
"""

LISTING_COLUMNS = f"""
    l.id, l.title, l.description, l.city, l.state, l.country, l.listing_type,
    l.repertoire, l.venue, l.fee_amount, l.fee_currency, l.fee_negotiable,
    l.ensemble_type, l.event_date, l.available_from, l.available_until, l.created_at,
    l.travel_cost_covered, l.rehearsal_schedule_available, l.sheet_music_available,
    l.is_urgent, l.urgent_marked_at,
    {EVENT_STATUS_SQL}
"""

# P5 Etapa 2 (18/09/2026): "urgência" só faz sentido pra quem está
# procurando preencher uma vaga — um autoanúncio de disponibilidade
# não tem "vaga" nenhuma pra marcar como urgente. Decisão do Daniel.
URGENCY_ELIGIBLE_LISTING_TYPES = ("seeking_singer", "seeking_conductor")

BOARD_PAGE_SIZE = 20

# Brake against "listing spam" (someone posting dozens of listings in
# a row, e.g. via automation) — this isn't about login/signup, it's
# about how many LISTINGS the same account can create in a short
# interval. Same "moving window" pattern used in
# app/routers/messages_routes.py (a direct COUNT on the table, no
# need for a separate counter table).
MAX_LISTINGS_PER_WINDOW = 5
LISTING_WINDOW_MINUTES = 5


def _listing_creation_throttled(author_id: int) -> bool:
    row = fetch_one(
        "SELECT COUNT(*) AS n FROM visible_listings WHERE author_id = :id AND created_at > now() - interval '1 minute' * :window",
        {"id": author_id, "window": LISTING_WINDOW_MINUTES},
    )
    return bool(row and row["n"] >= MAX_LISTINGS_PER_WINDOW)


def _job_fields_valid(listing_type: str, city: str, repertoire: str, has_vacancy: bool) -> bool:
    """
    Hiring a singer or conductor requires Repertoire, City, and at
    least one vacancy.

    FIX (19/09/2026, Daniel: "duas formas de adicionar vagas, fica
    confuso, inclusive para o código e db") — supersedes the previous
    same-day fix that made a standalone `voice_type_id` field required.
    That standalone field is GONE now for seeking_singer/
    seeking_conductor: the vacancy list (app/vacancies.py) is the only
    place voice type and fee are entered for these two types, so "at
    least one voice" and "at least one vacancy" are now the same
    requirement. Fee is intentionally NOT required here anymore either
    — it moved to being a per-vacancy field, same leniency vacancies
    already had (see parse_vacancies_form's docstring: a vaga's fee
    isn't strictly validated, it can be added/edited later).

    `has_vacancy` is computed by the caller from the already-parsed
    vacancies list: for seeking_singer, at least one row with a real
    voice type; for seeking_conductor, always True — a conductor
    listing always gets exactly one implicit vacancy synthesized by
    parse_vacancies_form(), since conductors have no naipe to choose.
    """
    if listing_type not in ("seeking_singer", "seeking_conductor"):
        return True
    return bool(city.strip()) and bool(repertoire.strip()) and has_vacancy


def _derive_listing_fields_from_vacancies(vacancies: list[dict], fallback_currency: str) -> tuple:
    """
    (19/09/2026) seeking_singer/seeking_conductor no longer collect
    voice_type_id/fee_amount/fee_currency/fee_negotiable directly —
    those live only in the vacancy list now (app/vacancies.py). This
    mirrors the vacancy data back onto `listings`' own columns so every
    OTHER piece of code that still reads `listings.voice_type_id`/fee
    directly — home page matching, board filtering, e-mail alerts in
    app/notifications.py, banner targeting in app/banners.py, the
    "Buscar pessoas" directory — keeps working unchanged, without
    having to be rewritten against listing_vacancies. Deliberately
    approximate for a multi-vacancy listing (several different voices):
    voice_type_id falls back to NULL ("all voices", an already-valid
    meaning) and fee falls back to unset, since there's no single
    correct answer to mirror in that case — the vacancy list itself
    (shown on listing_detail.html) is what shows the real breakdown.
    """
    if len(vacancies) == 1:
        v = vacancies[0]
        return v["voice_type_id"], v["fee_amount"], v["fee_currency"], v["fee_negotiable"]
    distinct_voice_ids = {v["voice_type_id"] for v in vacancies if v["voice_type_id"]}
    voice_type_id = next(iter(distinct_voice_ids)) if len(distinct_voice_ids) == 1 else None
    currency = fallback_currency if fallback_currency in CURRENCIES else DEFAULT_CURRENCY
    return voice_type_id, None, currency, False


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    """
    Home page — now a short welcome screen, not the whole listing
    board (that moved to /board).

    Logged in: "Welcome, {name}" + up to 5 openings that match the
    profile (singer: 'seeking_singer' listings for their own voice
    category; conductor: 'seeking_conductor' listings), prioritizing
    listings from their own city.

    Not logged in: a teaser with the 5 most recent openings, without
    the details ("freemium" model — see /board and /listings/{id} for
    the rest).
    """
    user = get_current_user(request)
    matches = []

    # P2 cluster, Profile Wizard (19/09/2026, decided with Daniel via
    # AskUserQuestion — "1 and 2": BOTH shown once automatically right
    # after signup AND reachable anytime later on demand from the
    # Atento mascot nudge, see app/templates/base.html). This is the
    # "once automatically" half: fires only the very first time this
    # person ever lands on a page with an incomplete profile, gated by
    # users.profile_wizard_seen_at (set the moment they actually reach
    # /profile/wizard — see app/routers/profile_routes.py). Never
    # fires again after that, even if the profile becomes incomplete
    # again later (e.g. they clear their bio) — it's a first-time
    # onboarding nudge, not a recurring interruption; the Atento toast
    # already covers "incomplete profile" as an ongoing nudge.
    if user and not user.get("profile_wizard_seen_at") and profile_incomplete(user):
        return RedirectResponse(url="/profile/wizard", status_code=303)

    if user:
        # P3.E: "quem paga mais primeiro", negociável por último,
        # desempatando por compatibilidade (cidade > nota, nunca
        # exibida) — ver app/compatibility.py. Substitui a antiga
        # ordem só-por-cidade.
        match_params = viewer_location_params(user)
        order_by_city = FEE_COMPATIBILITY_ORDER_SQL

        if user["role"] == "singer":
            conditions = [
                "l.is_active = TRUE",
                "l.listing_type = 'seeking_singer'",
                "(l.event_date IS NULL OR l.event_date >= CURRENT_DATE)",
                "NOT EXISTS (SELECT 1 FROM blocked_users bu WHERE (bu.blocker_id = :viewer_block_id AND bu.blocked_id = l.author_id) OR (bu.blocker_id = l.author_id AND bu.blocked_id = :viewer_block_id))",
            ]
            match_params["viewer_block_id"] = user["id"]
            # A singer can now have more than one voice type.  The old
            # singer_profiles.voice_type_id remains as a compatibility
            # fallback, but matching must use the dedicated relation first.
            conditions.append(
                """(
                    l.voice_type_id IS NULL
                    OR EXISTS (
                        SELECT 1 FROM singer_profile_voice_types spvt
                        WHERE spvt.user_id = :viewer_voice_user_id
                          AND spvt.voice_type_id = l.voice_type_id
                    )
                    OR EXISTS (
                        SELECT 1 FROM singer_profiles sp
                        WHERE sp.user_id = :viewer_voice_user_id
                          AND sp.voice_type_id = l.voice_type_id
                    )
                )"""
            )
            match_params["viewer_voice_user_id"] = user["id"]
            matches = fetch_all(
                f"""
                SELECT {LISTING_COLUMNS}, u.id AS author_id, u.full_name AS author_name, vt.name AS voice_type_name
                FROM visible_listings l
                JOIN users u ON u.id = l.author_id AND u.deleted_at IS NULL
                LEFT JOIN voice_types vt ON vt.id = l.voice_type_id
                {RATING_JOIN_SQL}
                WHERE {" AND ".join(conditions)}
                ORDER BY {order_by_city}
                LIMIT 5
                """,  # nosec B608 - only fixed fragments (conditions/order_by_city, no
                      # direct person input); the real values go in match_params, by parameter.
                match_params,
            )
        elif user["role"] == "conductor":
            match_params["viewer_block_id"] = user["id"]
            matches = fetch_all(
                f"""
                SELECT {LISTING_COLUMNS}, u.id AS author_id, u.full_name AS author_name, vt.name AS voice_type_name
                FROM visible_listings l
                JOIN users u ON u.id = l.author_id AND u.deleted_at IS NULL
                LEFT JOIN voice_types vt ON vt.id = l.voice_type_id
                {RATING_JOIN_SQL}
                WHERE l.is_active = TRUE AND l.listing_type = 'seeking_conductor'
                    AND (l.event_date IS NULL OR l.event_date >= CURRENT_DATE)
                    AND NOT EXISTS (SELECT 1 FROM blocked_users bu WHERE (bu.blocker_id = :viewer_block_id AND bu.blocked_id = l.author_id) OR (bu.blocker_id = l.author_id AND bu.blocked_id = :viewer_block_id))
                ORDER BY {order_by_city}
                LIMIT 5
                """,  # nosec B608 - only fixed fragments (order_by_city, no direct
                      # person input); the real values go in match_params, by parameter.
                match_params,
            )

    teaser_listings = []
    if not user:
        # P3.E: sem login não dá pra personalizar por cidade/perfil —
        # mas a ordem "quem paga mais primeiro, negociável por último"
        # vale igual (Daniel: "aparecerá 5 anúncios genéricos e
        # mistos, com os que pagam mais primeiro").
        teaser_listings = fetch_all(
            f"""
            SELECT {LISTING_COLUMNS}, u.full_name AS author_name
            FROM visible_listings l
            JOIN users u ON u.id = l.author_id AND u.deleted_at IS NULL
            {RATING_JOIN_SQL}
            WHERE l.is_active = TRUE AND (l.event_date IS NULL OR l.event_date >= CURRENT_DATE)
            ORDER BY {FEE_COMPATIBILITY_ORDER_SQL}
            LIMIT 5
            """,  # nosec B608 - only fixed fragments (FEE_COMPATIBILITY_ORDER_SQL,
                  # no person input); the real values go in the params dict, by parameter.
            viewer_location_params(None),
        )

    posts = fetch_all(
        """
        SELECT p.id, p.title, p.body, p.created_at, u.full_name AS author_name
        FROM posts p
        JOIN users u ON u.id = p.author_id
        WHERE p.is_published = TRUE
        ORDER BY p.created_at DESC
        LIMIT 5
        """
    )
    # The card on the home page shows only a plain-text summary
    # (without the editor's formatting/images) — the whole post, with
    # everything, lives at /posts/{id} (see post_detail() right below).
    for p in posts:
        p["excerpt"], p["is_truncated"] = html_to_excerpt(p["body"])

    # "Destaques da semana" — logged-in only (see app/highlights.py):
    # a teaser to a curated list of people would just be one more
    # "sign up to see more" wall, and this feature is meant to
    # reward/surface community members, not pressure visitors.
    highlights = get_weekly_highlights(user["id"]) if user else []

    context = {
        "user": user,
        "matches": matches,
        "teaser_listings": teaser_listings,
        "posts": posts,
        "highlights": highlights,
        "verify_required": request.query_params.get("verify_required") == "1",
    }
    return render(request, "home.html", context)


@router.get("/posts/{post_id}", response_class=HTMLResponse)
def post_detail(request: Request, post_id: int):
    """
    The full post page (open to any visitor, logged in or not — same
    model as /board). The card on the home page only shows a
    plain-text summary; here you get the full HTML, already sanitized
    when it was saved (see app/richtext.py), with formatting and
    images.

    An unpublished post is only visible to whoever has admin level
    (2+) — to give it one last check before reactivating it — anyone
    else gets a 404 (the reason isn't disclosed, so as not to leak
    that the post exists but is hidden).
    """
    user = get_current_user(request)
    post = fetch_one(
        """
        SELECT p.id, p.title, p.body, p.is_published, p.created_at, u.full_name AS author_name
        FROM posts p
        JOIN users u ON u.id = p.author_id
        WHERE p.id = :id
        """,
        {"id": post_id},
    )
    if not post:
        raise HTTPException(status_code=404)
    if not post["is_published"] and not (user and user.get("role_level") and user["role_level"] >= 2):
        raise HTTPException(status_code=404)

    context = {"user": user, "post": post}
    return render(request, "post_detail.html", context)


@router.get("/board", response_class=HTMLResponse)
def board(
    request: Request,
    city: str = "",
    state: str = "",
    country: str = "",
    listing_type: str = "",
    voice_type_id: str = "",
    ensemble_type: str = "",
    q: str = "",
    tag: str = "",
    show_past: str = "",
    date_from: str = "",
    date_to: str = "",
    urgent: str = "",
    page: int = 1,
):
    """
    The full listing board, with all filters. Open to any visitor
    (even without login) — what's locked without login is the
    *detail* of each listing (/listings/{id}), not the list.

    Listings with a past event are "archived" by default (they don't
    show up here, but stay in the database and are reachable via a
    direct link or in /my-listings) — ?show_past=1 shows all of them
    again.

    Date-range filter (Zeitraum) — "I have nothing marked in August,
    show me what exists between the 1st and 31st": date_from/date_to
    filter l.event_date within the range. Since choosing an explicit
    range is already the person saying exactly which time window
    matters to them, it replaces the default "hide past" filter
    (deliberately including the ability to search a range that
    already passed). Listings without an event_date (e.g.
    "available", with no date set) have no way to match a range and
    are left out when this filter is used.
    """
    user = get_current_user(request)

    # A verified e-mail is required to see the listings (not just to
    # publish) — whoever isn't logged in can still browse normally
    # (it's the public showcase that encourages signup); whoever
    # already created an account but hasn't confirmed their e-mail is
    # sent to the home page, which shows the notice and the button to
    # resend the confirmation link.
    if user and not user["email_verified"]:
        return RedirectResponse(url="/?verify_required=1", status_code=303)

    conditions = ["l.is_active = TRUE"]
    params = {}

    # Whoever the person blocked disappears from the board (their
    # listings no longer show up) — blocking is a one-way decision,
    # there's no need to check the reverse direction here.
    if user:
        conditions.append(
            "NOT EXISTS (SELECT 1 FROM blocked_users bu WHERE (bu.blocker_id = :viewer_block_id AND bu.blocked_id = l.author_id) OR (bu.blocker_id = l.author_id AND bu.blocked_id = :viewer_block_id))"
        )
        params["viewer_block_id"] = user["id"]

    # Retention view, rather than event end, determines when a listing disappears.

    if date_from:
        conditions.append("COALESCE(l.available_until,l.event_date) >= :date_from")
        params["date_from"] = date_from

    if date_to:
        conditions.append("COALESCE(l.available_from,l.event_date) <= :date_to")
        params["date_to"] = date_to

    if city:
        conditions.append("(l.city ILIKE :city OR (l.listing_type='singer_available' AND l.country IS NULL))")
        params["city"] = f"%{city}%"

    if state:
        conditions.append("(l.state = :state OR (l.listing_type='singer_available' AND l.country IS NULL))")
        params["state"] = state

    if country:
        conditions.append("(l.country = :country OR (l.listing_type='singer_available' AND l.country IS NULL))")
        params["country"] = country

    if listing_type:
        conditions.append("l.listing_type = :listing_type")
        params["listing_type"] = listing_type

    if voice_type_id:
        conditions.append("l.voice_type_id = :voice_type_id")
        params["voice_type_id"] = int(voice_type_id)

    if ensemble_type:
        conditions.append("l.ensemble_type = :ensemble_type")
        params["ensemble_type"] = ensemble_type

    if q:
        conditions.append("(l.title ILIKE :q OR l.description ILIKE :q OR l.repertoire ILIKE :q)")
        params["q"] = f"%{q}%"

    if tag:
        conditions.append(
            "EXISTS (SELECT 1 FROM singer_composer_tags sct WHERE sct.user_id = l.author_id AND sct.tag ILIKE :tag)"
        )
        params["tag"] = f"%{tag}%"

    # P5 Etapa 2 (18/09/2026): "?urgent=1" é o "quadro de vagas
    # urgentes" — reaproveita TODOS os filtros já existentes acima
    # (inclusive o de voz, "filtro por voz" do plano) em vez de ser
    # uma página separada com sua própria query.
    if urgent:
        conditions.append("l.is_urgent = TRUE")

    where_clause = " AND ".join(conditions)

    page = max(1, page)

    total_row = fetch_one(
        f"""
        SELECT count(*) AS n
        FROM visible_listings l
        WHERE {where_clause}
        """,  # nosec B608 - where_clause is just the join of fixed fragments (`conditions`,
              # assembled above); the real search values go in `params`.
        params,
    )
    total = total_row["n"] if total_row else 0
    total_pages = max(1, (total + BOARD_PAGE_SIZE - 1) // BOARD_PAGE_SIZE)
    page = min(page, total_pages)
    offset = (page - 1) * BOARD_PAGE_SIZE

    # "is_saved": to draw the little favorite star already correctly
    # marked on each card, without needing a second query per listing
    # (N+1) — a correlated EXISTS resolves it in a single query.
    # Without login, nobody has any favorite (:viewer_id = NULL
    # doesn't match anything in saved_listings.user_id, which is NOT NULL).
    listings = fetch_all(
        f"""
        SELECT
            {LISTING_COLUMNS},
            u.id AS author_id, u.full_name AS author_name,
            vt.name AS voice_type_name,
            EXISTS (
                SELECT 1 FROM saved_listings sl
                WHERE sl.listing_id = l.id AND sl.user_id = :viewer_id
            ) AS is_saved
        FROM visible_listings l
        JOIN users u ON u.id = l.author_id AND u.deleted_at IS NULL
        LEFT JOIN voice_types vt ON vt.id = l.voice_type_id
        WHERE {where_clause}
        ORDER BY l.is_urgent DESC, l.created_at DESC, l.id DESC
        LIMIT :limit OFFSET :offset
        """,  # nosec B608 - same fixed-fragment where_clause explained above.
        {**params, "limit": BOARD_PAGE_SIZE, "offset": offset, "viewer_id": user["id"] if user else None},
    )

    voice_types = fetch_all("SELECT id, name FROM voice_types ORDER BY sort_order")

    context = {
        "user": user,
        "listings": listings,
        "voice_types": voice_types,
        "listing_type_keys": LISTING_TYPE_KEYS,
        "ensemble_type_keys": ENSEMBLE_TYPE_KEYS,
        "country_options": COUNTRY_OPTIONS,
        "state_options": STATE_OPTIONS,
        "city_options": get_city_options(),
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "filters": {
            "city": city,
            "state": state,
            "country": country,
            "listing_type": listing_type,
            "voice_type_id": voice_type_id,
            "ensemble_type": ensemble_type,
            "q": q,
            "tag": tag,
            "show_past": show_past,
            "date_from": date_from,
            "date_to": date_to,
            "urgent": urgent,
        },
    }
    return render(request, "board.html", context)


@router.get("/listings/new", response_class=HTMLResponse)
def new_listing_form(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not user["email_verified"]:
        return RedirectResponse(url="/?verify_required=1", status_code=303)
    voice_types = fetch_all("SELECT id, name FROM voice_types ORDER BY sort_order")
    context = {
        "user": user,
        "voice_types": voice_types,
        "listing_type_keys": LISTING_TYPE_KEYS,
        "ensemble_type_keys": ENSEMBLE_TYPE_KEYS,
        "country_options": COUNTRY_OPTIONS,
        "state_options": STATE_OPTIONS,
        "city_options": get_city_options(),
        "currencies": CURRENCIES,
        "values": {"country": "DE", "fee_currency": DEFAULT_CURRENCY},
        "is_edit": False,
        "listing_id": None,
        "error": None,
        "vacancies": [],
    }
    return render(request, "listing_form.html", context)


def _listing_form_error_context(user, listing_type, title, description, city, state, country,
                                 voice_type_id, repertoire, venue, fee_amount, fee_currency, fee_negotiable,
                                 ensemble_type, event_date,
                                 is_edit, listing_id, available_from="", available_until=""):
    voice_types = fetch_all("SELECT id, name FROM voice_types ORDER BY sort_order")
    return {
        "user": user,
        "voice_types": voice_types,
        "listing_type_keys": LISTING_TYPE_KEYS,
        "ensemble_type_keys": ENSEMBLE_TYPE_KEYS,
        "country_options": COUNTRY_OPTIONS,
        "state_options": STATE_OPTIONS,
        "city_options": get_city_options(),
        "currencies": CURRENCIES,
        "values": {
            "listing_type": listing_type,
            "title": title,
            "description": description,
            "city": city,
            "state": state,
            "country": country,
            "voice_type_id": voice_type_id,
            "repertoire": repertoire,
            "venue": venue,
            "fee_amount": fee_amount,
            "fee_currency": fee_currency,
            "fee_negotiable": fee_negotiable,
            "ensemble_type": ensemble_type,
            "event_date": event_date,
            "available_from": available_from,
            "available_until": available_until,
        },
        "is_edit": is_edit,
        "listing_id": listing_id,
        "error": "error_required_fields",
        # Known rough edge: vacancy rows and the logistics checkboxes
        # aren't threaded back through this specific error path yet, so
        # they reset to empty on a validation error — the person just
        # re-checks them, nothing is lost from the database.
        "vacancies": [],
    }


@router.post("/listings/new")
async def create_listing(
    request: Request,
    background_tasks: BackgroundTasks,
    csrf_token: str = Form(""),
    listing_type: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    city: str = Form(""),
    state: str = Form(""),
    country: str = Form("DE"),
    voice_type_id: str = Form(""),
    repertoire: str = Form(""),
    venue: str = Form(""),
    fee_amount: str = Form(""),
    fee_currency: str = Form(DEFAULT_CURRENCY),
    fee_negotiable: str = Form(""),
    ensemble_type: str = Form(""),
    event_date: str = Form(""),
    available_from: str = Form(""),
    available_until: str = Form(""),
    travel_cost_covered: str = Form(""),
    sheet_music_available: str = Form(""),
    sheet_music_url: str = Form(""),
    rehearsal_schedule_available: str = Form(""),
    is_urgent: str = Form(""),
):
    verify_csrf(request, csrf_token)

    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not user["email_verified"]:
        return RedirectResponse(url="/?verify_required=1", status_code=303)

    # P3.E: valor numérico + moeda + "a negociar" — ver app/fees.py.
    # fee_amount_parsed é o Decimal já pronto pro INSERT — só é
    # realmente usado quando listing_type NÃO é seeking_singer/
    # seeking_conductor (esses dois passaram a derivar cachê da lista
    # de vagas, ver _derive_listing_fields_from_vacancies abaixo).
    # fee_ok fica sem uso pra esses dois tipos desde a mudança de
    # 19/09/2026 (fee deixou de ser obrigatório no nível do anúncio).
    fee_negotiable_bool = bool(fee_negotiable)
    if fee_currency not in CURRENCIES:
        fee_currency = DEFAULT_CURRENCY
    fee_ok, fee_amount_parsed = fee_valid(fee_amount, fee_negotiable_bool)

    # P3.A / FIX 19/09/2026: vacancies (naipe + cotas + cachê) are now
    # the ONLY way to enter voice type/fee for seeking_singer/
    # seeking_conductor — see app/vacancies.py's module docstring.
    form = await request.form()
    vacancies = parse_vacancies_form(
        form.getlist("vacancy_voice_type_id"),
        form.getlist("vacancy_fee_amount"),
        form.getlist("vacancy_fee_currency"),
        lambda i: form.get(f"vacancy_fee_negotiable_{i}"),
        form.getlist("vacancy_total_slots"),
        listing_type,
    )

    # P2.C: e-mail (já garantido acima, precisa estar verificado) e
    # telefone são obrigatórios para publicar um anúncio — nenhum dos
    # dois aparece em nenhum lugar até acontecer um Match (ver
    # match_history_routes.py); aqui só garantimos que existem.
    if not (user.get("phone") or "").strip():
        context = _listing_form_error_context(
            user, listing_type, title, description, city, state, country,
            voice_type_id, repertoire, venue, fee_amount, fee_currency, fee_negotiable_bool, ensemble_type, event_date, False, None, available_from, available_until,
        )
        context["error"] = "error_phone_required_for_listing"
        return render(request, "listing_form.html", context, status_code=400)

    if country not in COUNTRY_OPTIONS:
        country = "DE"
    if ensemble_type not in ENSEMBLE_TYPE_KEYS:
        ensemble_type = None

    if _listing_creation_throttled(user["id"]):
        context = _listing_form_error_context(
            user, listing_type, title, description, city, state, country,
            voice_type_id, repertoire, venue, fee_amount, fee_currency, fee_negotiable_bool, ensemble_type, event_date, False, None, available_from, available_until,
        )
        context["error"] = "error_listing_rate_limited"
        return render(request, "listing_form.html", context, status_code=429)

    # "State" is required for any listing (not just openings) —
    # together with Repertoire/City/at-least-one-vacancy in the
    # specific case of seeking_singer/seeking_conductor (see
    # _job_fields_valid's FIX note).
    available = listing_type == 'singer_available'
    has_vacancy = bool(vacancies)
    if (available and not availability_valid(available_from, available_until)) or (not available and (not state.strip() or not _job_fields_valid(listing_type, city, repertoire, has_vacancy))):
        context = _listing_form_error_context(
            user, listing_type, title, description, city, state, country,
            voice_type_id, repertoire, venue, fee_amount, fee_currency, fee_negotiable_bool, ensemble_type, event_date, False, None, available_from, available_until,
        )
        return render(request, "listing_form.html", context, status_code=400)

    if listing_type in ('seeking_singer', 'seeking_conductor') and not _valid_event_date(event_date):
        raise HTTPException(status_code=400, detail='Event date required')
    if available:
        event_date = ''
        if not state.strip() and not city.strip():
            country = None

    # FIX 19/09/2026: for seeking_singer/seeking_conductor, the
    # top-level voice_type_id/fee_* columns are no longer filled from
    # the (now-removed) standalone form fields — they're derived from
    # the vacancy rows instead, see _derive_listing_fields_from_vacancies.
    if listing_type in ('seeking_singer', 'seeking_conductor'):
        derived_voice_type_id, derived_fee_amount, derived_fee_currency, derived_fee_negotiable = \
            _derive_listing_fields_from_vacancies(vacancies, fee_currency)
    else:
        derived_voice_type_id = int(voice_type_id) if voice_type_id else None
        derived_fee_amount, derived_fee_currency, derived_fee_negotiable = fee_amount_parsed, fee_currency, fee_negotiable_bool

    new_listing = _persist_listing(
        """
        INSERT INTO listings (author_id, listing_type, title, description, city, state, country, voice_type_id, repertoire, venue, fee_amount, fee_currency, fee_negotiable, ensemble_type, event_date, available_from, available_until,
                               travel_cost_covered, sheet_music_available, sheet_music_url, rehearsal_schedule_available)
        VALUES (:author_id, :listing_type, :title, :description, :city, :state, :country, :voice_type_id, :repertoire, :venue, :fee_amount, :fee_currency, :fee_negotiable, :ensemble_type, :event_date, :available_from, :available_until,
                :travel_cost_covered, :sheet_music_available, :sheet_music_url, :rehearsal_schedule_available)
        RETURNING id
        """,
        {
            "author_id": user["id"],
            "listing_type": listing_type,
            "title": title,
            "description": description,
            "city": city or None,
            "state": state.strip() or None,
            "country": country,
            "voice_type_id": derived_voice_type_id,
            "repertoire": repertoire or None,
            "venue": venue or None,
            "fee_amount": derived_fee_amount,
            "fee_currency": derived_fee_currency,
            "fee_negotiable": derived_fee_negotiable,
            "ensemble_type": ensemble_type,
            "event_date": event_date or None,
            "available_from": available_from if available else None,
            "available_until": available_until if available else None,
            "travel_cost_covered": bool(travel_cost_covered),
            # Zero-Storage: the link is only kept when "available" is
            # checked — an unchecked box discards any leftover URL text.
            "sheet_music_available": bool(sheet_music_available),
            "sheet_music_url": (sheet_music_url.strip()[:500] or None) if sheet_music_available else None,
            "rehearsal_schedule_available": bool(rehearsal_schedule_available),
        }, returning=True,
    )

    if listing_type in ('seeking_singer', 'seeking_conductor') and vacancies:
        set_vacancies(new_listing["id"], vacancies)

    # P5 Etapa 2 (18/09/2026): checkbox "marcar como urgente" já na
    # criação — mesma função usada pelo botão "depois" em
    # mark_listing_urgent_route(). Síncrono (não background_task) de
    # propósito: se faltar Notas pra comprar, a pessoa precisa saber
    # na hora (vira um aviso na página seguinte), não descobrir depois
    # que a vaga simplesmente não ficou urgente.
    urgent_error = ""
    if is_urgent and listing_type in URGENCY_ELIGIBLE_LISTING_TYPES:
        try:
            mark_listing_urgent(user["id"], new_listing["id"])
        except UrgencyUnavailable:
            urgent_error = "insufficient_balance"
        except ListingNotEligible:
            pass  # não deveria acontecer aqui — vaga recém-criada, tipo já validado acima

    # Matching-listing alert: sends an e-mail to whoever has the
    # right profile (a singer with the voice being sought, or a
    # conductor) — in the background, so as not to delay the
    # redirect for whoever posted.
    background_tasks.add_task(
        notify_matching_users,
        str(request.base_url),
        new_listing["id"],
        listing_type,
        title,
        city or None,
        user["id"],
        int(voice_type_id) if voice_type_id else None,
    )

    background_tasks.add_task(check_and_notify_new_badges, user["id"], str(request.base_url))
    # Recompensa de Notas por anúncio publicado: REDESENHADA 19/09/2026 —
    # não credita mais na hora daqui. app/listing_reward_worker.py (rodando
    # de hora em hora) é quem credita agora, depois que a vaga fica 48h no
    # ar (ou na hora, se marcada urgente) — ver app/listing_rewards.py pro
    # design completo. Nada a chamar aqui.

    redirect_url = "/my-listings?urgent_error=insufficient_balance" if urgent_error else "/my-listings?created=1"
    return RedirectResponse(url=redirect_url, status_code=303)


@router.get("/listings/{listing_id}", response_class=HTMLResponse)
def listing_detail(request: Request, listing_id: int):
    listing = fetch_one(
        f"""
        SELECT
            {LISTING_COLUMNS}, l.author_id,
            u.full_name AS author_name, u.email AS author_email, u.phone AS author_phone,
            vt.name AS voice_type_name
        FROM visible_listings l
        JOIN users u ON u.id = l.author_id AND u.deleted_at IS NULL
        LEFT JOIN voice_types vt ON vt.id = l.voice_type_id
        WHERE l.id = :id
        """,  # nosec B608 - only LISTING_COLUMNS (fixed constant); the id goes by parameter.
        {"id": listing_id},
    )
    user = get_current_user(request)

    # Names and the internal messenger can be used by verified people, but
    # direct e-mail/phone contact is intentionally withheld until both sides
    # have a confirmed Match for this particular listing.  This prevents the
    # board from becoming a directory of scrapeable contact details.
    can_view_direct_contact = False
    if user and listing:
        if user["id"] == listing["author_id"]:
            can_view_direct_contact = True
        elif user["email_verified"]:
            can_view_direct_contact = fetch_one(
                """
                SELECT 1 FROM job_matches
                WHERE listing_id = :listing_id
                  AND status IN ('confirmed', 'completed')
                  AND (
                    (artist_user_id = :viewer_id AND contractor_user_id = :author_id)
                    OR (contractor_user_id = :viewer_id AND artist_user_id = :author_id)
                  )
                LIMIT 1
                """,
                {"listing_id": listing_id, "viewer_id": user["id"], "author_id": listing["author_id"]},
            ) is not None

    # "Message already sent for this listing" — doesn't prevent
    # sending again, just keeps the person from forgetting and
    # flooding the poster's inbox with the same question several times.
    already_messaged = False
    if user and listing and user["id"] != listing["author_id"]:
        existing_message = fetch_one(
            "SELECT 1 FROM visible_messages WHERE sender_id = :sender AND listing_id = :listing_id LIMIT 1",
            {"sender": user["id"], "listing_id": listing_id},
        )
        already_messaged = existing_message is not None

    # P3.A / FIX 19/09/2026: vacancies (one row per naipe, or one plain
    # row with no naipe for a conductor) — the only way a seeking_singer/
    # seeking_conductor listing has a voice/fee/candidate path at all now.
    vacancies = get_vacancies(listing_id) if listing and listing["listing_type"] in ("seeking_singer", "seeking_conductor") else []

    # P3.B: does the viewer (a singer or conductor) already have a
    # pending/accepted row for each vacancy? Avoids an N+1 by fetching
    # once and mapping by vacancy_id, and lets the template show
    # "already applied" instead of an Apply button for those rows.
    my_invitation_by_vacancy = {}
    if user and listing and user["role"] in ("singer", "conductor") and user["id"] != listing["author_id"] and vacancies:
        vacancy_ids = [v["id"] for v in vacancies]
        my_rows = fetch_all(
            "SELECT vacancy_id, status FROM job_invitations WHERE artist_user_id = :artist_id AND vacancy_id = ANY(:vacancy_ids) AND status IN ('pending', 'accepted') ORDER BY created_at DESC",
            {"artist_id": user["id"], "vacancy_ids": vacancy_ids},
        )
        for row in my_rows:
            my_invitation_by_vacancy.setdefault(row["vacancy_id"], row["status"])

    # Zero-Storage: the sheet music link itself (not just the "available"
    # flag) is withheld until the viewer has a confirmed Match for this
    # listing — same gating as direct contact details above.
    sheet_music_url = None
    if listing and listing["sheet_music_available"] and can_view_direct_contact:
        sheet_music_row = fetch_one(
            "SELECT sheet_music_url FROM listings WHERE id = :id", {"id": listing_id}
        )
        sheet_music_url = sheet_music_row["sheet_music_url"] if sheet_music_row else None

    is_saved = False
    already_reported = False
    if user and listing:
        saved = fetch_one(
            "SELECT 1 FROM saved_listings WHERE user_id = :user_id AND listing_id = :listing_id",
            {"user_id": user["id"], "listing_id": listing_id},
        )
        is_saved = saved is not None

        reported = fetch_one(
            "SELECT 1 FROM listing_reports WHERE reporter_id = :user_id AND listing_id = :listing_id",
            {"user_id": user["id"], "listing_id": listing_id},
        )
        already_reported = reported is not None

    context = {
        "user": user,
        "listing": listing,
        "already_messaged": already_messaged,
        "is_saved": is_saved,
        "already_reported": already_reported,
        "can_view_direct_contact": can_view_direct_contact,
        "vacancies": vacancies,
        "sheet_music_url": sheet_music_url,
        "my_invitation_by_vacancy": my_invitation_by_vacancy,
        "reported_just_now": request.query_params.get("reported") == "1",
        "applied": request.query_params.get("applied") == "1",
        "invite_error": request.query_params.get("invite_error"),
        # Freemium: without login (or logged in but with an e-mail
        # not yet confirmed) you can see that the listing exists
        # (title, city, type, status dot) but not the full
        # description or the contact info — this encourages both
        # signup AND e-mail confirmation. "anon" and "unverified"
        # show different CTAs in the template (register/log in vs.
        # resend confirmation).
        "lock_reason": "anon" if user is None else ("unverified" if not user["email_verified"] else None),
        # P3.D follow-up, confirmed with Daniel on 2026-09-18: a vaga's
        # Cachê (and venue/date/voice type) pulls too much of the
        # incentive to register away — an anonymous visitor on a vaga
        # listing now sees only Nome/Obra/Cidade in the meta line (see
        # listing_detail.html), same fields as the convite express
        # preview card. Scoped to vaga listings only (seeking_singer/
        # seeking_conductor) — self-ad listings (singer_available/
        # conductor_available) are unaffected, wasn't part of this ask.
        "anon_teaser": user is None and bool(listing) and listing["listing_type"] in ("seeking_singer", "seeking_conductor"),
    }
    return render(request, "listing_detail.html", context)


@router.get("/listings/{listing_id}/flyer.pdf")
def download_listing_flyer(request: Request, listing_id: int):
    """Printable flyer PDF (19/09/2026, Daniel: "a pessoa pode imprimir
    e colar em algum lugar, as pessoas só escaneiam o QR code e pronto")
    — a poster-style page with a big QR Code linking back to the
    listing. Same stateless shape as invoice_pdf.py/cv_pdf.py.

    Restricted to the listing's own author, same as edit/mark-urgent —
    this is a tool for the person who posted the ad to go print it, not
    a public download link on every listing page.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    listing = fetch_one(
        f"""
        SELECT {LISTING_COLUMNS}, l.author_id, vt.name AS voice_type_name
        FROM visible_listings l
        LEFT JOIN voice_types vt ON vt.id = l.voice_type_id
        WHERE l.id = :id
        """,  # nosec B608 - only LISTING_COLUMNS (fixed constant); the id goes by parameter.
        {"id": listing_id},
    )
    if not listing or listing["author_id"] != user["id"]:
        return RedirectResponse(url=f"/listings/{listing_id}", status_code=303)

    lang = getattr(request.state, "lang", "de")
    listing_url = f"{str(request.base_url).rstrip('/')}/listings/{listing_id}"
    fee_text = format_fee(
        listing["fee_amount"], listing["fee_currency"], listing["fee_negotiable"],
        translate("fee_negotiable_label", lang),
    )
    event_date = listing["event_date"].strftime("%d.%m.%Y") if listing.get("event_date") else ""

    flyer = ListingFlyerDocument(
        title=listing["title"],
        type_label=translate(f"listing_type_{listing['listing_type']}", lang),
        listing_url=listing_url,
        voice_type=listing.get("voice_type_name") or "",
        city=listing.get("city") or "",
        country=listing.get("country") or "",
        event_date=event_date,
        fee_text=fee_text or "",
        venue=listing.get("venue") or "",
        scan_caption=translate("listing_flyer_scan_caption", lang),
    )
    pdf_bytes = render_listing_flyer_pdf(flyer)
    return StreamingResponse(
        iter([pdf_bytes]), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="vokalboard-anuncio-{listing_id}.pdf"'},
    )


@router.post("/listings/{listing_id}/report")
def report_listing(request: Request, listing_id: int, csrf_token: str = Form(""), reason: str = Form("")):
    """
    Report listing: requires the person to write the reason (minimum
    10 characters, also enforced in the database via CHECK). There's
    no moderation screen in the site — reports are stored in
    listing_reports to be queried directly in the database by
    whoever administers the site (the same pattern already used in
    profile_views).
    """
    verify_csrf(request, csrf_token)
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    listing = fetch_one("SELECT id, author_id FROM visible_listings WHERE id = :id", {"id": listing_id})
    reason = reason.strip()
    if not listing or listing["author_id"] == user["id"] or len(reason) < 10:
        return RedirectResponse(url=f"/listings/{listing_id}", status_code=303)

    execute(
        "INSERT INTO listing_reports (listing_id, reporter_id, reason) VALUES (:listing_id, :reporter_id, :reason)",
        {"listing_id": listing_id, "reporter_id": user["id"], "reason": reason},
    )
    return RedirectResponse(url=f"/listings/{listing_id}?reported=1", status_code=303)


@router.get("/listings/{listing_id}/edit", response_class=HTMLResponse)
def edit_listing_form(request: Request, listing_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    listing = fetch_one("SELECT * FROM visible_listings WHERE id = :id", {"id": listing_id})
    if not listing or listing["author_id"] != user["id"]:
        return RedirectResponse(url=f"/listings/{listing_id}", status_code=303)

    voice_types = fetch_all("SELECT id, name FROM voice_types ORDER BY sort_order")
    context = {
        "user": user,
        "voice_types": voice_types,
        "listing_type_keys": LISTING_TYPE_KEYS,
        "ensemble_type_keys": ENSEMBLE_TYPE_KEYS,
        "country_options": COUNTRY_OPTIONS,
        "state_options": STATE_OPTIONS,
        "city_options": get_city_options(),
        "currencies": CURRENCIES,
        "values": listing,
        "is_edit": True,
        "listing_id": listing_id,
        "error": None,
        "vacancies": get_vacancies(listing_id) if listing["listing_type"] in ("seeking_singer", "seeking_conductor") else [],
    }
    return render(request, "listing_form.html", context)


@router.post("/listings/{listing_id}/edit")
async def update_listing(
    request: Request,
    listing_id: int,
    csrf_token: str = Form(""),
    listing_type: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    city: str = Form(""),
    state: str = Form(""),
    country: str = Form("DE"),
    voice_type_id: str = Form(""),
    repertoire: str = Form(""),
    venue: str = Form(""),
    fee_amount: str = Form(""),
    fee_currency: str = Form(DEFAULT_CURRENCY),
    fee_negotiable: str = Form(""),
    ensemble_type: str = Form(""),
    event_date: str = Form(""),
    available_from: str = Form(""),
    available_until: str = Form(""),
    travel_cost_covered: str = Form(""),
    sheet_music_available: str = Form(""),
    sheet_music_url: str = Form(""),
    rehearsal_schedule_available: str = Form(""),
):
    verify_csrf(request, csrf_token)

    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    existing = fetch_one("SELECT author_id FROM visible_listings WHERE id = :id", {"id": listing_id})
    if not existing or existing["author_id"] != user["id"]:
        return RedirectResponse(url=f"/listings/{listing_id}", status_code=303)

    fee_negotiable_bool = bool(fee_negotiable)
    if fee_currency not in CURRENCIES:
        fee_currency = DEFAULT_CURRENCY
    fee_ok, fee_amount_parsed = fee_valid(fee_amount, fee_negotiable_bool)

    form = await request.form()
    vacancies = parse_vacancies_form(
        form.getlist("vacancy_voice_type_id"),
        form.getlist("vacancy_fee_amount"),
        form.getlist("vacancy_fee_currency"),
        lambda i: form.get(f"vacancy_fee_negotiable_{i}"),
        form.getlist("vacancy_total_slots"),
        listing_type,
    )

    if country not in COUNTRY_OPTIONS:
        country = "DE"
    if ensemble_type not in ENSEMBLE_TYPE_KEYS:
        ensemble_type = None

    available = listing_type == 'singer_available'
    has_vacancy = bool(vacancies)
    if (available and not availability_valid(available_from, available_until)) or (not available and (not state.strip() or not _job_fields_valid(listing_type, city, repertoire, has_vacancy))):
        context = _listing_form_error_context(
            user, listing_type, title, description, city, state, country,
            voice_type_id, repertoire, venue, fee_amount, fee_currency, fee_negotiable_bool, ensemble_type, event_date, True, listing_id, available_from, available_until,
        )
        return render(request, "listing_form.html", context, status_code=400)

    if listing_type in ('seeking_singer', 'seeking_conductor') and not _valid_event_date(event_date):
        raise HTTPException(status_code=400, detail='Event date required')
    if available:
        event_date = ''
        if not state.strip() and not city.strip():
            country = None

    # FIX 19/09/2026 — see the matching comment in create_listing().
    if listing_type in ('seeking_singer', 'seeking_conductor'):
        derived_voice_type_id, derived_fee_amount, derived_fee_currency, derived_fee_negotiable = \
            _derive_listing_fields_from_vacancies(vacancies, fee_currency)
    else:
        derived_voice_type_id = int(voice_type_id) if voice_type_id else None
        derived_fee_amount, derived_fee_currency, derived_fee_negotiable = fee_amount_parsed, fee_currency, fee_negotiable_bool

    _persist_listing(
        """
        UPDATE listings
        SET listing_type = :listing_type, title = :title, description = :description,
            city = :city, state = :state, country = :country, voice_type_id = :voice_type_id, repertoire = :repertoire,
            venue = :venue, fee_amount = :fee_amount, fee_currency = :fee_currency, fee_negotiable = :fee_negotiable,
            ensemble_type = :ensemble_type, event_date = :event_date,
            available_from = :available_from, available_until = :available_until,
            travel_cost_covered = :travel_cost_covered, sheet_music_available = :sheet_music_available,
            sheet_music_url = :sheet_music_url, rehearsal_schedule_available = :rehearsal_schedule_available,
            updated_at = now()
        WHERE id = :id
        """,
        {
            "id": listing_id,
            "listing_type": listing_type,
            "title": title,
            "description": description,
            "city": city or None,
            "state": state.strip() or None,
            "country": country,
            "voice_type_id": derived_voice_type_id,
            "repertoire": repertoire or None,
            "venue": venue or None,
            "fee_amount": derived_fee_amount,
            "fee_currency": derived_fee_currency,
            "fee_negotiable": derived_fee_negotiable,
            "ensemble_type": ensemble_type,
            "event_date": event_date or None,
            "available_from": available_from if available else None,
            "available_until": available_until if available else None,
            "travel_cost_covered": bool(travel_cost_covered),
            "sheet_music_available": bool(sheet_music_available),
            "sheet_music_url": (sheet_music_url.strip()[:500] or None) if sheet_music_available else None,
            "rehearsal_schedule_available": bool(rehearsal_schedule_available),
        },
    )
    if listing_type in ('seeking_singer', 'seeking_conductor'):
        set_vacancies(listing_id, vacancies)
    return RedirectResponse(url=f"/listings/{listing_id}", status_code=303)


@router.post("/listings/{listing_id}/delete")
def delete_listing(request: Request, listing_id: int, csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)

    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    listing = fetch_one("SELECT author_id FROM visible_listings WHERE id = :id", {"id": listing_id})
    if listing and listing["author_id"] == user["id"]:
        execute("UPDATE listings SET deleted_at=now(), archived_at=now(), is_active=FALSE WHERE id = :id", {"id": listing_id})
    return RedirectResponse(url="/", status_code=303)


@router.get("/my-listings", response_class=HTMLResponse)
def my_listings(request: Request, urgent_error: str = "", urgent_marked: str = "", created: str = ""):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    listings = fetch_all(
        f"""
        SELECT l.id, l.title, l.listing_type, l.city, l.state, l.country, l.is_active, l.created_at,
               l.is_urgent, {EVENT_STATUS_SQL},
               -- "Buscar para este anúncio" (19/09/2026, Daniel): the
               -- voice type to pre-fill on /people, when there's one
               -- unambiguous answer — the listing's own single
               -- voice_type_id (legacy path), or, for a vacancy-based
               -- listing, its voice type ONLY when every vacancy
               -- shares the same one (a listing with several naipes
               -- has no single answer, so the button just searches
               -- broadly with no voice filter instead of guessing).
               COALESCE(
                   l.voice_type_id,
                   (SELECT MIN(lv.voice_type_id) FROM listing_vacancies lv
                    WHERE lv.listing_id = l.id
                    GROUP BY lv.listing_id
                    HAVING COUNT(DISTINCT lv.voice_type_id) = 1)
               ) AS search_voice_type_id
        FROM visible_listings l
        WHERE l.author_id = :author_id
        ORDER BY l.created_at DESC
        """,  # nosec B608 - only EVENT_STATUS_SQL (fixed constant); author_id goes by parameter.
        {"author_id": user["id"]},
    )
    context = {
        "user": user,
        "listings": listings,
        # P5 Etapa 2 (18/09/2026): usado pelo botão "Marcar como
        # urgente" por linha — mostra se ainda sobra o token grátis
        # dessa semana, ou o custo em Notas se já foi usado.
        "urgency_status": get_urgency_status(user["id"]),
        "urgency_eligible_types": URGENCY_ELIGIBLE_LISTING_TYPES,
        "urgent_error": urgent_error,
        "urgent_marked": urgent_marked,
        "created": created == "1",
    }
    return render(request, "my_listings.html", context)


@router.post("/listings/{listing_id}/mark-urgent")
def mark_listing_urgent_route(request: Request, listing_id: int, csrf_token: str = Form("")):
    """P5 Etapa 2 (18/09/2026): o botão "marcar como urgente depois",
    pra quem não marcou na hora de publicar — mesma função
    (mark_listing_urgent) usada pelo checkbox de create_listing()."""
    verify_csrf(request, csrf_token)
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    try:
        mark_listing_urgent(user["id"], listing_id)
        return RedirectResponse(url="/my-listings?urgent_marked=1", status_code=303)
    except UrgencyUnavailable:
        return RedirectResponse(url="/my-listings?urgent_error=insufficient_balance", status_code=303)
    except ListingNotEligible:
        return RedirectResponse(url="/my-listings?urgent_error=not_eligible", status_code=303)


@router.post("/listings/{listing_id}/save")
def save_listing(request: Request, listing_id: int, csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    listing = fetch_one("SELECT id FROM visible_listings WHERE id = :id", {"id": listing_id})
    if listing:
        # ON CONFLICT DO NOTHING: favoriting again something that's
        # already favorited simply does nothing (idempotent), instead
        # of raising a UNIQUE constraint error.
        execute(
            """
            INSERT INTO saved_listings (user_id, listing_id) VALUES (:user_id, :listing_id)
            ON CONFLICT (user_id, listing_id) DO NOTHING
            """,
            {"user_id": user["id"], "listing_id": listing_id},
        )
    return RedirectResponse(url=f"/listings/{listing_id}", status_code=303)


@router.post("/listings/{listing_id}/unsave")
def unsave_listing(request: Request, listing_id: int, csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    execute(
        "DELETE FROM saved_listings WHERE user_id = :user_id AND listing_id = :listing_id",
        {"user_id": user["id"], "listing_id": listing_id},
    )
    # If it came from the favorites page itself, go back there
    # (otherwise the "disappeared" item would still show up until the
    # next refresh); otherwise go back to the listing as usual.
    referer = request.headers.get("referer", "")
    if "/my-favorites" in referer:
        return RedirectResponse(url="/my-favorites", status_code=303)
    return RedirectResponse(url=f"/listings/{listing_id}", status_code=303)


@router.get("/my-favorites", response_class=HTMLResponse)
def my_favorites(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    listings = fetch_all(
        f"""
        SELECT {LISTING_COLUMNS}, u.id AS author_id, u.full_name AS author_name, vt.name AS voice_type_name,
            sl.created_at AS saved_at
        FROM saved_listings sl
        JOIN visible_listings l ON l.id = sl.listing_id
        JOIN users u ON u.id = l.author_id AND u.deleted_at IS NULL
        LEFT JOIN voice_types vt ON vt.id = l.voice_type_id
        WHERE sl.user_id = :user_id
        ORDER BY sl.created_at DESC
        """,  # nosec B608 - only LISTING_COLUMNS (fixed constant); user_id goes by parameter.
        {"user_id": user["id"]},
    )
    context = {
        "user": user,
        "listings": listings,
    }
    return render(request, "my_favorites.html", context)

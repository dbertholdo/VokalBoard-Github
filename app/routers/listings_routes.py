from fastapi import APIRouter, Request, Form, BackgroundTasks, HTTPException
from app import store
from app.seo import job_posting_jsonld, public_base, website_jsonld
from app.vacancies import get_listing_invitations
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse

from app.database import fetch_all, fetch_one, execute
from app.auth import get_current_user
from app.render import render
from app.csrf import verify_csrf
from app.listing_terms import LISTING_SUMMARY_JOIN
from app.notifications import notify_matching_users
from app.badges import check_and_notify_new_badges
from app.urgency import ListingNotEligible, UrgencyUnavailable, get_urgency_status, mark_listing_urgent
from app.locations import COUNTRY_OPTIONS, STATE_OPTIONS, get_city_options
from app.richtext import html_to_excerpt
from app.highlights import get_weekly_highlights
from app.vacancies import get_vacancies
from app.listings_service import (
    LISTING_TYPE_KEYS, ENSEMBLE_TYPE_KEYS, JOB_TYPES, ListingFormError, clean_listing_form, form_values,
    create_listing as create_listing_row, update_listing as update_listing_row,
)
from app.fees import format_fee, CURRENCIES, DEFAULT_CURRENCY
from app.compatibility import FEE_COMPATIBILITY_ORDER_SQL, RATING_JOIN_SQL, viewer_location_params
from app.mascot_moments import profile_incomplete
from app.i18n import translate
from app.listing_pdf import ListingFlyerDocument, render_listing_flyer_pdf


router = APIRouter()


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
    l.repertoire, l.venue, ls.fee_amount, ls.fee_currency, ls.fee_negotiable,
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
                # #55: every vacancy voice counts (listing_terms), not one copied value.
                """EXISTS (
                    SELECT 1 FROM listing_terms t
                    WHERE t.listing_id = l.id AND (
                        t.voice_type_id IS NULL
                        OR EXISTS (
                            SELECT 1 FROM singer_profile_voice_types spvt
                            WHERE spvt.user_id = :viewer_voice_user_id
                              AND spvt.voice_type_id = t.voice_type_id
                        )
                        OR EXISTS (
                            SELECT 1 FROM singer_profiles sp
                            WHERE sp.user_id = :viewer_voice_user_id
                              AND sp.voice_type_id = t.voice_type_id
                        )
                    )
                )"""
            )
            match_params["viewer_voice_user_id"] = user["id"]
            matches = fetch_all(
                f"""
                SELECT {LISTING_COLUMNS}, u.id AS author_id, u.full_name AS author_name, vt.name AS voice_type_name
                FROM visible_listings l
                JOIN users u ON u.id = l.author_id AND u.deleted_at IS NULL
                {LISTING_SUMMARY_JOIN}
                LEFT JOIN voice_types vt ON vt.id = ls.voice_type_id
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
                {LISTING_SUMMARY_JOIN}
                LEFT JOIN voice_types vt ON vt.id = ls.voice_type_id
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
            {LISTING_SUMMARY_JOIN}
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
    context["website_jsonld"] = website_jsonld(public_base(request), translate("seo_home_description", getattr(request.state, "lang", "de")))
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
        conditions.append("EXISTS (SELECT 1 FROM listing_terms t WHERE t.listing_id = l.id AND t.voice_type_id = :voice_type_id)")
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
    # Store (2026-09-28): up to 3 random featured listings matching the filters
    # go first — page 1 only, so paging stays stable.
    pinned = store.pinned_featured_ids(where_clause, params) if page == 1 else []

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
            {store.super_user_sql('u')} AS author_super_user,
            (l.id = ANY(:pinned)) AS is_pinned,
            EXISTS (
                SELECT 1 FROM saved_listings sl
                WHERE sl.listing_id = l.id AND sl.user_id = :viewer_id
            ) AS is_saved
        FROM visible_listings l
        JOIN users u ON u.id = l.author_id AND u.deleted_at IS NULL
        {LISTING_SUMMARY_JOIN}
        LEFT JOIN voice_types vt ON vt.id = ls.voice_type_id
        WHERE {where_clause}
        ORDER BY (l.id = ANY(:pinned)) DESC, l.is_urgent DESC, l.created_at DESC, l.id DESC
        LIMIT :limit OFFSET :offset
        """,  # nosec B608 - same fixed-fragment where_clause explained above.
        {**params, "limit": BOARD_PAGE_SIZE, "offset": offset, "viewer_id": user["id"] if user else None,
         "pinned": pinned},
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
    context = _listing_form_context(user, {"country": "DE", "fee_currency": DEFAULT_CURRENCY},
                                    is_edit=False, listing_id=None, error=None, vacancies=[])
    return render(request, "listing_form.html", context)


def _listing_form_context(user, values: dict, *, is_edit: bool, listing_id, error, vacancies) -> dict:
    return {
        "user": user,
        "voice_types": fetch_all("SELECT id, name FROM voice_types ORDER BY sort_order"),
        "listing_type_keys": LISTING_TYPE_KEYS,
        "ensemble_type_keys": ENSEMBLE_TYPE_KEYS,
        "country_options": COUNTRY_OPTIONS,
        "state_options": STATE_OPTIONS,
        "city_options": get_city_options(),
        "currencies": CURRENCIES,
        "values": values,
        "is_edit": is_edit,
        "listing_id": listing_id,
        "error": error,
        "vacancies": vacancies,
    }


def _form_error(request, user, exc: ListingFormError, *, is_edit=False, listing_id=None, status=400):
    # Vacancy rows and checkboxes are threaded back now (they used to reset to empty).
    context = _listing_form_context(user, form_values(exc.data), is_edit=is_edit, listing_id=listing_id,
                                    error=exc.key, vacancies=exc.data.get("vacancies", []))
    return render(request, "listing_form.html", context, status_code=status)


@router.post("/listings/new")
async def create_listing(request: Request, background_tasks: BackgroundTasks, csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not user["email_verified"]:
        return RedirectResponse(url="/?verify_required=1", status_code=303)

    form = await request.form()
    try:
        data = clean_listing_form(form)
    except ListingFormError as exc:
        return _form_error(request, user, exc)

    # P2.C: a phone is required to publish (only revealed after a Match — see match_history_routes.py).
    if not (user.get("phone") or "").strip():
        return _form_error(request, user, ListingFormError("error_phone_required_for_listing", data))
    if _listing_creation_throttled(user["id"]):
        return _form_error(request, user, ListingFormError("error_listing_rate_limited", data), status=429)

    try:
        listing_id = create_listing_row(user["id"], data)
    except ListingFormError as exc:
        return _form_error(request, user, exc)

    # P5 Etapa 2: "mark as urgent" at creation — synchronous on purpose, so a
    # missing-Notas problem shows up on the next page instead of silently failing.
    urgent_error = ""
    if data["is_urgent"] and data["listing_type"] in URGENCY_ELIGIBLE_LISTING_TYPES:
        try:
            mark_listing_urgent(user["id"], listing_id)
        except UrgencyUnavailable:
            urgent_error = "insufficient_balance"
        except ListingNotEligible:
            pass

    # Matching-listing alert (background): #55 every vacancy voice, or the self-ad's own voice.
    voice_ids = ([v["voice_type_id"] for v in data["vacancies"] if v["voice_type_id"]]
                 if data["listing_type"] in JOB_TYPES
                 else ([data["db_voice_type_id"]] if data["db_voice_type_id"] else []))
    background_tasks.add_task(notify_matching_users, str(request.base_url), listing_id, data["listing_type"],
                              data["title"], data["city"] or None, user["id"], voice_ids)
    background_tasks.add_task(check_and_notify_new_badges, user["id"], str(request.base_url))
    # Notas reward for posting: credited later by app/listing_reward_worker.py (see app/listing_rewards.py).

    redirect_url = "/my-listings?urgent_error=insufficient_balance" if urgent_error else "/my-listings?created=1"
    return RedirectResponse(url=redirect_url, status_code=303)


@router.get("/listings/{listing_id}", response_class=HTMLResponse)
def listing_detail(request: Request, listing_id: int):
    listing = fetch_one(
        f"""
        SELECT
            {LISTING_COLUMNS}, l.author_id, l.is_active,
            u.full_name AS author_name, u.email AS author_email, u.phone AS author_phone,
            vt.name AS voice_type_name
        FROM visible_listings l
        JOIN users u ON u.id = l.author_id AND u.deleted_at IS NULL
        {LISTING_SUMMARY_JOIN}
        LEFT JOIN voice_types vt ON vt.id = ls.voice_type_id
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

    # B1 (2026-09-28): the author answers applications right on the
    # listing page instead of hunting for /listings/{id}/candidates.
    author_candidacies = []
    if user and listing and user["id"] == listing["author_id"] and vacancies:
        author_candidacies = get_listing_invitations(listing_id)[0]

    # SEO (2026-09-28): only what a logged-out visitor (= Google) sees on the page.
    seo_listing_description = ""
    job_posting = None
    if listing:
        lang = getattr(request.state, "lang", "de")
        parts = [translate(f"listing_type_{listing['listing_type']}", lang), listing.get("repertoire"), listing.get("city")]
        seo_listing_description = " · ".join(p for p in parts if p)
        excerpt = (listing.get("description") or "")[:120]
        job_posting = job_posting_jsonld(dict(listing), public_base(request),
                                         f"{listing['title']}. {seo_listing_description}. {excerpt}".strip())

    context = {
        "user": user,
        "listing": listing,
        "seo_listing_description": seo_listing_description,
        "job_posting_jsonld": job_posting,
        "author_candidacies": author_candidacies,
        "responded": request.query_params.get("responded"),
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
        {LISTING_SUMMARY_JOIN}
        LEFT JOIN voice_types vt ON vt.id = ls.voice_type_id
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
    # One report per person per listing (the page hides the form, but a direct POST could repeat it).
    if fetch_one("SELECT 1 FROM listing_reports WHERE listing_id = :l AND reporter_id = :u", {"l": listing_id, "u": user["id"]}):
        return RedirectResponse(url=f"/listings/{listing_id}", status_code=303)
    reason = reason[:500]

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

    vacancies = get_vacancies(listing_id) if listing["listing_type"] in JOB_TYPES else []
    context = _listing_form_context(user, listing, is_edit=True, listing_id=listing_id, error=None, vacancies=vacancies)
    return render(request, "listing_form.html", context)


@router.post("/listings/{listing_id}/edit")
async def update_listing(request: Request, listing_id: int, csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    existing = fetch_one("SELECT author_id, listing_type FROM visible_listings WHERE id = :id", {"id": listing_id})
    if not existing or existing["author_id"] != user["id"]:
        return RedirectResponse(url=f"/listings/{listing_id}", status_code=303)

    form = await request.form()
    try:
        # The type stays what it was: switching a job listing to a self-ad would orphan its vacancies/Matches.
        data = clean_listing_form(form, existing_type=existing["listing_type"])
        update_listing_row(listing_id, data)
    except ListingFormError as exc:
        return _form_error(request, user, exc, is_edit=True, listing_id=listing_id)
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
        # Pending invitations/applications can no longer turn into a Match on a deleted listing.
        execute(
            """UPDATE job_invitations SET status = 'expired', responded_at = now()
               WHERE status = 'pending' AND vacancy_id IN (SELECT id FROM listing_vacancies WHERE listing_id = :id)""",
            {"id": listing_id},
        )
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
               (SELECT CASE WHEN COUNT(DISTINCT t.voice_type_id) = 1 THEN MIN(t.voice_type_id) END
                FROM listing_terms t WHERE t.listing_id = l.id) AS search_voice_type_id
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
        {LISTING_SUMMARY_JOIN}
        LEFT JOIN voice_types vt ON vt.id = ls.voice_type_id
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

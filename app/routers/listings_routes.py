from fastapi import APIRouter, Request, Form, BackgroundTasks, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse

from app.database import fetch_all, fetch_one, execute, execute_returning
from app.auth import get_current_user
from app.render import render
from app.csrf import verify_csrf
from app.notifications import notify_matching_users
from app.badges import check_and_notify_new_badges
from app.locations import COUNTRY_OPTIONS, STATE_OPTIONS, get_city_options
from app.richtext import html_to_excerpt
from app.highlights import get_weekly_highlights

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
    l.repertoire, l.venue, l.fee, l.ensemble_type, l.event_date, l.created_at,
    {EVENT_STATUS_SQL}
"""

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
        "SELECT COUNT(*) AS n FROM listings WHERE author_id = :id AND created_at > now() - interval '1 minute' * :window",
        {"id": author_id, "window": LISTING_WINDOW_MINUTES},
    )
    return bool(row and row["n"] >= MAX_LISTINGS_PER_WINDOW)


def _job_fields_valid(listing_type: str, city: str, repertoire: str, fee: str) -> bool:
    """
    Listings of type 'seeking_singer' (looking for a singer for a
    job) need Repertoire, City and Fee filled in — as requested.
    Voice type doesn't enter the validation because "blank" already
    means "all voices", a valid choice.
    """
    if listing_type != "seeking_singer":
        return True
    return bool(city.strip()) and bool(repertoire.strip()) and bool(fee.strip())


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

    if user:
        match_params = {"city": f"%{user['city']}%" if user["city"] else ""}
        order_by_city = "CASE WHEN l.city ILIKE :city THEN 0 ELSE 1 END, l.created_at DESC" if user["city"] else "l.created_at DESC"

        if user["role"] == "singer":
            singer_profile = fetch_one(
                "SELECT voice_type_id FROM singer_profiles WHERE user_id = :id", {"id": user["id"]}
            )
            voice_type_id = singer_profile["voice_type_id"] if singer_profile else None
            conditions = [
                "l.is_active = TRUE",
                "l.listing_type = 'seeking_singer'",
                "(l.event_date IS NULL OR l.event_date >= CURRENT_DATE)",
                "NOT EXISTS (SELECT 1 FROM blocked_users bu WHERE (bu.blocker_id = :viewer_block_id AND bu.blocked_id = l.author_id) OR (bu.blocker_id = l.author_id AND bu.blocked_id = :viewer_block_id))",
            ]
            match_params["viewer_block_id"] = user["id"]
            if voice_type_id:
                conditions.append("(l.voice_type_id = :voice_type_id OR l.voice_type_id IS NULL)")
                match_params["voice_type_id"] = voice_type_id
            matches = fetch_all(
                f"""
                SELECT {LISTING_COLUMNS}, u.id AS author_id, u.full_name AS author_name, vt.name AS voice_type_name
                FROM listings l
                JOIN users u ON u.id = l.author_id AND u.deleted_at IS NULL
                LEFT JOIN voice_types vt ON vt.id = l.voice_type_id
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
                FROM listings l
                JOIN users u ON u.id = l.author_id AND u.deleted_at IS NULL
                LEFT JOIN voice_types vt ON vt.id = l.voice_type_id
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
        teaser_listings = fetch_all(
            f"""
            SELECT {LISTING_COLUMNS}, u.full_name AS author_name
            FROM listings l
            JOIN users u ON u.id = l.author_id AND u.deleted_at IS NULL
            WHERE l.is_active = TRUE AND (l.event_date IS NULL OR l.event_date >= CURRENT_DATE)
            ORDER BY l.created_at DESC
            LIMIT 5
            """  # nosec B608 - only LISTING_COLUMNS (fixed constant, no person input) and a SQL literal.
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

    if not show_past and not date_from and not date_to:
        conditions.append("(l.event_date IS NULL OR l.event_date >= CURRENT_DATE)")

    if date_from:
        conditions.append("l.event_date >= :date_from")
        params["date_from"] = date_from

    if date_to:
        conditions.append("l.event_date <= :date_to")
        params["date_to"] = date_to

    if city:
        conditions.append("l.city ILIKE :city")
        params["city"] = f"%{city}%"

    if state:
        conditions.append("l.state = :state")
        params["state"] = state

    if country:
        conditions.append("l.country = :country")
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

    where_clause = " AND ".join(conditions)

    page = max(1, page)
    offset = (page - 1) * BOARD_PAGE_SIZE

    total_row = fetch_one(
        f"""
        SELECT count(*) AS n
        FROM listings l
        WHERE {where_clause}
        """,  # nosec B608 - where_clause is just the join of fixed fragments (`conditions`,
              # assembled above); the real search values go in `params`.
        params,
    )
    total = total_row["n"] if total_row else 0
    total_pages = max(1, (total + BOARD_PAGE_SIZE - 1) // BOARD_PAGE_SIZE)

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
        FROM listings l
        JOIN users u ON u.id = l.author_id AND u.deleted_at IS NULL
        LEFT JOIN voice_types vt ON vt.id = l.voice_type_id
        WHERE {where_clause}
        ORDER BY l.created_at DESC
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
        "values": {"country": "DE"},
        "is_edit": False,
        "listing_id": None,
        "error": None,
    }
    return render(request, "listing_form.html", context)


def _listing_form_error_context(user, listing_type, title, description, city, state, country,
                                 voice_type_id, repertoire, venue, fee, ensemble_type, event_date,
                                 is_edit, listing_id):
    voice_types = fetch_all("SELECT id, name FROM voice_types ORDER BY sort_order")
    return {
        "user": user,
        "voice_types": voice_types,
        "listing_type_keys": LISTING_TYPE_KEYS,
        "ensemble_type_keys": ENSEMBLE_TYPE_KEYS,
        "country_options": COUNTRY_OPTIONS,
        "state_options": STATE_OPTIONS,
        "city_options": get_city_options(),
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
            "fee": fee,
            "ensemble_type": ensemble_type,
            "event_date": event_date,
        },
        "is_edit": is_edit,
        "listing_id": listing_id,
        "error": "error_required_fields",
    }


@router.post("/listings/new")
def create_listing(
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
    fee: str = Form(""),
    ensemble_type: str = Form(""),
    event_date: str = Form(""),
):
    verify_csrf(request, csrf_token)

    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not user["email_verified"]:
        return RedirectResponse(url="/?verify_required=1", status_code=303)

    if country not in COUNTRY_OPTIONS:
        country = "DE"
    if ensemble_type not in ENSEMBLE_TYPE_KEYS:
        ensemble_type = None

    if _listing_creation_throttled(user["id"]):
        context = _listing_form_error_context(
            user, listing_type, title, description, city, state, country,
            voice_type_id, repertoire, venue, fee, ensemble_type, event_date, False, None,
        )
        context["error"] = "error_listing_rate_limited"
        return render(request, "listing_form.html", context, status_code=429)

    # "State" is required for any listing (not just openings) —
    # together with Repertoire/City/Fee in the specific case of seeking_singer.
    if not state.strip() or not _job_fields_valid(listing_type, city, repertoire, fee):
        context = _listing_form_error_context(
            user, listing_type, title, description, city, state, country,
            voice_type_id, repertoire, venue, fee, ensemble_type, event_date, False, None,
        )
        return render(request, "listing_form.html", context, status_code=400)

    new_listing = execute_returning(
        """
        INSERT INTO listings (author_id, listing_type, title, description, city, state, country, voice_type_id, repertoire, venue, fee, ensemble_type, event_date)
        VALUES (:author_id, :listing_type, :title, :description, :city, :state, :country, :voice_type_id, :repertoire, :venue, :fee, :ensemble_type, :event_date)
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
            "voice_type_id": int(voice_type_id) if voice_type_id else None,
            "repertoire": repertoire or None,
            "venue": venue or None,
            "fee": fee or None,
            "ensemble_type": ensemble_type,
            "event_date": event_date or None,
        },
    )

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

    return RedirectResponse(url="/my-listings", status_code=303)


@router.get("/listings/{listing_id}", response_class=HTMLResponse)
def listing_detail(request: Request, listing_id: int):
    listing = fetch_one(
        f"""
        SELECT
            {LISTING_COLUMNS}, l.author_id,
            u.full_name AS author_name, u.email AS author_email, u.phone AS author_phone,
            vt.name AS voice_type_name
        FROM listings l
        JOIN users u ON u.id = l.author_id AND u.deleted_at IS NULL
        LEFT JOIN voice_types vt ON vt.id = l.voice_type_id
        WHERE l.id = :id
        """,  # nosec B608 - only LISTING_COLUMNS (fixed constant); the id goes by parameter.
        {"id": listing_id},
    )
    user = get_current_user(request)

    # "Message already sent for this listing" — doesn't prevent
    # sending again, just keeps the person from forgetting and
    # flooding the poster's inbox with the same question several times.
    already_messaged = False
    if user and listing and user["id"] != listing["author_id"]:
        existing_message = fetch_one(
            "SELECT 1 FROM messages WHERE sender_id = :sender AND listing_id = :listing_id LIMIT 1",
            {"sender": user["id"], "listing_id": listing_id},
        )
        already_messaged = existing_message is not None

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
        "reported_just_now": request.query_params.get("reported") == "1",
        # Freemium: without login (or logged in but with an e-mail
        # not yet confirmed) you can see that the listing exists
        # (title, city, type, status dot) but not the full
        # description or the contact info — this encourages both
        # signup AND e-mail confirmation. "anon" and "unverified"
        # show different CTAs in the template (register/log in vs.
        # resend confirmation).
        "lock_reason": "anon" if user is None else ("unverified" if not user["email_verified"] else None),
    }
    return render(request, "listing_detail.html", context)


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

    listing = fetch_one("SELECT id, author_id FROM listings WHERE id = :id", {"id": listing_id})
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

    listing = fetch_one("SELECT * FROM listings WHERE id = :id", {"id": listing_id})
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
        "values": listing,
        "is_edit": True,
        "listing_id": listing_id,
        "error": None,
    }
    return render(request, "listing_form.html", context)


@router.post("/listings/{listing_id}/edit")
def update_listing(
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
    fee: str = Form(""),
    ensemble_type: str = Form(""),
    event_date: str = Form(""),
):
    verify_csrf(request, csrf_token)

    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    existing = fetch_one("SELECT author_id FROM listings WHERE id = :id", {"id": listing_id})
    if not existing or existing["author_id"] != user["id"]:
        return RedirectResponse(url=f"/listings/{listing_id}", status_code=303)

    if country not in COUNTRY_OPTIONS:
        country = "DE"
    if ensemble_type not in ENSEMBLE_TYPE_KEYS:
        ensemble_type = None

    if not state.strip() or not _job_fields_valid(listing_type, city, repertoire, fee):
        context = _listing_form_error_context(
            user, listing_type, title, description, city, state, country,
            voice_type_id, repertoire, venue, fee, ensemble_type, event_date, True, listing_id,
        )
        return render(request, "listing_form.html", context, status_code=400)

    execute(
        """
        UPDATE listings
        SET listing_type = :listing_type, title = :title, description = :description,
            city = :city, state = :state, country = :country, voice_type_id = :voice_type_id, repertoire = :repertoire,
            venue = :venue, fee = :fee, ensemble_type = :ensemble_type, event_date = :event_date, updated_at = now()
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
            "voice_type_id": int(voice_type_id) if voice_type_id else None,
            "repertoire": repertoire or None,
            "venue": venue or None,
            "fee": fee or None,
            "ensemble_type": ensemble_type,
            "event_date": event_date or None,
        },
    )
    return RedirectResponse(url=f"/listings/{listing_id}", status_code=303)


@router.post("/listings/{listing_id}/delete")
def delete_listing(request: Request, listing_id: int, csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)

    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    listing = fetch_one("SELECT author_id FROM listings WHERE id = :id", {"id": listing_id})
    if listing and listing["author_id"] == user["id"]:
        execute("DELETE FROM listings WHERE id = :id", {"id": listing_id})
    return RedirectResponse(url="/", status_code=303)


@router.get("/my-listings", response_class=HTMLResponse)
def my_listings(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    listings = fetch_all(
        f"""
        SELECT l.id, l.title, l.listing_type, l.city, l.is_active, l.created_at, {EVENT_STATUS_SQL}
        FROM listings l
        WHERE l.author_id = :author_id
        ORDER BY l.created_at DESC
        """,  # nosec B608 - only EVENT_STATUS_SQL (fixed constant); author_id goes by parameter.
        {"author_id": user["id"]},
    )
    context = {
        "user": user,
        "listings": listings,
    }
    return render(request, "my_listings.html", context)


@router.post("/listings/{listing_id}/save")
def save_listing(request: Request, listing_id: int, csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    listing = fetch_one("SELECT id FROM listings WHERE id = :id", {"id": listing_id})
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
        JOIN listings l ON l.id = sl.listing_id
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

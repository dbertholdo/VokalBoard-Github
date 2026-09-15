"""
"Buscar pessoas" (people search) — a separate search from the listings
board (/board): here you look for a PERSON directly (any singer or
conductor with a complete-enough profile who opted to be findable),
filtered by country/state/city and voice type, instead of an open
listing/gig.

Members-only (like most of the site beyond the board itself) — a
visitor who isn't logged in is sent to /login rather than shown a
locked teaser, since a list of real people feels like something worth
gating harder than a handful of listing cards.

`users.appear_in_search` decides whether someone shows up here at
all — it defaults to TRUE (opt-out), editable on /profile.
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse

from app.database import fetch_all, fetch_one
from app.auth import get_current_user
from app.render import render
from app.badges import top_badges
from app.locations import COUNTRY_OPTIONS, STATE_OPTIONS, get_city_options

router = APIRouter()

PEOPLE_PAGE_SIZE = 20


@router.get("/people", response_class=HTMLResponse)
def search_people(
    request: Request,
    country: str = "",
    state: str = "",
    city: str = "",
    voice_type_id: str = "",
    role: str = "",
    page: int = 1,
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not user["email_verified"]:
        return RedirectResponse(url="/?verify_required=1", status_code=303)

    conditions = [
        "u.deleted_at IS NULL",
        "u.email_verified = TRUE",
        "u.appear_in_search = TRUE",
        "u.id != :viewer_id",
        # Symmetric block: neither side should be able to find the
        # other through search either, same rule as viewing a profile
        # or seeing their listings on the board (see profile_routes.py).
        "NOT EXISTS (SELECT 1 FROM blocked_users bu WHERE (bu.blocker_id = :viewer_id AND bu.blocked_id = u.id) OR (bu.blocker_id = u.id AND bu.blocked_id = :viewer_id))",
    ]
    params = {"viewer_id": user["id"]}

    if country:
        conditions.append("u.country = :country")
        params["country"] = country
    if state:
        conditions.append("u.state = :state")
        params["state"] = state
    if city:
        conditions.append("u.city ILIKE :city")
        params["city"] = f"%{city}%"
    if role in ("singer", "conductor"):
        conditions.append("u.role = :role")
        params["role"] = role
    if voice_type_id:
        conditions.append("sp.voice_type_id = :voice_type_id")
        params["voice_type_id"] = int(voice_type_id)

    where_clause = " AND ".join(conditions)

    page = max(1, page)
    offset = (page - 1) * PEOPLE_PAGE_SIZE

    total_row = fetch_one(
        f"""
        SELECT count(*) AS n
        FROM users u
        LEFT JOIN singer_profiles sp ON sp.user_id = u.id
        WHERE {where_clause}
        """,  # nosec B608 - where_clause is the join of fixed fragments (`conditions`) built above;
              # every actual value goes through `params`.
        params,
    )
    total = total_row["n"] if total_row else 0
    total_pages = max(1, (total + PEOPLE_PAGE_SIZE - 1) // PEOPLE_PAGE_SIZE)

    rows = fetch_all(
        f"""
        SELECT u.id, u.full_name, u.role, u.city, u.state, u.country, u.avatar_url, u.profile_slug,
               vt.name AS voice_type_name
        FROM users u
        LEFT JOIN singer_profiles sp ON sp.user_id = u.id
        LEFT JOIN voice_types vt ON vt.id = sp.voice_type_id
        WHERE {where_clause}
        ORDER BY u.last_seen_at DESC NULLS LAST, u.created_at DESC
        LIMIT :limit OFFSET :offset
        """,  # nosec B608 - same fixed where_clause explained above.
        {**params, "limit": PEOPLE_PAGE_SIZE, "offset": offset},
    )

    # Top-3 badges per card — a handful of small COUNT queries each,
    # acceptable at this project's scale (see app/badges.py:top_badges).
    people = []
    for row in rows:
        person = dict(row)
        person["badges"] = top_badges(row["id"], limit=3)
        people.append(person)

    context = {
        "user": user,
        "people": people,
        "voice_types": fetch_all("SELECT id, name FROM voice_types ORDER BY sort_order"),
        "country_options": COUNTRY_OPTIONS,
        "state_options": STATE_OPTIONS,
        "city_options": get_city_options(),
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "filters": {
            "country": country,
            "state": state,
            "city": city,
            "voice_type_id": voice_type_id,
            "role": role,
        },
    }
    return render(request, "search_people.html", context)


@router.get("/u/{slug}")
def profile_by_slug(slug: str):
    """Short, shareable custom profile URL (/u/{slug}) — resolves to
    the real canonical route (/users/{id}) via redirect, so all the
    actual profile logic (freemium lock, blocking, ratings, view
    counting, ...) stays in one place (public_profile() in
    profile_routes.py) instead of being duplicated here."""
    row = fetch_one("SELECT id FROM users WHERE profile_slug = :slug AND deleted_at IS NULL", {"slug": slug})
    if not row:
        raise HTTPException(status_code=404)
    return RedirectResponse(url=f"/users/{row['id']}", status_code=302)

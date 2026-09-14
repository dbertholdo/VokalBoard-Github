import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Form, UploadFile, File, BackgroundTasks
from fastapi.responses import RedirectResponse, HTMLResponse, Response

from app.database import fetch_all, fetch_one, execute
from app.auth import get_current_user, hash_password, verify_password
from app.render import render
from app.csrf import verify_csrf
from app.avatars import save_avatar, remove_existing_avatar
from app.referrals import ensure_referral_code, get_referral_stats
from app.badges import get_user_badges, with_profile_complete, check_and_notify_new_badges
from app.locations import COUNTRY_OPTIONS, STATE_OPTIONS, get_city_options
from app.password_policy import password_error

router = APIRouter()

MAX_COMPOSER_TAGS = 10
MAX_BIO_LENGTH = 1000
MAX_AUDIO_LINKS = 3
MAX_RATING_COMMENT = 500

# "Cooldown" window for profile view counting: the same session
# (same browser) only generates a new row in profile_views per
# profile every 12h, even if the person hits F5 several times.
VIEW_COOLDOWN_SECONDS = 12 * 60 * 60

# Accepted social network platforms — a fixed set (not a free-text
# field) so we can always show just the network's name ("Instagram",
# "Facebook"...) instead of the full link, and keep the profile view
# uncluttered, as requested.
SOCIAL_PLATFORMS = ["website", "facebook", "instagram", "twitter", "whatsapp"]


def parse_hashtags(raw: str) -> list[str]:
    """
    Takes something like "#Mozart, Verdi #Puccini" and returns a
    clean list with no duplicates, with at most MAX_COMPOSER_TAGS items.

    Accepts comma or space as separator, and the "#" is optional.
    """
    if not raw:
        return []
    parts = raw.replace(",", " ").split()
    seen: dict[str, str] = {}
    for part in parts:
        tag = part.lstrip("#").strip()
        if not tag:
            continue
        key = tag.lower()
        if key not in seen:
            seen[key] = tag[:50]
    return list(seen.values())[:MAX_COMPOSER_TAGS]


def parse_audio_links(raw: str) -> list[str]:
    """
    Takes "Audiobeispiel" links separated by comma and/or line break
    (e.g. a YouTube link, SoundCloud etc.) and returns up to
    MAX_AUDIO_LINKS valid URLs (starting with http:// or https://).
    Invalid links are simply ignored, without blocking the signup.
    """
    if not raw:
        return []
    parts = raw.replace(",", "\n").splitlines()
    links: list[str] = []
    for part in parts:
        url = part.strip()
        if url.startswith("http://") or url.startswith("https://"):
            links.append(url[:500])
        if len(links) >= MAX_AUDIO_LINKS:
            break
    return links


def get_singer_profile(user_id: int) -> dict | None:
    return fetch_one(
        """
        SELECT sp.voice_type_id, sp.fach, sp.bio, vt.name AS voice_type_name
        FROM singer_profiles sp
        LEFT JOIN voice_types vt ON vt.id = sp.voice_type_id
        WHERE sp.user_id = :user_id
        """,
        {"user_id": user_id},
    )


def get_conductor_profile(user_id: int) -> dict | None:
    return fetch_one(
        "SELECT ensemble_name, bio FROM conductor_profiles WHERE user_id = :user_id",
        {"user_id": user_id},
    )


def get_composer_tags(user_id: int) -> list[str]:
    rows = fetch_all(
        "SELECT tag FROM singer_composer_tags WHERE user_id = :user_id ORDER BY tag",
        {"user_id": user_id},
    )
    return [r["tag"] for r in rows]


def get_audio_links(user_id: int) -> list[str]:
    rows = fetch_all(
        "SELECT url FROM singer_audio_links WHERE user_id = :user_id ORDER BY id",
        {"user_id": user_id},
    )
    return [r["url"] for r in rows]


def set_audio_links(user_id: int, links: list[str]) -> None:
    execute("DELETE FROM singer_audio_links WHERE user_id = :user_id", {"user_id": user_id})
    for url in links:
        execute(
            "INSERT INTO singer_audio_links (user_id, url) VALUES (:user_id, :url)",
            {"user_id": user_id, "url": url},
        )


def get_social_links(user_id: int) -> dict[str, str]:
    rows = fetch_all(
        "SELECT platform, url FROM user_social_links WHERE user_id = :user_id",
        {"user_id": user_id},
    )
    return {r["platform"]: r["url"] for r in rows}


def set_social_links(user_id: int, links: dict[str, str]) -> None:
    """
    `links` is {platform: url}; missing platforms or ones with an
    empty URL are removed. Only accepts http(s) — this avoids people
    pasting "@username" without a real link, which would break the
    button when displaying it.
    """
    execute("DELETE FROM user_social_links WHERE user_id = :user_id", {"user_id": user_id})
    for platform, url in links.items():
        url = (url or "").strip()
        if platform not in SOCIAL_PLATFORMS or not url:
            continue
        if not (url.startswith("http://") or url.startswith("https://")):
            continue
        execute(
            "INSERT INTO user_social_links (user_id, platform, url) VALUES (:user_id, :platform, :url)",
            {"user_id": user_id, "platform": platform, "url": url[:500]},
        )


def get_my_ratings(user_id: int) -> list[dict]:
    """
    Ratings RECEIVED by this person — only called from /profile (the
    person themselves seeing what they received). Never called from
    /users/{id} (public profile) or anywhere else visible to third
    parties.
    """
    return fetch_all(
        """
        SELECT r.stars, r.comment, r.created_at, u.full_name AS rater_name, r.rater_id
        FROM ratings r
        JOIN users u ON u.id = r.rater_id
        WHERE r.rated_id = :user_id
        ORDER BY r.created_at DESC
        """,
        {"user_id": user_id},
    )


def get_rating_summary(user_id: int) -> dict:
    row = fetch_one(
        "SELECT COUNT(*) AS n, AVG(stars)::numeric(3,1) AS avg_stars FROM ratings WHERE rated_id = :user_id",
        {"user_id": user_id},
    )
    return {"count": row["n"] if row else 0, "avg_stars": row["avg_stars"] if row else None}


def get_rating_given(rater_id: int, rated_id: int) -> dict | None:
    return fetch_one(
        "SELECT stars, comment FROM ratings WHERE rater_id = :rater_id AND rated_id = :rated_id",
        {"rater_id": rater_id, "rated_id": rated_id},
    )


# Items that count toward the "complete profile" indicator in
# /profile — each one carries the same weight (simple to explain: "8
# of 10 items = 80%"). The idea (as requested) is to reinforce that a
# more complete profile inspires more trust in visitors and improves
# what the Home page can "match" automatically (voice, city, composer
# tags factor into the matching).
def compute_profile_completeness(user: dict, role_profile: dict | None, composer_tags: list,
                                  audio_links: list, social_links: dict) -> dict:
    items = [
        ("avatar", bool(user.get("avatar_url"))),
        ("city", bool(user.get("city"))),
        ("phone", bool(user.get("phone"))),
        ("bio", bool(role_profile and role_profile.get("bio"))),
        ("social_link", bool(social_links)),
    ]
    if user["role"] == "singer":
        items.append(("voice_type", bool(role_profile and role_profile.get("voice_type_id"))))
        items.append(("composer_tags", bool(composer_tags)))
        items.append(("audio_links", bool(audio_links)))
    else:
        items.append(("ensemble_name", bool(role_profile and role_profile.get("ensemble_name"))))

    done = sum(1 for _, ok in items if ok)
    total = len(items)
    missing = [key for key, ok in items if not ok]
    percent = round((done / total) * 100) if total else 0
    return {"percent": percent, "done": done, "total": total, "missing": missing}


def get_blocked_users(user_id: int) -> list[dict]:
    return fetch_all(
        """
        SELECT u.id, u.full_name, bu.reason, bu.created_at
        FROM blocked_users bu
        JOIN users u ON u.id = bu.blocked_id
        WHERE bu.blocker_id = :user_id
        ORDER BY bu.created_at DESC
        """,
        {"user_id": user_id},
    )


def _my_profile_context(request: Request, user: dict, error: str | None = None, saved: bool = False) -> dict:
    singer_profile = get_singer_profile(user["id"]) if user["role"] == "singer" else None
    conductor_profile = get_conductor_profile(user["id"]) if user["role"] == "conductor" else None
    composer_tags = get_composer_tags(user["id"]) if user["role"] == "singer" else []
    audio_links = get_audio_links(user["id"]) if user["role"] == "singer" else []
    social_links = get_social_links(user["id"])
    role_profile = singer_profile if user["role"] == "singer" else conductor_profile

    referral_code = ensure_referral_code(user["id"], user.get("referral_code"))
    user["referral_code"] = referral_code
    referral_url = f"{str(request.base_url).rstrip('/')}/register?ref={referral_code}"

    completeness = compute_profile_completeness(user, role_profile, composer_tags, audio_links, social_links)
    badges = with_profile_complete(get_user_badges(user["id"]), completeness["percent"])

    return {
        "user": user,
        "referral_url": referral_url,
        "referral_count": get_referral_stats(user["id"])["count"],
        "blocked_users": get_blocked_users(user["id"]),
        "badges": badges,
        "voice_types": fetch_all("SELECT id, name FROM voice_types ORDER BY sort_order"),
        "singer_profile": singer_profile,
        "conductor_profile": conductor_profile,
        "composer_tags": composer_tags,
        "audio_links": audio_links,
        "social_links": social_links,
        "social_platforms": SOCIAL_PLATFORMS,
        # Ratings received — ONLY show up here, on the person's own
        # profile page (private, never on /users/{id}).
        "my_ratings": get_my_ratings(user["id"]),
        "rating_summary": get_rating_summary(user["id"]),
        "completeness": completeness,
        "max_bio_length": MAX_BIO_LENGTH,
        "max_composer_tags": MAX_COMPOSER_TAGS,
        "max_audio_links": MAX_AUDIO_LINKS,
        "country_options": COUNTRY_OPTIONS,
        "state_options": STATE_OPTIONS,
        "city_options": get_city_options(),
        "error": error,
        "saved": saved,
    }


@router.get("/profile", response_class=HTMLResponse)
def my_profile(request: Request, background_tasks: BackgroundTasks):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    # "Lazy" check of tiered badges that depend only on time passing
    # (anniversary) or on data that changes outside a direct action
    # (views) — since the project doesn't use any internal cron, we
    # take advantage of the most natural and frequent visit (the
    # person opening their own profile) to recalculate and, if that's
    # the case, send the "new badge" e-mail.
    background_tasks.add_task(check_and_notify_new_badges, user["id"], str(request.base_url))

    context = _my_profile_context(request, user, saved=request.query_params.get("saved") == "1")
    return render(request, "profile.html", context)


@router.post("/profile")
async def update_profile(
    request: Request,
    background_tasks: BackgroundTasks,
    csrf_token: str = Form(""),
    bio: str = Form(""),
    city: str = Form(""),
    state: str = Form(""),
    country: str = Form("DE"),
    voice_type_id: str = Form(""),
    fach: str = Form(""),
    ensemble_name: str = Form(""),
    composer_hashtags: str = Form(""),
    audio_links: str = Form(""),
    social_website: str = Form(""),
    social_facebook: str = Form(""),
    social_instagram: str = Form(""),
    social_twitter: str = Form(""),
    social_whatsapp: str = Form(""),
    notify_matches: str = Form(""),
    notify_messages: str = Form(""),
    remove_avatar: str = Form(""),
    avatar: UploadFile | None = File(None),
):
    verify_csrf(request, csrf_token)

    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    bio = bio.strip()[:MAX_BIO_LENGTH]

    if country not in COUNTRY_OPTIONS:
        context = _my_profile_context(request, user, error="register_error_invalid_country")
        return render(request, "profile.html", context, status_code=400)

    execute(
        """
        UPDATE users
        SET notify_matches = :notify_matches, notify_messages = :notify_messages,
            city = :city, state = :state, country = :country
        WHERE id = :id
        """,
        {
            "notify_matches": bool(notify_matches),
            "notify_messages": bool(notify_messages),
            "city": city or None,
            "state": state or None,
            "country": country,
            "id": user["id"],
        },
    )

    if remove_avatar:
        remove_existing_avatar(user["id"])
        execute("UPDATE users SET avatar_url = NULL WHERE id = :id", {"id": user["id"]})
    elif avatar is not None and avatar.filename:
        new_avatar_url = await save_avatar(user["id"], avatar)
        if new_avatar_url:
            execute("UPDATE users SET avatar_url = :avatar_url WHERE id = :id", {"avatar_url": new_avatar_url, "id": user["id"]})
        else:
            # Invalid file (unsupported type or too large) — doesn't
            # block the rest of the save, just skips the photo and warns.
            context = _my_profile_context(request, get_current_user(request), error="profile_avatar_invalid")
            return render(request, "profile.html", context, status_code=400)

    set_social_links(user["id"], {
        "website": social_website,
        "facebook": social_facebook,
        "instagram": social_instagram,
        "twitter": social_twitter,
        "whatsapp": social_whatsapp,
    })

    if user["role"] == "singer":
        execute(
            """
            UPDATE singer_profiles
            SET voice_type_id = :voice_type_id, fach = :fach, bio = :bio
            WHERE user_id = :user_id
            """,
            {
                "voice_type_id": int(voice_type_id) if voice_type_id else None,
                "fach": fach or None,
                "bio": bio or None,
                "user_id": user["id"],
            },
        )

        tags = parse_hashtags(composer_hashtags)
        execute("DELETE FROM singer_composer_tags WHERE user_id = :user_id", {"user_id": user["id"]})
        for tag in tags:
            execute(
                "INSERT INTO singer_composer_tags (user_id, tag) VALUES (:user_id, :tag)",
                {"user_id": user["id"], "tag": tag},
            )

        set_audio_links(user["id"], parse_audio_links(audio_links))
    else:
        execute(
            """
            UPDATE conductor_profiles
            SET ensemble_name = :ensemble_name, bio = :bio
            WHERE user_id = :user_id
            """,
            {"ensemble_name": ensemble_name or None, "bio": bio or None, "user_id": user["id"]},
        )

    background_tasks.add_task(check_and_notify_new_badges, user["id"], str(request.base_url))
    return RedirectResponse(url="/profile?saved=1", status_code=303)


@router.get("/profile/change-password", response_class=HTMLResponse)
def change_password_form(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return render(request, "change_password.html", {"user": user, "error": None})


@router.post("/profile/change-password")
def change_password_submit(
    request: Request,
    csrf_token: str = Form(""),
    current_password: str = Form(...),
    new_password: str = Form(...),
):
    verify_csrf(request, csrf_token)
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    row = fetch_one("SELECT password_hash FROM users WHERE id = :id", {"id": user["id"]})
    if not row or not verify_password(current_password, row["password_hash"]):
        return render(
            request, "change_password.html",
            {"user": user, "error": "change_password_wrong_current"},
            status_code=400,
        )

    pw_error = password_error(new_password)
    if pw_error:
        return render(
            request, "change_password.html",
            {"user": user, "error": pw_error},
            status_code=400,
        )

    execute(
        "UPDATE users SET password_hash = :hash WHERE id = :id",
        {"hash": hash_password(new_password), "id": user["id"]},
    )
    return RedirectResponse(url="/profile?saved=1", status_code=303)


@router.post("/profile/delete-account")
def delete_account_submit(request: Request, csrf_token: str = Form(""), current_password: str = Form(...)):
    """
    Soft delete: sets deleted_at = now() and drops the session. The
    account becomes "invisible" (get_current_user, author joins etc.
    filter on deleted_at IS NULL) but the data stays in the database
    for 6 months — if the person tries to log in again during that
    period, they fall into the reactivation flow (see
    /reactivate-account in auth_routes.py). After 6 months, an
    external script (scripts/purge_deleted_accounts.py) deletes it
    for good — no cron inside the app, like the rest of the project.
    """
    verify_csrf(request, csrf_token)
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    row = fetch_one("SELECT password_hash FROM users WHERE id = :id", {"id": user["id"]})
    if not row or not verify_password(current_password, row["password_hash"]):
        context = _my_profile_context(request, user, error="delete_account_wrong_password")
        return render(request, "profile.html", context, status_code=400)

    execute("UPDATE users SET deleted_at = now() WHERE id = :id", {"id": user["id"]})
    request.session.clear()
    return RedirectResponse(url="/?account_deleted=1", status_code=303)


@router.get("/profile/export")
def export_my_data(request: Request):
    """
    Data export (GDPR Art. 20 — right to portability): a JSON with
    everything the person has registered in the system, to download.
    Deliberately does NOT include password_hash (it isn't "your data"
    in the portability sense, it's an authentication secret) nor
    other people's data beyond what's already necessary to give
    context to the person's own messages/ratings.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    user_id = user["id"]

    account = fetch_one(
        "SELECT id, email, full_name, role, city, phone, email_verified, avatar_url, notify_matches, notify_messages, created_at FROM users WHERE id = :id",
        {"id": user_id},
    )
    listings = fetch_all(
        "SELECT id, listing_type, title, description, city, state, country, repertoire, venue, fee, ensemble_type, event_date, is_active, created_at FROM listings WHERE author_id = :id ORDER BY created_at",
        {"id": user_id},
    )
    messages_sent = fetch_all(
        "SELECT id, recipient_id, listing_id, body, created_at FROM messages WHERE sender_id = :id ORDER BY created_at",
        {"id": user_id},
    )
    messages_received = fetch_all(
        "SELECT id, sender_id, listing_id, body, created_at, read_at FROM messages WHERE recipient_id = :id ORDER BY created_at",
        {"id": user_id},
    )
    ratings_received = get_my_ratings(user_id)
    ratings_given = fetch_all(
        "SELECT rated_id, stars, comment, created_at FROM ratings WHERE rater_id = :id ORDER BY created_at",
        {"id": user_id},
    )
    saved_listings = fetch_all(
        "SELECT listing_id, created_at FROM saved_listings WHERE user_id = :id ORDER BY created_at",
        {"id": user_id},
    )

    export = {
        "account": account,
        "singer_profile": get_singer_profile(user_id) if user["role"] == "singer" else None,
        "conductor_profile": get_conductor_profile(user_id) if user["role"] == "conductor" else None,
        "composer_tags": get_composer_tags(user_id) if user["role"] == "singer" else [],
        "audio_links": get_audio_links(user_id) if user["role"] == "singer" else [],
        "social_links": get_social_links(user_id),
        "listings_posted": listings,
        "messages_sent": messages_sent,
        "messages_received": messages_received,
        "ratings_received": ratings_received,
        "ratings_given": ratings_given,
        "saved_listings": saved_listings,
    }

    body = json.dumps(export, indent=2, ensure_ascii=False, default=str)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="vokalboard-data-{user_id}.json"'},
    )


@router.post("/users/{user_id}/block")
def block_user(request: Request, user_id: int, csrf_token: str = Form(""), reason: str = Form("")):
    """
    Blocking someone: from now on neither side can send the other a
    message (checked in messages_routes.py), and the blocked
    person's listings disappear from /board and from the Home
    matches for whoever blocked them (see the NOT EXISTS filters in
    listings_routes.py). A reason is optional here (unlike reporting
    a listing, which requires one) — blocking is a personal decision,
    no justification needed.
    """
    verify_csrf(request, csrf_token)
    viewer = get_current_user(request)
    if not viewer:
        return RedirectResponse(url="/login", status_code=303)
    if viewer["id"] == user_id:
        return RedirectResponse(url=f"/users/{user_id}", status_code=303)

    target = fetch_one("SELECT id FROM users WHERE id = :id", {"id": user_id})
    if target:
        execute(
            """
            INSERT INTO blocked_users (blocker_id, blocked_id, reason) VALUES (:blocker_id, :blocked_id, :reason)
            ON CONFLICT (blocker_id, blocked_id) DO NOTHING
            """,
            {"blocker_id": viewer["id"], "blocked_id": user_id, "reason": reason.strip()[:500] or None},
        )
    return RedirectResponse(url=f"/users/{user_id}?blocked=1", status_code=303)


@router.post("/users/{user_id}/unblock")
def unblock_user(request: Request, user_id: int, csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)
    viewer = get_current_user(request)
    if not viewer:
        return RedirectResponse(url="/login", status_code=303)

    execute(
        "DELETE FROM blocked_users WHERE blocker_id = :blocker_id AND blocked_id = :blocked_id",
        {"blocker_id": viewer["id"], "blocked_id": user_id},
    )
    referer = request.headers.get("referer", "")
    if "/profile" in referer:
        return RedirectResponse(url="/profile", status_code=303)
    return RedirectResponse(url=f"/users/{user_id}", status_code=303)


@router.post("/users/{user_id}/rate")
def rate_user(
    request: Request,
    user_id: int,
    csrf_token: str = Form(""),
    stars: int = Form(...),
    comment: str = Form(""),
    listing_id: str = Form(""),
):
    verify_csrf(request, csrf_token)
    viewer = get_current_user(request)
    if not viewer:
        return RedirectResponse(url="/login", status_code=303)
    if viewer["id"] == user_id:
        return RedirectResponse(url=f"/users/{user_id}", status_code=303)
    if stars < 0 or stars > 5:
        return RedirectResponse(url=f"/users/{user_id}", status_code=303)

    rated_exists = fetch_one("SELECT id FROM users WHERE id = :id AND deleted_at IS NULL", {"id": user_id})
    if not rated_exists:
        return RedirectResponse(url="/board", status_code=303)

    listing_id_val = int(listing_id) if listing_id.strip().isdigit() else None
    comment_val = comment.strip()[:MAX_RATING_COMMENT] or None

    execute(
        """
        INSERT INTO ratings (rater_id, rated_id, listing_id, stars, comment)
        VALUES (:rater_id, :rated_id, :listing_id, :stars, :comment)
        ON CONFLICT (rater_id, rated_id)
        DO UPDATE SET stars = :stars, comment = :comment, listing_id = :listing_id, updated_at = now()
        """,
        {
            "rater_id": viewer["id"],
            "rated_id": user_id,
            "listing_id": listing_id_val,
            "stars": stars,
            "comment": comment_val,
        },
    )
    return RedirectResponse(url=f"/users/{user_id}?rated=1", status_code=303)


@router.get("/users/{user_id}", response_class=HTMLResponse)
def public_profile(request: Request, user_id: int, background_tasks: BackgroundTasks):
    profile_user = fetch_one(
        "SELECT id, full_name, role, city, phone, avatar_url FROM users WHERE id = :id", {"id": user_id}
    )

    singer_profile = None
    conductor_profile = None
    composer_tags = []
    audio_links = []
    if profile_user:
        if profile_user["role"] == "singer":
            singer_profile = get_singer_profile(user_id)
            composer_tags = get_composer_tags(user_id)
            audio_links = get_audio_links(user_id)
        else:
            conductor_profile = get_conductor_profile(user_id)

        # Visit log — doesn't show up on any screen, it's just for
        # you (the admin) to query directly in the database. Doesn't
        # count the person themselves visiting their own profile.
        #
        # To prevent hitting F5 on the page from inflating the count,
        # each session (browser cookie, already used for login/CSRF)
        # only counts as a new visit to this profile once every
        # VIEW_COOLDOWN. It's not foolproof (clearing cookies or
        # using an incognito tab gets around it), but that's
        # acceptable for a lightweight metric — it's not worth
        # tracking IP to close this gap completely, which would go
        # against the project's "profile_views is private and
        # minimal" principle.
        viewer = get_current_user(request)
        if not viewer or viewer["id"] != user_id:
            session_key = f"viewed_profile_{user_id}"
            last_viewed = request.session.get(session_key)
            now_ts = datetime.now(timezone.utc).timestamp()
            if not last_viewed or (now_ts - last_viewed) > VIEW_COOLDOWN_SECONDS:
                request.session[session_key] = now_ts
                execute(
                    "INSERT INTO profile_views (profile_user_id, viewer_user_id) VALUES (:profile_id, :viewer_id)",
                    {"profile_id": user_id, "viewer_id": viewer["id"] if viewer else None},
                )
                # The visit may have made the profile OWNER cross a
                # "views" threshold (100/500/1000) — check and notify
                # THEM, not whoever is visiting.
                background_tasks.add_task(check_and_notify_new_badges, user_id, str(request.base_url))

    listings = fetch_all(
        """
        SELECT id, title, listing_type, city, created_at,
            CASE
                WHEN event_date IS NULL THEN NULL
                WHEN event_date < CURRENT_DATE THEN 'past'
                WHEN event_date <= CURRENT_DATE + INTERVAL '7 days' THEN 'soon'
                ELSE 'upcoming'
            END AS event_status
        FROM listings
        WHERE author_id = :author_id AND is_active = TRUE
        ORDER BY created_at DESC
        """,
        {"author_id": user_id},
    )

    viewer = get_current_user(request)

    # Social networks: only make sense to show when the profile isn't
    # "locked" (visitor logged in), otherwise it would be one more
    # piece of data exposed for free to whoever hasn't signed up.
    social_links = get_social_links(user_id) if profile_user and viewer is not None else {}

    # The rating I (the viewer) already gave this person, to
    # pre-fill the rating form. This is different from "ratings this
    # person received" (my_ratings/rating_summary) — that's private
    # and NEVER shows up here, only on /profile (the person
    # themselves seeing what they received). Here there's only the
    # widget to give/update a rating.
    rating_given = None
    can_rate = False
    is_blocked = False
    # A block needs to be invisible from BOTH sides, otherwise it
    # doesn't help much — if I blocked someone (or was blocked by
    # them), neither of us should be able to see the other's profile,
    # not just exchange messages. "blocked_either_way" covers both
    # directions.
    blocked_either_way = False
    if profile_user and viewer is not None and viewer["id"] != user_id:
        can_rate = True
        rating_given = get_rating_given(viewer["id"], user_id)
        blocked_row = fetch_one(
            "SELECT 1 FROM blocked_users WHERE blocker_id = :blocker_id AND blocked_id = :blocked_id",
            {"blocker_id": viewer["id"], "blocked_id": user_id},
        )
        is_blocked = blocked_row is not None

        blocked_other_way = fetch_one(
            "SELECT 1 FROM blocked_users WHERE blocker_id = :blocker_id AND blocked_id = :blocked_id",
            {"blocker_id": user_id, "blocked_id": viewer["id"]},
        )
        blocked_either_way = is_blocked or (blocked_other_way is not None)

    # Badges: only the unlocked ones show up on the public profile
    # (the profile doesn't get cluttered with "locked achievements"
    # for visitors) — the person themselves sees all of them, locked
    # or not, in /profile.
    badges = []
    if profile_user and not blocked_either_way:
        role_profile_for_badges = singer_profile if profile_user["role"] == "singer" else conductor_profile
        completeness_pct = compute_profile_completeness(
            profile_user, role_profile_for_badges, composer_tags, audio_links, social_links
        )["percent"]
        all_badges = with_profile_complete(get_user_badges(user_id), completeness_pct)
        badges = [b for b in all_badges if b["unlocked"]]

    context = {
        "user": viewer,
        "profile_user": profile_user,
        "singer_profile": singer_profile,
        "conductor_profile": conductor_profile,
        "composer_tags": composer_tags,
        "audio_links": audio_links,
        "social_links": social_links,
        "social_platforms": SOCIAL_PLATFORMS,
        "can_rate": can_rate,
        "rating_given": rating_given,
        "is_blocked": is_blocked,
        "blocked_either_way": blocked_either_way,
        "badges": badges,
        "listings": listings,
        # Freemium: without login you can only see name/role/city —
        # bio, hashtags, audio links and listings stay behind signup.
        "locked": viewer is None,
    }
    return render(request, "public_profile.html", context)

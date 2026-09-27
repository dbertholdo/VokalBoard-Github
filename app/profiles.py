"""Profile service: reading/writing a user's profile parts and the profile save.

Moved out of app/routers/profile_routes.py on 2026-09-27 (CLAUDE.md §4 — no
fat routers). Other modules import from here, not from the router.
"""
import re

from sqlalchemy import text

from app.database import fetch_all, fetch_one, execute, transaction
from app.i18n import SUPPORTED_LANGUAGES
from app.languages import MAX_SPOKEN_LANGUAGES
from app.locations import COUNTRY_OPTIONS

MAX_COMPOSER_TAGS = 10
MAX_BIO_LENGTH = 1000
MAX_AUDIO_LINKS = 3
MAX_RATING_COMMENT = 500

# Custom profile URL slug (/u/{slug}) — lowercase letters, digits and
# hyphens only, 3-60 chars. Kept intentionally strict/simple (no
# unicode, no leading/trailing hyphen edge cases to worry about) since
# this becomes part of a public URL.
PROFILE_SLUG_RE = re.compile(r"^[a-z0-9-]{3,60}$")


# Accepted social network platforms — a fixed set (not a free-text
# field) so we can always show just the network's name ("Instagram",
# "Facebook"...) instead of the full link, and keep the profile view
# uncluttered, as requested.
SOCIAL_PLATFORMS = ["website", "facebook", "instagram", "twitter"]


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


def get_extra_voice_types(user_id: int) -> list[dict]:
    """Additional voice types the singer also sings, besides the primary
    one in singer_profiles.voice_type_id (see singer_profile_voice_types
    in db/schema.sql — foundation applied 17/09, UI added here in P2)."""
    return fetch_all(
        """
        SELECT vt.id, vt.name
        FROM singer_profile_voice_types spvt
        JOIN voice_types vt ON vt.id = spvt.voice_type_id
        WHERE spvt.user_id = :user_id
        ORDER BY vt.sort_order
        """,
        {"user_id": user_id},
    )


def get_all_voice_type_names(user_id: int) -> list[str]:
    """Primary voice + additional voices, deduplicated, in catalog order
    — used for display on the person's own /profile and on the public
    profile (/users/{id})."""
    rows = fetch_all(
        """
        SELECT vt.id, vt.name
        FROM voice_types vt
        WHERE vt.id IN (
            SELECT voice_type_id FROM singer_profiles WHERE user_id = :user_id AND voice_type_id IS NOT NULL
            UNION
            SELECT voice_type_id FROM singer_profile_voice_types WHERE user_id = :user_id
        )
        ORDER BY vt.sort_order
        """,
        {"user_id": user_id},
    )
    return [r["name"] for r in rows]


# Not called from any route since 19/09/2026 (the "Weitere Stimmlagen"
# fieldset was removed from profile.html/profile_wizard.html) — kept as
# a working function rather than deleted, since get_extra_voice_types()
# above still reads singer_profile_voice_types elsewhere (search
# filtering, notification matching) and this is its natural write-side
# counterpart if that UI ever comes back.
def set_extra_voice_types(user_id: int, voice_type_ids: list[int]) -> None:
    execute("DELETE FROM singer_profile_voice_types WHERE user_id = :user_id", {"user_id": user_id})
    seen = set()
    for vt_id in voice_type_ids:
        if vt_id in seen:
            continue
        seen.add(vt_id)
        execute(
            """
            INSERT INTO singer_profile_voice_types (user_id, voice_type_id)
            VALUES (:user_id, :voice_type_id)
            ON CONFLICT DO NOTHING
            """,
            {"user_id": user_id, "voice_type_id": vt_id},
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


def public_base_url(request) -> str:
    """The site's public address for links people copy or share (SITE_BASE_URL,
    else the request's host)."""
    from app.email_layout import SITE_BASE_URL
    return (SITE_BASE_URL or str(request.base_url)).rstrip("/")


def profile_public_url(request_base_url: str, user_id: int, slug: str | None) -> str:
    """The shareable profile link. SITE_BASE_URL (the public domain) wins over the
    request's host, so links copied behind a proxy/preview still point at the real site."""
    from app.email_layout import SITE_BASE_URL
    base = (SITE_BASE_URL or str(request_base_url)).rstrip("/")
    return f"{base}/u/{slug}" if slug else f"{base}/users/{user_id}"


MAX_CITY_LENGTH = 100
MAX_FACH_LENGTH = 100
MAX_ENSEMBLE_LENGTH = 150
MAX_PHONE_LENGTH = 50


class ProfileError(Exception):
    """Invalid profile input; `key` is the i18n key shown to the user."""

    def __init__(self, key: str):
        super().__init__(key)
        self.key = key


def clean_profile_input(user: dict, form: dict) -> dict:
    """Validates and normalizes the /profile form. Raises ProfileError(key)."""
    country = form.get("country") or "DE"
    if country not in COUNTRY_OPTIONS:
        raise ProfileError("register_error_invalid_country")
    language = form.get("preferred_language") or "en"
    if language not in SUPPORTED_LANGUAGES:
        language = "en"

    slug = (form.get("profile_slug") or "").strip().lower() or None
    if slug is not None:
        if not PROFILE_SLUG_RE.match(slug):
            raise ProfileError("profile_slug_invalid")
        if fetch_one("SELECT 1 FROM users WHERE profile_slug = :slug AND id != :id", {"slug": slug, "id": user["id"]}):
            raise ProfileError("profile_slug_taken")

    voice_type_id = None
    raw_voice = (form.get("voice_type_id") or "").strip()
    if user["role"] == "singer" and raw_voice:
        # A tampered/stale value used to crash the save (int() or the FK) — now it's a form error.
        if not raw_voice.isdigit() or not fetch_one("SELECT 1 FROM voice_types WHERE id = :id", {"id": int(raw_voice)}):
            raise ProfileError("register_error_invalid_category")
        voice_type_id = int(raw_voice)

    def short(name: str, limit: int) -> str | None:
        return (form.get(name) or "").strip()[:limit] or None

    return {
        "country": country, "preferred_language": language, "profile_slug": slug,
        "city": short("city", MAX_CITY_LENGTH), "state": short("state", MAX_CITY_LENGTH),
        "phone": short("phone", MAX_PHONE_LENGTH),
        "phone_visibility": "public" if form.get("phone_visibility_public") else "private",
        "notify_matches": bool(form.get("notify_matches")), "notify_messages": bool(form.get("notify_messages")),
        "appear_in_search": bool(form.get("appear_in_search")),
        "bio": (form.get("bio") or "").strip()[:MAX_BIO_LENGTH] or None,
        "voice_type_id": voice_type_id, "fach": short("fach", MAX_FACH_LENGTH),
        "ensemble_name": short("ensemble_name", MAX_ENSEMBLE_LENGTH),
        "composer_tags": parse_hashtags(form.get("composer_hashtags") or ""),
        "audio_links": parse_audio_links(form.get("audio_links") or ""),
        "social_links": {p: (form.get(f"social_{p}") or "").strip() for p in SOCIAL_PLATFORMS},
    }


def save_profile(user: dict, data: dict, spoken_languages: list[tuple[str, str | None]]) -> None:
    """Writes everything from clean_profile_input() in ONE transaction."""
    uid = user["id"]
    with transaction() as conn:
        def run(sql: str, params: dict) -> None:
            conn.execute(text(sql), params)

        run("""
            UPDATE users
            SET notify_matches = :notify_matches, notify_messages = :notify_messages,
                preferred_language = :preferred_language, appear_in_search = :appear_in_search,
                profile_slug = :profile_slug, city = :city, state = :state, country = :country,
                phone = :phone, phone_visibility = :phone_visibility
            WHERE id = :id
            """, {**{k: data[k] for k in ("notify_matches", "notify_messages", "preferred_language", "appear_in_search",
                                          "profile_slug", "city", "state", "country", "phone", "phone_visibility")}, "id": uid})

        run("DELETE FROM user_social_links WHERE user_id = :uid", {"uid": uid})
        for platform, url in data["social_links"].items():
            # http(s) only — a bare "@username" would render as a broken button.
            if platform in SOCIAL_PLATFORMS and url.startswith(("http://", "https://")):
                run("INSERT INTO user_social_links (user_id, platform, url) VALUES (:uid, :p, :url)",
                    {"uid": uid, "p": platform, "url": url[:500]})

        if user["role"] == "singer":
            run("UPDATE singer_profiles SET voice_type_id = :vt, fach = :fach, bio = :bio WHERE user_id = :uid",
                {"vt": data["voice_type_id"], "fach": data["fach"], "bio": data["bio"], "uid": uid})
            run("DELETE FROM singer_composer_tags WHERE user_id = :uid", {"uid": uid})
            for tag in data["composer_tags"]:
                run("INSERT INTO singer_composer_tags (user_id, tag) VALUES (:uid, :tag)", {"uid": uid, "tag": tag})
            run("DELETE FROM singer_audio_links WHERE user_id = :uid", {"uid": uid})
            for url in data["audio_links"]:
                run("INSERT INTO singer_audio_links (user_id, url) VALUES (:uid, :url)", {"uid": uid, "url": url})
        else:
            run("UPDATE conductor_profiles SET ensemble_name = :ens, bio = :bio WHERE user_id = :uid",
                {"ens": data["ensemble_name"], "bio": data["bio"], "uid": uid})

        # Spoken languages (P2.B) — any role.
        run("DELETE FROM user_spoken_languages WHERE user_id = :uid", {"uid": uid})
        for position, (code, custom_name) in enumerate(spoken_languages[:MAX_SPOKEN_LANGUAGES]):
            run("""INSERT INTO user_spoken_languages (user_id, language_code, custom_name, sort_order)
                   VALUES (:uid, :code, :custom, :pos)""", {"uid": uid, "code": code, "custom": custom_name, "pos": position})


def is_blocked_either_way(a: int, b: int) -> bool:
    return fetch_one(
        """SELECT 1 FROM blocked_users
           WHERE (blocker_id = :a AND blocked_id = :b) OR (blocker_id = :b AND blocked_id = :a)""",
        {"a": a, "b": b},
    ) is not None


def save_rating(rater: dict, rated_id: int, stars: int, comment: str, listing_id: str) -> bool:
    """Public star rating (the older, non-secret system). False = not allowed:
    self, bad stars, unknown/deleted target, unverified rater, or a block in
    either direction (a blocked person must not reach the blocker this way)."""
    if rater["id"] == rated_id or not 0 <= stars <= 5 or not rater.get("email_verified"):
        return False
    if not fetch_one("SELECT 1 FROM users WHERE id = :id AND deleted_at IS NULL", {"id": rated_id}):
        return False
    if is_blocked_either_way(rater["id"], rated_id):
        return False
    listing_val = int(listing_id) if (listing_id or "").strip().isdigit() else None
    if listing_val is not None and not fetch_one("SELECT 1 FROM listings WHERE id = :id", {"id": listing_val}):
        listing_val = None  # stale/tampered id: keep the rating, drop the reference (was an FK 500)
    execute(
        """
        INSERT INTO ratings (rater_id, rated_id, listing_id, stars, comment)
        VALUES (:rater_id, :rated_id, :listing_id, :stars, :comment)
        ON CONFLICT (rater_id, rated_id)
        DO UPDATE SET stars = :stars, comment = :comment, listing_id = :listing_id, updated_at = now()
        """,
        {"rater_id": rater["id"], "rated_id": rated_id, "listing_id": listing_val, "stars": stars,
         "comment": (comment or "").strip()[:MAX_RATING_COMMENT] or None},
    )
    return True

"""
Badges: simple "achievements".

The badges themselves are CALCULATED on the fly from what already
exists (referrals, listings, messages, complete profile, views,
account age) — no rule is stored in a table. The user_badges table
only records WHEN each badge/tier was first unlocked, so that we can
(1) send the "new badge" email exactly once per tier, and (2) badges
with tiers (views, anniversary) keep track of each tier already
reached.

LIGHT gamification, with no ranking or comparison between people —
nothing like "so-and-so has more badges than someone else" anywhere,
it's purely individual recognition. The views badge only shows "passed
X", never the exact number — deliberately, to keep profile_views
private.
"""
import html as html_module

from app.database import fetch_one, fetch_all, execute
from app.email import send_email

# Ordered highest to lowest: we only take the highest tier already
# reached (instead of showing 3 views badges at once).
VIEW_MILESTONES = [
    (1000, "gold"),
    (500, "silver"),
    (100, "bronze"),
]

# Same idea for verified referrals — "platinum" is deliberately rare
# (100 people invited is a lot), it's meant to stand out.
REFERRAL_MILESTONES = [
    (100, "platinum"),
    (50, "gold"),
    (25, "silver"),
    (10, "bronze"),
]

# Anniversary doesn't have a natural "count" like the two above (it's
# years on the site), so its medal thresholds are defined separately —
# see _anniversary_medal(). Its "tier" field (below) keeps storing the
# exact year number, not the medal name, because that's what
# check_and_notify_new_badges() uses to send one e-mail per year —
# changing that would mean re-notifying everyone on their next
# anniversary. "medal" is a second, purely visual field for how the
# badge icon is colored (see app/static/css/style.css's
# .badge-tier-* rules), independent from that tracking key.


def _anniversary_medal(years: int) -> str:
    if years >= 10:
        return "platinum"
    if years >= 5:
        return "gold"
    if years >= 3:
        return "silver"
    if years >= 1:
        return "bronze"
    return ""


def _referral_count(user_id: int) -> int:
    return fetch_one(
        "SELECT COUNT(*) AS n FROM users WHERE referred_by_user_id = :id AND email_verified = TRUE",
        {"id": user_id},
    )["n"]


def _listing_count(user_id: int) -> int:
    return fetch_one("SELECT COUNT(*) AS n FROM listings WHERE author_id = :id", {"id": user_id})["n"]


def _message_sent_count(user_id: int) -> int:
    return fetch_one("SELECT COUNT(*) AS n FROM messages WHERE sender_id = :id", {"id": user_id})["n"]


def _view_count(user_id: int) -> int:
    return fetch_one("SELECT COUNT(*) AS n FROM profile_views WHERE profile_user_id = :id", {"id": user_id})["n"]


def _has_fast_response(user_id: int) -> bool:
    """
    Has replied to some message within 24h at least once: there exists
    a message M1 received by this person and a message M2, from them
    to whoever sent M1, created after M1 and within 24h.
    """
    row = fetch_one(
        """
        SELECT 1
        FROM messages m1
        JOIN messages m2
            ON m2.sender_id = m1.recipient_id
           AND m2.recipient_id = m1.sender_id
           AND m2.created_at > m1.created_at
           AND m2.created_at <= m1.created_at + INTERVAL '24 hours'
        WHERE m1.recipient_id = :user_id
        LIMIT 1
        """,
        {"user_id": user_id},
    )
    return row is not None


def _years_on_site(user_id: int) -> int:
    row = fetch_one(
        "SELECT EXTRACT(YEAR FROM age(now(), created_at))::int AS years FROM users WHERE id = :id",
        {"id": user_id},
    )
    return row["years"] if row and row["years"] else 0


def get_user_badges(user_id: int) -> list[dict]:
    # "icon" holds a symbol id from app/static/img/icons.svg (our own
    # icon set — see app/templates/profile.html / public_profile.html,
    # which render it as <svg><use href="...#{{ b.icon }}"></svg>), not
    # an emoji character.
    # "medal" (bronze/silver/gold/platinum, or "" when the badge has no
    # tiers) drives the icon color in the templates — see the
    # .badge-tier-* / .badge-key-* rules in style.css. It's separate
    # from "tier" (which is what check_and_notify_new_badges() uses as
    # the uniqueness key for "already notified this one").
    referral_count = _referral_count(user_id)
    referral_medal = ""
    for threshold, medal in REFERRAL_MILESTONES:
        if referral_count >= threshold:
            referral_medal = medal
            break

    badges = [
        {"key": "referral", "icon": "icon-gift", "unlocked": referral_count > 0, "tier": referral_medal, "medal": referral_medal},
        {"key": "listing", "icon": "icon-listings", "unlocked": _listing_count(user_id) > 0, "tier": "", "medal": ""},
        {"key": "contact", "icon": "icon-mail", "unlocked": _message_sent_count(user_id) > 0, "tier": "", "medal": ""},
        {"key": "fast_response", "icon": "icon-bolt", "unlocked": _has_fast_response(user_id), "tier": "", "medal": ""},
        # "profile_complete" is filled in by with_profile_complete() —
        # the caller already computes completeness for other purposes
        # (the progress bar on /profile), so there's no point computing
        # it again here.
        {"key": "profile_complete", "icon": "icon-sparkle", "unlocked": False, "tier": "", "medal": ""},
    ]

    views_badge = {"key": "views", "icon": "icon-eye", "unlocked": False, "tier": None, "medal": ""}
    view_count = _view_count(user_id)
    for threshold, tier in VIEW_MILESTONES:
        if view_count >= threshold:
            views_badge = {"key": "views", "icon": "icon-eye", "unlocked": True, "tier": tier, "medal": tier, "threshold": threshold}
            break
    badges.append(views_badge)

    years = _years_on_site(user_id)
    anniversary_badge = {
        "key": "anniversary", "icon": "icon-cake", "unlocked": years >= 1,
        "tier": str(years) if years >= 1 else "", "medal": _anniversary_medal(years), "years": years,
    }
    badges.append(anniversary_badge)

    return badges


# Importance order for showing "top 3 badges" on a search-result card
# (see app/routers/search_people_routes.py) — medal tiers (rarer =
# higher) come first, then the binary badges by how meaningful they
# feel from an outsider's point of view. "profile_complete" is
# deliberately left out here: computing profile completeness needs the
# role profile/tags/links loaded too, which would mean an extra set of
# queries per card in a results list — not worth it just to decide
# whether to show a checkmark badge.
_MEDAL_WEIGHT = {"platinum": 4, "gold": 3, "silver": 2, "bronze": 1, "": 0}
_KEY_WEIGHT = {"referral": 5, "views": 4, "anniversary": 3, "fast_response": 2, "contact": 1, "listing": 1}


def top_badges(user_id: int, limit: int = 3) -> list[dict]:
    """The `limit` most noteworthy UNLOCKED badges for this user, for
    compact display (e.g. a search-result card) — highest medal tier
    first, then the more "impressive" badge types."""
    badges = [b for b in get_user_badges(user_id) if b["unlocked"]]
    badges.sort(key=lambda b: (_MEDAL_WEIGHT.get(b.get("medal") or "", 0), _KEY_WEIGHT.get(b["key"], 0)), reverse=True)
    return badges[:limit]


def with_profile_complete(badges: list[dict], completeness_percent: int) -> list[dict]:
    """Fills in the 'profile 100%' badge — completeness is already computed in profile_routes.py."""
    for b in badges:
        if b["key"] == "profile_complete":
            b["unlocked"] = completeness_percent >= 100
    return badges


def check_and_notify_new_badges(user_id: int, base_url: str) -> None:
    """
    Compares the current badges with what is already recorded in
    user_badges and, for each new one, writes the row and sends a
    notification email. Called (via BackgroundTask, so as not to delay
    the response) after actions that could unlock a badge — see the
    call sites in profile_routes.py, listings_routes.py and
    messages_routes.py.

    Deliberately does not receive a ready-made completeness value (it
    computes it again in here) — this way the function can be called
    from anywhere without needing everything recalculated manually
    beforehand.
    """
    from app.routers.profile_routes import (
        get_singer_profile, get_conductor_profile, get_composer_tags,
        get_audio_links, get_social_links, compute_profile_completeness,
    )

    user = fetch_one("SELECT * FROM users WHERE id = :id", {"id": user_id})
    if not user:
        return

    singer_profile = get_singer_profile(user_id) if user["role"] == "singer" else None
    conductor_profile = get_conductor_profile(user_id) if user["role"] == "conductor" else None
    composer_tags = get_composer_tags(user_id) if user["role"] == "singer" else []
    audio_links = get_audio_links(user_id) if user["role"] == "singer" else []
    social_links = get_social_links(user_id)
    role_profile = singer_profile if user["role"] == "singer" else conductor_profile
    completeness = compute_profile_completeness(user, role_profile, composer_tags, audio_links, social_links)

    badges = with_profile_complete(get_user_badges(user_id), completeness["percent"])

    already = fetch_all(
        "SELECT badge_key, tier FROM user_badges WHERE user_id = :id", {"id": user_id}
    )
    already_set = {(r["badge_key"], r["tier"]) for r in already}

    for b in badges:
        if not b["unlocked"]:
            continue
        tier = b.get("tier") or ""
        if (b["key"], tier) in already_set:
            continue

        execute(
            """
            INSERT INTO user_badges (user_id, badge_key, tier, notified_at)
            VALUES (:user_id, :badge_key, :tier, now())
            ON CONFLICT (user_id, badge_key, tier) DO NOTHING
            """,
            {"user_id": user_id, "badge_key": b["key"], "tier": tier},
        )

        profile_url = f"{base_url.rstrip('/')}/profile"
        badge_name_de, badge_name_en = _badge_names(b)
        safe_name = html_module.escape(user["full_name"])
        html = f"""
            <p>Hallo {safe_name},</p>
            <p>Du hast eine neue Auszeichnung freigeschaltet: <strong>{badge_name_de}</strong></p>
            <p><a href="{profile_url}">{profile_url}</a></p>
            <hr>
            <p>(EN) You've unlocked a new badge: <strong>{badge_name_en}</strong><br>
            <a href="{profile_url}">{profile_url}</a></p>
        """
        send_email(user["email"], "Neue Auszeichnung freigeschaltet — VokalBoard", html)


def _badge_names(b: dict) -> tuple[str, str]:
    names = {
        "referral": ("Botschafter(in)", "Ambassador"),
        "listing": ("Erste Anzeige", "First listing"),
        "contact": ("Kontaktfreudig", "Reached out"),
        "fast_response": ("Schnelle Antwort", "Fast response"),
        "profile_complete": ("Profil komplett", "Complete profile"),
        "views": ("Gefragt", "In demand"),
        "anniversary": ("Jahrestag", "Anniversary"),
    }
    de, en = names.get(b["key"], (b["key"], b["key"]))
    if b["key"] == "views" and b.get("threshold"):
        de += f" ({b['threshold']}+)"
        en += f" ({b['threshold']}+)"
    if b["key"] == "anniversary" and b.get("years"):
        de += f" ({b['years']} {'Jahr' if b['years'] == 1 else 'Jahre'})"
        en += f" ({b['years']} {'year' if b['years'] == 1 else 'years'})"
    return de, en

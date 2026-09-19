"""P2 cluster (19/09/2026) — a singer's own repertoire ("works"), shown
on their public profile split into two card groups: solo vs. choir.
Decided with Daniel via AskUserQuestion: a brand-new table
(singer_works, see db/schema.sql), separate from listings.repertoire
(a job-posting field, not a personal portfolio) and from
singer_audio_links (a bare, untagged URL list).

Business logic lives here, not in the router (CLAUDE.md section 4,
"Fat Routers Proibidos") — app/routers/profile_routes.py only receives
the form, calls these functions, and renders the template.
"""
from app.database import fetch_all, fetch_one, execute

MAX_WORKS = 12
MAX_TITLE_LENGTH = 150
MAX_COMPOSER_LENGTH = 150
CATEGORIES = ("solo", "choir")


def _clean_url(raw: str) -> str | None:
    url = (raw or "").strip()
    if not url:
        return None
    if not (url.startswith("http://") or url.startswith("https://")):
        return None
    return url[:500]


def get_works(user_id: int) -> list[dict]:
    return fetch_all(
        """
        SELECT id, title, composer, category, video_url, audio_url, sort_order
        FROM singer_works
        WHERE user_id = :user_id
        ORDER BY sort_order, created_at
        """,
        {"user_id": user_id},
    )


def get_works_by_category(user_id: int) -> dict[str, list[dict]]:
    """Used by public_profile.html to render the two card groups."""
    works = get_works(user_id)
    return {
        "solo": [w for w in works if w["category"] == "solo"],
        "choir": [w for w in works if w["category"] == "choir"],
    }


def count_works(user_id: int) -> int:
    row = fetch_one("SELECT count(*) AS n FROM singer_works WHERE user_id = :user_id", {"user_id": user_id})
    return row["n"] if row else 0


class WorkValidationError(ValueError):
    pass


def add_work(user_id: int, title: str, composer: str, category: str, video_url: str, audio_url: str) -> None:
    title = (title or "").strip()[:MAX_TITLE_LENGTH]
    if not title:
        raise WorkValidationError("title_required")
    if category not in CATEGORIES:
        raise WorkValidationError("invalid_category")
    if count_works(user_id) >= MAX_WORKS:
        raise WorkValidationError("max_works_reached")

    execute(
        """
        INSERT INTO singer_works (user_id, title, composer, category, video_url, audio_url, sort_order)
        VALUES (:user_id, :title, :composer, :category, :video_url, :audio_url,
                COALESCE((SELECT max(sort_order) + 1 FROM singer_works WHERE user_id = :user_id), 0))
        """,
        {
            "user_id": user_id,
            "title": title,
            "composer": (composer or "").strip()[:MAX_COMPOSER_LENGTH] or None,
            "category": category,
            "video_url": _clean_url(video_url),
            "audio_url": _clean_url(audio_url),
        },
    )


def delete_work(user_id: int, work_id: int) -> None:
    # Scoped by user_id too, not just id — a user can never delete
    # someone else's work row via a crafted form post.
    execute("DELETE FROM singer_works WHERE id = :id AND user_id = :user_id", {"id": work_id, "user_id": user_id})

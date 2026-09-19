"""
Central de Notificações (19/09/2026) — designed together with Daniel
via AskUserQuestion before coding (see AI_CHANGELOG.md for the design
conversation). A real list of discrete, individually-readable events
("aconteceu algo, ou alguma ação é necessária, aí aparece ali" —
Daniel's own words) — NOT the same thing as the live pending-count nav
badges already on the site (unread messages, pending invitations,
pending evaluations, pending invoice actions — see app/render.py).
Those stay exactly as they are; this is additive.

Scope agreed with Daniel — four categories:
  - Social/Match: invitation received, candidatura received, invite
    accepted/declined, Match formed.
  - Notas/Loja/Financeiro: Notas credited, Loja item redeemed.
  - New messages.
  - Profile pending items: deliberately NOT a stored row (a discrete
    row would need to be deleted the instant the profile becomes
    complete, which is more bookkeeping than computing it live) — see
    profile_incomplete_notification() below, which reuses
    app.mascot_moments' own completeness check so the two never
    disagree, and is merged into the list at read time instead.

Retention (Daniel: "mesmo espírito do Zero-Storage"): read
notifications older than 30 days are purged by app/retention_worker.py.
Unread notifications are NEVER auto-deleted, no matter how old.
"""
import json

from app.database import fetch_all, fetch_one, execute, execute_returning
from app.mascot_moments import profile_incomplete

NOTIFICATIONS_PAGE_SIZE = 20


def create_notification(
    user_id: int, type_: str, title_key: str,
    title_params: dict | None = None, link_url: str | None = None, icon: str = "icon-bell",
) -> None:
    """
    Inserts one notification row. `title_key` is an app.i18n key,
    rendered with `title_params` at display time (see
    render_notification_title() below) — never pre-rendered into a
    fixed string, so it still translates correctly if the viewer's
    language changes after the notification was created.
    """
    execute(
        """
        INSERT INTO notifications (user_id, type, title_key, title_params, link_url, icon)
        VALUES (:user_id, :type, :title_key, :title_params, :link_url, :icon)
        """,
        {
            "user_id": user_id,
            "type": type_,
            "title_key": title_key,
            "title_params": json.dumps(title_params) if title_params else None,
            "link_url": link_url,
            "icon": icon,
        },
    )


def get_recent_notifications(user_id: int, limit: int = NOTIFICATIONS_PAGE_SIZE) -> list[dict]:
    return fetch_all(
        """
        SELECT id, type, title_key, title_params, link_url, icon, read_at, created_at
        FROM notifications WHERE user_id = :id ORDER BY created_at DESC LIMIT :limit
        """,
        {"id": user_id, "limit": limit},
    )


def get_unread_count(user_id: int) -> int:
    row = fetch_one("SELECT count(*) AS n FROM notifications WHERE user_id = :id AND read_at IS NULL", {"id": user_id})
    return row["n"] if row else 0


def mark_as_read(user_id: int, notification_id: int) -> str | None:
    """
    Marks one notification read and returns its link_url (or None) —
    the whole point of "opening a notification" is "mark it read, then
    go where it points" (see notification_center_routes.py's
    open_notification()). Works whether it was already read or not, so
    re-clicking an old notification still navigates correctly.
    """
    row = execute_returning(
        "UPDATE notifications SET read_at = now() WHERE id = :id AND user_id = :user_id AND read_at IS NULL RETURNING link_url",
        {"id": notification_id, "user_id": user_id},
    )
    if row:
        return row["link_url"]
    existing = fetch_one(
        "SELECT link_url FROM notifications WHERE id = :id AND user_id = :user_id",
        {"id": notification_id, "user_id": user_id},
    )
    return existing["link_url"] if existing else None


def mark_all_as_read(user_id: int) -> None:
    execute("UPDATE notifications SET read_at = now() WHERE user_id = :id AND read_at IS NULL", {"id": user_id})


def render_notification_title(notification: dict, translate_fn) -> str:
    """
    Renders a notification's title_key through the viewer's current
    language and fills in title_params — the same `{placeholder}` /
    `.replace()` pattern already used by the mascot toasts (see
    base.html), just centralized here since a notification can carry
    more than one param (e.g. Notas credited: {amount} and {reason}).
    `translate_fn` is the request-scoped `t()` from app/render.py, so
    this never needs to import app.i18n directly.
    """
    text = translate_fn(notification["title_key"])
    params = notification.get("title_params") or {}
    if isinstance(params, str):
        params = json.loads(params)
    for key, value in params.items():
        text = text.replace("{" + key + "}", str(value))
    return text


def profile_incomplete_notification(user: dict) -> dict | None:
    """
    The one synthetic (never stored) item — see this module's
    docstring. Shaped exactly like a real notification row so the
    template doesn't need a special case, plus `"synthetic": True` so
    the "mark as read" link isn't shown for it (there's nothing to
    mark — it just stops appearing once the profile is complete).
    """
    if not profile_incomplete(user):
        return None
    return {
        "id": None,
        "type": "profile_incomplete",
        "title_key": "notification_profile_incomplete",
        "title_params": {},
        "link_url": "/profile",
        "icon": "icon-profile",
        "read_at": None,
        "created_at": None,
        "synthetic": True,
    }

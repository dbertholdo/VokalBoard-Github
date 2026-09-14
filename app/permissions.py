"""
Administrative access levels (see users.role_level in db/schema.sql):

    0 = common      — regular user, no access to /admin at all
    1 = moderator   — only the reports/blocks queue (read + act on
                       reports), no touching users or anything
                       financial
    2 = admin       — everything the /admin panel already did before
                       levels existed: users, posts, analytics
    3 = god mode    — the only level that sees the Red Zone
                       (Capitalism Mode, subscription price,
                       financial panel) — see
                       app/routers/financial_routes.py

Each level includes the permissions of the levels below it (it's a
scale, not separate categories).
"""
from fastapi import Request

from app.auth import get_current_user, verify_password
from app.database import execute, fetch_one
from app.client_ip import get_client_ip

LEVEL_COMMON = 0
LEVEL_MODERATOR = 1
LEVEL_ADMIN = 2
LEVEL_GOD = 3


def require_level(request: Request, min_level: int) -> dict | None:
    """Returns the logged-in user if their level is >= min_level, else None.

    Deliberately returns only None (doesn't raise an exception,
    doesn't distinguish "not logged in" from "insufficient level") —
    each route decides what to do, usually redirecting to "/" with no
    specific message, the same pattern the original require_admin
    already used.
    """
    user = get_current_user(request)
    if not user or (user.get("role_level") or 0) < min_level:
        return None
    return user


def sync_is_admin_flag(user_id: int, new_role_level: int) -> None:
    """Keeps the legacy is_admin column in sync with role_level.

    is_admin still exists (old screens, the README, require_admin
    itself for level 2) — whenever role_level changes through here,
    is_admin follows along: True for level >= 2, False below that.
    """
    execute(
        "UPDATE users SET is_admin = :is_admin WHERE id = :id",
        {"is_admin": new_role_level >= LEVEL_ADMIN, "id": user_id},
    )


def reauthenticate(request: Request, user: dict, password: str) -> bool:
    """Confirms the current password again (step-up auth), the same
    pattern already used in /profile/delete-account. Used before any
    action inside the Red Zone — turning Capitalism Mode on/off,
    changing the price — even if the person is already logged in as
    god mode.
    """
    row = fetch_one("SELECT password_hash FROM users WHERE id = :id", {"id": user["id"]})
    if not row:
        return False
    return verify_password(password, row["password_hash"])


def log_audit_action(request: Request, actor: dict | None, action: str, details: str = "") -> None:
    """Writes a row to audit_log — called after every Red Zone action,
    whether the reauthentication succeeded or failed (so a failed
    password attempt also gets recorded).
    """
    execute(
        """
        INSERT INTO audit_log (actor_user_id, action, details, ip_address)
        VALUES (:actor_id, :action, :details, :ip)
        """,
        {
            "actor_id": actor["id"] if actor else None,
            "action": action,
            "details": details,
            "ip": get_client_ip(request),
        },
    )

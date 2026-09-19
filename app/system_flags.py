"""
Small on/off toggles in system_settings that aren't Red Zone / financial
(those stay in app/financial_settings.py, which requires password
re-auth to flip — see CLAUDE.md seção 2.4). This module is for flags
any regular Admin (LEVEL_GOD, no re-auth) can flip from /admin.

P3.E: compatibility_score_visible — whether the "% compatibilidade"
signal (see app/compatibility.py) is shown to end users at all, or
stays purely an internal sort key. Starts OFF (see
db/migrations/2026-09-19_p3e_structured_fees.sql) — Daniel wants to
discuss the actual display before turning it on.
"""
from app.database import fetch_all, execute

_TRUE_VALUES = {"true", "1", "yes"}


def is_compatibility_score_visible() -> bool:
    rows = fetch_all(
        "SELECT value FROM system_settings WHERE key = 'compatibility_score_visible'"
    )
    if not rows:
        return False
    return (rows[0]["value"] or "").strip().lower() in _TRUE_VALUES


def set_compatibility_score_visible(enabled: bool, admin_user_id: int) -> None:
    execute(
        """
        INSERT INTO system_settings (key, value, updated_by_user_id, updated_at)
        VALUES ('compatibility_score_visible', :value, :admin_id, now())
        ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value, updated_by_user_id = EXCLUDED.updated_by_user_id, updated_at = now()
        """,
        {"value": "true" if enabled else "false", "admin_id": admin_user_id},
    )

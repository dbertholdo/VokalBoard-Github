"""
Reads the Red Zone settings (system_settings) — kept separate from
app/routers/financial_routes.py on purpose, because app/render.py also
needs to read the Capitalism Mode state (to decide whether to show the
subscription banner to everyone) without importing an entire router.

While Capitalism Mode is off (the default), none of this shows up to
anyone who isn't in god mode — no banner, no price mentioned anywhere
on the site.
"""
from app.database import fetch_all

_TRUE_VALUES = {"true", "1", "yes"}


def get_settings() -> dict[str, str]:
    rows = fetch_all("SELECT key, value FROM system_settings")
    return {r["key"]: r["value"] for r in rows}


def is_capitalismo_mode_enabled() -> bool:
    rows = fetch_all(
        "SELECT value FROM system_settings WHERE key = 'capitalismo_mode_enabled'"
    )
    if not rows:
        return False
    return (rows[0]["value"] or "").strip().lower() in _TRUE_VALUES


def get_subscription_prices_cents() -> dict[str, int]:
    settings = get_settings()
    return {
        "EUR": int(settings.get("subscription_price_eur_cents") or 590),
        "CHF": int(settings.get("subscription_price_chf_cents") or 690),
    }

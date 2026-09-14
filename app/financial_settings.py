"""
Leitura das configurações da Zona Vermelha (system_settings) — separado
de app/routers/financial_routes.py de propósito, porque app/render.py
também precisa ler o estado do Modo Capitalismo (pra decidir se mostra
o banner de assinatura pra todo mundo) sem importar um router inteiro.

Enquanto o Modo Capitalismo estiver desligado (o padrão), nada disso
aparece pra ninguém que não seja god mode — nem o banner, nem menção a
preço em lugar nenhum do site.
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

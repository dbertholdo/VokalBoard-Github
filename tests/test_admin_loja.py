"""P5 Loja — painel de Admin (18/09/2026): ativar/desativar item do
catálogo, histórico geral da loja, extrato de Notas na página de
detalhe do usuário. Ver app/shop_catalog.py e
app/routers/admin_routes.py."""
from decimal import Decimal

from app.database import execute, execute_returning, fetch_one
from app.shop_catalog import (
    get_active_catalog,
    get_redeemable_item,
    toggle_catalog_item_active,
    is_shop_reason,
)
from tests.test_security import extract_csrf, login, register_test_user


def _make_admin(client):
    user_id, email, password = register_test_user(client, full_name="Loja Admin Test")
    execute("UPDATE users SET email_verified = TRUE, role_level = 2 WHERE id = :id", {"id": user_id})
    login(client, email, password)
    return user_id


def _profile_highlight_item_id() -> int:
    row = fetch_one("SELECT id FROM shop_catalog_items WHERE item_key = 'profile_highlight_7d'")
    return row["id"]


def _reset_profile_highlight_active():
    execute(
        "UPDATE shop_catalog_items SET active = TRUE WHERE item_key = 'profile_highlight_7d'"
    )


def test_is_shop_reason_matches_redeem_and_urgency_purchase_only():
    assert is_shop_reason("redeem_profile_highlight_7d") is True
    assert is_shop_reason("urgency_purchase") is True
    assert is_shop_reason("referral_bonus") is False
    assert is_shop_reason("listing_posted") is False
    assert is_shop_reason("urgency_match_reward") is False


def test_toggle_catalog_item_active_flips_state(client):
    _reset_profile_highlight_active()
    item_id = _profile_highlight_item_id()

    assert toggle_catalog_item_active(item_id) is False  # estava ativo -> desativado
    assert get_redeemable_item("profile_highlight_7d") is None
    assert all(i["key"] != "profile_highlight_7d" for i in get_active_catalog())

    assert toggle_catalog_item_active(item_id) is True  # desativado -> ativo de novo
    assert get_redeemable_item("profile_highlight_7d") is not None
    _reset_profile_highlight_active()


def test_toggle_catalog_item_active_unknown_id_returns_none(client):
    assert toggle_catalog_item_active(999999) is None


def test_admin_loja_page_lists_catalog_and_requires_admin(client):
    # Sem estar logado como admin: redireciona pra fora.
    resp = client.get("/admin/loja", follow_redirects=False)
    assert resp.status_code in (303, 401, 403)

    _make_admin(client)
    resp = client.get("/admin/loja")
    assert resp.status_code == 200
    assert "profile_highlight_7d" in resp.text


def test_admin_can_toggle_catalog_item_via_route(client):
    _reset_profile_highlight_active()
    _make_admin(client)
    item_id = _profile_highlight_item_id()

    page = client.get("/admin/loja")
    token = extract_csrf(page.text)
    resp = client.post(
        f"/admin/loja/catalog/{item_id}/toggle-active",
        data={"csrf_token": token},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    row = fetch_one("SELECT active FROM shop_catalog_items WHERE id = :id", {"id": item_id})
    assert row["active"] is False
    _reset_profile_highlight_active()


def test_deactivated_item_blocks_new_redemptions_but_not_the_route_itself(client):
    """Desativar só bloqueia NOVOS resgates — não mexe em quem já
    resgatou antes (decisão do Daniel, 18/09/2026)."""
    _reset_profile_highlight_active()
    user_id, email, password = register_test_user(client, full_name="Loja Redeem Test")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    execute("DELETE FROM credit_ledger WHERE user_id = :id", {"id": user_id})
    execute(
        "INSERT INTO credit_ledger (user_id, delta, reason) VALUES (:id, 5, 'sectest_seed')",
        {"id": user_id},
    )
    login(client, email, password)

    # Extrai o csrf ANTES de desativar o item — depois de desativado o
    # catálogo fica vazio e a página /notas não tem mais nenhum
    # <form>/token nela (o campo csrf só existe dentro do loop de
    # itens do catálogo).
    page = client.get("/notas")
    token = extract_csrf(page.text)

    item_id = _profile_highlight_item_id()
    toggle_catalog_item_active(item_id)  # desativa

    resp = client.post(
        "/notas/redeem",
        data={"item_key": "profile_highlight_7d", "csrf_token": token},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "error=notas_item_not_found" in resp.headers["location"]

    # Nada foi debitado.
    balance = fetch_one(
        "SELECT COALESCE(SUM(delta), 0) AS n FROM credit_ledger WHERE user_id = :id", {"id": user_id}
    )["n"]
    assert balance == Decimal("5")

    _reset_profile_highlight_active()


def test_shop_history_shows_up_in_admin_loja_page(client):
    _reset_profile_highlight_active()
    user_id, email, password = register_test_user(client, full_name="Loja History Test")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    execute("DELETE FROM credit_ledger WHERE user_id = :id", {"id": user_id})
    execute(
        "INSERT INTO credit_ledger (user_id, delta, reason) VALUES (:id, 5, 'sectest_seed')",
        {"id": user_id},
    )
    login(client, email, password)

    page = client.get("/notas")
    token = extract_csrf(page.text)
    resp = client.post(
        "/notas/redeem",
        data={"item_key": "profile_highlight_7d", "csrf_token": token},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "redeemed=profile_highlight_7d" in resp.headers["location"]

    _make_admin(client)
    admin_page = client.get("/admin/loja")
    assert "redeem_profile_highlight_7d" in admin_page.text
    assert "Loja History Test" in admin_page.text


def test_admin_user_detail_shows_notas_extract(client):
    user_id, email, password = register_test_user(client, full_name="Loja Extrato Test")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    execute("DELETE FROM credit_ledger WHERE user_id = :id", {"id": user_id})
    execute(
        "INSERT INTO credit_ledger (user_id, delta, reason) VALUES (:id, 2, 'referral_bonus')",
        {"id": user_id},
    )

    _make_admin(client)
    resp = client.get(f"/admin/users/{user_id}")
    assert resp.status_code == 200
    assert "referral_bonus" in resp.text

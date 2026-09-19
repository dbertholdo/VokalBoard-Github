"""P5 Loja — CRUD de itens pelo Admin + "comprar Notas que faltam"
(18/09/2026). Ver app/shop_catalog.py, app/routers/admin_routes.py e
app/routers/notas_routes.py."""
from decimal import Decimal

from app.database import execute, fetch_one
from app.shop_catalog import (
    create_catalog_item,
    update_catalog_item,
    get_active_catalog,
    get_redeemable_item,
    get_catalog_titles_by_key,
    list_all_catalog_items,
    ITEM_EFFECTS,
    ALLOWED_ICONS,
)
from tests.test_security import extract_csrf, login, register_test_user


def _make_admin(client):
    user_id, email, password = register_test_user(client, full_name="Loja CRUD Admin")
    execute("UPDATE users SET email_verified = TRUE, role_level = 2 WHERE id = :id", {"id": user_id})
    login(client, email, password)
    return user_id


def _cleanup(item_id: int):
    execute("DELETE FROM credit_ledger WHERE reference_id = :id AND reason LIKE 'redeem_%'", {"id": item_id})
    execute("DELETE FROM shop_catalog_items WHERE id = :id", {"id": item_id})


def test_create_catalog_item_generates_unique_slug_key():
    created = create_catalog_item("Convite especial!", "Acesso a um grupo fechado.", Decimal("2"), "icon-star")
    try:
        assert created["item_key"] == "convite_especial"
        row = fetch_one("SELECT * FROM shop_catalog_items WHERE id = :id", {"id": created["id"]})
        assert row["title"] == "Convite especial!"
        assert row["cost"] == Decimal("2")
        assert row["active"] is True
        assert row["icon"] == "icon-star"
    finally:
        _cleanup(created["id"])


def test_create_catalog_item_key_collision_gets_numeric_suffix():
    first = create_catalog_item("Mesmo Titulo", "desc 1", Decimal("1"), "icon-gift")
    second = create_catalog_item("Mesmo Titulo", "desc 2", Decimal("1"), "icon-gift")
    try:
        assert first["item_key"] != second["item_key"]
        assert second["item_key"].startswith(first["item_key"])
    finally:
        _cleanup(first["id"])
        _cleanup(second["id"])


def test_create_catalog_item_rejects_invalid_icon_with_default():
    created = create_catalog_item("Item icone invalido", "desc", Decimal("1"), "icon-does-not-exist")
    try:
        row = fetch_one("SELECT icon FROM shop_catalog_items WHERE id = :id", {"id": created["id"]})
        assert row["icon"] in ALLOWED_ICONS
    finally:
        _cleanup(created["id"])


def test_new_item_has_no_code_effect_and_is_a_generic_voucher():
    created = create_catalog_item("Voucher generico", "so debita notas", Decimal("1"), "icon-gift")
    try:
        assert created["item_key"] not in ITEM_EFFECTS
        item = get_redeemable_item(created["item_key"])
        assert item is not None
        assert "days" not in item  # sem efeito de código nenhum
    finally:
        _cleanup(created["id"])


def test_update_catalog_item_overwrites_title_and_description():
    created = create_catalog_item("Titulo original", "desc original", Decimal("1"), "icon-gift")
    try:
        ok = update_catalog_item(created["id"], "Titulo novo", "desc nova", Decimal("4"), "icon-star")
        assert ok is True
        row = fetch_one("SELECT * FROM shop_catalog_items WHERE id = :id", {"id": created["id"]})
        assert row["title"] == "Titulo novo"
        assert row["description"] == "desc nova"
        assert row["cost"] == Decimal("4")
        assert row["icon"] == "icon-star"
    finally:
        _cleanup(created["id"])


def test_update_catalog_item_unknown_id_returns_false():
    assert update_catalog_item(999999, "x", "y", Decimal("1"), "icon-gift") is False


def test_active_catalog_includes_generic_vouchers():
    created = create_catalog_item("Voucher no catalogo", "desc", Decimal("1"), "icon-gift")
    try:
        keys = [i["key"] for i in get_active_catalog()]
        assert created["item_key"] in keys
    finally:
        _cleanup(created["id"])


def test_get_catalog_titles_by_key_includes_inactive_items():
    created = create_catalog_item("Item pro extrato", "desc", Decimal("1"), "icon-gift")
    try:
        execute("UPDATE shop_catalog_items SET active = FALSE WHERE id = :id", {"id": created["id"]})
        titles = get_catalog_titles_by_key()
        assert titles.get(created["item_key"]) == "Item pro extrato"
    finally:
        _cleanup(created["id"])


def test_admin_can_create_item_via_route(client):
    _make_admin(client)
    page = client.get("/admin/loja")
    token = extract_csrf(page.text)

    resp = client.post(
        "/admin/loja/catalog/new",
        data={
            "csrf_token": token,
            "title": "Item via rota HTTP",
            "description": "Criado pelo teste HTTP.",
            "cost": "3,50",
            "icon": "icon-trophy",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "created=1" in resp.headers["location"]

    row = fetch_one("SELECT * FROM shop_catalog_items WHERE title = 'Item via rota HTTP'")
    assert row is not None
    assert row["cost"] == Decimal("3.50")
    _cleanup(row["id"])


def test_admin_create_item_rejects_missing_fields(client):
    _make_admin(client)
    page = client.get("/admin/loja")
    token = extract_csrf(page.text)

    # "   " (espaços) em vez de "" — Starlette trata um campo de Form
    # totalmente vazio como AUSENTE (422 antes mesmo de chegar na
    # rota), então pra testar a validação de "só espaço em branco"
    # (item.strip() vazio) precisa mandar algo, só que sem conteúdo.
    resp = client.post(
        "/admin/loja/catalog/new",
        data={"csrf_token": token, "title": "   ", "description": "   ", "cost": "abc", "icon": "icon-gift"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "error=invalid_item" in resp.headers["location"]


def test_admin_can_edit_item_via_route(client):
    created = create_catalog_item("Item pra editar", "desc antiga", Decimal("1"), "icon-gift")
    try:
        _make_admin(client)
        page = client.get("/admin/loja")
        token = extract_csrf(page.text)

        resp = client.post(
            f"/admin/loja/catalog/{created['id']}/edit",
            data={
                "csrf_token": token,
                "title": "Item editado",
                "description": "desc editada",
                "cost": "7",
                "icon": "icon-crown",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "updated=1" in resp.headers["location"]

        row = fetch_one("SELECT * FROM shop_catalog_items WHERE id = :id", {"id": created["id"]})
        assert row["title"] == "Item editado"
        assert row["cost"] == Decimal("7")
        assert row["icon"] == "icon-crown"
    finally:
        _cleanup(created["id"])


def test_notas_page_shows_buy_missing_link_when_balance_insufficient(client):
    user_id, email, password = register_test_user(client, full_name="Loja Shortfall Test")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    execute("DELETE FROM credit_ledger WHERE user_id = :id", {"id": user_id})
    execute(
        "INSERT INTO credit_ledger (user_id, delta, reason) VALUES (:id, 1, 'sectest_seed')",
        {"id": user_id},
    )
    login(client, email, password)

    page = client.get("/notas")
    assert page.status_code == 200
    # Saldo (1) é menor que o custo do item original (3) — precisa
    # oferecer o link de comprar a diferença, não um botão desabilitado.
    assert "/notas/comprar-notas?faltam=2" in page.text


def test_comprar_notas_stub_shows_missing_amount(client):
    user_id, email, password = register_test_user(client, full_name="Loja Stub Test")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    login(client, email, password)

    resp = client.get("/notas/comprar-notas?faltam=8")
    assert resp.status_code == 200
    assert "8" in resp.text


def test_comprar_notas_stub_requires_login(client):
    resp = client.get("/notas/comprar-notas?faltam=8", follow_redirects=False)
    assert resp.status_code == 303
    assert "/login" in resp.headers["location"]

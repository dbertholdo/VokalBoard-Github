"""Ad-hoc admin grant (/financeiro/conceder) — P6 close-out
(19/09/2026). Daniel's request ("Make p6 done"), scoped via
AskUserQuestion: an Admin (God Mode) can credit/debit a specific
user's Notas balance, or issue a shop catalog item to them directly
(bypassing self-purchase), each with a mandatory justification,
Red Zone gated (password reauth + audit log). See
app/routers/financial_routes.py (financeiro_conceder*) and
app/shop_catalog.py (grant_catalog_item_to_user).
"""
from decimal import Decimal

import pytest

from app.database import execute, fetch_one
from app.notas_wallet import get_credit_balance
from tests.test_security import DEFAULT_PASSWORD, extract_csrf, login, register_test_user


def _promote(user_id: int, level: int):
    execute("UPDATE users SET role_level = :lvl, email_verified = TRUE WHERE id = :id", {"lvl": level, "id": user_id})


@pytest.fixture()
def god_user(client):
    user_id, email, password = register_test_user(client, full_name="Grant God Test")
    _promote(user_id, 3)
    login(client, email, password)
    return {"id": user_id, "email": email, "password": password}


@pytest.fixture(autouse=True)
def _cleanup_ledger_test_rows():
    max_id = fetch_one("SELECT COALESCE(MAX(id), 0) AS n FROM credit_ledger")["n"]
    yield
    execute("DELETE FROM credit_ledger WHERE id > :max_id", {"max_id": max_id})


def _get_csrf(client):
    r = client.get("/financeiro/conceder")
    return extract_csrf(r.text)


def test_non_god_mode_cannot_reach_conceder(client):
    user_id, email, password = register_test_user(client, full_name="Grant Level2 Test")
    _promote(user_id, 2)
    login(client, email, password)
    resp = client.get("/financeiro/conceder", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


def test_search_finds_user_by_name(client, god_user):
    target_id, _, _ = register_test_user(client, full_name="Findable Grant Target")
    login(client, god_user["email"], god_user["password"])
    resp = client.get("/financeiro/conceder", params={"q": "Findable Grant Target"})
    assert "Findable Grant Target" in resp.text


def test_credit_notas_requires_reason_and_password(client, god_user):
    target_id, _, _ = register_test_user(client, full_name="Credit Grant Target")
    login(client, god_user["email"], god_user["password"])
    csrf_token = _get_csrf(client)

    # Wrong password — nothing credited.
    resp = client.post(
        "/financeiro/conceder/notas",
        data={
            "csrf_token": csrf_token, "target_user_id": target_id, "acao": "credit",
            "amount": "5", "reason": "Support compensation", "current_password": "wrong-password",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "error=senha_incorreta" in resp.headers["location"]
    assert get_credit_balance(target_id) == 0

    # Correct password, valid reason — credited.
    resp = client.post(
        "/financeiro/conceder/notas",
        data={
            "csrf_token": csrf_token, "target_user_id": target_id, "acao": "credit",
            "amount": "5", "reason": "Support compensation", "current_password": DEFAULT_PASSWORD,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "saved=1" in resp.headers["location"]
    assert get_credit_balance(target_id) == Decimal("5")

    ledger_row = fetch_one(
        "SELECT reason, admin_note FROM credit_ledger WHERE user_id = :id AND reason = 'admin_grant_credit'",
        {"id": target_id},
    )
    assert ledger_row["admin_note"] == "Support compensation"


def test_debit_notas_insufficient_balance_rejected(client, god_user):
    target_id, _, _ = register_test_user(client, full_name="Debit Grant Target")
    login(client, god_user["email"], god_user["password"])
    csrf_token = _get_csrf(client)

    resp = client.post(
        "/financeiro/conceder/notas",
        data={
            "csrf_token": csrf_token, "target_user_id": target_id, "acao": "debit",
            "amount": "100", "reason": "Correcting a mistaken credit", "current_password": DEFAULT_PASSWORD,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "error=saldo_insuficiente" in resp.headers["location"]
    assert get_credit_balance(target_id) == 0


def test_short_reason_rejected(client, god_user):
    target_id, _, _ = register_test_user(client, full_name="Short Reason Target")
    login(client, god_user["email"], god_user["password"])
    csrf_token = _get_csrf(client)

    resp = client.post(
        "/financeiro/conceder/notas",
        data={
            "csrf_token": csrf_token, "target_user_id": target_id, "acao": "credit",
            "amount": "5", "reason": "hi", "current_password": DEFAULT_PASSWORD,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "error=dados_invalidos" in resp.headers["location"]
    assert get_credit_balance(target_id) == 0


def test_grant_shop_item_bypasses_balance(client, god_user):
    target_id, _, _ = register_test_user(client, full_name="Item Grant Target")
    login(client, god_user["email"], god_user["password"])
    csrf_token = _get_csrf(client)

    assert get_credit_balance(target_id) == 0

    resp = client.post(
        "/financeiro/conceder/item",
        data={
            "csrf_token": csrf_token, "target_user_id": target_id, "item_key": "profile_highlight_7d",
            "reason": "Comping a failed redemption", "current_password": DEFAULT_PASSWORD,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "saved=1" in resp.headers["location"]

    # Never touches the user's balance — it's a comp, not a purchase.
    assert get_credit_balance(target_id) == 0

    highlighted = fetch_one("SELECT profile_highlighted_until FROM users WHERE id = :id", {"id": target_id})
    assert highlighted["profile_highlighted_until"] is not None

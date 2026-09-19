"""Extrato Geral (18/09/2026) — Daniel's request: "We should have at
Financeiro a way to have an Extrato of the whole Finances of the
platform. Choose from what's going out what's coming in both like
functions of a normal bank. Choose what to see and what to export."

Scope decided via AskUserQuestion (all "Recommended"): money in =
subscription revenue only (non-refunded); a new dedicated screen
(/financeiro/extrato-geral), separate from /financeiro/painel
(expenses dashboard) and /financeiro/extrato (bank-statement import);
filters are period + type (in/out) + expense category, and every
export matches exactly what the filters show on screen. See
app/routers/financial_routes.py::_build_extrato_geral().
"""
from datetime import date

import pytest

from app.database import execute, execute_returning, fetch_one
from tests.test_security import extract_csrf, login, register_test_user


def _promote(user_id: int, level: int):
    execute("UPDATE users SET role_level = :lvl, email_verified = TRUE WHERE id = :id", {"lvl": level, "id": user_id})


@pytest.fixture()
def god_user(client):
    user_id, email, password = register_test_user(client, full_name="Extrato Geral God Test")
    _promote(user_id, 3)
    login(client, email, password)
    return {"id": user_id, "email": email, "password": password}


@pytest.fixture(autouse=True)
def _cleanup_extrato_test_rows():
    max_ids = {
        t: (fetch_one(f"SELECT COALESCE(MAX(id), 0) AS n FROM {t}")["n"])
        for t in ("expenses", "subscriptions")
    }
    yield
    for t, max_id in max_ids.items():
        execute(f"DELETE FROM {t} WHERE id > :max_id", {"max_id": max_id})  # nosec B608 - t comes only from the fixed tuple above


def test_non_god_mode_cannot_reach_extrato_geral(client):
    user_id, email, password = register_test_user(client, full_name="Extrato Geral Level2 Test")
    _promote(user_id, 2)
    login(client, email, password)
    resp = client.get("/financeiro/extrato-geral", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


def test_extrato_geral_merges_expenses_and_subscriptions(client, god_user):
    r = client.get("/financeiro/painel")
    token = extract_csrf(r.text)
    client.post(
        "/financeiro/expenses",
        data={
            "csrf_token": token, "description": "Extrato Geral Hosting Bill", "amount": "15.00",
            "currency": "EUR", "category": "hosting", "expense_date": "2026-09-05",
        },
        follow_redirects=False,
    )

    target_id, _, _ = register_test_user(client, full_name="Extrato Geral Subscriber")
    execute_returning(
        """
        INSERT INTO subscriptions (user_id, price_paid_cents, currency, country, started_at)
        VALUES (:uid, 590, 'EUR', 'DE', '2026-09-06')
        RETURNING id
        """,
        {"uid": target_id},
    )

    login(client, god_user["email"], god_user["password"])
    page = client.get("/financeiro/extrato-geral")
    assert page.status_code == 200
    assert "Extrato Geral Hosting Bill" in page.text
    assert "Extrato Geral Subscriber" in page.text
    # Net = 5.90 (subscription) - 15.00 (expense) = -9.10.
    assert "9.1" in page.text or "9,1" in page.text


def test_extrato_geral_tipo_filter_isolates_in_or_out(client, god_user):
    r = client.get("/financeiro/painel")
    token = extract_csrf(r.text)
    client.post(
        "/financeiro/expenses",
        data={
            "csrf_token": token, "description": "Tipo Filter Expense", "amount": "9.00",
            "currency": "EUR", "category": "hosting", "expense_date": "2026-09-05",
        },
        follow_redirects=False,
    )
    target_id, _, _ = register_test_user(client, full_name="Tipo Filter Subscriber")
    execute_returning(
        """
        INSERT INTO subscriptions (user_id, price_paid_cents, currency, country, started_at)
        VALUES (:uid, 590, 'EUR', 'DE', '2026-09-06')
        RETURNING id
        """,
        {"uid": target_id},
    )

    login(client, god_user["email"], god_user["password"])

    only_out = client.get("/financeiro/extrato-geral", params={"tipo": "out"})
    assert "Tipo Filter Expense" in only_out.text
    assert "Tipo Filter Subscriber" not in only_out.text

    only_in = client.get("/financeiro/extrato-geral", params={"tipo": "in"})
    assert "Tipo Filter Subscriber" in only_in.text
    assert "Tipo Filter Expense" not in only_in.text


def test_extrato_geral_refunded_subscription_excluded_from_revenue(client, god_user):
    target_id, _, _ = register_test_user(client, full_name="Refunded Sub In Extrato")
    execute_returning(
        """
        INSERT INTO subscriptions (user_id, price_paid_cents, currency, country, started_at, refunded_at)
        VALUES (:uid, 590, 'EUR', 'DE', '2026-09-06', now())
        RETURNING id
        """,
        {"uid": target_id},
    )
    login(client, god_user["email"], god_user["password"])
    page = client.get("/financeiro/extrato-geral")
    assert "Refunded Sub In Extrato" not in page.text


def test_extrato_geral_exports(client, god_user):
    r = client.get("/financeiro/painel")
    token = extract_csrf(r.text)
    client.post(
        "/financeiro/expenses",
        data={
            "csrf_token": token, "description": "Export Test Expense", "amount": "3.00",
            "currency": "EUR", "category": "other", "expense_date": "2026-09-05",
        },
        follow_redirects=False,
    )
    login(client, god_user["email"], god_user["password"])

    csv_resp = client.get("/financeiro/extrato-geral/export.csv")
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    assert "Export Test Expense" in csv_resp.text

    xlsx_resp = client.get("/financeiro/extrato-geral/export.xlsx")
    assert xlsx_resp.status_code == 200
    assert "spreadsheetml" in xlsx_resp.headers["content-type"]

    pdf_resp = client.get("/financeiro/extrato-geral/export.pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"


def test_extrato_geral_category_filter_only_affects_expenses(client, god_user):
    r = client.get("/financeiro/painel")
    token = extract_csrf(r.text)
    client.post(
        "/financeiro/expenses",
        data={
            "csrf_token": token, "description": "Hosting Category Row", "amount": "4.00",
            "currency": "EUR", "category": "hosting", "expense_date": "2026-09-05",
        },
        follow_redirects=False,
    )
    client.post(
        "/financeiro/expenses",
        data={
            "csrf_token": token, "description": "Marketing Category Row", "amount": "6.00",
            "currency": "EUR", "category": "marketing", "expense_date": "2026-09-05",
        },
        follow_redirects=False,
    )
    login(client, god_user["email"], god_user["password"])
    filtered = client.get("/financeiro/extrato-geral", params={"categoria": "hosting"})
    assert "Hosting Category Row" in filtered.text
    assert "Marketing Category Row" not in filtered.text

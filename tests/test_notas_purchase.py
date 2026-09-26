"""Notas v2 — N5: buying Notas with Stripe (app/notas_purchase.py).
Webhooks are signed exactly like Stripe does (HMAC-SHA256 over
"timestamp.payload"), so the real signature check runs; only the
Checkout Session API call is stubbed."""
import hashlib
import hmac
import json
import time
import uuid
from decimal import Decimal

import pytest

import app.notas_purchase as purchase
from app.database import execute, fetch_all
from app.notas_wallet import debit_notas_atomic, get_balances
from tests.test_security import extract_csrf, login, register_test_user

SECRET = "whsec_test_" + "x" * 24


@pytest.fixture(autouse=True)
def _stripe_configured(monkeypatch):
    monkeypatch.setattr(purchase, "STRIPE_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(purchase, "STRIPE_SECRET_KEY", "rk_test_dummy")


def _post_event(client, event_type, obj, secret=SECRET):
    payload = json.dumps({"id": f"evt_{uuid.uuid4().hex}", "object": "event", "type": event_type,
                          "data": {"object": obj}})
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.{payload}".encode(), hashlib.sha256).hexdigest()
    return client.post("/webhooks/stripe", content=payload,
                       headers={"stripe-signature": f"t={ts},v1={sig}", "content-type": "application/json"})


def _paid_session(user_id, notas=10, status="paid"):
    pi = f"pi_{uuid.uuid4().hex[:16]}"
    return pi, {"object": "checkout.session", "payment_status": status, "payment_intent": pi,
                "metadata": {"user_id": str(user_id), "notas": str(notas), "bundle": f"notas_{notas}"}}


def _user(client, name):
    uid, email, password = register_test_user(client, full_name=name)
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": uid})
    return uid, email, password


def test_bad_signature_is_rejected_and_credits_nothing(client):
    uid, _, _ = _user(client, "Stripe Bad Sig")
    _, session = _paid_session(uid)
    r = _post_event(client, "checkout.session.completed", session, secret="whsec_wrong_secret_value_1234")
    assert r.status_code == 400
    assert get_balances(uid)["total"] == 0


def test_paid_session_credits_purchased_notas_exactly_once(client):
    uid, _, _ = _user(client, "Stripe Paid")
    _, session = _paid_session(uid, notas=25)

    first = _post_event(client, "checkout.session.completed", session)
    replay = _post_event(client, "checkout.session.completed", session)

    assert first.json()["status"] == "credited" and replay.json()["status"] == "duplicate"
    b = get_balances(uid)
    assert (b["purchased"], b["earned"]) == (Decimal("25"), Decimal("0"))
    rows = fetch_all("SELECT category, expires_at FROM credit_ledger WHERE user_id = :u", {"u": uid})
    assert [(r["category"], r["expires_at"]) for r in rows] == [("purchased", None)]


def test_unpaid_session_credits_nothing(client):
    uid, _, _ = _user(client, "Stripe Unpaid")
    _, session = _paid_session(uid, status="unpaid")
    assert _post_event(client, "checkout.session.completed", session).json()["status"] == "not_paid_yet"
    assert get_balances(uid)["total"] == 0


def test_partial_then_full_refund_removes_notas_proportionally_and_can_go_negative(client):
    uid, _, _ = _user(client, "Stripe Refund")
    pi, session = _paid_session(uid, notas=10)
    _post_event(client, "checkout.session.completed", session)
    assert debit_notas_atomic(uid, 8, "sectest_spend")  # 2 left

    charge = {"object": "charge", "payment_intent": pi, "amount": 1000, "amount_refunded": 500}
    _post_event(client, "charge.refunded", charge)
    _post_event(client, "charge.refunded", charge)  # replay: no double debit
    charge["amount_refunded"] = 1000
    _post_event(client, "charge.refunded", charge)

    assert get_balances(uid)["total"] == Decimal("-8")
    assert not debit_notas_atomic(uid, 1, "sectest_spend")


def test_dispute_removes_notas_and_a_won_dispute_restores_them(client):
    uid, _, _ = _user(client, "Stripe Dispute")
    pi, session = _paid_session(uid, notas=10)
    _post_event(client, "checkout.session.completed", session)
    dispute = {"object": "dispute", "id": f"dp_{uuid.uuid4().hex[:12]}", "payment_intent": pi}

    _post_event(client, "charge.dispute.created", dispute)
    assert get_balances(uid)["total"] == 0
    _post_event(client, "charge.dispute.closed", dict(dispute, status="won"))
    _post_event(client, "charge.dispute.closed", dict(dispute, status="won"))  # replay
    b = get_balances(uid)
    assert (b["purchased"], b["total"]) == (Decimal("10"), Decimal("10"))


def test_buy_page_respects_capitalism_mode_and_needs_the_waiver(client, monkeypatch):
    import app.routers.notas_routes as routes
    uid, email, password = _user(client, "Stripe Buyer")
    login(client, email, password)
    monkeypatch.setattr(purchase, "is_capitalismo_mode_enabled", lambda: False)
    assert "accept_terms_waiver" not in client.get("/notas/comprar-notas").text  # "coming soon" page

    monkeypatch.setattr(purchase, "is_capitalismo_mode_enabled", lambda: True)
    page = client.get("/notas/comprar-notas")
    assert "accept_terms_waiver" in page.text and "notas_25" in page.text
    token = extract_csrf(page.text)

    no_waiver = client.post("/notas/comprar-notas", data={"csrf_token": token, "bundle": "notas_25"}, follow_redirects=False)
    assert no_waiver.status_code == 200 and "accept_terms_waiver" in no_waiver.text

    calls = []
    monkeypatch.setattr(routes, "create_checkout_url",
                        lambda user, bundle, lang, base: calls.append((user["id"], bundle)) or "https://checkout.stripe.com/c/pay/test")
    ok = client.post("/notas/comprar-notas", data={"csrf_token": token, "bundle": "notas_25", "accept_terms_waiver": "1"},
                     follow_redirects=False)
    assert ok.status_code == 303 and ok.headers["location"].startswith("https://checkout.stripe.com/")
    assert calls == [(uid, "notas_25")]

    forged = client.post("/notas/comprar-notas", data={"csrf_token": token, "bundle": "notas_9999", "accept_terms_waiver": "1"},
                         follow_redirects=False)
    assert forged.status_code == 303 and forged.headers["location"] == "/notas/comprar-notas"


def test_god_mode_can_test_purchases_while_capitalism_mode_is_off(client, monkeypatch):
    uid, email, password = _user(client, "Stripe God")
    execute("UPDATE users SET role_level = 3 WHERE id = :id", {"id": uid})
    login(client, email, password)
    monkeypatch.setattr(purchase, "is_capitalismo_mode_enabled", lambda: False)
    assert "accept_terms_waiver" in client.get("/notas/comprar-notas").text


def test_csp_allows_the_redirect_to_stripe_checkout(client):
    assert "form-action 'self' https://checkout.stripe.com" in client.get("/").headers["content-security-policy"]

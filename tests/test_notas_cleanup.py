"""Notas cleanup (2026-09-27): atomic shop redeem, Stripe events that aren't
ours, invite links on the public address."""
from decimal import Decimal

import app.email_layout as email_layout
import app.notas_purchase as purchase
from app.database import fetch_one
from app.notas_wallet import credit_notas, get_credit_balance
from app.shop_catalog import redeem_item
from tests.test_security import register_test_user


def test_redeem_applies_debit_and_highlight_together(client):
    uid, _, _ = register_test_user(client)
    credit_notas(uid, Decimal("10"), "admin_grant_credit", idempotency_key=f"t:{uid}")
    status, item = redeem_item(uid, "profile_highlight_7d", "tok1")
    assert status == "redeemed"
    assert fetch_one("SELECT profile_highlighted_until > now() + interval '6 days' AS ok FROM users WHERE id = :id", {"id": uid})["ok"]
    balance_after = get_credit_balance(uid)
    assert redeem_item(uid, "profile_highlight_7d", "tok1")[0] == "replay"
    assert get_credit_balance(uid) == balance_after


def test_redeem_without_enough_notas_changes_nothing(client):
    uid, _, _ = register_test_user(client)
    assert redeem_item(uid, "profile_highlight_7d", "tok")[0] == "insufficient"
    assert fetch_one("SELECT profile_highlighted_until FROM users WHERE id = :id", {"id": uid})["profile_highlighted_until"] is None
    assert redeem_item(uid, "no_such_item", "tok")[0] == "not_found"


def test_stripe_session_without_our_metadata_is_acknowledged_not_crashed():
    event = {"type": "checkout.session.completed",
             "data": {"object": {"payment_status": "paid", "metadata": {}, "payment_intent": "pi_x"}}}
    assert purchase.handle_event(event) == "not_ours"


def test_invite_link_uses_the_public_site_address(client, monkeypatch):
    uid, _, _ = register_test_user(client)
    monkeypatch.setattr(email_layout, "SITE_BASE_URL", "https://vokalboard.example")
    from app.database import execute
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": uid})
    assert "https://vokalboard.example/register?ref=" in client.get("/hall-da-fama").text

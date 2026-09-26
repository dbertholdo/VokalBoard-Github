"""Antifraud pass, 19/09/2026: /notas/redeem now goes through
app/notas_wallet.py's shared atomic-debit-with-idempotency helper (see
that module's docstring — this endpoint was the one deliberately-deferred
exception) instead of hand-rolled SQL with no double-submit protection.

These tests cover the gap that fix closes: a double-click / browser
back-button resubmit / network retry of the exact same rendered form must
be a safe no-op, not a second debit (and, for the profile-highlight item,
not a second stacked extension). See tests/test_admin_loja.py for the
pre-existing coverage of the redeem flow itself (single redeem, deactivated
item, admin history) — unaffected by this change and left as-is.
"""
import re
from decimal import Decimal

from app.database import execute, fetch_one
from tests.test_security import extract_csrf, login, register_test_user

IDEMPOTENCY_TOKEN_RE = re.compile(r'name="idempotency_token" value="([^"]+)"')


def _seed_user(client, balance=Decimal("10")):
    user_id, email, password = register_test_user(client, full_name="Notas Idempotency Test")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    execute("DELETE FROM credit_ledger WHERE user_id = :id", {"id": user_id})
    execute(
        "INSERT INTO credit_ledger (user_id, delta, reason, category) VALUES (:id, :bal, 'sectest_seed', 'earned')",
        {"id": user_id, "bal": balance},
    )
    execute("UPDATE shop_catalog_items SET active = TRUE WHERE item_key = 'profile_highlight_7d'")
    login(client, email, password)
    return user_id


def _get_notas_page(client):
    page = client.get("/notas")
    token = IDEMPOTENCY_TOKEN_RE.search(page.text)
    assert token, "idempotency_token hidden field missing from /notas — template regressed?"
    return page, extract_csrf(page.text), token.group(1)


def _balance(user_id):
    return fetch_one(
        "SELECT COALESCE(SUM(delta), 0) AS n FROM credit_ledger WHERE user_id = :id", {"id": user_id}
    )["n"]


def test_redeem_form_carries_a_fresh_idempotency_token(client):
    _seed_user(client)
    page1, _, token1 = _get_notas_page(client)
    page2, _, token2 = _get_notas_page(client)
    assert token1 != token2


def test_replaying_the_same_redeem_submission_does_not_double_debit(client):
    user_id = _seed_user(client)
    _, csrf_token, idem_token = _get_notas_page(client)
    cost = fetch_one("SELECT cost FROM shop_catalog_items WHERE item_key = 'profile_highlight_7d'")["cost"]

    form = {"item_key": "profile_highlight_7d", "csrf_token": csrf_token, "idempotency_token": idem_token}

    resp1 = client.post("/notas/redeem", data=form, follow_redirects=False)
    assert resp1.status_code == 303
    assert "redeemed=profile_highlight_7d" in resp1.headers["location"]
    balance_after_first = _balance(user_id)
    assert balance_after_first == Decimal("10") - cost

    # Same exact form data again — a double-click, not a fresh page load.
    resp2 = client.post("/notas/redeem", data=form, follow_redirects=False)
    assert resp2.status_code == 303
    assert _balance(user_id) == balance_after_first, "replay must not debit a second time"


def test_replaying_the_same_submission_does_not_stack_the_highlight_extension(client):
    user_id = _seed_user(client)
    _, csrf_token, idem_token = _get_notas_page(client)
    form = {"item_key": "profile_highlight_7d", "csrf_token": csrf_token, "idempotency_token": idem_token}

    client.post("/notas/redeem", data=form, follow_redirects=False)
    until_after_first = fetch_one(
        "SELECT profile_highlighted_until AS u FROM users WHERE id = :id", {"id": user_id}
    )["u"]
    assert until_after_first is not None

    client.post("/notas/redeem", data=form, follow_redirects=False)
    until_after_replay = fetch_one(
        "SELECT profile_highlighted_until AS u FROM users WHERE id = :id", {"id": user_id}
    )["u"]
    assert until_after_replay == until_after_first, "replay must not stack a second extension"


def test_a_fresh_page_load_allows_a_genuine_second_redeem(client):
    user_id = _seed_user(client, balance=Decimal("10"))
    cost = fetch_one("SELECT cost FROM shop_catalog_items WHERE item_key = 'profile_highlight_7d'")["cost"]

    _, csrf_token_1, idem_token_1 = _get_notas_page(client)
    client.post(
        "/notas/redeem",
        data={"item_key": "profile_highlight_7d", "csrf_token": csrf_token_1, "idempotency_token": idem_token_1},
        follow_redirects=False,
    )
    balance_after_first = _balance(user_id)

    # A genuinely new page load gets a new token — this is a real second
    # purchase, not a replay, and must go through.
    _, csrf_token_2, idem_token_2 = _get_notas_page(client)
    assert idem_token_2 != idem_token_1
    resp = client.post(
        "/notas/redeem",
        data={"item_key": "profile_highlight_7d", "csrf_token": csrf_token_2, "idempotency_token": idem_token_2},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "redeemed=profile_highlight_7d" in resp.headers["location"]
    assert _balance(user_id) == balance_after_first - cost


def test_redeem_without_idempotency_token_field_still_works(client):
    """Backward compatibility: an older/custom client that doesn't send the
    field at all still gets a normal (non-deduplicated) redeem, same as
    before this change — the field is additive protection, not a new
    requirement."""
    user_id = _seed_user(client)
    _, csrf_token, _ = _get_notas_page(client)
    resp = client.post(
        "/notas/redeem",
        data={"item_key": "profile_highlight_7d", "csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "redeemed=profile_highlight_7d" in resp.headers["location"]

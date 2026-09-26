"""P6 (18/09/2026) — dois pedidos do mesmo dia:

1. "Adicionar um botão ou submenu para estornar compra, tanto da loja
   quanto com dinheiro, em algum submenu do financeiro" — nova tela
   /financeiro/estornos (God Mode), reaproveitando refund_ledger_entry()
   (app/notas_wallet.py) pro lado Notas, e um estorno interno de
   subscriptions (ainda sem nenhuma linha real — sem gateway) pro lado
   dinheiro.

2. "No botão de denúncia precisamos definir alguma forma de
   warning/punição/banimento" — aceitar uma denúncia agora pode aplicar
   warning/suspend/ban ao autor do anúncio. Ban é diferente de
   suspender: bloqueia login e reativação (só um Admin reverte, via
   unban). Ver app/moderation.py.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.database import execute, execute_returning, fetch_one
from app.moderation import apply_moderation_punishment, unban_user, get_moderation_history, PUNISHMENT_TYPES
from app.notas_wallet import credit_notas, debit_notas_atomic, get_credit_balance
from tests.test_security import DEFAULT_PASSWORD, extract_csrf, login, register_test_user, job_vacancy_fields


def _promote(user_id: int, level: int):
    execute("UPDATE users SET role_level = :lvl, email_verified = TRUE WHERE id = :id", {"lvl": level, "id": user_id})


@pytest.fixture()
def god_user(client):
    user_id, email, password = register_test_user(client, full_name="Punishments God Test")
    _promote(user_id, 3)
    login(client, email, password)
    return {"id": user_id, "email": email, "password": password}


@pytest.fixture(autouse=True)
def _cleanup_subscription_test_rows():
    max_id = fetch_one("SELECT COALESCE(MAX(id), 0) AS n FROM subscriptions")["n"]
    yield
    execute("DELETE FROM subscriptions WHERE id > :max_id", {"max_id": max_id})


def _listing_data(csrf_token):
    return {
        "csrf_token": csrf_token,
        "listing_type": "seeking_singer",
        "title": "Sectest Punishment Listing",
        "description": "Test description.",
        "state": "Bayern",
        "city": "München",
        "country": "DE",
        "repertoire": "Requiem",
        "venue": "",
        "ensemble_type": "",
        **job_vacancy_fields(),
        "event_date": (date.today() + timedelta(days=10)).isoformat(),
    }


def _make_reported_listing(client):
    author_id, author_email, author_password = register_test_user(client, full_name="Punishment Author")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": author_id})
    login(client, author_email, author_password)
    r = client.get("/listings/new")
    token = extract_csrf(r.text)
    client.post("/listings/new", data=_listing_data(token), follow_redirects=False)
    listing = fetch_one(
        "SELECT id FROM listings WHERE author_id = :id ORDER BY created_at DESC LIMIT 1", {"id": author_id}
    )

    reporter_id, reporter_email, reporter_password = register_test_user(client, full_name="Punishment Reporter")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": reporter_id})
    login(client, reporter_email, reporter_password)
    page = client.get(f"/listings/{listing['id']}")
    token = extract_csrf(page.text)
    client.post(
        f"/listings/{listing['id']}/report",
        data={"csrf_token": token, "reason": "Reporting for a punishment-flow test."},
        follow_redirects=False,
    )
    report = fetch_one(
        "SELECT id FROM listing_reports WHERE listing_id = :lid AND reporter_id = :rid",
        {"lid": listing["id"], "rid": reporter_id},
    )
    return author_id, author_email, author_password, report["id"]


# --- apply_moderation_punishment() (module-level) -----------------------

def test_warning_does_not_touch_the_account():
    user_id = _bootstrap_user()
    apply_moderation_punishment(user_id, "warning", report_id=None, admin_id=None)
    row = fetch_one("SELECT deleted_at, banned_at FROM users WHERE id = :id", {"id": user_id})
    assert row["deleted_at"] is None
    assert row["banned_at"] is None
    history = get_moderation_history(user_id)
    assert len(history) == 1
    assert history[0]["action_type"] == "warning"


def test_suspend_sets_deleted_at_but_not_banned_at():
    user_id = _bootstrap_user()
    apply_moderation_punishment(user_id, "suspend", report_id=None, admin_id=None)
    row = fetch_one("SELECT deleted_at, banned_at FROM users WHERE id = :id", {"id": user_id})
    assert row["deleted_at"] is not None
    assert row["banned_at"] is None


def test_ban_sets_both_deleted_at_and_banned_at():
    admin_id = _bootstrap_user()
    user_id = _bootstrap_user()
    apply_moderation_punishment(user_id, "ban", report_id=None, admin_id=admin_id)
    row = fetch_one("SELECT deleted_at, banned_at, banned_by_user_id FROM users WHERE id = :id", {"id": user_id})
    assert row["deleted_at"] is not None
    assert row["banned_at"] is not None
    assert row["banned_by_user_id"] == admin_id


def test_apply_moderation_punishment_rejects_unknown_level():
    user_id = _bootstrap_user()
    with pytest.raises(ValueError):
        apply_moderation_punishment(user_id, "nope", report_id=None, admin_id=None)


def test_unban_user_clears_ban_and_reactivates():
    admin_id = _bootstrap_user()
    user_id = _bootstrap_user()
    apply_moderation_punishment(user_id, "ban", report_id=None, admin_id=admin_id)
    unban_user(user_id)
    row = fetch_one("SELECT deleted_at, banned_at, banned_by_user_id FROM users WHERE id = :id", {"id": user_id})
    assert row["deleted_at"] is None
    assert row["banned_at"] is None
    assert row["banned_by_user_id"] is None


def _bootstrap_user():
    import uuid
    from app.auth import hash_password

    email = f"sectest_punish_{uuid.uuid4().hex[:10]}@example.com"
    row = execute_returning(
        """
        INSERT INTO users (full_name, email, password_hash, role, email_verified)
        VALUES (:name, :email, :hash, 'singer', TRUE)
        RETURNING id
        """,
        {"name": "Direct Punishment Test", "email": email, "hash": hash_password("Sectest123!")},
    )
    return row["id"]


# --- ban blocks login, not just deactivation -----------------------------

def test_banned_account_cannot_login_and_gets_no_reactivation_offer(client):
    user_id, email, password = register_test_user(client, full_name="Banned Login Test")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    apply_moderation_punishment(user_id, "ban", report_id=None, admin_id=None)

    resp = login(client, email, password)
    assert resp.status_code == 403
    assert "banned" in resp.text.lower() or "gesperrt" in resp.text.lower() or "banida" in resp.text.lower()

    # It should not have set the reactivation session flag either.
    resp2 = client.get("/reactivate-account", follow_redirects=False)
    assert resp2.status_code == 303  # redirected to /login — no pending reactivation


def test_reactivate_route_refuses_to_lift_a_ban(client):
    """A level-2 admin hitting /admin/users/{id}/reactivate directly
    must not be able to undo a ban — only /unban (God Mode) can."""
    user_id, email, password = register_test_user(client, full_name="Ban Reactivate Bypass Test")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    apply_moderation_punishment(user_id, "ban", report_id=None, admin_id=None)

    admin_id, admin_email, admin_password = register_test_user(client, full_name="Ban Reactivate Bypass Admin")
    _promote(admin_id, 2)
    login(client, admin_email, admin_password)

    page = client.get(f"/admin/users/{user_id}")
    token = extract_csrf(page.text)
    client.post(f"/admin/users/{user_id}/reactivate", data={"csrf_token": token}, follow_redirects=False)

    row = fetch_one("SELECT deleted_at, banned_at FROM users WHERE id = :id", {"id": user_id})
    assert row["deleted_at"] is not None
    assert row["banned_at"] is not None


def test_registration_with_a_banned_email_is_rejected(client):
    user_id, email, password = register_test_user(client, full_name="Banned Email Reuse Test")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    apply_moderation_punishment(user_id, "ban", report_id=None, admin_id=None)

    r = client.get("/register")
    token = extract_csrf(r.text)
    resp = client.post(
        "/register",
        data={
            "csrf_token": token,
            "category": "soprano",
            "full_name": "Reuse Attempt",
            "email": email,
            "password": DEFAULT_PASSWORD,
            "city": "München",
            "state": "Bayern",
            "country": "DE",
            "phone": "+49 151 00000000",
            "bio": "",
            "composer_hashtags": "",
            "audio_links": "",
            "ensemble_name": "",
            "ref": "",
            "website": "",
            "cf-turnstile-response": "",
        },
        follow_redirects=False,
    )
    assert resp.status_code != 303  # registration did not succeed


# --- accept-a-report route applies punishment ----------------------------

def test_accepting_a_report_with_a_ban_punishment_bans_the_author(client, god_user):
    author_id, author_email, _, report_id = _make_reported_listing(client)
    login(client, god_user["email"], god_user["password"])

    page = client.get("/admin")
    token = extract_csrf(page.text)
    resp = client.post(
        f"/admin/reports/{report_id}/accept",
        data={"csrf_token": token, "punishment": "ban"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    row = fetch_one("SELECT deleted_at, banned_at FROM users WHERE id = :id", {"id": author_id})
    assert row["deleted_at"] is not None
    assert row["banned_at"] is not None

    history = get_moderation_history(author_id)
    assert any(h["action_type"] == "ban" for h in history)


def test_accepting_a_report_with_no_punishment_does_not_touch_the_account(client, god_user):
    author_id, author_email, _, report_id = _make_reported_listing(client)
    login(client, god_user["email"], god_user["password"])

    page = client.get("/admin")
    token = extract_csrf(page.text)
    resp = client.post(
        f"/admin/reports/{report_id}/accept",
        data={"csrf_token": token, "punishment": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    row = fetch_one("SELECT deleted_at, banned_at FROM users WHERE id = :id", {"id": author_id})
    assert row["deleted_at"] is None
    assert row["banned_at"] is None


def test_rejecting_a_report_never_applies_punishment(client, god_user):
    author_id, author_email, _, report_id = _make_reported_listing(client)
    login(client, god_user["email"], god_user["password"])

    page = client.get("/admin")
    token = extract_csrf(page.text)
    client.post(f"/admin/reports/{report_id}/reject", data={"csrf_token": token}, follow_redirects=False)

    row = fetch_one("SELECT deleted_at, banned_at FROM users WHERE id = :id", {"id": author_id})
    assert row["deleted_at"] is None
    assert row["banned_at"] is None


def test_admin_can_unban_via_route(client, god_user):
    author_id, author_email, author_password, report_id = _make_reported_listing(client)
    login(client, god_user["email"], god_user["password"])
    page = client.get("/admin")
    token = extract_csrf(page.text)
    client.post(
        f"/admin/reports/{report_id}/accept",
        data={"csrf_token": token, "punishment": "ban"},
        follow_redirects=False,
    )

    page2 = client.get(f"/admin/users/{author_id}")
    token2 = extract_csrf(page2.text)
    resp = client.post(f"/admin/users/{author_id}/unban", data={"csrf_token": token2}, follow_redirects=False)
    assert resp.status_code == 303

    row = fetch_one("SELECT deleted_at, banned_at FROM users WHERE id = :id", {"id": author_id})
    assert row["deleted_at"] is None
    assert row["banned_at"] is None


def test_unban_route_requires_god_mode(client):
    user_id, email, password = register_test_user(client, full_name="Unban Level2 Test")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    apply_moderation_punishment(user_id, "ban", report_id=None, admin_id=None)

    admin_id, admin_email, admin_password = register_test_user(client, full_name="Unban Level2 Admin")
    _promote(admin_id, 2)
    login(client, admin_email, admin_password)

    resp = client.post(
        f"/admin/users/{user_id}/unban", data={"csrf_token": "irrelevant"}, follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
    row = fetch_one("SELECT banned_at FROM users WHERE id = :id", {"id": user_id})
    assert row["banned_at"] is not None


# --- /financeiro/estornos -------------------------------------------------

def test_financeiro_estornos_requires_god_mode(client):
    user_id, email, password = register_test_user(client, full_name="Estornos Level2 Test")
    _promote(user_id, 2)
    login(client, email, password)
    resp = client.get("/financeiro/estornos", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


def test_financeiro_estornos_lists_notas_debits_and_refunds(client, god_user):
    target_id, _, _ = register_test_user(client, full_name="Estornos Notas Target")
    credit_notas(target_id, Decimal("5"), reason="referral_bonus")
    debit_notas_atomic(target_id, Decimal("2"), reason="redeem_profile_highlight_7d")

    login(client, god_user["email"], god_user["password"])
    page = client.get("/financeiro/estornos")
    assert page.status_code == 200
    assert "redeem_profile_highlight_7d" in page.text

    token = extract_csrf(page.text)
    ledger_row = fetch_one(
        "SELECT id FROM credit_ledger WHERE user_id = :id AND delta < 0 ORDER BY created_at DESC LIMIT 1",
        {"id": target_id},
    )
    balance_before = get_credit_balance(target_id)
    resp = client.post(
        f"/financeiro/estornos/notas/{ledger_row['id']}", data={"csrf_token": token}, follow_redirects=False,
    )
    assert resp.status_code == 303
    assert get_credit_balance(target_id) == balance_before + Decimal("2")


def test_financeiro_estornos_subscription_requires_correct_password(client, god_user):
    target_id, _, _ = register_test_user(client, full_name="Estornos Sub Target")
    sub = execute_returning(
        """
        INSERT INTO subscriptions (user_id, price_paid_cents, currency, country)
        VALUES (:uid, 590, 'EUR', 'DE')
        RETURNING id
        """,
        {"uid": target_id},
    )

    login(client, god_user["email"], god_user["password"])
    page = client.get("/financeiro/estornos")
    token = extract_csrf(page.text)

    bad_resp = client.post(
        f"/financeiro/estornos/assinatura/{sub['id']}",
        data={"csrf_token": token, "current_password": "wrong-password"},
        follow_redirects=False,
    )
    assert "error=senha_incorreta" in bad_resp.headers["location"]
    row = fetch_one("SELECT refunded_at FROM subscriptions WHERE id = :id", {"id": sub["id"]})
    assert row["refunded_at"] is None

    good_resp = client.post(
        f"/financeiro/estornos/assinatura/{sub['id']}",
        data={"csrf_token": token, "current_password": god_user["password"]},
        follow_redirects=False,
    )
    assert "refund_done=1" in good_resp.headers["location"]
    row2 = fetch_one("SELECT refunded_at, is_active FROM subscriptions WHERE id = :id", {"id": sub["id"]})
    assert row2["refunded_at"] is not None
    assert row2["is_active"] is False


def test_financeiro_estornos_period_filter(client, god_user):
    """Same "transactions by period" filter as /financeiro/painel
    (Daniel, 18/09/2026), applied here to the Notas debits and
    subscriptions lists. A future start date excludes everything
    created just now; no filter (or a past start date) includes it."""
    target_id, _, _ = register_test_user(client, full_name="Estornos Period Target")
    credit_notas(target_id, Decimal("5"), reason="referral_bonus")
    debit_notas_atomic(target_id, Decimal("2"), reason="redeem_profile_highlight_7d")

    login(client, god_user["email"], god_user["password"])

    unfiltered = client.get("/financeiro/estornos")
    assert "redeem_profile_highlight_7d" in unfiltered.text

    future_start = (date.today() + timedelta(days=1)).isoformat()
    excluded = client.get("/financeiro/estornos", params={"start": future_start})
    assert excluded.status_code == 200
    assert "redeem_profile_highlight_7d" not in excluded.text

    past_start = (date.today() - timedelta(days=1)).isoformat()
    included = client.get("/financeiro/estornos", params={"start": past_start})
    assert "redeem_profile_highlight_7d" in included.text
    assert f'value="{past_start}"' in included.text

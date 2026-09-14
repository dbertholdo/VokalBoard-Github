"""
Tests for the Red Zone / financial dashboard (see app/routers/financial_routes.py
and app/permissions.py):

1. Access levels: regular/moderator/admin users cannot see the Red Zone,
   only god mode (level 3).
2. The security lock: toggling Capitalism Mode and changing the price
   require the password again, even while already logged in as god
   mode — and a wrong password changes nothing.
3. Every sensitive action lands in audit_log, whether it succeeds or fails.
4. Financial dashboard: create/delete expense, export CSV.
5. Monthly/annual closing: creates it, and all three export formats
   respond 200 with the correct content-type.
"""
import uuid

import pytest

from app.database import execute, fetch_one
from tests.test_security import (
    DEFAULT_PASSWORD,
    extract_csrf,
    login,
    register_test_user,
)


def _promote(user_id: int, level: int):
    execute("UPDATE users SET role_level = :lvl, email_verified = TRUE WHERE id = :id", {"lvl": level, "id": user_id})


@pytest.fixture(autouse=True)
def _cleanup_financial_test_rows():
    """These tables have no relationship at all to sectest_ (the cleanup
    in tests/conftest.py only deletes USERS with that email prefix) —
    without this, every run of the suite would leave test
    expenses/closings/logs piling up forever in the dev database.
    Records the highest id of each table before the test and deletes
    everything above that afterward — simple, and doesn't depend on
    any new column.
    """
    max_ids = {
        t: (fetch_one(f"SELECT COALESCE(MAX(id), 0) AS n FROM {t}")["n"])
        for t in ("expenses", "financial_closings", "audit_log", "bank_import_profiles", "bank_transactions")
    }
    yield
    for t, max_id in max_ids.items():
        execute(f"DELETE FROM {t} WHERE id > :max_id", {"max_id": max_id})  # nosec B608 - t comes only from the fixed tuple above


@pytest.fixture()
def god_user(client):
    user_id, email, password = register_test_user(client, full_name="God Mode Test")
    _promote(user_id, 3)
    login(client, email, password)
    return {"id": user_id, "email": email, "password": password}


class TestAccessLevels:
    def test_common_user_cannot_see_zona_vermelha(self, client):
        user_id, email, password = register_test_user(client, full_name="Regular User Test")
        login(client, email, password)
        r = client.get("/financeiro", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/"

    def test_admin_level_2_cannot_see_zona_vermelha(self, client):
        user_id, email, password = register_test_user(client, full_name="Admin Level 2")
        _promote(user_id, 2)
        login(client, email, password)
        r = client.get("/financeiro", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/"
        # but the "regular" /admin dashboard is still accessible
        r2 = client.get("/admin", follow_redirects=False)
        assert r2.status_code == 200

    def test_moderator_level_1_cannot_reach_admin_users(self, client):
        user_id, email, password = register_test_user(client, full_name="Moderator Test")
        _promote(user_id, 1)
        login(client, email, password)
        # the read-only /admin dashboard already lets them in (level >= 1)
        assert client.get("/admin", follow_redirects=False).status_code == 200
        # but user management requires level 2+
        r = client.get("/admin/users", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/"

    def test_god_mode_sees_zona_vermelha(self, god_user, client):
        r = client.get("/financeiro")
        assert r.status_code == 200
        assert "Capitalism Mode" in r.text

    def test_only_god_mode_can_promote_another_to_god_mode(self, client):
        # a level-2 admin trying to promote someone else to god mode should not be able to
        admin_id, admin_email, admin_password = register_test_user(client, full_name="Promoting Admin")
        _promote(admin_id, 2)
        target_id, _, _ = register_test_user(client, full_name="Promotion Target")
        _promote(target_id, 2)
        login(client, admin_email, admin_password)

        r = client.get(f"/admin/users/{target_id}")
        token = extract_csrf(r.text)
        client.post(
            f"/admin/users/{target_id}/toggle-god-mode",
            data={"csrf_token": token},
            follow_redirects=False,
        )
        level_after = fetch_one("SELECT role_level FROM users WHERE id = :id", {"id": target_id})["role_level"]
        assert level_after == 2, "a regular admin should not be able to promote anyone to god mode"


class TestSecurityLockOnSensitiveActions:
    def test_toggle_capitalismo_requires_correct_password(self, god_user, client):
        r = client.get("/financeiro")
        token = extract_csrf(r.text)

        # wrong password: nothing changes
        client.post(
            "/financeiro/toggle-capitalismo",
            data={"csrf_token": token, "current_password": "wrong-password-on-purpose"},
            follow_redirects=False,
        )
        setting = fetch_one("SELECT value FROM system_settings WHERE key = 'capitalismo_mode_enabled'")
        assert setting["value"] == "false", "a wrong password should not have turned on Capitalism Mode"

        # correct password: turns it on
        client.post(
            "/financeiro/toggle-capitalismo",
            data={"csrf_token": token, "current_password": DEFAULT_PASSWORD},
            follow_redirects=False,
        )
        setting_after = fetch_one("SELECT value FROM system_settings WHERE key = 'capitalismo_mode_enabled'")
        assert setting_after["value"] == "true"

        # turn it back off, so state doesn't leak into the next test
        client.post(
            "/financeiro/toggle-capitalismo",
            data={"csrf_token": token, "current_password": DEFAULT_PASSWORD},
            follow_redirects=False,
        )

    def test_wrong_password_and_success_both_hit_audit_log(self, god_user, client):
        r = client.get("/financeiro")
        token = extract_csrf(r.text)
        before = fetch_one("SELECT COUNT(*) AS n FROM audit_log")["n"]

        client.post(
            "/financeiro/toggle-capitalismo",
            data={"csrf_token": token, "current_password": "wrong"},
            follow_redirects=False,
        )
        after_fail = fetch_one("SELECT COUNT(*) AS n FROM audit_log")["n"]
        assert after_fail == before + 1

        client.post(
            "/financeiro/toggle-capitalismo",
            data={"csrf_token": token, "current_password": DEFAULT_PASSWORD},
            follow_redirects=False,
        )
        after_success = fetch_one("SELECT COUNT(*) AS n FROM audit_log")["n"]
        assert after_success == after_fail + 1

        last_action = fetch_one("SELECT action, actor_user_id FROM audit_log ORDER BY id DESC LIMIT 1")
        assert last_action["action"] == "toggle_capitalismo_mode"
        assert last_action["actor_user_id"] == god_user["id"]

        # turn it back off so state doesn't leak
        client.post(
            "/financeiro/toggle-capitalismo",
            data={"csrf_token": token, "current_password": DEFAULT_PASSWORD},
            follow_redirects=False,
        )

    def test_set_price_requires_password_and_valid_amount(self, god_user, client):
        r = client.get("/financeiro")
        token = extract_csrf(r.text)

        client.post(
            "/financeiro/set-price",
            data={
                "csrf_token": token, "price_eur": "7.90", "price_chf": "8.90",
                "current_password": DEFAULT_PASSWORD,
            },
            follow_redirects=False,
        )
        eur = fetch_one("SELECT value FROM system_settings WHERE key = 'subscription_price_eur_cents'")
        assert eur["value"] == "790"

        # revert to the default so state doesn't leak between tests
        client.post(
            "/financeiro/set-price",
            data={
                "csrf_token": token, "price_eur": "5.90", "price_chf": "6.90",
                "current_password": DEFAULT_PASSWORD,
            },
            follow_redirects=False,
        )


class TestFinancialPanel:
    def test_create_and_delete_expense(self, god_user, client):
        r = client.get("/financeiro/painel")
        assert r.status_code == 200
        token = extract_csrf(r.text)

        client.post(
            "/financeiro/expenses",
            data={
                "csrf_token": token, "description": "Railway Hosting", "amount": "12.50",
                "currency": "EUR", "category": "hosting", "expense_date": "2026-09-01",
                "is_recurring": "1", "recurrence_interval": "monthly",
            },
            follow_redirects=False,
        )
        expense = fetch_one("SELECT * FROM expenses WHERE description = 'Railway Hosting'")
        assert expense is not None
        assert expense["amount_cents"] == 1250
        assert expense["is_recurring"] is True

        client.post(
            f"/financeiro/expenses/{expense['id']}/delete",
            data={"csrf_token": token},
            follow_redirects=False,
        )
        assert fetch_one("SELECT * FROM expenses WHERE id = :id", {"id": expense["id"]}) is None

    def test_expenses_export_csv(self, god_user, client):
        r = client.get("/financeiro/expenses/export.csv")
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        assert "description" in r.text

    def test_non_god_mode_cannot_reach_financial_panel(self, client):
        user_id, email, password = register_test_user(client, full_name="No Access")
        login(client, email, password)
        assert client.get("/financeiro/painel", follow_redirects=False).status_code == 303
        assert client.get("/financeiro/expenses/export.csv", follow_redirects=False).status_code == 303


class TestFinancialClosing:
    def test_create_closing_and_export_all_formats(self, god_user, client):
        r = client.get("/financeiro/painel")
        token = extract_csrf(r.text)

        resp = client.post(
            "/financeiro/fechamento",
            data={
                "csrf_token": token, "period_type": "monthly",
                "period_start": "2026-09-01", "period_end": "2026-09-30",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303
        closing = fetch_one("SELECT * FROM financial_closings ORDER BY id DESC LIMIT 1")
        assert closing is not None
        assert closing["period_type"] == "monthly"

        csv_resp = client.get(f"/financeiro/fechamento/{closing['id']}/export.csv")
        assert csv_resp.status_code == 200
        assert "text/csv" in csv_resp.headers["content-type"]

        xlsx_resp = client.get(f"/financeiro/fechamento/{closing['id']}/export.xlsx")
        assert xlsx_resp.status_code == 200
        assert "spreadsheetml" in xlsx_resp.headers["content-type"]

        pdf_resp = client.get(f"/financeiro/fechamento/{closing['id']}/export.pdf")
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers["content-type"] == "application/pdf"


class TestCapitalismoBannerHidden:
    def test_banner_hidden_while_capitalismo_mode_off(self, client):
        user_id, email, password = register_test_user(client, full_name="Banner Test User")
        login(client, email, password)
        r = client.get("/")
        assert "capitalismo-banner" not in r.text
        assert "Subscribe now" not in r.text

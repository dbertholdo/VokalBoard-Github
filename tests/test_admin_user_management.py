"""P6 — painel de Admin de usuários (18/09/2026): filtro "somente
ativos" em /admin/users, mini card de status em /admin/users/{id},
adicionar/remover dias de destaque manualmente, e reembolso de uma
linha específica do extrato de Notas. Pedido do Daniel: "lista de
usuários ativos filtrável, adicionar/remover dias, reembolso". Ver
app/highlights.py (adjust_highlight_days) e
app/routers/admin_routes.py."""
from decimal import Decimal

from app.database import execute, fetch_one
from app.highlights import adjust_highlight_days, MAX_HIGHLIGHT_DAYS_ADJUSTMENT
from app.notas_wallet import credit_notas, get_credit_balance
from tests.test_security import extract_csrf, login, register_test_user


def _make_plain_user(client, full_name="Plain User Mgmt Test"):
    # Registers and logs in as a throwaway second user, then logs the
    # admin back in — tests need a target user that isn't the admin.
    user_id, email, password = register_test_user(client, full_name=full_name)
    return user_id, email, password


# --- adjust_highlight_days() (module-level) ---------------------------

def test_adjust_highlight_days_starts_from_now_when_never_highlighted():
    user_id, _, _ = register_test_user_direct()
    new_until = adjust_highlight_days(user_id, 5)
    assert new_until is not None
    row = fetch_one("SELECT profile_highlighted_until FROM users WHERE id = :id", {"id": user_id})
    assert row["profile_highlighted_until"] == new_until


def test_adjust_highlight_days_stacks_on_top_of_existing_future_date():
    user_id, _, _ = register_test_user_direct()
    first = adjust_highlight_days(user_id, 5)
    second = adjust_highlight_days(user_id, 3)
    assert second > first


def test_adjust_highlight_days_negative_clears_to_null_when_it_goes_to_the_past():
    user_id, _, _ = register_test_user_direct()
    adjust_highlight_days(user_id, 5)
    result = adjust_highlight_days(user_id, -30)
    assert result is None
    row = fetch_one("SELECT profile_highlighted_until FROM users WHERE id = :id", {"id": user_id})
    assert row["profile_highlighted_until"] is None


def register_test_user_direct():
    """Registers a user without needing a TestClient — module-level
    helper tests don't go through HTTP."""
    import uuid
    from app.database import execute_returning
    from app.auth import hash_password

    email = f"sectest_highlight_{uuid.uuid4().hex[:10]}@example.com"
    row = execute_returning(
        """
        INSERT INTO users (full_name, email, password_hash, role, email_verified)
        VALUES (:name, :email, :hash, 'singer', TRUE)
        RETURNING id
        """,
        {"name": "Highlight Direct Test", "email": email, "hash": hash_password("Sectest123!")},
    )
    return row["id"], email, "Sectest123!"


# --- /admin/users active-only filter -----------------------------------

def test_admin_users_list_active_only_hides_deactivated_accounts(client):
    admin_id, admin_email, admin_password = register_test_user(client, full_name="Active Filter Admin")
    execute("UPDATE users SET email_verified = TRUE, role_level = 2 WHERE id = :id", {"id": admin_id})

    target_id, _, _ = _make_plain_user(client, "Deactivated Filter Target")
    execute("UPDATE users SET deleted_at = now() WHERE id = :id", {"id": target_id})

    # register_test_user() for the target above logged the target in on
    # the shared client session — log the admin back in before hitting
    # an admin-only route.
    login(client, admin_email, admin_password)

    resp_all = client.get("/admin/users?q=Deactivated+Filter+Target")
    assert "1 user(s) found." in resp_all.text

    # The name still shows up once — inside the search box's own value=
    # attribute — so assert on the result count/empty-state, not a bare
    # text search for the name.
    resp_active = client.get("/admin/users?q=Deactivated+Filter+Target&active_only=1")
    assert "No users found." in resp_active.text
    assert "0 user(s) found." in resp_active.text


# --- mini card ----------------------------------------------------------

def test_admin_user_detail_shows_mini_card_status(client):
    target_id, _, _ = _make_plain_user(client, "Mini Card Target")

    admin_id, admin_email, admin_password = register_test_user(client, full_name="Mini Card Admin")
    execute("UPDATE users SET email_verified = TRUE, role_level = 2 WHERE id = :id", {"id": admin_id})
    login(client, admin_email, admin_password)

    resp = client.get(f"/admin/users/{target_id}")
    assert resp.status_code == 200
    assert "No active highlight" in resp.text
    assert "0 Notas" in resp.text or "Notas" in resp.text


# --- highlight-days route ------------------------------------------------

def test_admin_can_add_highlight_days_via_route(client):
    admin_id, admin_email, admin_password = register_test_user(client, full_name="Highlight Route Admin")
    execute("UPDATE users SET email_verified = TRUE, role_level = 2 WHERE id = :id", {"id": admin_id})
    login(client, admin_email, admin_password)

    target_id, _, _ = _make_plain_user(client, "Highlight Route Target")
    login(client, admin_email, admin_password)  # switch back to admin

    page = client.get(f"/admin/users/{target_id}")
    token = extract_csrf(page.text)

    resp = client.post(
        f"/admin/users/{target_id}/highlight-days",
        data={"csrf_token": token, "days": "7"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "highlight_updated=1" in resp.headers["location"]

    row = fetch_one("SELECT profile_highlighted_until FROM users WHERE id = :id", {"id": target_id})
    assert row["profile_highlighted_until"] is not None


def test_admin_highlight_days_route_rejects_over_the_max(client):
    admin_id, admin_email, admin_password = register_test_user(client, full_name="Highlight Max Admin")
    execute("UPDATE users SET email_verified = TRUE, role_level = 2 WHERE id = :id", {"id": admin_id})
    login(client, admin_email, admin_password)

    target_id, _, _ = _make_plain_user(client, "Highlight Max Target")
    login(client, admin_email, admin_password)

    page = client.get(f"/admin/users/{target_id}")
    token = extract_csrf(page.text)

    resp = client.post(
        f"/admin/users/{target_id}/highlight-days",
        data={"csrf_token": token, "days": str(MAX_HIGHLIGHT_DAYS_ADJUSTMENT + 1)},
        follow_redirects=False,
    )
    assert "highlight_error=1" in resp.headers["location"]


# --- refund-notas route --------------------------------------------------

def test_admin_can_refund_a_debit_ledger_line_via_route(client):
    admin_id, admin_email, admin_password = register_test_user(client, full_name="Refund Route Admin")
    execute("UPDATE users SET email_verified = TRUE, role_level = 2 WHERE id = :id", {"id": admin_id})
    login(client, admin_email, admin_password)

    target_id, _, _ = _make_plain_user(client, "Refund Route Target")
    credit_notas(target_id, Decimal("5"), reason="referral_bonus")
    from app.notas_wallet import debit_notas_atomic
    debit_notas_atomic(target_id, Decimal("3"), reason="redeem_profile_highlight_7d")

    login(client, admin_email, admin_password)  # switch back to admin

    page = client.get(f"/admin/users/{target_id}")
    token = extract_csrf(page.text)
    ledger_row = fetch_one(
        "SELECT id FROM credit_ledger WHERE user_id = :id AND delta < 0 ORDER BY created_at DESC LIMIT 1",
        {"id": target_id},
    )
    balance_before = get_credit_balance(target_id)

    resp = client.post(
        f"/admin/users/{target_id}/refund-notas/{ledger_row['id']}",
        data={"csrf_token": token, "current_password": admin_password},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "refund_done=1" in resp.headers["location"]
    assert get_credit_balance(target_id) == balance_before + Decimal("3")


def test_admin_refund_is_idempotent_double_submit_does_not_double_credit(client):
    admin_id, admin_email, admin_password = register_test_user(client, full_name="Refund Idempotent Admin")
    execute("UPDATE users SET email_verified = TRUE, role_level = 2 WHERE id = :id", {"id": admin_id})
    login(client, admin_email, admin_password)

    target_id, _, _ = _make_plain_user(client, "Refund Idempotent Target")
    credit_notas(target_id, Decimal("5"), reason="referral_bonus")
    from app.notas_wallet import debit_notas_atomic
    debit_notas_atomic(target_id, Decimal("2"), reason="redeem_profile_highlight_7d")

    login(client, admin_email, admin_password)

    page = client.get(f"/admin/users/{target_id}")
    token = extract_csrf(page.text)
    ledger_row = fetch_one(
        "SELECT id FROM credit_ledger WHERE user_id = :id AND delta < 0 ORDER BY created_at DESC LIMIT 1",
        {"id": target_id},
    )
    balance_before = get_credit_balance(target_id)

    client.post(f"/admin/users/{target_id}/refund-notas/{ledger_row['id']}", data={"csrf_token": token, "current_password": admin_password}, follow_redirects=False)
    client.post(f"/admin/users/{target_id}/refund-notas/{ledger_row['id']}", data={"csrf_token": token, "current_password": admin_password}, follow_redirects=False)

    assert get_credit_balance(target_id) == balance_before + Decimal("2")


def test_admin_refund_rejects_a_credit_line(client):
    admin_id, admin_email, admin_password = register_test_user(client, full_name="Refund Credit Admin")
    execute("UPDATE users SET email_verified = TRUE, role_level = 2 WHERE id = :id", {"id": admin_id})
    login(client, admin_email, admin_password)

    target_id, _, _ = _make_plain_user(client, "Refund Credit Target")
    credit_notas(target_id, Decimal("5"), reason="referral_bonus")

    login(client, admin_email, admin_password)

    page = client.get(f"/admin/users/{target_id}")
    token = extract_csrf(page.text)
    ledger_row = fetch_one(
        "SELECT id FROM credit_ledger WHERE user_id = :id AND delta > 0 ORDER BY created_at DESC LIMIT 1",
        {"id": target_id},
    )
    balance_before = get_credit_balance(target_id)

    resp = client.post(
        f"/admin/users/{target_id}/refund-notas/{ledger_row['id']}",
        data={"csrf_token": token, "current_password": admin_password},
        follow_redirects=False,
    )
    assert "refund_error=1" in resp.headers["location"]
    assert get_credit_balance(target_id) == balance_before

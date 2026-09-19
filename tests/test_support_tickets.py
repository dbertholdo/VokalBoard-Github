"""Support tickets — "Fale conosco" (contact) + "Reportar erro" (bug
report) — P6 close-out (19/09/2026). Daniel's request ("Make p6
done"), scoped via AskUserQuestion: one unified admin inbox for both.
See app/support_tickets.py and app/routers/support_routes.py.
"""
import pytest

from app.database import execute, fetch_one
from tests.test_security import extract_csrf, login, register_test_user


def _promote(user_id: int, level: int):
    execute("UPDATE users SET role_level = :lvl, email_verified = TRUE WHERE id = :id", {"lvl": level, "id": user_id})


@pytest.fixture()
def admin_user(client):
    user_id, email, password = register_test_user(client, full_name="Tickets Admin Test")
    _promote(user_id, 2)
    login(client, email, password)
    return {"id": user_id, "email": email, "password": password}


@pytest.fixture(autouse=True)
def _cleanup_ticket_test_rows():
    max_id = fetch_one("SELECT COALESCE(MAX(id), 0) AS n FROM support_tickets")["n"]
    yield
    execute("DELETE FROM support_tickets WHERE id > :max_id", {"max_id": max_id})


def test_contact_requires_login(client):
    resp = client.get("/contato", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/login")


def test_contact_submission_creates_ticket(client):
    user_id, email, password = register_test_user(client, full_name="Contact Sender Test")
    login(client, email, password)
    r = client.get("/contato")
    csrf_token = extract_csrf(r.text)

    resp = client.post(
        "/contato",
        data={"csrf_token": csrf_token, "subject": "Billing question", "description": "How does the referral bonus work exactly?"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "sent=1" in resp.headers["location"]

    ticket = fetch_one("SELECT * FROM support_tickets WHERE user_id = :id AND type = 'contact'", {"id": user_id})
    assert ticket is not None
    assert ticket["subject"] == "Billing question"
    assert ticket["status"] == "open"


def test_contact_description_too_short_rejected(client):
    user_id, email, password = register_test_user(client, full_name="Contact Short Test")
    login(client, email, password)
    r = client.get("/contato")
    csrf_token = extract_csrf(r.text)

    resp = client.post(
        "/contato",
        data={"csrf_token": csrf_token, "subject": "", "description": "short"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "error=descricao_curta" in resp.headers["location"]
    assert fetch_one("SELECT id FROM support_tickets WHERE user_id = :id", {"id": user_id}) is None


def test_bug_report_works_logged_out(client):
    r = client.get("/")
    csrf_token = extract_csrf(r.text)

    resp = client.post(
        "/support/report-bug",
        data={
            "csrf_token": csrf_token, "description": "The board page shows a blank screen after filtering.",
            "page_url": "https://vokalboard.example/board?voice=soprano", "page_name": "Board",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/board")
    assert "bug_report_sent=1" in resp.headers["location"]

    ticket = fetch_one("SELECT * FROM support_tickets WHERE type = 'bug_report' AND page_name = 'Board'")
    assert ticket is not None
    assert ticket["user_id"] is None
    assert ticket["page_url"] == "https://vokalboard.example/board?voice=soprano"


def test_bug_report_captures_logged_in_user_id(client):
    user_id, email, password = register_test_user(client, full_name="Bug Reporter Test")
    login(client, email, password)
    r = client.get("/")
    csrf_token = extract_csrf(r.text)

    client.post(
        "/support/report-bug",
        data={
            "csrf_token": csrf_token, "description": "My profile photo doesn't update after I crop it.",
            "page_url": "https://vokalboard.example/profile", "page_name": "My profile",
        },
        follow_redirects=False,
    )
    ticket = fetch_one(
        "SELECT * FROM support_tickets WHERE type = 'bug_report' AND page_name = 'My profile' AND user_id = :id",
        {"id": user_id},
    )
    assert ticket is not None


def test_bug_report_redirect_never_leaves_the_site():
    """page_url is client-supplied — an attacker posting an absolute
    off-site URL must never turn this endpoint into an open redirect."""
    from app.routers.support_routes import _safe_redirect_target

    assert _safe_redirect_target("https://vokalboard.example/board?x=1") == "/board?x=1"
    # Only the PATH is ever reused — an attacker-supplied host is simply
    # discarded, so this never redirects to evil.example itself, only to
    # a same-site path that happens to share its spelling.
    assert _safe_redirect_target("https://evil.example/phish") == "/phish"
    assert _safe_redirect_target("//evil.example/phish") == "/phish"
    assert _safe_redirect_target("javascript:alert(1)") == "/"
    assert _safe_redirect_target("") == "/"


def test_admin_can_respond_and_resolve_ticket(client, admin_user):
    user_id, email, password = register_test_user(client, full_name="Ticket Owner Test")
    login(client, email, password)
    r = client.get("/contato")
    csrf_token = extract_csrf(r.text)
    client.post(
        "/contato",
        data={"csrf_token": csrf_token, "subject": "Help", "description": "I can't find the referral link."},
        follow_redirects=False,
    )
    ticket = fetch_one("SELECT id FROM support_tickets WHERE user_id = :id", {"id": user_id})

    login(client, admin_user["email"], admin_user["password"])
    r = client.get("/admin/tickets")
    admin_csrf = extract_csrf(r.text)

    resp = client.post(
        f"/admin/tickets/{ticket['id']}/respond",
        data={"csrf_token": admin_csrf, "admin_response": "It's on your profile page, under Referrals.", "resolve": "1"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "responded=1" in resp.headers["location"]

    updated = fetch_one("SELECT status, admin_response FROM support_tickets WHERE id = :id", {"id": ticket["id"]})
    assert updated["status"] == "resolved"
    assert "Referrals" in updated["admin_response"]


def test_non_admin_cannot_reach_tickets_inbox(client):
    user_id, email, password = register_test_user(client, full_name="Not Admin Test")
    login(client, email, password)
    resp = client.get("/admin/tickets", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"

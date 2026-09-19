"""Periodic mails (/admin/emails?tab=periodic) — P0 backlog item, built
19/09/2026 at Daniel's request. Recipients fixed to the admin team
this round (see app/periodic_mails.py's module docstring). Covers the
admin CRUD screen and the worker (app/periodic_mail_worker.py)
separately.
"""
import pytest

from app.database import execute, fetch_one
from app.periodic_mails import create_periodic_mail
from app.periodic_mail_worker import run_periodic_mails
from tests.test_security import extract_csrf, login, register_test_user


def _promote(user_id: int, level: int):
    execute("UPDATE users SET role_level = :lvl, email_verified = TRUE WHERE id = :id", {"lvl": level, "id": user_id})


@pytest.fixture()
def admin_user(client):
    user_id, email, password = register_test_user(client, full_name="Periodic Mail Admin Test")
    _promote(user_id, 2)
    login(client, email, password)
    return {"id": user_id, "email": email, "password": password}


@pytest.fixture(autouse=True)
def _cleanup_periodic_mail_rows():
    max_id = fetch_one("SELECT COALESCE(MAX(id), 0) AS n FROM periodic_mails")["n"]
    yield
    execute("DELETE FROM periodic_mails WHERE id > :max_id", {"max_id": max_id})


def test_non_admin_cannot_reach_periodic_tab(client):
    user_id, email, password = register_test_user(client, full_name="Not Admin Periodic Test")
    login(client, email, password)
    resp = client.get("/admin/emails?tab=periodic", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


def test_create_list_edit_periodic_mail(client, admin_user):
    r = client.get("/admin/emails/periodic/new")
    csrf_token = extract_csrf(r.text)

    resp = client.post(
        "/admin/emails/periodic/new",
        data={
            "csrf_token": csrf_token, "name": "Weekly signups report", "subject": "Signups this week",
            "body_html": "<p>3 new singers, 1 new conductor.</p>", "frequency": "weekly",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "tab=periodic" in resp.headers["location"]

    mail = fetch_one("SELECT * FROM periodic_mails WHERE name = 'Weekly signups report'")
    assert mail is not None
    assert mail["frequency"] == "weekly"
    assert mail["is_active"] is True
    assert mail["next_send_at"] is not None  # scheduled forward, not immediate

    # Shows up in the list.
    list_resp = client.get("/admin/emails?tab=periodic")
    assert "Weekly signups report" in list_resp.text

    # Edit: change the body and the frequency in one go.
    r = client.get(f"/admin/emails/periodic/{mail['id']}/edit")
    edit_csrf = extract_csrf(r.text)
    resp = client.post(
        f"/admin/emails/periodic/{mail['id']}/edit",
        data={
            "csrf_token": edit_csrf, "name": "Weekly signups report", "subject": "Signups this week (v2)",
            "body_html": "<p>Updated body.</p>", "frequency": "monthly",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    updated = fetch_one("SELECT * FROM periodic_mails WHERE id = :id", {"id": mail["id"]})
    assert updated["subject"] == "Signups this week (v2)"
    assert updated["frequency"] == "monthly"


def test_create_rejects_blank_fields(client, admin_user):
    r = client.get("/admin/emails/periodic/new")
    csrf_token = extract_csrf(r.text)

    resp = client.post(
        "/admin/emails/periodic/new",
        data={"csrf_token": csrf_token, "name": "", "subject": "Subject", "body_html": "<p>Body</p>", "frequency": "daily"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "error=dados_invalidos" in resp.headers["location"]
    assert fetch_one("SELECT id FROM periodic_mails WHERE subject = 'Subject'") is None


def test_pause_and_resume(client, admin_user):
    mail_id = create_periodic_mail("Daily digest", "Digest", "<p>Body</p>", "daily", admin_user["id"])

    r = client.get("/admin/emails?tab=periodic")
    csrf_token = extract_csrf(r.text)

    client.post(f"/admin/emails/periodic/{mail_id}/toggle", data={"csrf_token": csrf_token, "is_active": "0"})
    assert fetch_one("SELECT is_active FROM periodic_mails WHERE id = :id", {"id": mail_id})["is_active"] is False

    client.post(f"/admin/emails/periodic/{mail_id}/toggle", data={"csrf_token": csrf_token, "is_active": "1"})
    assert fetch_one("SELECT is_active FROM periodic_mails WHERE id = :id", {"id": mail_id})["is_active"] is True


def test_delete(client, admin_user):
    mail_id = create_periodic_mail("To delete", "Subject", "<p>Body</p>", "daily", admin_user["id"])

    r = client.get("/admin/emails?tab=periodic")
    csrf_token = extract_csrf(r.text)
    client.post(f"/admin/emails/periodic/{mail_id}/delete", data={"csrf_token": csrf_token})

    assert fetch_one("SELECT id FROM periodic_mails WHERE id = :id", {"id": mail_id}) is None


def test_worker_sends_only_when_due_and_reschedules(admin_user):
    mail_id = create_periodic_mail("Due now test", "Subject", "<p>Body</p>", "daily", admin_user["id"])
    # create_periodic_mail schedules the first send in the future — not due yet.
    result = run_periodic_mails()
    assert result["mails_sent"] == 0

    execute("UPDATE periodic_mails SET next_send_at = now() - interval '1 minute' WHERE id = :id", {"id": mail_id})
    result = run_periodic_mails()
    assert result["mails_sent"] == 1
    assert result["emails_sent"] >= 1  # at least the one admin_user created above

    updated = fetch_one("SELECT last_sent_at, next_send_at FROM periodic_mails WHERE id = :id", {"id": mail_id})
    assert updated["last_sent_at"] is not None
    assert updated["next_send_at"] > updated["last_sent_at"]  # rescheduled forward


def test_worker_skips_paused_mail(admin_user):
    mail_id = create_periodic_mail("Paused test", "Subject", "<p>Body</p>", "daily", admin_user["id"])
    execute(
        "UPDATE periodic_mails SET next_send_at = now() - interval '1 minute', is_active = FALSE WHERE id = :id",
        {"id": mail_id},
    )
    result = run_periodic_mails()
    assert result["mails_sent"] == 0
    assert fetch_one("SELECT last_sent_at FROM periodic_mails WHERE id = :id", {"id": mail_id})["last_sent_at"] is None

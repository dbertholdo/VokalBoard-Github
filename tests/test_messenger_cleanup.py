"""Messenger & notifications cleanup (2026-09-27)."""
from datetime import datetime, timezone

from app import messenger as m
from app.database import execute, fetch_one
from app.notifications import _matching_recipients
from app.safe_redirect import safe_path
from tests.test_security import extract_csrf, register_test_user


def test_clock_times_are_shown_in_the_site_zone():
    summer = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
    winter = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    assert m.local_time(summer) == "01.07. 12:00"   # CEST
    assert m.local_time(winter) == "15.01. 11:00"   # CET
    assert m.local_time(None) == ""


def test_stale_listing_reference_does_not_break_sending(client):
    a, _, _ = register_test_user(client)
    b, _, _ = register_test_user(client)
    status, conv = m.send_message(a, b, "Hello", listing_id=987654321)
    assert status == "request_sent"
    assert fetch_one("SELECT listing_id FROM messages WHERE conversation_id = :c", {"c": conv})["listing_id"] is None


def test_safe_path_keeps_redirects_on_site():
    assert safe_path("/invitations") == "/invitations"
    assert safe_path("https://evil.example/x?y=1") == "/x?y=1"
    assert safe_path("https://evil.example") == "/"
    for bad in ("//evil.example", "javascript:alert(1)", "/\\evil.example", "", None):
        assert safe_path(bad, "/home") == "/home"


def test_mark_all_read_ignores_foreign_referer(client):
    register_test_user(client)
    token = extract_csrf(client.get("/profile").text)
    r = client.post("/notifications/mark-all-read", data={"csrf_token": token},
                    headers={"Referer": "https://evil.example/phish"}, follow_redirects=False)
    assert r.headers["location"] == "/phish"


def test_job_alerts_skip_people_across_a_block(client):
    author, _, _ = register_test_user(client)
    blocker, _, _ = register_test_user(client)
    execute("UPDATE users SET role = 'conductor', email_verified = TRUE, notify_matches = TRUE WHERE id = :id", {"id": blocker})
    ids = lambda: {r["email"] for r in _matching_recipients("seeking_conductor", author, [])}  # noqa: E731
    email = fetch_one("SELECT email FROM users WHERE id = :id", {"id": blocker})["email"]
    assert email in ids()
    execute("INSERT INTO blocked_users (blocker_id, blocked_id) VALUES (:a, :b)", {"a": blocker, "b": author})
    assert email not in ids()

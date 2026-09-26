"""Messenger pages end to end (app/routers/messages_routes.py)."""
from fastapi.testclient import TestClient

from app import messenger as m
from app.database import execute, fetch_one
from app.main import app
from tests.test_security import extract_csrf, login, register_test_user


def _person(name):
    client = TestClient(app)
    uid, email, password = register_test_user(client, full_name=name)
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": uid})
    login(client, email, password)
    return client, uid


def _send(client, to, body):
    token = extract_csrf(client.get(f"/messages/new?to={to}").text)
    return client.post("/messages/send", data={"csrf_token": token, "recipient_id": to, "listing_id": "", "body": body},
                       follow_redirects=False)


def test_request_flow_through_the_pages():
    alice, a = _person("Route Alice")
    bob, b = _person("Route Bob")

    first = _send(alice, b, "Hi Bob, are you free on 12 May?")
    assert first.status_code == 303 and first.headers["location"].startswith("/messages/c/")
    conv = int(first.headers["location"].rsplit("/", 1)[1])
    second = _send(alice, b, "Hello?")  # /messages/new now opens the existing conversation
    assert second.headers["location"] == f"/messages/c/{conv}?notice=request_pending"

    requests_page = bob.get("/messages?folder=requests").text
    assert "Route Alice" in requests_page and "messenger-requests-new" in requests_page
    thread = bob.get(f"/messages/c/{conv}").text
    assert "Hi Bob, are you free on 12 May?" in thread and f"/messages/c/{conv}/accept" in thread

    token = extract_csrf(thread)
    assert bob.post(f"/messages/c/{conv}/accept", data={"csrf_token": token}, follow_redirects=False).status_code == 303
    assert fetch_one("SELECT status FROM conversations WHERE id = :c", {"c": conv})["status"] == "active"
    assert "Route Alice" in bob.get("/messages").text


def test_outsiders_cannot_open_a_conversation_and_old_urls_redirect():
    alice, a = _person("Route Owner A")
    bob, b = _person("Route Owner B")
    eve, _ = _person("Route Outsider")
    _, conv = m.send_message(a, b, "Private note")
    msg_id = fetch_one("SELECT id FROM messages WHERE conversation_id = :c", {"c": conv})["id"]

    assert eve.get(f"/messages/c/{conv}", follow_redirects=False).headers["location"] == "/messages"
    assert eve.get(f"/messages/{msg_id}", follow_redirects=False).headers["location"] == "/messages"
    assert bob.get(f"/messages/{msg_id}", follow_redirects=False).headers["location"] == f"/messages/c/{conv}"
    for old in ("/messages/sent", "/messages/trash"):
        assert alice.get(old, follow_redirects=False).headers["location"] == "/messages"


def test_report_from_the_thread():
    alice, a = _person("Route Reporter A")
    bob, b = _person("Route Reporter B")
    _, conv = m.send_message(a, b, "Something offensive")
    msg_id = fetch_one("SELECT id FROM messages WHERE conversation_id = :c", {"c": conv})["id"]

    token = extract_csrf(bob.get(f"/messages/c/{conv}").text)
    r = bob.post(f"/messages/{msg_id}/report", data={"csrf_token": token, "reason": "Offensive language"},
                 follow_redirects=False)
    assert r.headers["location"] == f"/messages/c/{conv}?notice=report_reported"
    assert fetch_one("SELECT status FROM message_reports WHERE message_id = :m", {"m": msg_id})["status"] == "open"
    # The sender's own view never offers "report" on their own message.
    assert f"/messages/{msg_id}/report" not in alice.get(f"/messages/c/{conv}").text


def test_retention_warning_shows_in_the_last_10_days():
    alice, a = _person("Route Warn A")
    bob, b = _person("Route Warn B")
    m.send_message(a, b, "Hi")
    _, conv = m.send_message(b, a, "Hi")
    execute("UPDATE conversations SET last_activity_at = now() - interval '55 days' WHERE id = :c", {"c": conv})
    page = alice.get(f"/messages/c/{conv}").text
    assert "retention-warning" in page and ("5 days" in page or "5 Tagen" in page)

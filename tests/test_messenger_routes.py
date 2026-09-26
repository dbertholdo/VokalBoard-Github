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


def test_polling_endpoints_counts_latest_and_since():
    alice, a = _person("Poll A")
    bob, b = _person("Poll B")
    _, conv = m.send_message(a, b, "First")
    m.accept_request(b, conv)
    m.send_message(a, b, "Second")

    summary = bob.get("/messages/unread-count").json()
    assert summary["total"] == 2 and summary["latest"]["snippet"] == "Second"
    assert TestClient(app).get("/messages/unread-count").status_code == 401

    first_id = fetch_one("SELECT min(id) AS id FROM messages WHERE conversation_id = :c", {"c": conv})["id"]
    since = bob.get(f"/messages/c/{conv}/since?after={first_id}").json()["messages"]
    assert [x["body"] for x in since] == ["Second"] and since[0]["mine"] is False
    assert bob.get("/messages/unread-count").json()["total"] == 0  # reading via polling marks read

    eve, _ = _person("Poll Outsider")
    assert eve.get(f"/messages/c/{conv}/since").status_code == 404


def test_notification_center_shows_messages_unread_for_5_minutes_only():
    alice, a = _person("Notify A")
    bob, b = _person("Notify B")
    m.send_message(a, b, "Fresh")
    assert fetch_one("SELECT count(*) AS n FROM notifications WHERE user_id = :b AND type = 'new_message'", {"b": b})["n"] == 0
    page = bob.get("/board?lang=en").text
    assert "unread message(s)" not in page

    execute("UPDATE messages SET created_at = now() - interval '6 minutes' WHERE recipient_id = :b", {"b": b})
    assert "You have 1 unread message(s)." in bob.get("/board?lang=en").text


def test_chat_window_json_post_and_peek():
    alice, a = _person("Dock A")
    bob, b = _person("Dock B")
    m.send_message(a, b, "Hi")
    _, conv = m.send_message(b, a, "Hello")
    token = extract_csrf(alice.get("/board").text)

    ok = alice.post(f"/messages/c/{conv}/post", data={"csrf_token": token, "body": "From the small window"})
    assert ok.json() == {"status": "sent"}
    # Bob's minimized window peeks: sees the new message but nothing becomes read.
    unread_before = bob.get("/messages/unread-count").json()["total"]
    peek = bob.get(f"/messages/c/{conv}/since?after=0&peek=1").json()
    assert "From the small window" in [x["body"] for x in peek["messages"]] and peek["other_name"] == "Dock A"
    assert bob.get("/messages/unread-count").json()["total"] == unread_before >= 1

    eve, _ = _person("Dock Outsider")
    eve_token = extract_csrf(eve.get("/board").text)
    assert eve.post(f"/messages/c/{conv}/post", data={"csrf_token": eve_token, "body": "x"}).status_code == 404


def test_dock_is_rendered_outside_messages_pages_only():
    alice, _ = _person("Dock Render")
    assert 'id="vb-chat-dock"' in alice.get("/board").text
    assert 'id="vb-chat-dock"' not in alice.get("/messages").text
    assert 'id="vb-chat-dock"' not in TestClient(app).get("/board").text  # logged out

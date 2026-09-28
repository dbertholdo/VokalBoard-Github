"""Messenger rules (app/messenger.py, docs/specs/MESSENGER.md)."""
from app import messenger as m
from app.database import execute, execute_returning, fetch_one
from tests.test_security import register_test_user


def _users(client, n=2):
    return [register_test_user(client, full_name=f"Msg User {i}")[0] for i in range(n)]


def _folder_ids(user_id, folder):
    return [c["id"] for c in m.list_conversations(user_id, folder)]


def test_first_contact_is_a_request_limited_to_one_message(client):
    a, b = _users(client)
    status, conv = m.send_message(a, b, "Hello, are you free in May?")
    again, _ = m.send_message(a, b, "Hello?? Please answer")

    assert (status, again) == ("request_sent", "request_pending")
    assert fetch_one("SELECT count(*) AS n FROM messages WHERE conversation_id = :c", {"c": conv})["n"] == 1
    assert _folder_ids(b, "requests") == [conv] and _folder_ids(b, "inbox") == []
    mine = m.list_conversations(a, "inbox")
    assert [c["id"] for c in mine] == [conv] and mine[0]["pending_mine"]
    assert m.unread_counts(b) == {"inbox": 0, "requests": 1}


def test_replying_accepts_and_the_contact_survives_a_deleted_chat(client):
    a, b = _users(client)
    _, conv = m.send_message(a, b, "Hi!")
    assert m.send_message(b, a, "Hi back")[0] == "sent"
    assert m.send_message(a, b, "Great, a second message")[0] == "sent"
    assert fetch_one("SELECT status FROM conversations WHERE id = :c", {"c": conv})["status"] == "active"

    execute("DELETE FROM conversations WHERE id = :c", {"c": conv})  # e.g. expired after 60 days
    assert m.send_message(a, b, "Hello again months later")[0] == "sent"


def test_accept_and_decline(client):
    a, b, c = _users(client, 3)
    _, conv_ab = m.send_message(a, b, "Request 1")
    _, conv_cb = m.send_message(c, b, "Request 2")

    assert not m.accept_request(a, conv_ab)  # the sender can't accept their own request
    assert m.accept_request(b, conv_ab)
    assert m.decline_request(b, conv_cb)

    assert _folder_ids(b, "requests") == []
    assert _folder_ids(b, "inbox") == [conv_ab]
    # The declined sender isn't told: still "waiting", and can't push more.
    assert m.list_conversations(c, "inbox")[0]["pending_mine"]
    assert m.send_message(c, b, "Why no answer?")[0] == "request_pending"


def test_a_match_counts_as_consent(client):
    artist, contractor = _users(client)
    execute(
        """INSERT INTO job_matches (listing_id, vacancy_id, artist_user_id, contractor_user_id, status)
           VALUES (NULL, NULL, :a, :c, 'confirmed')""",
        {"a": artist, "c": contractor},
    )
    assert m.send_message(artist, contractor, "About our concert")[0] == "sent"


def test_blocking_wins_in_both_directions(client):
    a, b = _users(client)
    execute("INSERT INTO blocked_users (blocker_id, blocked_id) VALUES (:a, :b)", {"a": b, "b": a})
    assert m.send_message(a, b, "Hi")[0] == "blocked"
    assert m.send_message(b, a, "Hi")[0] == "blocked"


def test_only_participants_see_a_conversation(client):
    a, b, outsider = _users(client, 3)
    _, conv = m.send_message(a, b, "Private")
    assert m.conversation_for(a, conv) and m.conversation_for(b, conv)
    assert m.conversation_for(outsider, conv) is None


def test_thread_marks_read_and_never_exposes_seen(client):
    a, b = _users(client)
    m.send_message(a, b, "One")
    _, conv = m.send_message(b, a, "Two")
    rows = m.thread(a, conv)
    assert [r["body"] for r in rows] == ["One", "Two"]
    assert all("read_at" not in r for r in rows)
    assert m.unread_counts(a)["inbox"] == 0
    assert all("read_at" not in c for c in m.list_conversations(b, "inbox"))


def test_hide_until_the_next_message(client):
    a, b = _users(client)
    m.send_message(a, b, "Hi")
    _, conv = m.send_message(b, a, "Hi")
    assert m.hide_conversation(a, conv)
    assert _folder_ids(a, "inbox") == []
    m.send_message(b, a, "Still there?")
    assert _folder_ids(a, "inbox") == [conv]


def test_archived_folder_and_unarchive(client):
    a, b = _users(client)
    m.send_message(a, b, "Hi")
    _, conv = m.send_message(b, a, "Hi")
    assert _folder_ids(a, "archived") == []
    m.hide_conversation(a, conv)
    assert _folder_ids(a, "archived") == [conv]
    assert _folder_ids(b, "archived") == []  # per side
    assert m.unarchive_conversation(a, conv)
    assert _folder_ids(a, "archived") == [] and _folder_ids(a, "inbox") == [conv]


def test_report_message_snapshot_and_permissions(client):
    a, b = _users(client)
    m.send_message(a, b, "Rude text")
    msg = fetch_one("SELECT id FROM messages WHERE sender_id = :a ORDER BY id DESC LIMIT 1", {"a": a})["id"]

    assert m.report_message(a, msg, "my own message") == "not_allowed"
    assert m.report_message(b, msg, "x") == "invalid"
    assert m.report_message(b, msg, "Insulting me") == "reported"
    assert m.report_message(b, msg, "Insulting me again") == "already"
    report = fetch_one("SELECT reported_user_id, body_snapshot, status FROM message_reports WHERE message_id = :m", {"m": msg})
    assert (report["reported_user_id"], report["body_snapshot"], report["status"]) == (a, "Rude text", "open")


def test_listing_context_is_kept_on_the_message(client):
    a, b = _users(client)
    listing = execute_returning(
        """INSERT INTO listings (author_id, listing_type, title, description, city, country, event_date)
           VALUES (:b, 'seeking_singer', 'Requiem München', 'A valid listing description.', 'München', 'DE', CURRENT_DATE + 10)
           RETURNING id""",
        {"b": b},
    )
    _, conv = m.send_message(a, b, "About your listing", listing_id=listing["id"])
    assert m.thread(b, conv)[0]["listing_title"] == "Requiem München"

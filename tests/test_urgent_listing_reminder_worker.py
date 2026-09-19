"""P5 Etapa 2 (18/09/2026): lembrete de 6h pra vaga urgente ainda sem
Match — ver app/urgent_listing_reminder_worker.py."""
from datetime import date, timedelta

from app.database import execute, execute_returning, fetch_one
from app.urgent_listing_reminder_worker import run_urgent_listing_reminder
from tests.test_security import register_test_user


def _make_urgent_listing(user_id: int, marked_hours_ago: float, reminder_sent=False):
    row = execute_returning(
        """
        INSERT INTO listings (author_id, listing_type, title, description, city, state, country, event_date,
                               is_urgent, urgent_marked_at)
        VALUES (:author_id, 'seeking_singer', 'Sectest Reminder Listing', 'A valid description.', 'München', 'Bayern', 'DE', :event_date,
                TRUE, now() - interval '1 hour' * :hours_ago)
        RETURNING id
        """,
        {
            "author_id": user_id, "event_date": date.today() + timedelta(days=10),
            "hours_ago": marked_hours_ago,
        },
    )
    if reminder_sent:
        execute("UPDATE listings SET urgent_reminder_sent_at = now() WHERE id = :id", {"id": row["id"]})
    return row["id"]


def test_dry_run_counts_but_does_not_mark_sent(client):
    user_id, _, _ = register_test_user(client)
    listing_id = _make_urgent_listing(user_id, marked_hours_ago=7)

    result = run_urgent_listing_reminder(dry_run=True)
    assert result["reminded"] >= 1

    listing = fetch_one("SELECT urgent_reminder_sent_at FROM listings WHERE id = :id", {"id": listing_id})
    assert listing["urgent_reminder_sent_at"] is None


def test_sends_and_marks_reminder_sent_after_six_hours(client):
    user_id, _, _ = register_test_user(client)
    listing_id = _make_urgent_listing(user_id, marked_hours_ago=7)

    run_urgent_listing_reminder()

    listing = fetch_one("SELECT urgent_reminder_sent_at FROM listings WHERE id = :id", {"id": listing_id})
    assert listing["urgent_reminder_sent_at"] is not None


def test_listing_marked_less_than_six_hours_ago_is_left_alone(client):
    user_id, _, _ = register_test_user(client)
    listing_id = _make_urgent_listing(user_id, marked_hours_ago=2)

    run_urgent_listing_reminder()

    listing = fetch_one("SELECT urgent_reminder_sent_at FROM listings WHERE id = :id", {"id": listing_id})
    assert listing["urgent_reminder_sent_at"] is None


def test_already_reminded_listing_is_not_reminded_twice(client):
    from app.database import fetch_one as _fetch_one

    user_id, _, _ = register_test_user(client)
    listing_id = _make_urgent_listing(user_id, marked_hours_ago=8, reminder_sent=True)
    sent_at_before = _fetch_one(
        "SELECT urgent_reminder_sent_at FROM listings WHERE id = :id", {"id": listing_id}
    )["urgent_reminder_sent_at"]

    run_urgent_listing_reminder()

    sent_at_after = _fetch_one(
        "SELECT urgent_reminder_sent_at FROM listings WHERE id = :id", {"id": listing_id}
    )["urgent_reminder_sent_at"]
    assert sent_at_after == sent_at_before  # não foi tocado de novo (já tinha sido lembrado)


def test_listing_with_a_match_already_is_not_reminded(client):
    from app.match_service import create_invitation, respond_invitation

    user_id, _, _ = register_test_user(client, full_name="Reminder Contractor")
    artist_id, _, _ = register_test_user(client, full_name="Reminder Artist")
    listing_id = _make_urgent_listing(user_id, marked_hours_ago=7)

    voice_type_id = fetch_one("SELECT id FROM voice_types ORDER BY id LIMIT 1")["id"]
    vacancy = execute_returning(
        "INSERT INTO listing_vacancies (listing_id, voice_type_id) VALUES (:listing_id, :voice_type_id) RETURNING id",
        {"listing_id": listing_id, "voice_type_id": voice_type_id},
    )
    invite = create_invitation(vacancy["id"], artist_id, user_id)
    respond_invitation(invite["id"], artist_id, "accept")

    run_urgent_listing_reminder()

    listing = fetch_one("SELECT urgent_reminder_sent_at FROM listings WHERE id = :id", {"id": listing_id})
    assert listing["urgent_reminder_sent_at"] is None

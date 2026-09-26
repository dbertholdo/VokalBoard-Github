"""Automatic erasure of accounts past the 6-month reactivation window
(Daniel, 2026-09-26) — app/account_purge.py, run by the retention worker."""
import os

from app.account_purge import purge_expired_accounts
from app.avatars import avatar_path_for
from app.database import engine, execute, execute_returning, fetch_one
from tests.test_security import register_test_user


def _deactivate(user_id, months_ago):
    execute(f"UPDATE users SET deleted_at = now() - interval '{months_ago} months' WHERE id = :id", {"id": user_id})


def _match(contractor_id, artist_id):
    listing = execute_returning(
        """INSERT INTO listings (author_id, listing_type, title, description, city, country, event_date)
           VALUES (:a, 'seeking_singer', 'Purge test', 'A valid listing description.', 'München', 'DE', CURRENT_DATE + 10)
           RETURNING id""",
        {"a": contractor_id},
    )
    voice = fetch_one("SELECT id FROM voice_types ORDER BY id LIMIT 1")["id"]
    vacancy = execute_returning(
        "INSERT INTO listing_vacancies (listing_id, voice_type_id) VALUES (:l, :v) RETURNING id",
        {"l": listing["id"], "v": voice},
    )
    match = execute_returning(
        """INSERT INTO job_matches (listing_id, vacancy_id, artist_user_id, contractor_user_id, status)
           VALUES (:l, :v, :artist, :contractor, 'confirmed') RETURNING id""",
        {"l": listing["id"], "v": vacancy["id"], "artist": artist_id, "contractor": contractor_id},
    )
    return listing["id"], match["id"]


def _run(dry_run=False):
    with engine.begin() as conn:
        return purge_expired_accounts(conn, dry_run=dry_run)


def test_expired_accounts_are_erased_with_matches_and_avatar(client):
    expired_artist, _, _ = register_test_user(client, full_name="Purge Expired Artist")
    expired_owner, _, _ = register_test_user(client, full_name="Purge Expired Owner")
    other, _, _ = register_test_user(client, full_name="Purge Counterpart")

    other_listing, match_as_artist = _match(contractor_id=other, artist_id=expired_artist)
    own_listing, match_as_owner = _match(contractor_id=expired_owner, artist_id=other)
    _deactivate(expired_artist, 7)
    _deactivate(expired_owner, 7)

    avatar = avatar_path_for(expired_artist)
    os.makedirs(os.path.dirname(avatar), exist_ok=True)
    with open(avatar, "wb") as f:
        f.write(b"fake")

    result = _run()
    assert result["accounts_failed"] == 0
    assert result["accounts_purged"] >= 2

    for uid in (expired_artist, expired_owner):
        assert fetch_one("SELECT id FROM users WHERE id = :id", {"id": uid}) is None
    for mid in (match_as_artist, match_as_owner):
        assert fetch_one("SELECT id FROM job_matches WHERE id = :id", {"id": mid}) is None
    assert fetch_one("SELECT id FROM listings WHERE id = :id", {"id": own_listing}) is None
    assert not os.path.exists(avatar)
    # The counterpart and their own listing are untouched.
    assert fetch_one("SELECT id FROM users WHERE id = :id", {"id": other}) is not None
    assert fetch_one("SELECT id FROM listings WHERE id = :id", {"id": other_listing}) is not None


def test_accounts_inside_the_window_and_active_accounts_are_kept(client):
    recent, _, _ = register_test_user(client, full_name="Purge Recent")
    active, _, _ = register_test_user(client, full_name="Purge Active")
    _deactivate(recent, 5)

    _run()

    assert fetch_one("SELECT id FROM users WHERE id = :id", {"id": recent}) is not None
    assert fetch_one("SELECT id FROM users WHERE id = :id", {"id": active}) is not None


def test_dry_run_counts_without_deleting(client):
    user_id, _, _ = register_test_user(client, full_name="Purge Dry Run")
    _deactivate(user_id, 8)

    result = _run(dry_run=True)

    assert result["accounts_due"] >= 1
    assert fetch_one("SELECT id FROM users WHERE id = :id", {"id": user_id}) is not None

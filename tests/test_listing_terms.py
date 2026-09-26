"""Backlog #55: a listing's voice type + fee come from one source
(app/listing_terms.py) — vacancies for job listings, own columns for
self-ads. No copy on `listings` for job listings any more."""
import pytest
from sqlalchemy.exc import IntegrityError

from app.database import execute, execute_returning, fetch_all, fetch_one
from app.notifications import _matching_recipients
from tests.test_security import extract_csrf, job_vacancy_fields, login, register_test_user


def _voice(name):
    return fetch_one("SELECT id FROM voice_types WHERE name = :n", {"n": name})["id"]


def _job(author_id, vacancies):
    listing = execute_returning(
        """INSERT INTO listings (author_id, listing_type, title, description, city, country, event_date, repertoire)
           VALUES (:a, 'seeking_singer', 'Terms Job', 'A valid listing description.', 'München', 'DE', CURRENT_DATE + 10, 'Requiem')
           RETURNING id""",
        {"a": author_id},
    )["id"]
    for voice, fee in vacancies:
        execute("INSERT INTO listing_vacancies (listing_id, voice_type_id, fee_amount) VALUES (:l, :v, :f)",
                {"l": listing, "v": voice, "f": fee})
    return listing


def _singer(client, voice_id, name):
    uid, email, password = register_test_user(client, full_name=name)
    execute("UPDATE users SET email_verified = TRUE, notify_matches = TRUE, city = 'München' WHERE id = :id", {"id": uid})
    execute("DELETE FROM singer_profile_voice_types WHERE user_id = :id", {"id": uid})
    execute("UPDATE singer_profiles SET voice_type_id = :v WHERE user_id = :id", {"v": voice_id, "id": uid})
    return uid, email, password


def test_creating_a_job_listing_leaves_no_copy_on_listings(client):
    uid, email, password = register_test_user(client, full_name="Terms Author")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": uid})
    login(client, email, password)
    token = extract_csrf(client.get("/listings/new").text)
    client.post("/listings/new", data={
        "csrf_token": token, "listing_type": "seeking_singer", "title": "No copy", "description": "Test description.",
        "state": "Bayern", "city": "München", "country": "DE", "repertoire": "Requiem", "venue": "", "ensemble_type": "",
        "event_date": "2030-01-10", **job_vacancy_fields(fee_amount="300"),
    }, follow_redirects=False)
    row = fetch_one("SELECT id, voice_type_id, fee_amount, fee_negotiable FROM listings WHERE author_id = :a", {"a": uid})
    assert (row["voice_type_id"], row["fee_amount"], row["fee_negotiable"]) == (None, None, False)
    terms = fetch_all("SELECT fee_amount FROM listing_terms WHERE listing_id = :l", {"l": row["id"]})
    assert [t["fee_amount"] for t in terms] == [300]
    with pytest.raises(IntegrityError):
        execute("UPDATE listings SET fee_amount = 1 WHERE id = :l", {"l": row["id"]})


def test_multi_voice_listing_matches_each_of_its_voices(client):
    soprano, tenor, bass = _voice("Soprano"), _voice("Tenor"), _voice("Bass")
    author, _, _ = register_test_user(client, full_name="Terms Conductor")
    listing = _job(author, [(soprano, 250), (tenor, None)])

    viewer, v_email, v_password = register_test_user(client, full_name="Terms Filter Viewer")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": viewer})
    login(client, v_email, v_password)
    # Board voice filter finds it by either voice (the old copy was empty → never matched).
    for voice in (soprano, tenor):
        assert f"/listings/{listing}" in client.get(f"/board?voice_type_id={voice}").text
    assert f"/listings/{listing}" not in client.get(f"/board?voice_type_id={bass}").text

    # E-mail alerts go to sopranos and tenors, not basses.
    s_id, s_email, _ = _singer(client, soprano, "Terms Soprano")
    b_id, b_email, _ = _singer(client, bass, "Terms Bass")
    alerted = {r["email"] for r in _matching_recipients("seeking_singer", author, [soprano, tenor])}
    assert s_email in alerted and b_email not in alerted


def test_cards_show_the_single_vacancy_fee_and_self_ads_keep_theirs(client):
    soprano = _voice("Soprano")
    author, _, _ = register_test_user(client, full_name="Terms Card Author")
    job = _job(author, [(soprano, 275)])
    self_ad = execute_returning(
        """INSERT INTO listings (author_id, listing_type, title, description, city, country, available_from, available_until,
                                 voice_type_id, fee_amount, fee_currency)
           VALUES (:a, 'singer_available', 'Terms Self Ad', 'A valid listing description.', 'Berlin', 'DE',
                   CURRENT_DATE, CURRENT_DATE + 20, :v, 180, 'EUR') RETURNING id""",
        {"a": author, "v": soprano},
    )["id"]
    summary = {r["listing_id"]: r for r in fetch_all(
        "SELECT listing_id, fee_amount, voice_type_id FROM listing_terms WHERE listing_id IN (:j, :s)", {"j": job, "s": self_ad})}
    assert summary[job]["fee_amount"] == 275 and summary[self_ad]["fee_amount"] == 180
    viewer, email, password = register_test_user(client, full_name="Terms Viewer")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": viewer})
    login(client, email, password)
    board = client.get("/board").text
    assert "275" in board and "180" in board

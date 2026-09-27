"""Jobs & Matches cleanup (2026-09-27): listing form validation, atomic create/edit,
report dedupe, invitation rules, safe redirects, Match fee from the vacancy."""
from datetime import date, timedelta

from app.database import execute, fetch_all, fetch_one
from app.match_service import create_invitation, respond_invitation
from tests.test_security import DEFAULT_PASSWORD, extract_csrf, job_vacancy_fields, login, register_test_user


def _verified(client, **kw):
    uid, email, pw = register_test_user(client, **kw)
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": uid})
    return uid


def _listing_data(token, **over):
    data = {"csrf_token": token, "listing_type": "seeking_singer", "title": "Sectest Jobs Cleanup",
            "description": "Test description.", "state": "Bayern", "city": "München", "country": "DE",
            "repertoire": "Requiem", "venue": "", "ensemble_type": "", **job_vacancy_fields(fee_amount="300"),
            "event_date": (date.today() + timedelta(days=10)).isoformat()}
    data.update(over)
    return data


def _post(client, **over):
    token = extract_csrf(client.get("/listings/new").text)
    return client.post("/listings/new", data=_listing_data(token, **over), follow_redirects=False)


def _my_listing_ids(uid):
    return [r["id"] for r in fetch_all("SELECT id FROM listings WHERE author_id = :id ORDER BY id", {"id": uid})]


def test_bad_listing_input_is_a_form_error_not_500_or_json(client):
    uid = _verified(client)
    for over in ({"listing_type": "nonsense"}, {"event_date": ""}, {"title": "   "},
                 {"sheet_music_available": "1", "sheet_music_url": "javascript:alert(1)"},
                 {"listing_type": "conductor_available", "voice_type_id": "abc"}):
        r = _post(client, **over)
        assert r.status_code == 400, over
        assert "<form" in r.text, f"expected the form back, got: {r.text[:120]}"
    assert _my_listing_ids(uid) == []
    # Vacancy rows survive the error now (the fee we typed is back in the form).
    assert 'value="300' in _post(client, event_date="").text


def test_self_ad_with_amount_and_negotiable_saves_instead_of_500(client):
    uid = _verified(client)
    r = _post(client, listing_type="conductor_available", fee_amount="200", fee_negotiable="1", repertoire="", city="")
    assert r.status_code == 303
    row = fetch_one("SELECT fee_amount, fee_negotiable FROM listings WHERE author_id = :id", {"id": uid})
    assert row["fee_amount"] is None and row["fee_negotiable"] is True


def test_edit_keeps_listing_type_and_vacancies(client):
    uid = _verified(client)
    assert _post(client).status_code == 303
    lid = _my_listing_ids(uid)[0]
    token = extract_csrf(client.get(f"/listings/{lid}/edit").text)
    data = _listing_data(token, listing_type="singer_available", title="Renamed")
    assert client.post(f"/listings/{lid}/edit", data=data, follow_redirects=False).status_code == 303
    row = fetch_one("SELECT listing_type, title FROM listings WHERE id = :id", {"id": lid})
    assert row == {"listing_type": "seeking_singer", "title": "Renamed"}
    assert fetch_one("SELECT total_slots FROM listing_vacancies WHERE listing_id = :id", {"id": lid})


def test_report_is_stored_once_per_person(client):
    author = _verified(client)
    assert _post(client).status_code == 303
    lid = _my_listing_ids(author)[0]
    client.cookies.clear()
    _verified(client)
    for _ in range(3):
        token = extract_csrf(client.get(f"/listings/{lid}").text)
        client.post(f"/listings/{lid}/report", data={"csrf_token": token, "reason": "Looks like a scam listing"})
    assert len(fetch_all("SELECT id FROM listing_reports WHERE listing_id = :id", {"id": lid})) == 1


def test_invitation_rules_and_delete_expires_pending(client):
    author = _verified(client)
    assert _post(client).status_code == 303
    lid = _my_listing_ids(author)[0]
    vacancy = fetch_one("SELECT id FROM listing_vacancies WHERE listing_id = :id", {"id": lid})["id"]
    client.cookies.clear()
    singer = _verified(client)
    client.cookies.clear()
    conductor_uid, _, _ = register_test_user(client)
    execute("UPDATE users SET role = 'conductor', email_verified = TRUE WHERE id = :id", {"id": conductor_uid})
    client.cookies.clear()
    unverified, _, _ = register_test_user(client)

    assert create_invitation(vacancy, conductor_uid, conductor_uid)["reason"] == "invitation_error_not_allowed"  # wrong role
    assert create_invitation(vacancy, unverified, unverified)["reason"] == "invitation_error_not_allowed"  # unverified
    execute("INSERT INTO blocked_users (blocker_id, blocked_id) VALUES (:a, :b)", {"a": author, "b": singer})
    assert create_invitation(vacancy, singer, singer)["ok"] is False  # blocked
    execute("DELETE FROM blocked_users WHERE blocker_id = :a", {"a": author})
    invite = create_invitation(vacancy, singer, singer)
    assert invite["ok"]

    # Delete through the route (as the author) so the pending application is expired.
    client.cookies.clear()
    login(client, fetch_one("SELECT email FROM users WHERE id = :id", {"id": author})["email"], DEFAULT_PASSWORD)
    token = extract_csrf(client.get("/my-listings").text)
    client.post(f"/listings/{lid}/delete", data={"csrf_token": token})
    assert fetch_one("SELECT status FROM job_invitations WHERE id = :id", {"id": invite["id"]})["status"] == "expired"
    assert respond_invitation(invite["id"], author, "accept")["ok"] is False


def test_invite_next_param_cannot_redirect_off_site(client):
    author = _verified(client)
    assert _post(client).status_code == 303
    lid = _my_listing_ids(author)[0]
    vacancy = fetch_one("SELECT id FROM listing_vacancies WHERE listing_id = :id", {"id": lid})["id"]
    token = extract_csrf(client.get("/my-listings").text)
    r = client.post(f"/listings/{lid}/invite", data={"csrf_token": token, "artist_user_id": "1", "vacancy_id": str(vacancy),
                                                     "next": "https://evil.example"}, follow_redirects=False)
    assert r.headers["location"].startswith("/users/")


def test_match_history_shows_the_vacancy_fee(client):
    author = _verified(client)
    assert _post(client).status_code == 303
    lid = _my_listing_ids(author)[0]
    vacancy = fetch_one("SELECT id FROM listing_vacancies WHERE listing_id = :id", {"id": lid})["id"]
    client.cookies.clear()
    singer = _verified(client)
    invite = create_invitation(vacancy, singer, singer)
    assert respond_invitation(invite["id"], author, "accept")["ok"]
    html = client.get("/profile/matches").text
    assert "300" in html

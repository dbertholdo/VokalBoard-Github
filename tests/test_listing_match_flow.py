"""B1 (2026-09-28): the Match flow is visible on the listing page itself —
the author answers applications inline, the artist gets a clear
"I'm available!" button (or an explanation when they can't apply)."""
from app.database import execute, fetch_one
from app.match_service import create_invitation
from tests.test_security import login, register_test_user
from tests.test_urgency_match_reward import _make_vacancy


def _verified_user(client, name):
    user_id, email, password = register_test_user(client, full_name=name)
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    return user_id, email, password


def _as(client, email, password):
    client.cookies.clear()
    login(client, email, password)


def test_artist_sees_available_button_and_author_sees_inline_accept(client):
    author_id, author_email, author_pw = _verified_user(client, "Flow Author")
    artist_id, artist_email, artist_pw = _verified_user(client, "Flow Artist")
    listing_id, vacancy_id = _make_vacancy(author_id)

    _as(client, artist_email, artist_pw)
    page = client.get(f"/listings/{listing_id}").text
    assert f'action="/vacancies/{vacancy_id}/apply"' in page
    assert "vacancy-apply-button" in page

    # The artist applies (candidacy = started by the artist).
    result = create_invitation(vacancy_id, artist_id, artist_id)
    assert result["ok"] is True

    _as(client, author_email, author_pw)
    page = client.get(f"/listings/{listing_id}").text
    assert 'id="candidates"' in page
    assert "Flow Artist" in page
    assert f'action="/invitations/{result["id"]}/respond"' in page
    assert f'name="next" value="/listings/{listing_id}"' in page
    assert f'href="/listings/{listing_id}/candidates"' in page


def test_wrong_role_gets_an_explanation_instead_of_nothing(client):
    author_id, _, _ = _verified_user(client, "Role Author")
    _, email, password = _verified_user(client, "Role Singer")
    listing_id, _ = _make_vacancy(author_id)
    execute("UPDATE listings SET listing_type = 'seeking_conductor' WHERE id = :id", {"id": listing_id})
    execute("UPDATE listing_vacancies SET voice_type_id = NULL WHERE listing_id = :id", {"id": listing_id})
    assert fetch_one("SELECT role FROM users WHERE email = :e", {"e": email})["role"] == "singer"

    _as(client, email, password)
    page = client.get(f"/listings/{listing_id}").text
    assert "vacancy-apply-form" not in page
    assert 'class="field-help"' in page and ("conductor" in page.lower() or "Dirigent" in page)
    assert 'id="candidates"' not in page


def test_matches_entry_opens_open_tab_only_when_something_waits(client):
    author_id, author_email, author_pw = _verified_user(client, "Entry Author")
    artist_id, _, _ = _verified_user(client, "Entry Artist")
    _as(client, author_email, author_pw)
    assert client.get("/matches", follow_redirects=False).headers["location"] == "/profile/matches?view=confirmed"

    listing_id, vacancy_id = _make_vacancy(author_id)
    assert create_invitation(vacancy_id, artist_id, artist_id)["ok"]
    assert client.get("/matches", follow_redirects=False).headers["location"] == "/invitations?tab=pending"
    page = client.get("/invitations?tab=pending").text
    assert 'href="/profile/matches?view=confirmed"' in page and 'href="/profile/matches?view=history"' in page
    assert client.get("/profile/matches?view=history").status_code == 200


def test_confirmed_and_history_views_split_by_event_date(client):
    from app.match_service import respond_invitation
    author_id, author_email, author_pw = _verified_user(client, "Views Author")
    artist_id, _, _ = _verified_user(client, "Views Artist")
    listing_id, vacancy_id = _make_vacancy(author_id)  # event in 10 days
    invite = create_invitation(vacancy_id, artist_id, artist_id)
    assert respond_invitation(invite["id"], author_id, "accept")["ok"]

    _as(client, author_email, author_pw)
    assert "Sectest Reward Listing" in client.get("/profile/matches?view=confirmed").text
    assert "Sectest Reward Listing" not in client.get("/profile/matches?view=history").text
    execute("UPDATE listings SET event_date = CURRENT_DATE - 3 WHERE id = :id", {"id": listing_id})
    execute("UPDATE job_matches SET listing_snapshot = listing_snapshot - 'event_date' WHERE listing_id = :id", {"id": listing_id})
    assert "Sectest Reward Listing" in client.get("/profile/matches?view=history").text

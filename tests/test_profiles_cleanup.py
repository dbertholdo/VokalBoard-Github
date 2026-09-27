"""Profile & people-search cleanup (2026-09-27)."""
from app.badges import get_user_badges, top_badges, top_badges_for_users
from app.database import execute, fetch_one
from tests.test_security import extract_csrf, register_test_user


def _verify(uid):
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": uid})


def _save_profile(client, **fields):
    token = extract_csrf(client.get("/profile").text)
    data = {"csrf_token": token, "country": "DE", "bio": "Lyric soprano", **fields}
    files = fields.pop("_files", None)
    data.pop("_files", None)
    return client.post("/profile", data=data, files=files, follow_redirects=False)


def test_invalid_photo_no_longer_drops_the_rest_of_the_form(client):
    uid, _, _ = register_test_user(client)
    r = _save_profile(client, bio="Kept even with a bad photo", _files={"avatar": ("x.jpg", b"not an image", "image/jpeg")})
    assert r.status_code == 400
    assert fetch_one("SELECT bio FROM singer_profiles WHERE user_id = :id", {"id": uid})["bio"] == "Kept even with a bad photo"


def test_bad_voice_type_and_overlong_fields_are_form_errors_not_500(client):
    uid, _, _ = register_test_user(client)
    assert _save_profile(client, voice_type_id="abc").status_code == 400
    assert _save_profile(client, voice_type_id="999999").status_code == 400
    assert _save_profile(client, city="K" * 300, fach="F" * 300).status_code == 303
    row = fetch_one("SELECT u.city, sp.fach FROM users u JOIN singer_profiles sp ON sp.user_id = u.id WHERE u.id = :id", {"id": uid})
    assert len(row["city"]) == 100 and len(row["fach"]) == 100


def test_rating_is_blocked_across_a_block_and_for_unverified_accounts(client):
    target, _, _ = register_test_user(client)
    client.cookies.clear()
    rater, _, _ = register_test_user(client)

    def rate():
        token = extract_csrf(client.get(f"/users/{target}").text)
        client.post(f"/users/{target}/rate", data={"csrf_token": token, "stars": "1", "comment": "hi", "listing_id": "99999999"})
        return fetch_one("SELECT stars FROM ratings WHERE rater_id = :r AND rated_id = :t", {"r": rater, "t": target})

    assert rate() is None  # unverified
    _verify(rater)
    execute("INSERT INTO blocked_users (blocker_id, blocked_id) VALUES (:a, :b)", {"a": target, "b": rater})
    assert rate() is None  # blocked by the target
    execute("DELETE FROM blocked_users WHERE blocker_id = :a", {"a": target})
    assert rate()["stars"] == 1  # stale listing_id no longer 500s


def test_share_links_use_the_site_address_and_a_valid_path(client):
    uid, _, _ = register_test_user(client)
    html = client.get(f"/users/{uid}").text
    assert "vokalboard.de" not in html and "/u/users/" not in html
    assert f"/users/{uid}" in html


def test_people_search_survives_bad_filters_and_batches_badges(client):
    uid, _, _ = register_test_user(client)
    _verify(uid)
    assert client.get("/people?voice_type_id=abc&city=%25_").status_code == 200
    assert top_badges_for_users([uid])[uid] == top_badges(uid)
    assert [b["key"] for b in get_user_badges(uid)]  # single-user path still works

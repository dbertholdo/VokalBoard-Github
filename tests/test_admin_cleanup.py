"""Admin cleanup (2026-09-27): privilege changes and "delete forever" need the
admin's password again and are audited (CLAUDE.md §2.4); deleting a user with a
Match no longer 500s."""
from datetime import date

from app.database import execute, execute_returning, fetch_one
from tests.test_security import extract_csrf, login, register_test_user


def _god(client):
    uid, email, password = register_test_user(client, full_name="Cleanup God")
    execute("UPDATE users SET role_level = 3, is_admin = TRUE, email_verified = TRUE WHERE id = :id", {"id": uid})
    login(client, email, password)
    return uid, password


def _audit(action, actor):
    return fetch_one("SELECT details FROM audit_log WHERE action = :a AND actor_user_id = :u ORDER BY id DESC LIMIT 1",
                     {"a": action, "u": actor})


def test_privilege_change_needs_password_and_is_audited(client):
    target, _, _ = register_test_user(client)
    god, password = _god(client)
    token = extract_csrf(client.get(f"/admin/users/{target}").text)
    r = client.post(f"/admin/users/{target}/toggle-admin", data={"csrf_token": token, "current_password": "wrong!1a"},
                    follow_redirects=False)
    assert "auth_failed=1" in r.headers["location"]
    assert fetch_one("SELECT role_level FROM users WHERE id = :id", {"id": target})["role_level"] == 0
    assert _audit("toggle_admin_failed_auth", god)

    client.post(f"/admin/users/{target}/toggle-admin", data={"csrf_token": token, "current_password": password})
    assert fetch_one("SELECT role_level FROM users WHERE id = :id", {"id": target})["role_level"] == 2
    assert "0->2" in _audit("toggle_admin", god)["details"]


def test_delete_forever_needs_password_and_works_with_a_match(client):
    target, _, _ = register_test_user(client)
    other, _, _ = register_test_user(client)
    listing = execute_returning(
        "INSERT INTO listings (author_id, listing_type, title, description, city, country, event_date) "
        "VALUES (:a, 'seeking_singer', 'Sectest', 'desc', 'Köln', 'DE', :d) RETURNING id",
        {"a": other, "d": date.today()})
    vacancy = execute_returning("INSERT INTO listing_vacancies (listing_id, voice_type_id) "
                                "VALUES (:l, (SELECT min(id) FROM voice_types)) RETURNING id", {"l": listing["id"]})
    execute("INSERT INTO job_matches (listing_id, vacancy_id, artist_user_id, contractor_user_id) VALUES (:l, :v, :a, :c)",
            {"l": listing["id"], "v": vacancy["id"], "a": target, "c": other})
    god, password = _god(client)
    token = extract_csrf(client.get(f"/admin/users/{target}").text)
    client.post(f"/admin/users/{target}/delete-forever", data={"csrf_token": token, "current_password": "nope!1a"})
    assert fetch_one("SELECT 1 FROM users WHERE id = :id", {"id": target})
    r = client.post(f"/admin/users/{target}/delete-forever", data={"csrf_token": token, "current_password": password},
                    follow_redirects=False)
    assert r.status_code == 303 and fetch_one("SELECT 1 FROM users WHERE id = :id", {"id": target}) is None
    assert _audit("admin_delete_forever", god)


def test_deactivate_is_audited(client):
    target, _, _ = register_test_user(client)
    god, _ = _god(client)
    token = extract_csrf(client.get(f"/admin/users/{target}").text)
    client.post(f"/admin/users/{target}/deactivate", data={"csrf_token": token})
    assert _audit("admin_deactivate_user", god)

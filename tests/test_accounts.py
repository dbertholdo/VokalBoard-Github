"""Account section cleanup (2026-09-27): e-mail normalization, lockout by e-mail,
sign-up validation, reset/verification e-mail cooldowns, reset-link burning, export."""
import json

from app.accounts import clean_full_name, is_valid_email, normalize_email
from app.database import execute, fetch_all, fetch_one
from tests.test_security import (
    DEFAULT_PASSWORD, _fake_ip, extract_csrf, login, register_test_user, unique_email,
)


def test_email_helpers():
    assert normalize_email("  Ana@Example.COM ") == "ana@example.com"
    assert is_valid_email("ana@example.com") and not is_valid_email("ana@example") and not is_valid_email("a b@c.de")
    assert clean_full_name("  Ana   Maria ") == "Ana Maria"
    assert clean_full_name("   ") is None and clean_full_name("x" * 151) is None


def _register_form(client, **overrides):
    headers = {"X-Forwarded-For": _fake_ip()}
    token = extract_csrf(client.get("/register", headers=headers).text)
    data = {"csrf_token": token, "category": "tenor", "full_name": "Case Test", "email": unique_email(),
            "password": DEFAULT_PASSWORD, "city": "Köln", "state": "Nordrhein-Westfalen", "country": "DE",
            "phone": "", "bio": "", "composer_hashtags": "Mozart", "audio_links": "", "ensemble_name": "",
            "ref": "", "website": "", "cf-turnstile-response": ""}
    data.update(overrides)
    return client.post("/register", data=data, headers=headers, follow_redirects=False)


def test_signup_stores_normalized_email_and_creates_profile(client):
    email = unique_email()
    assert _register_form(client, email="  " + email.upper() + " ").status_code == 303
    user = fetch_one("SELECT id, email FROM users WHERE email = :e", {"e": email})
    assert user, "e-mail should be stored trimmed + lowercase"
    assert fetch_one("SELECT 1 FROM singer_profiles WHERE user_id = :id", {"id": user["id"]})
    assert fetch_one("SELECT tag FROM singer_composer_tags WHERE user_id = :id", {"id": user["id"]})["tag"] == "Mozart"


def test_signup_rejects_duplicate_in_other_case_blank_name_and_bad_email(client):
    _, email, _ = register_test_user(client)
    assert _register_form(client, email=email.upper()).status_code == 400
    assert _register_form(client, full_name="   ").status_code == 400
    assert _register_form(client, email="not-an-email").status_code == 400


def test_login_is_case_insensitive_and_lockout_cannot_be_dodged_by_case(client):
    _, email, password = register_test_user(client)
    client.cookies.clear()
    assert login(client, email.upper(), password).status_code == 303
    client.cookies.clear()
    for i in range(5):
        variant = email.upper() if i % 2 else email.title()
        login(client, variant, "wrong-password-1!")
    # Locked for every spelling of the address — including the right password.
    assert login(client, email, password).status_code == 429


def test_forgot_password_sends_at_most_one_email_per_cooldown(client):
    uid, email, _ = register_test_user(client)
    for _ in range(3):
        token = extract_csrf(client.get("/forgot-password").text)
        client.post("/forgot-password", data={"csrf_token": token, "email": email.upper(), "website": "", "cf-turnstile-response": ""})
    assert len(fetch_all("SELECT id FROM password_reset_tokens WHERE user_id = :id", {"id": uid})) == 1


def test_password_reset_burns_every_open_link(client):
    uid, _, _ = register_test_user(client)
    for tok in ("tokA_" + str(uid), "tokB_" + str(uid)):
        execute("INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (:u, :t, now() + interval '1 hour')", {"u": uid, "t": tok})
    client.cookies.clear()
    page = client.get(f"/reset-password?token=tokA_{uid}")
    r = client.post("/reset-password", data={"csrf_token": extract_csrf(page.text), "token": f"tokA_{uid}", "password": "N3w!password"})
    assert r.status_code == 200
    assert fetch_one("SELECT used_at FROM password_reset_tokens WHERE token = :t", {"t": f"tokB_{uid}"})["used_at"] is not None


def test_resend_verification_is_rate_limited(client):
    uid, _, _ = register_test_user(client)  # sign-up already sent one
    token = extract_csrf(client.get("/profile").text)
    client.post("/resend-verification", data={"csrf_token": token})
    assert len(fetch_all("SELECT id FROM email_verification_tokens WHERE user_id = :id", {"id": uid})) == 1


def test_wrong_current_password_on_delete_counts_toward_lockout(client):
    uid, email, _ = register_test_user(client)
    for _ in range(5):
        token = extract_csrf(client.get("/profile").text)
        client.post("/profile/delete-account", data={"csrf_token": token, "current_password": "nope-nope-1!"})
    assert fetch_one("SELECT locked_until FROM login_lockouts WHERE email = :e", {"e": email})["locked_until"] is not None
    assert fetch_one("SELECT deleted_at FROM users WHERE id = :id", {"id": uid})["deleted_at"] is None


def test_data_export_includes_account_sections(client):
    register_test_user(client)
    data = json.loads(client.get("/profile/export").text)
    for key in ("works", "spoken_languages", "notas_ledger", "invitations_and_applications", "matches"):
        assert key in data
    assert {"state", "country", "preferred_language"} <= set(data["account"])

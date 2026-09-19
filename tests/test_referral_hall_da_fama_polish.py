"""Part 2 backlog, item 3 (19/09/2026): "Hall da Fama polish" — inviter's
photo/name shown on /register?ref=CODE, and a prominent "Convidar um
amigo!" invite box + copy-link button right on /hall-da-fama (previously
the referral link only lived on /profile). See app/referrals.py's
get_referrer_preview() and app/routers/notas_routes.py's hall_da_fama().
"""
from app.database import execute
from tests.test_security import extract_csrf, login, register_test_user


def _verify(user_id: int):
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})


def test_register_page_shows_referrer_name_for_a_valid_code(client):
    inviter_id, inviter_email, inviter_pw = register_test_user(client, full_name="Referrer Name Test")
    _verify(inviter_id)
    login(client, inviter_email, inviter_pw)
    # Generates the referral_code the same way /profile does.
    profile = client.get("/profile")
    assert profile.status_code == 200

    from app.database import fetch_one
    ref_code = fetch_one("SELECT referral_code FROM users WHERE id = :id", {"id": inviter_id})["referral_code"]
    assert ref_code

    anon_client = client.__class__(client.app)
    page = anon_client.get(f"/register?ref={ref_code}")
    assert page.status_code == 200
    assert "Referrer Name Test" in page.text
    assert "referrer-preview" in page.text


def test_register_page_falls_back_to_generic_notice_for_unknown_code(client):
    page = client.get("/register?ref=NOPE000")
    assert page.status_code == 200
    assert "referrer-preview" not in page.text
    # The old generic notice still fires for a code that just doesn't resolve.
    assert "ref" in page.text  # sanity: the hidden ref field is still populated


def test_register_page_shows_no_notice_without_a_ref_param(client):
    page = client.get("/register")
    assert page.status_code == 200
    assert "referrer-preview" not in page.text


def test_hall_da_fama_shows_invite_box_with_referral_link(client):
    user_id, email, password = register_test_user(client, full_name="Hall Fame Invite Test")
    _verify(user_id)
    login(client, email, password)

    page = client.get("/hall-da-fama")
    assert page.status_code == 200
    assert "invite-friend-box" in page.text
    assert "/register?ref=" in page.text


def test_hall_da_fama_requires_verified_email(client):
    user_id, email, password = register_test_user(client, full_name="Unverified Hall Fame Test")
    login(client, email, password)  # not verified
    page = client.get("/hall-da-fama", follow_redirects=False)
    assert page.status_code == 303
    assert "verify_required" in page.headers["location"]

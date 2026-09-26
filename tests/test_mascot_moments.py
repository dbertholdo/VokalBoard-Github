"""Part 2 backlog, item 4 (19/09/2026): the remaining five Tangará
mascot poses, placed per app/mascot_moments.py's design writeup —
Acolhedor (login welcome, every login), Atento (one pending-item
nudge, priority-picked), Joinha (brief confirmation wink on three
success moments) and Piscadinha (Hall da Fama incentive + the 404
page's "lost bird" joke, using the alert-zone pose by Daniel's own
explicit call — see app/main.py's http_exception_handler)."""
from app.database import execute

from tests.test_security import register_test_user, extract_csrf


def test_login_shows_welcome_toast_every_time():
    from fastapi.testclient import TestClient
    from app.main import app

    c = TestClient(app)
    user_id, email, password = register_test_user(c, full_name="Welcome Test")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})

    c2 = TestClient(app)
    r = c2.get("/login")
    token = extract_csrf(r.text)
    c2.post("/login", data={"csrf_token": token, "email": email, "password": password}, follow_redirects=False)

    r2 = c2.get("/")
    assert "mascot-welcoming.png" in r2.text
    assert "Welcome Test" in r2.text

    # Doesn't repeat on the next page load in the same session...
    r3 = c2.get("/")
    assert "mascot-welcoming.png" not in r3.text

    # ...but DOES show again on a fresh login (Daniel: "Everytime I log in").
    c3 = TestClient(app)
    r = c3.get("/login")
    token = extract_csrf(r.text)
    c3.post("/login", data={"csrf_token": token, "email": email, "password": password}, follow_redirects=False)
    r4 = c3.get("/")
    assert "mascot-welcoming.png" in r4.text


def test_reminder_toast_shows_once_per_session_for_incomplete_profile(client):
    user_id, email, password = register_test_user(client, full_name="Reminder Test")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})

    r = client.get("/login")
    token = extract_csrf(r.text)
    client.post("/login", data={"csrf_token": token, "email": email, "password": password}, follow_redirects=False)

    r2 = client.get("/")
    assert "mascot-attentive.png" in r2.text

    r3 = client.get("/")
    assert "mascot-attentive.png" not in r3.text


def test_joinha_thumbsup_on_profile_save(client):
    user_id, email, password = register_test_user(client)
    r = client.get("/login")
    token = extract_csrf(r.text)
    client.post("/login", data={"csrf_token": token, "email": email, "password": password}, follow_redirects=False)

    r2 = client.get("/profile?saved=1")
    assert "mascot-thumbsup.png" in r2.text


def test_joinha_thumbsup_on_notas_redeem(client):
    user_id, email, password = register_test_user(client)
    # /notas requires a verified email (Notas antifraud pass, 19/09/2026).
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    r = client.get("/login")
    token = extract_csrf(r.text)
    client.post("/login", data={"csrf_token": token, "email": email, "password": password}, follow_redirects=False)

    r2 = client.get("/notas?redeemed=1")
    assert "mascot-thumbsup.png" in r2.text


def test_joinha_thumbsup_on_listing_created(client):
    user_id, email, password = register_test_user(client)
    r = client.get("/login")
    token = extract_csrf(r.text)
    client.post("/login", data={"csrf_token": token, "email": email, "password": password}, follow_redirects=False)

    r2 = client.get("/my-listings?created=1")
    assert "mascot-thumbsup.png" in r2.text
    assert "Listing published" in r2.text or "publicado" in r2.text or "veröffentlicht" in r2.text


def test_hall_da_fama_shows_wink_incentive(client):
    user_id, email, password = register_test_user(client, full_name="Hall Test")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    r = client.get("/login")
    token = extract_csrf(r.text)
    client.post("/login", data={"csrf_token": token, "email": email, "password": password}, follow_redirects=False)

    r2 = client.get("/hall-da-fama")
    assert "mascot-wink.png" in r2.text
    assert "Hall Test" in r2.text


def test_404_page_shows_alert_zone_mascot(client):
    r = client.get("/this-page-does-not-exist-xyz")
    assert r.status_code == 404
    assert "mascot-alert-zone.png" in r.text


def test_non_404_error_pages_never_show_the_404_mascot(client):
    """auth_message.html is shared by 404 AND other messages (e.g. an
    invalid password-reset link) — the mascot must only show up on the
    actual 404, never leak into those other message pages."""
    r = client.get("/reset-password?token=not-a-real-token")
    assert "mascot-alert-zone.png" not in r.text

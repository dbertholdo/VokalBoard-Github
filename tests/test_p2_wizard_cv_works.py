"""P2 cluster (19/09/2026) — Profile Wizard, CV export, solo/choir
"works" cards. Decided with Daniel via AskUserQuestion; directory
Fach-filter was explicitly dropped from this cluster ("Delete this
from the list."), so there's nothing to test for it here."""
from app.database import execute

from tests.test_security import register_test_user, extract_csrf


def _login(client, email, password):
    r = client.get("/login")
    token = extract_csrf(r.text)
    client.post("/login", data={"csrf_token": token, "email": email, "password": password}, follow_redirects=False)


def test_home_redirects_to_wizard_once_for_new_incomplete_profile(client):
    user_id, email, password = register_test_user(client, full_name="Wizard Test")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    _login(client, email, password)

    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/profile/wizard"

    # Visiting the wizard marks the one-shot gate as spent...
    client.get("/profile/wizard")
    r2 = client.get("/", follow_redirects=False)
    assert r2.status_code == 200


def test_profile_wizard_page_reuses_profile_post_action(client):
    user_id, email, password = register_test_user(client, full_name="Wizard Form Test")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    _login(client, email, password)

    r = client.get("/profile/wizard")
    assert r.status_code == 200
    assert 'action="/profile"' in r.text
    assert "wizard-form" in r.text


def test_singer_can_add_and_delete_a_work(client):
    user_id, email, password = register_test_user(client, full_name="Works Test")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    _login(client, email, password)

    r = client.get("/profile")
    token = extract_csrf(r.text)
    r2 = client.post(
        "/profile/works/add",
        data={
            "csrf_token": token,
            "title": "Mozart — Requiem",
            "composer": "W.A. Mozart",
            "category": "choir",
            "video_url": "https://www.youtube.com/watch?v=example",
            "audio_url": "",
        },
        follow_redirects=False,
    )
    assert r2.status_code == 303

    r3 = client.get("/profile")
    assert "Mozart" in r3.text
    assert "Requiem" in r3.text

    # Delete it again.
    import re

    work_id_match = re.search(r"/profile/works/(\d+)/delete", r3.text)
    assert work_id_match, "expected a delete form for the newly added work"
    work_id = work_id_match.group(1)
    token2 = extract_csrf(r3.text)
    r4 = client.post(f"/profile/works/{work_id}/delete", data={"csrf_token": token2}, follow_redirects=False)
    assert r4.status_code == 303

    r5 = client.get("/profile")
    assert "Mozart — Requiem" not in r5.text


def test_public_profile_shows_solo_and_choir_work_cards(client):
    user_id, email, password = register_test_user(client, full_name="Public Works Test")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    _login(client, email, password)

    r = client.get("/profile")
    token = extract_csrf(r.text)
    client.post(
        "/profile/works/add",
        data={"csrf_token": token, "title": "Solo Aria", "composer": "", "category": "solo", "video_url": "", "audio_url": ""},
        follow_redirects=False,
    )

    r2 = client.get(f"/users/{user_id}")
    assert "Solo Aria" in r2.text
    assert "works-card" in r2.text


def test_cv_pdf_download_returns_a_pdf(client):
    user_id, email, password = register_test_user(client, full_name="CV Test")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    _login(client, email, password)

    r = client.get("/profile/cv.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_cv_pdf_respects_private_phone_visibility():
    """A phone kept private must not leak into the downloadable PDF,
    even though it's the person's own document — a PDF is easy to
    forward on to someone else."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    user_id, email, password = register_test_user(client, full_name="Private Phone Test")
    execute(
        "UPDATE users SET email_verified = TRUE, phone = '+49 151 98765432', phone_visibility = 'private' WHERE id = :id",
        {"id": user_id},
    )
    _login(client, email, password)

    r = client.get("/profile/cv.pdf")
    assert r.status_code == 200
    # Check the extracted text, not raw bytes: page streams are compressed
    # and the xref table always contains runs like "0000000000".
    import io
    from pypdf import PdfReader
    text = "".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(r.content)).pages)
    assert "Private Phone Test" in text  # sanity: extraction works
    assert "98765432" not in text.replace(" ", "")

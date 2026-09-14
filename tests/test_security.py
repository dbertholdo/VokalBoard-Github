"""
Automated "security net" — tests, against the real application (not a
simulation), four security behaviors specific to this project:

1. CSRF: a POST without the correct token is always rejected.
2. Login lockout: 5 wrong passwords in a row lock the email out.
3. Admin: anyone who isn't an admin can never see /admin.
4. XSS: text typed by a person (e.g. a name) never becomes real HTML
   on the page — it appears escaped, as plain text.

This doesn't replace a real security audit, but it guarantees that a
future code change won't break these four protections without anyone
noticing (GitHub Actions runs this on every push — see
.github/workflows/security.yml).
"""
import re
import uuid

from app.database import fetch_one, execute

CSRF_RE = re.compile(r'name="csrf_token"\s+value="([^"]+)"')

DEFAULT_PASSWORD = "T3stPassword!Secure"


def extract_csrf(html: str) -> str:
    match = CSRF_RE.search(html)
    assert match, "couldn't find the hidden csrf_token field in the HTML — did the page change?"
    return match.group(1)


def unique_email() -> str:
    return f"sectest_{uuid.uuid4().hex[:12]}@example.com"


def _fake_ip() -> str:
    """A different fake IPv4 on every call — simulates people signing up from
    different networks, so these tests don't trip the mass-registration
    throttle (app/register_throttle.py), which is tested separately in
    TestRegistrationThrottle."""
    return f"203.0.113.{uuid.uuid4().int % 254 + 1}"


def register_test_user(client, full_name="Security Test User", password=DEFAULT_PASSWORD, email=None, ip=None):
    """Creates a real account via /register (the same path a real user uses)."""
    email = email or unique_email()
    ip = ip or _fake_ip()
    headers = {"X-Forwarded-For": ip}
    r = client.get("/register", headers=headers)
    token = extract_csrf(r.text)

    data = {
        "csrf_token": token,
        "category": "soprano",
        "full_name": full_name,
        "email": email,
        "password": password,
        "city": "München",
        "state": "Bayern",
        "country": "DE",
        "phone": "",
        "bio": "",
        "composer_hashtags": "",
        "audio_links": "",
        "ensemble_name": "",
        "ref": "",
        "website": "",  # honeypot — must stay empty
        "cf-turnstile-response": "",
    }
    r2 = client.post("/register", data=data, headers=headers, follow_redirects=False)
    assert r2.status_code == 303, f"registration failed: {r2.status_code} — {r2.text[:300]}"

    user = fetch_one("SELECT id FROM users WHERE email = :email", {"email": email})
    assert user, "user did not show up in the database after registration"
    return user["id"], email, password


def login(client, email, password, csrf_token=None):
    if csrf_token is None:
        r = client.get("/login")
        csrf_token = extract_csrf(r.text)
    return client.post(
        "/login",
        data={"csrf_token": csrf_token, "email": email, "password": password},
        follow_redirects=False,
    )


# ---------------------------------------------------------------------------
# 1. CSRF
# ---------------------------------------------------------------------------

class TestCSRFProtection:
    def test_login_without_csrf_token_is_rejected(self, client):
        r = client.post("/login", data={"email": "someone@example.com", "password": "whatever", "csrf_token": ""})
        assert r.status_code == 400

    def test_login_with_wrong_csrf_token_is_rejected(self, client):
        # Visit the login page to get a session with a VALID token —
        # and still send a different token in the POST.
        client.get("/login")
        r = client.post(
            "/login",
            data={"email": "someone@example.com", "password": "whatever", "csrf_token": "token-forged-by-an-attacker"},
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# 2. Progressive login lockout
# ---------------------------------------------------------------------------

class TestLoginLockout:
    def test_fifth_wrong_password_locks_the_account(self, client):
        _, email, real_password = register_test_user(client)

        r = client.get("/login")
        token = extract_csrf(r.text)

        for attempt in range(1, 6):
            resp = login(client, email, "wrong-password-on-purpose", csrf_token=token)
            assert resp.status_code == 400, f"attempt {attempt}: expected a regular password error, not a lockout yet"

        # the 6th attempt (even with the CORRECT password) should already be locked out
        blocked_resp = login(client, email, real_password, csrf_token=token)
        assert blocked_resp.status_code == 429

    def test_correct_password_resets_the_lockout_counter(self, client):
        _, email, real_password = register_test_user(client)

        r = client.get("/login")
        token = extract_csrf(r.text)

        for _ in range(3):
            login(client, email, "wrong-password", csrf_token=token)

        ok_resp = login(client, email, real_password, csrf_token=token)
        assert ok_resp.status_code == 303  # logged in normally — 3 errors aren't enough to lock out

        row = fetch_one("SELECT failed_count FROM login_lockouts WHERE email = :email", {"email": email})
        assert row is None, "the lockout row should have been deleted after a correct login"


# ---------------------------------------------------------------------------
# 3. Admin area
# ---------------------------------------------------------------------------

class TestAdminGating:
    def test_admin_dashboard_redirects_anonymous_visitors(self, client):
        r = client.get("/admin", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/"

    def test_admin_dashboard_redirects_regular_logged_in_users(self, client):
        _, email, password = register_test_user(client)
        login(client, email, password)

        r = client.get("/admin", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/"


# ---------------------------------------------------------------------------
# 4. HTML escaping (XSS)
# ---------------------------------------------------------------------------

class TestXSSEscaping:
    def test_full_name_with_script_tag_is_escaped_on_public_profile(self, client):
        malicious_name = "<script>alert('xss')</script>"
        user_id, _, _ = register_test_user(client, full_name=malicious_name)

        r = client.get(f"/users/{user_id}")
        assert r.status_code == 200
        # the tag must NEVER show up "live" in the response HTML
        assert "<script>alert" not in r.text
        # and Jinja2 must have escaped it to plain text
        assert "&lt;script&gt;" in r.text


# ---------------------------------------------------------------------------
# 5. Password rule
# ---------------------------------------------------------------------------

class TestPasswordPolicy:
    def test_short_password_is_rejected_at_registration(self, client):
        r = client.get("/register")
        token = extract_csrf(r.text)
        data = {
            "csrf_token": token,
            "category": "soprano",
            "full_name": "Weak Password User",
            "email": unique_email(),
            "password": "ab1!",  # only 4 characters
            "city": "München",
            "state": "Bayern",
            "country": "DE",
            "website": "",
            "cf-turnstile-response": "",
        }
        r2 = client.post("/register", data=data, follow_redirects=False)
        assert r2.status_code == 400

    def test_password_without_special_character_is_rejected(self, client):
        r = client.get("/register")
        token = extract_csrf(r.text)
        data = {
            "csrf_token": token,
            "category": "soprano",
            "full_name": "No Special Char User",
            "email": unique_email(),
            "password": "senha123",  # letter + number, no special character
            "city": "München",
            "state": "Bayern",
            "country": "DE",
            "website": "",
            "cf-turnstile-response": "",
        }
        r2 = client.post("/register", data=data, follow_redirects=False)
        assert r2.status_code == 400

    def test_password_meeting_all_rules_is_accepted(self, client):
        # DEFAULT_PASSWORD already meets the rule — this just confirms
        # validation isn't rejecting a valid password by mistake.
        register_test_user(client)


# ---------------------------------------------------------------------------
# 6. Mass-registration throttle (by IP)
# ---------------------------------------------------------------------------

class TestRegistrationThrottle:
    def test_too_many_accounts_from_same_ip_are_throttled(self, client):
        from app.register_throttle import MAX_REGISTRATIONS_PER_WINDOW

        ip = "198.51.100.77"
        for i in range(MAX_REGISTRATIONS_PER_WINDOW):
            register_test_user(client, email=f"sectest_throttle_{i}_{uuid.uuid4().hex[:8]}@example.com", ip=ip)

        # the next account, from the SAME ip, must be refused
        r = client.get("/register", headers={"X-Forwarded-For": ip})
        token = extract_csrf(r.text)
        data = {
            "csrf_token": token,
            "category": "soprano",
            "full_name": "One Too Many",
            "email": unique_email(),
            "password": DEFAULT_PASSWORD,
            "city": "München",
            "state": "Bayern",
            "country": "DE",
            "website": "",
            "cf-turnstile-response": "",
        }
        r2 = client.post("/register", data=data, headers={"X-Forwarded-For": ip}, follow_redirects=False)
        assert r2.status_code == 429

    def test_login_and_password_reset_are_never_throttled_by_registration_limit(self, client):
        # Same IP "used up" by the previous test — login must not be
        # affected by that, only the CREATION of new accounts.
        ip = "198.51.100.77"
        r = client.get("/login", headers={"X-Forwarded-For": ip})
        assert r.status_code == 200
        r2 = client.get("/forgot-password", headers={"X-Forwarded-For": ip})
        assert r2.status_code == 200


# ---------------------------------------------------------------------------
# 7. Security headers
# ---------------------------------------------------------------------------

class TestSecurityHeaders:
    def test_security_headers_are_present(self, client):
        r = client.get("/")
        assert r.headers.get("x-content-type-options") == "nosniff"
        assert r.headers.get("x-frame-options") == "DENY"
        assert "Referrer-Policy" in r.headers or "referrer-policy" in r.headers

    def test_csp_header_has_a_per_request_nonce_matching_the_page(self, client):
        r = client.get("/")
        csp = r.headers.get("content-security-policy") or r.headers.get("Content-Security-Policy")
        assert csp and "nonce-" in csp
        nonce = csp.split("nonce-")[1].split("'")[0]
        assert f'nonce="{nonce}"' in r.text

    def test_404_page_uses_the_site_layout_not_raw_json(self, client):
        r = client.get("/this-page-really-does-not-exist")
        assert r.status_code == 404
        assert "<html" in r.text.lower()
        assert "VokalBoard" in r.text


# ---------------------------------------------------------------------------
# 8. Message throttle (spam/harassment between users)
# ---------------------------------------------------------------------------

class TestMessageRateLimit:
    def test_too_many_messages_to_same_recipient_are_throttled(self, client):
        from app.routers.messages_routes import MAX_MESSAGES_PER_RECIPIENT_PER_HOUR

        sender_id, sender_email, sender_password = register_test_user(client, full_name="Message Sender")
        recipient_id, _, _ = register_test_user(client, full_name="Message Recipient")
        # /messages/send requires a verified email — without a real email
        # flow in the tests, confirm it directly in the database (the same
        # thing the email link would do).
        execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": sender_id})

        login(client, sender_email, sender_password)
        r = client.get(f"/messages/new?to={recipient_id}")
        token = extract_csrf(r.text)

        for i in range(MAX_MESSAGES_PER_RECIPIENT_PER_HOUR):
            resp = client.post(
                "/messages/send",
                data={"csrf_token": token, "recipient_id": recipient_id, "listing_id": "", "body": f"Hi! Message {i}"},
                follow_redirects=False,
            )
            assert resp.status_code == 303, f"message {i} should have gone through"

        blocked_resp = client.post(
            "/messages/send",
            data={"csrf_token": token, "recipient_id": recipient_id, "listing_id": "", "body": "One more..."},
            follow_redirects=False,
        )
        assert blocked_resp.status_code == 429


# ---------------------------------------------------------------------------
# 9. Admin posts (home feed)
# ---------------------------------------------------------------------------

class TestAdminPosts:
    def test_non_admin_cannot_reach_admin_posts(self, client):
        _, email, password = register_test_user(client)
        login(client, email, password)

        r = client.get("/admin/posts", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/"

        r2 = client.post("/admin/posts", data={"csrf_token": "x", "title": "t", "body": "b"}, follow_redirects=False)
        assert r2.status_code == 303
        assert r2.headers["location"] == "/"

    def test_admin_can_create_post_and_it_appears_on_home_for_everyone(self, client):
        admin_id, admin_email, admin_password = register_test_user(client, full_name="Post Admin")
        execute("UPDATE users SET is_admin = TRUE, email_verified = TRUE WHERE id = :id", {"id": admin_id})
        login(client, admin_email, admin_password)

        r = client.get("/admin/posts")
        token = extract_csrf(r.text)
        create = client.post(
            "/admin/posts",
            data={"csrf_token": token, "title": "Test Announcement", "body": "Body of the test post."},
            follow_redirects=False,
        )
        assert create.status_code == 303

        # shows up in the feed for a logged-out visitor (a fresh client,
        # without the admin's session)
        from fastapi.testclient import TestClient
        from app.main import app as fastapi_app

        anon_home = TestClient(fastapi_app).get("/")
        assert "Test Announcement" in anon_home.text

    def test_listing_creation_is_throttled_after_five_in_five_minutes(self, client):
        from app.routers.listings_routes import MAX_LISTINGS_PER_WINDOW

        user_id, email, password = register_test_user(client, full_name="Listing Spammer")
        execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
        login(client, email, password)

        r = client.get("/listings/new")
        token = extract_csrf(r.text)
        data = {
            "csrf_token": token,
            "listing_type": "singer_available",
            "title": "Test Listing",
            "description": "Test description.",
            "state": "Bayern",
            "city": "München",
            "country": "DE",
            "voice_type_id": "",
            "repertoire": "",
            "venue": "",
            "fee": "",
            "ensemble_type": "",
            "event_date": "",
        }

        for i in range(MAX_LISTINGS_PER_WINDOW):
            resp = client.post("/listings/new", data=data, follow_redirects=False)
            assert resp.status_code == 303, f"listing {i} should have gone through"

        blocked = client.post("/listings/new", data=data, follow_redirects=False)
        assert blocked.status_code == 429

    def test_unpublished_post_disappears_from_home(self, client):
        admin_id, admin_email, admin_password = register_test_user(client, full_name="Post Admin Two")
        execute("UPDATE users SET is_admin = TRUE, email_verified = TRUE WHERE id = :id", {"id": admin_id})
        login(client, admin_email, admin_password)

        r = client.get("/admin/posts")
        token = extract_csrf(r.text)
        client.post(
            "/admin/posts",
            data={"csrf_token": token, "title": "Post to Unpublish", "body": "This will disappear."},
            follow_redirects=False,
        )
        post_id = fetch_one("SELECT id FROM posts WHERE title = :t", {"t": "Post to Unpublish"})["id"]

        client.post(f"/admin/posts/{post_id}/toggle-publish", data={"csrf_token": token}, follow_redirects=False)

        home = client.get("/")
        assert "Post to Unpublish" not in home.text

    def test_post_body_html_is_sanitized_and_full_page_works(self, client):
        """The editor sends HTML — only the allowed tag list (see app/richtext.py)
        survives; <script>/onclick never make it into what's saved."""
        admin_id, admin_email, admin_password = register_test_user(client, full_name="Post Admin Rich")
        execute("UPDATE users SET is_admin = TRUE, email_verified = TRUE WHERE id = :id", {"id": admin_id})
        login(client, admin_email, admin_password)

        r = client.get("/admin/posts")
        token = extract_csrf(r.text)
        dirty_body = (
            '<p>Text <strong>in bold</strong> and <script>alert(1)</script></p>'
            '<img src="/post-images/x.webp" onerror="alert(2)">'
            '<a href="javascript:alert(3)">malicious link</a>'
        )
        client.post(
            "/admin/posts",
            data={"csrf_token": token, "title": "Post with HTML", "body": dirty_body},
            follow_redirects=False,
        )
        post = fetch_one("SELECT id, body FROM posts WHERE title = 'Post with HTML'")
        assert post is not None
        assert "<script>" not in post["body"]
        assert "onerror" not in post["body"]
        assert "javascript:" not in post["body"]
        assert "<strong>in bold</strong>" in post["body"]

        # the full post page renders the sanitized HTML without escaping it
        # (uses {{ post.body | safe }}) and the home card shows only the
        # plain-text summary, with no tags.
        detail = client.get(f"/posts/{post['id']}")
        assert detail.status_code == 200
        assert "<strong>in bold</strong>" in detail.text
        assert "<script>" not in detail.text

        home = client.get("/")
        assert "Post with HTML" in home.text
        assert "<strong>" not in home.text  # the summary is plain text, no markup

    def test_post_detail_404_for_missing_or_unpublished_to_non_admin(self, client):
        admin_id, admin_email, admin_password = register_test_user(client, full_name="Post Admin Unpub")
        execute("UPDATE users SET is_admin = TRUE, email_verified = TRUE WHERE id = :id", {"id": admin_id})
        login(client, admin_email, admin_password)

        assert client.get("/posts/999999999").status_code == 404

        r = client.get("/admin/posts")
        token = extract_csrf(r.text)
        client.post(
            "/admin/posts",
            data={"csrf_token": token, "title": "Unpublished Post Detail", "body": "Text."},
            follow_redirects=False,
        )
        post_id = fetch_one("SELECT id FROM posts WHERE title = 'Unpublished Post Detail'")["id"]
        client.post(f"/admin/posts/{post_id}/toggle-publish", data={"csrf_token": token}, follow_redirects=False)

        # admin can still see it (to check before republishing)
        assert client.get(f"/posts/{post_id}").status_code == 200

        # a logged-out visitor gets a 404 (doesn't "know" the post exists)
        from fastapi.testclient import TestClient
        from app.main import app as fastapi_app

        anon = TestClient(fastapi_app)
        assert anon.get(f"/posts/{post_id}").status_code == 404

    def test_upload_image_requires_admin_and_rejects_non_image(self, client):
        _, email, password = register_test_user(client)
        login(client, email, password)
        r = client.post("/admin/posts/upload-image", files={"image": ("x.png", b"not-an-image", "image/png")})
        assert r.status_code == 403

        admin_id, admin_email, admin_password = register_test_user(client, full_name="Post Admin Img")
        execute("UPDATE users SET is_admin = TRUE, email_verified = TRUE WHERE id = :id", {"id": admin_id})
        login(client, admin_email, admin_password)
        r2 = client.get("/admin/posts")
        token = extract_csrf(r2.text)

        bad = client.post(
            "/admin/posts/upload-image",
            files={"image": ("x.png", b"not-an-image", "image/png")},
            headers={"X-CSRF-Token": token},
        )
        assert bad.status_code == 400

        import io
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (10, 10), color="red").save(buf, format="PNG")
        buf.seek(0)
        good = client.post(
            "/admin/posts/upload-image",
            files={"image": ("x.png", buf.read(), "image/png")},
            headers={"X-CSRF-Token": token},
        )
        assert good.status_code == 200
        assert good.json()["url"].startswith("/post-images/")

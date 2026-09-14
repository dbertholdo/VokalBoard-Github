"""
"Rede de segurança" automatizada — testa, contra a aplicação real (não
uma simulação), quatro comportamentos de segurança específicos deste
projeto:

1. CSRF: um POST sem o token certo é sempre rejeitado.
2. Bloqueio de login: 5 senhas erradas seguidas bloqueiam o e-mail.
3. Admin: quem não é admin nunca consegue ver /admin.
4. XSS: texto digitado pela pessoa (ex: nome) nunca vira HTML de
   verdade na página — aparece escapado, como texto puro.

Isso não substitui uma auditoria de segurança de verdade, mas garante
que uma mudança futura no código não quebre essas quatro proteções sem
ninguém perceber (o GitHub Actions roda isso a cada push — ver
.github/workflows/security.yml).
"""
import re
import uuid

from app.database import fetch_one, execute

CSRF_RE = re.compile(r'name="csrf_token"\s+value="([^"]+)"')

DEFAULT_PASSWORD = "S3nhaDeTeste!Segura"


def extract_csrf(html: str) -> str:
    match = CSRF_RE.search(html)
    assert match, "não achei o campo escondido csrf_token no HTML — a página mudou?"
    return match.group(1)


def unique_email() -> str:
    return f"sectest_{uuid.uuid4().hex[:12]}@example.com"


def _fake_ip() -> str:
    """Um IPv4 fake diferente a cada chamada — simula gente se cadastrando de redes
    diferentes, pra esses testes não esbarrarem no freio de cadastro em massa
    (app/register_throttle.py), que é testado à parte em TestRegistrationThrottle."""
    return f"203.0.113.{uuid.uuid4().int % 254 + 1}"


def register_test_user(client, full_name="Security Test User", password=DEFAULT_PASSWORD, email=None, ip=None):
    """Cria uma conta de verdade via /register (o mesmo caminho que um usuário real usa)."""
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
        "website": "",  # honeypot — precisa continuar vazio
        "cf-turnstile-response": "",
    }
    r2 = client.post("/register", data=data, headers=headers, follow_redirects=False)
    assert r2.status_code == 303, f"cadastro falhou: {r2.status_code} — {r2.text[:300]}"

    user = fetch_one("SELECT id FROM users WHERE email = :email", {"email": email})
    assert user, "usuário não apareceu no banco depois do cadastro"
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
        r = client.post("/login", data={"email": "alguem@example.com", "password": "qualquer-coisa", "csrf_token": ""})
        assert r.status_code == 400

    def test_login_with_wrong_csrf_token_is_rejected(self, client):
        # Visita a página de login pra ganhar uma sessão com um token
        # VÁLIDO — e mesmo assim manda um token diferente no POST.
        client.get("/login")
        r = client.post(
            "/login",
            data={"email": "alguem@example.com", "password": "qualquer-coisa", "csrf_token": "token-forjado-por-um-atacante"},
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# 2. Bloqueio progressivo de login
# ---------------------------------------------------------------------------

class TestLoginLockout:
    def test_fifth_wrong_password_locks_the_account(self, client):
        _, email, real_password = register_test_user(client)

        r = client.get("/login")
        token = extract_csrf(r.text)

        for attempt in range(1, 6):
            resp = login(client, email, "senha-errada-de-propósito", csrf_token=token)
            assert resp.status_code == 400, f"tentativa {attempt}: esperava erro comum de senha, não bloqueio ainda"

        # a 6ª tentativa (mesmo com a senha CERTA) já deve estar bloqueada
        blocked_resp = login(client, email, real_password, csrf_token=token)
        assert blocked_resp.status_code == 429

    def test_correct_password_resets_the_lockout_counter(self, client):
        _, email, real_password = register_test_user(client)

        r = client.get("/login")
        token = extract_csrf(r.text)

        for _ in range(3):
            login(client, email, "senha-errada", csrf_token=token)

        ok_resp = login(client, email, real_password, csrf_token=token)
        assert ok_resp.status_code == 303  # logou normalmente — 3 erros não chegam a bloquear

        row = fetch_one("SELECT failed_count FROM login_lockouts WHERE email = :email", {"email": email})
        assert row is None, "a linha de bloqueio deveria ter sido apagada depois do login certo"


# ---------------------------------------------------------------------------
# 3. Área de administração
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
# 4. Escapamento de HTML (XSS)
# ---------------------------------------------------------------------------

class TestXSSEscaping:
    def test_full_name_with_script_tag_is_escaped_on_public_profile(self, client):
        malicious_name = "<script>alert('xss')</script>"
        user_id, _, _ = register_test_user(client, full_name=malicious_name)

        r = client.get(f"/users/{user_id}")
        assert r.status_code == 200
        # a tag JAMAIS pode aparecer "viva" no HTML da resposta
        assert "<script>alert" not in r.text
        # e o Jinja2 precisa ter escapado ela pra texto puro
        assert "&lt;script&gt;" in r.text


# ---------------------------------------------------------------------------
# 5. Regra de senha
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
            "password": "ab1!",  # só 4 caracteres
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
            "password": "senha123",  # letra + número, sem caractere especial
            "city": "München",
            "state": "Bayern",
            "country": "DE",
            "website": "",
            "cf-turnstile-response": "",
        }
        r2 = client.post("/register", data=data, follow_redirects=False)
        assert r2.status_code == 400

    def test_password_meeting_all_rules_is_accepted(self, client):
        # DEFAULT_PASSWORD já cumpre a regra — só confirma que a
        # validação não está rejeitando senha válida por engano.
        register_test_user(client)


# ---------------------------------------------------------------------------
# 6. Freio de cadastro em massa (por IP)
# ---------------------------------------------------------------------------

class TestRegistrationThrottle:
    def test_too_many_accounts_from_same_ip_are_throttled(self, client):
        from app.register_throttle import MAX_REGISTRATIONS_PER_WINDOW

        ip = "198.51.100.77"
        for i in range(MAX_REGISTRATIONS_PER_WINDOW):
            register_test_user(client, email=f"sectest_throttle_{i}_{uuid.uuid4().hex[:8]}@example.com", ip=ip)

        # a próxima conta, vinda do MESMO ip, deve ser recusada
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
        # Mesmo IP "gasto" pelo teste anterior — login não pode ser
        # afetado por isso, só a CRIAÇÃO de contas novas.
        ip = "198.51.100.77"
        r = client.get("/login", headers={"X-Forwarded-For": ip})
        assert r.status_code == 200
        r2 = client.get("/forgot-password", headers={"X-Forwarded-For": ip})
        assert r2.status_code == 200


# ---------------------------------------------------------------------------
# 7. Cabeçalhos de segurança
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
        r = client.get("/esta-pagina-nao-existe-de-verdade")
        assert r.status_code == 404
        assert "<html" in r.text.lower()
        assert "VokalBoard" in r.text


# ---------------------------------------------------------------------------
# 8. Freio de mensagens (spam/assédio entre usuários)
# ---------------------------------------------------------------------------

class TestMessageRateLimit:
    def test_too_many_messages_to_same_recipient_are_throttled(self, client):
        from app.routers.messages_routes import MAX_MESSAGES_PER_RECIPIENT_PER_HOUR

        sender_id, sender_email, sender_password = register_test_user(client, full_name="Message Sender")
        recipient_id, _, _ = register_test_user(client, full_name="Message Recipient")
        # /messages/send exige e-mail verificado — sem o fluxo de e-mail de
        # verdade nos testes, confirma direto no banco (o mesmo que o link
        # do e-mail faria).
        execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": sender_id})

        login(client, sender_email, sender_password)
        r = client.get(f"/messages/new?to={recipient_id}")
        token = extract_csrf(r.text)

        for i in range(MAX_MESSAGES_PER_RECIPIENT_PER_HOUR):
            resp = client.post(
                "/messages/send",
                data={"csrf_token": token, "recipient_id": recipient_id, "listing_id": "", "body": f"Olá! Mensagem {i}"},
                follow_redirects=False,
            )
            assert resp.status_code == 303, f"mensagem {i} deveria ter passado"

        blocked_resp = client.post(
            "/messages/send",
            data={"csrf_token": token, "recipient_id": recipient_id, "listing_id": "", "body": "Mais uma..."},
            follow_redirects=False,
        )
        assert blocked_resp.status_code == 429


# ---------------------------------------------------------------------------
# 9. Posts de admin (feed na home)
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
            data={"csrf_token": token, "title": "Novidade de teste", "body": "Corpo do post de teste."},
            follow_redirects=False,
        )
        assert create.status_code == 303

        # aparece no feed pra um visitante deslogado (cliente novo, sem
        # a sessão do admin)
        from fastapi.testclient import TestClient
        from app.main import app as fastapi_app

        anon_home = TestClient(fastapi_app).get("/")
        assert "Novidade de teste" in anon_home.text

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
            "title": "Anúncio de teste",
            "description": "Descrição de teste.",
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
            assert resp.status_code == 303, f"anúncio {i} deveria ter passado"

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
            data={"csrf_token": token, "title": "Post pra despublicar", "body": "Vai sumir."},
            follow_redirects=False,
        )
        post_id = fetch_one("SELECT id FROM posts WHERE title = :t", {"t": "Post pra despublicar"})["id"]

        client.post(f"/admin/posts/{post_id}/toggle-publish", data={"csrf_token": token}, follow_redirects=False)

        home = client.get("/")
        assert "Post pra despublicar" not in home.text

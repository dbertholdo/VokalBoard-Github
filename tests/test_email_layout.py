"""P6 — Layout compartilhado de e-mails (18/09/2026): todo e-mail
automático passa por render_email() dentro de send_email(), editável
em /admin/emails. Ver app/email_layout.py, app/email.py e
app/routers/admin_routes.py."""
from app.database import execute, fetch_one
from app.email_layout import (
    get_email_layout_settings,
    update_email_layout_settings,
    update_email_template,
    reset_email_template,
    render_email,
    DEFAULT_TEMPLATE_HTML,
)
from tests.test_security import extract_csrf, login, register_test_user


def _make_admin(client):
    user_id, email, password = register_test_user(client, full_name="Email Layout Admin")
    execute("UPDATE users SET email_verified = TRUE, role_level = 2 WHERE id = :id", {"id": user_id})
    login(client, email, password)
    return user_id


def _reset_layout_settings():
    for key, value in {
        "email_layout_logo_url": "",
        "email_layout_accent_color": "#12a488",
        "email_layout_header_emoji": "🎵",
        "email_layout_signature": "Equipe VokalBoard",
        "email_layout_footer": "Você recebeu este e-mail porque tem uma conta no VokalBoard.",
    }.items():
        execute("UPDATE system_settings SET value = :v WHERE key = :k", {"k": key, "v": value})
    execute("DELETE FROM system_settings WHERE key = 'email_layout_template_html'")


def test_render_email_wraps_body_with_layout_defaults():
    _reset_layout_settings()
    html = render_email("<p>Corpo de teste único e específico</p>")
    assert "Corpo de teste único e específico" in html
    assert "Equipe VokalBoard" in html
    assert "Você recebeu este e-mail" in html
    assert "#12a488" in html
    assert "🎵" in html


def test_update_email_layout_settings_persists_changes():
    _reset_layout_settings()
    update_email_layout_settings(
        None, "#ff0000", "⭐", "Assinatura de teste", "Rodapé de teste", updated_by_user_id=None,
    )
    settings = get_email_layout_settings()
    assert settings["email_layout_accent_color"] == "#ff0000"
    assert settings["email_layout_header_emoji"] == "⭐"
    assert settings["email_layout_signature"] == "Assinatura de teste"
    assert settings["email_layout_footer"] == "Rodapé de teste"
    _reset_layout_settings()


def test_update_email_layout_settings_rejects_invalid_color():
    _reset_layout_settings()
    update_email_layout_settings(
        None, "not-a-color", "🎵", "Assinatura", "Rodapé", updated_by_user_id=None,
    )
    settings = get_email_layout_settings()
    assert settings["email_layout_accent_color"] == "#12a488"  # caiu pro padrão, não guardou lixo
    _reset_layout_settings()


def test_update_email_layout_settings_none_logo_keeps_current_one():
    _reset_layout_settings()
    execute("UPDATE system_settings SET value = '/post-images/existing.webp' WHERE key = 'email_layout_logo_url'")
    update_email_layout_settings(None, "#12a488", "🎵", "Assinatura", "Rodapé", updated_by_user_id=None)
    row = fetch_one("SELECT value FROM system_settings WHERE key = 'email_layout_logo_url'")
    assert row["value"] == "/post-images/existing.webp"
    _reset_layout_settings()


def test_verification_email_body_goes_through_shared_layout(client, capsys):
    """Um e-mail real de verificação (auth_routes.py) precisa sair já
    embrulhado — sem precisar mudar nada em auth_routes.py pra isso
    acontecer (é o ponto principal do pedido: mudar em UM lugar afeta
    todos os e-mails automáticos)."""
    _reset_layout_settings()
    register_test_user(client, full_name="Layout Wrap Test")
    captured = capsys.readouterr()
    assert "Equipe VokalBoard" in captured.out
    assert "Você recebeu este e-mail" in captured.out


def test_admin_emails_page_requires_admin(client):
    resp = client.get("/admin/emails", follow_redirects=False)
    assert resp.status_code in (303, 401, 403)

    _make_admin(client)
    resp = client.get("/admin/emails")
    assert resp.status_code == 200
    assert "Equipe VokalBoard" in resp.text


def test_admin_can_update_email_layout_via_route(client):
    _reset_layout_settings()
    _make_admin(client)
    page = client.get("/admin/emails")
    token = extract_csrf(page.text)

    resp = client.post(
        "/admin/emails",
        data={
            "csrf_token": token,
            "accent_color": "#123456",
            "header_emoji": "🎶",
            "signature": "Time VokalBoard (teste)",
            "footer": "Rodapé via rota HTTP",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "updated=1" in resp.headers["location"]

    settings = get_email_layout_settings()
    assert settings["email_layout_accent_color"] == "#123456"
    assert settings["email_layout_signature"] == "Time VokalBoard (teste)"
    _reset_layout_settings()


def test_get_email_layout_settings_falls_back_to_default_template_when_unset():
    _reset_layout_settings()  # apaga a linha (não seedada por padrão)
    settings = get_email_layout_settings()
    assert settings["email_layout_template_html"] == DEFAULT_TEMPLATE_HTML


def test_update_email_template_upserts_without_a_pre_existing_row():
    _reset_layout_settings()
    ok = update_email_template("<div>{{BODY}}</div>", updated_by_user_id=None)
    assert ok is True
    settings = get_email_layout_settings()
    assert settings["email_layout_template_html"] == "<div>{{BODY}}</div>"
    _reset_layout_settings()


def test_update_email_template_rejects_missing_body_placeholder():
    _reset_layout_settings()
    ok = update_email_template("<div>sem o placeholder</div>", updated_by_user_id=None)
    assert ok is False
    settings = get_email_layout_settings()
    assert settings["email_layout_template_html"] == DEFAULT_TEMPLATE_HTML  # nada mudou
    _reset_layout_settings()


def test_update_email_template_strips_script_tags():
    _reset_layout_settings()
    update_email_template(
        "<div>{{BODY}}<script>alert('x')</script></div>", updated_by_user_id=None,
    )
    settings = get_email_layout_settings()
    assert "<script>" not in settings["email_layout_template_html"]
    _reset_layout_settings()


def test_reset_email_template_restores_default_after_a_custom_edit():
    _reset_layout_settings()
    update_email_template("<div>{{BODY}} customizado</div>", updated_by_user_id=None)
    reset_email_template(updated_by_user_id=None)
    settings = get_email_layout_settings()
    assert settings["email_layout_template_html"] == DEFAULT_TEMPLATE_HTML
    _reset_layout_settings()


def test_render_email_uses_custom_template_when_set():
    _reset_layout_settings()
    update_email_template("<div class=\"custom\">{{BODY}}</div>", updated_by_user_id=None)
    html = render_email("<p>corpo único de teste</p>")
    assert 'class="custom"' in html
    assert "corpo único de teste" in html
    _reset_layout_settings()


def test_admin_emails_code_tab_shows_template(client):
    _reset_layout_settings()
    _make_admin(client)
    resp = client.get("/admin/emails?tab=code")
    assert resp.status_code == 200
    assert "{{BODY}}" in resp.text


def test_admin_can_update_template_via_route(client):
    _reset_layout_settings()
    _make_admin(client)
    page = client.get("/admin/emails?tab=code")
    token = extract_csrf(page.text)

    resp = client.post(
        "/admin/emails/template",
        data={"csrf_token": token, "template_html": "<div>{{BODY}} via rota</div>"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "updated=1" in resp.headers["location"]

    settings = get_email_layout_settings()
    assert settings["email_layout_template_html"] == "<div>{{BODY}} via rota</div>"
    _reset_layout_settings()


def test_admin_update_template_route_rejects_missing_placeholder(client):
    _reset_layout_settings()
    _make_admin(client)
    page = client.get("/admin/emails?tab=code")
    token = extract_csrf(page.text)

    resp = client.post(
        "/admin/emails/template",
        data={"csrf_token": token, "template_html": "<div>sem placeholder</div>"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "error=invalid_template" in resp.headers["location"]

    settings = get_email_layout_settings()
    assert settings["email_layout_template_html"] == DEFAULT_TEMPLATE_HTML
    _reset_layout_settings()


def test_admin_can_reset_template_via_route(client):
    _reset_layout_settings()
    update_email_template("<div>{{BODY}} customizado</div>", updated_by_user_id=None)
    _make_admin(client)
    page = client.get("/admin/emails?tab=code")
    token = extract_csrf(page.text)

    resp = client.post(
        "/admin/emails/template/reset",
        data={"csrf_token": token},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    settings = get_email_layout_settings()
    assert settings["email_layout_template_html"] == DEFAULT_TEMPLATE_HTML
    _reset_layout_settings()

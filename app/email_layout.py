"""
Layout compartilhado de TODOS os e-mails automáticos — P6 (18/09/2026).

Pedido do Daniel: "preciso de uma forma de editar o layout dos e-mails
— os ícones, logo, texto/fontes, assinatura e rodapé — enfim tudo que
pode entrar aí — e só mudar o corpo automaticamente, baseado no
objetivo do e-mail. Porque facilita mudar o layout de todos os
e-mails automáticos de uma vez só." + (mesmo dia, pedido seguinte)
"também uma aba onde mostra o code do e-mail pra eu editar coisas
menores".

Antes desta etapa, cada função de e-mail (app/email_localization.py,
app/notifications.py, app/badges.py, os workers, etc. — ~16 pontos de
envio em ~7 arquivos) montava só o CORPO (parágrafos soltos, sem
cabeçalho, logo ou rodapé) e mandava direto pra `send_email()`. O
"corpo mudar automaticamente baseado no objetivo do e-mail" já
acontecia naturalmente — cada função já decide o que escrever, isso
nunca precisou de configuração. O que faltava era um "envelope"
compartilhado por cima de todos eles.

Esta etapa resolve isso num ÚNICO lugar: `render_email()` embrulha
qualquer corpo com o layout (logo, cor de destaque, assinatura,
rodapé), e `app/email.py`'s `send_email()` chama isso automaticamente
— então TODOS os ~16 pontos de envio herdam o layout sem precisar
tocar em nenhum deles. Editável em `/admin/emails`, em duas abas:

- **Formulário** (padrão): logo, cor de destaque, emoji de cabeçalho,
  assinatura, rodapé — cada um um campo separado, sem risco de
  quebrar o HTML.
- **Código** (pedido seguinte do Daniel): o HTML completo do "molde"
  (`DEFAULT_TEMPLATE_HTML` abaixo, ou o que o Admin salvou por cima
  dele), com placeholders (`{{BODY}}`, `{{LOGO}}`, `{{ACCENT}}`,
  `{{EMOJI}}`, `{{SIGNATURE}}`, `{{FOOTER}}`) — pra ajustes finos que
  o formulário simples não cobre (padding, borda, tamanho de fonte,
  etc.), sem precisar mexer em código de verdade/pedir deploy.

Decisões confirmadas com o Daniel via AskUserQuestion (na etapa
anterior, ainda valem pra esta): e-mail tem limitações reais de
renderização (CSS avançado e fontes customizadas não são confiáveis
na maioria dos clientes de e-mail) — por isso o molde usa tabela +
estilo inline (não `<style>` num `<head>`, nem flexbox/grid), a
técnica que renderiza de forma mais confiável entre clientes (Gmail,
Outlook, Apple Mail). Ícones são emoji unicode, não o sprite
icons.svg do site (não funciona em e-mail).

Sobre a aba Código ser HTML "cru": não passa pelo mesmo sanitizador
dos posts do blog (`app/richtext.py`) de propósito — aquele permite
só uma lista curta de tags (nem `<table>`/`<style>` inline), pensada
pro editor visual de posts, incompatível com a estrutura de tabela que
e-mail precisa. Isso nunca é renderizado dentro do próprio site (só
vira HTML de e-mails enviados), e já exige nível Admin (role_level>=2)
pra editar — mesmo patamar de confiança de quem já tem acesso ao
Adminer (ver app/templates/admin.html). Ainda assim, `<script>` é
removido por precaução antes de salvar (clientes de e-mail já
ignoram/bloqueiam isso quase sempre, mas não custa nada garantir).

Os valores ficam em `system_settings` (mesma tabela genérica de
chave/valor já usada por Capitalism Mode e preço de assinatura) —
sem precisar de tabela nova.
"""
import os
import re
from html import escape

from app.database import execute, fetch_all, fetch_one
from app.email_localization import email_language

# SITE_BASE_URL: separado do que cada rota calcula com request.base_url
# (não disponível aqui — e-mail também é mandado por workers em
# background, sem request nenhum) e também separado do "logo" em si
# (que é conteúdo, editável pelo Admin) — isso é infraestrutura de
# deploy (a URL pública do site), então vem de variável de ambiente,
# igual EMAIL_FROM/AVATAR_DIR. Sem isso configurado, o logo simplesmente
# não aparece no e-mail (uma <img> quebrada seria pior que nenhuma).
SITE_BASE_URL = os.getenv("SITE_BASE_URL", "").rstrip("/")

# Molde padrão — o que sai "de fábrica" e o que a aba Código mostra
# até o Admin sobrescrever. Os placeholders ({{BODY}}, {{LOGO}}, etc.)
# são o contrato entre esta string e render_email() — troque o visual
# à vontade na aba Código, mas mantendo pelo menos {{BODY}} em algum
# lugar (validado em update_email_template() antes de salvar, senão o
# corpo do e-mail simplesmente desapareceria de TODOS os envios).
DEFAULT_TEMPLATE_HTML = """<div style="font-family: Arial, Helvetica, sans-serif; max-width: 600px; margin: 0 auto; background:#ffffff;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
    <tr>
      <td style="padding: 20px 24px; border-bottom: 3px solid {{ACCENT}}; background:#f7f7f5;">
        {{LOGO}}<span style="font-size:20px; font-weight:bold; color:{{ACCENT}}; vertical-align:middle;">{{EMOJI}} VokalBoard</span>
      </td>
    </tr>
    <tr>
      <td style="padding: 24px; font-size:15px; line-height:1.6; color:#1a1a1a;">
        {{BODY}}
      </td>
    </tr>
    <tr>
      <td style="padding: 16px 24px; border-top:1px solid #e5e5e5;">
        <p style="margin:0 0 10px 0; font-size:14px; color:#333;">{{SIGNATURE}}</p>
        <p style="margin:0; font-size:12px; color:#888;">{{FOOTER}}</p>
      </td>
    </tr>
  </table>
</div>"""

MAX_TEMPLATE_LENGTH = 20000
REQUIRED_TOKEN = "{{BODY}}"

_DEFAULTS = {
    "email_layout_logo_url": "",
    "email_layout_accent_color": "#12a488",  # mesmo --accent do site (app/static/css/style.css)
    "email_layout_header_emoji": "🎵",
    "email_layout_signature": "From Team VokalBoard.com",
    "email_layout_footer": "You received this e-mail because you have an account on VokalBoard.com.",
    "email_layout_template_html": DEFAULT_TEMPLATE_HTML,
}

# Sign-off + footer in the RECIPIENT's language (Daniel, 2026-09-26: "From
# Team VokalBoard.com"). Used while the admin fields still hold a built-in
# default (the old Portuguese seed or the English one above); any other
# text typed at /admin/emails is a deliberate custom override for everyone.
_SIGNATURE_BY_LANG = {
    "de": "Dein Team von VokalBoard.com",
    "en": "From Team VokalBoard.com",
    "fr": "L'équipe VokalBoard.com",
    "it": "Il team di VokalBoard.com",
    "pt": "Equipe VokalBoard.com",
    "es": "El equipo de VokalBoard.com",
    "ro": "Echipa VokalBoard.com",
}
_FOOTER_BY_LANG = {
    "de": "Du erhältst diese E-Mail, weil du ein Konto bei VokalBoard.com hast.",
    "en": "You received this e-mail because you have an account on VokalBoard.com.",
    "fr": "Vous recevez cet e-mail parce que vous avez un compte sur VokalBoard.com.",
    "it": "Ricevi questa e-mail perché hai un account su VokalBoard.com.",
    "pt": "Você recebeu este e-mail porque tem uma conta no VokalBoard.com.",
    "es": "Recibes este correo porque tienes una cuenta en VokalBoard.com.",
    "ro": "Primești acest e-mail pentru că ai un cont pe VokalBoard.com.",
}
_BUILTIN_SIGNATURES = {"Equipe VokalBoard", _SIGNATURE_BY_LANG["en"]}
_BUILTIN_FOOTERS = {"Você recebeu este e-mail porque tem uma conta no VokalBoard.", _FOOTER_BY_LANG["en"]}

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_SCRIPT_TAG_RE = re.compile(r"<\s*script\b[^>]*>.*?<\s*/\s*script\s*>", re.IGNORECASE | re.DOTALL)


def get_email_layout_settings() -> dict:
    rows = fetch_all(
        "SELECT key, value FROM system_settings WHERE key = ANY(:keys)",
        {"keys": list(_DEFAULTS)},
    )
    saved = {r["key"]: r["value"] for r in rows}
    return {key: (saved.get(key) or default) for key, default in _DEFAULTS.items()}


def update_email_layout_settings(
    logo_url: str | None,
    accent_color: str,
    header_emoji: str,
    signature: str,
    footer: str,
    updated_by_user_id: int,
) -> None:
    """Atualiza as 5 configurações do formulário simples. `logo_url`
    None = mantém o logo atual (o Admin não é obrigado a reenviar um
    arquivo toda vez que edita só o texto). Cor inválida (fora do
    formato #rrggbb) cai pro padrão do site, nunca vira CSS quebrado."""
    values = {
        "email_layout_accent_color": accent_color if _HEX_COLOR_RE.match(accent_color or "") else _DEFAULTS["email_layout_accent_color"],
        "email_layout_header_emoji": (header_emoji or _DEFAULTS["email_layout_header_emoji"]).strip()[:8],
        "email_layout_signature": signature.strip()[:300],
        "email_layout_footer": footer.strip()[:500],
    }
    if logo_url is not None:
        values["email_layout_logo_url"] = logo_url

    for key, value in values.items():
        execute(
            "UPDATE system_settings SET value = :value, updated_at = now(), updated_by_user_id = :uid WHERE key = :key",
            {"key": key, "value": value, "uid": updated_by_user_id},
        )


def _upsert_template_setting(value: str, updated_by_user_id: int) -> None:
    # INSERT ... ON CONFLICT (não UPDATE puro): ao contrário das outras
    # 5 chaves do formulário (seedadas desde db/schema.sql),
    # "email_layout_template_html" nunca precisa de uma linha pré-
    # existente — evita duplicar um HTML grande em duas migrations
    # (o "molde de fábrica" já vive só em DEFAULT_TEMPLATE_HTML acima).
    execute(
        """
        INSERT INTO system_settings (key, value, updated_at, updated_by_user_id)
        VALUES ('email_layout_template_html', :value, now(), :uid)
        ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value, updated_at = now(), updated_by_user_id = EXCLUDED.updated_by_user_id
        """,
        {"value": value, "uid": updated_by_user_id},
    )


def update_email_template(template_html: str, updated_by_user_id: int) -> bool:
    """Salva o HTML cru da aba Código. Retorna False (sem salvar
    nada) se faltar o placeholder {{BODY}} ou passar do tamanho
    máximo — nesses casos o corpo do e-mail sumiria de todo envio
    automático, então a validação bloqueia ANTES de gravar, não
    depois. Remove <script> por precaução (ver docstring do módulo)."""
    template_html = _SCRIPT_TAG_RE.sub("", template_html).strip()
    if REQUIRED_TOKEN not in template_html or len(template_html) > MAX_TEMPLATE_LENGTH:
        return False
    _upsert_template_setting(template_html, updated_by_user_id)
    return True


def reset_email_template(updated_by_user_id: int) -> None:
    """Restaura o molde padrão (DEFAULT_TEMPLATE_HTML) — o botão
    "Restaurar padrão" da aba Código, pra desfazer uma edição que
    quebrou o visual sem precisar lembrar o HTML original."""
    _upsert_template_setting(DEFAULT_TEMPLATE_HTML, updated_by_user_id)


def _nl2br(text: str) -> str:
    return escape(text).replace("\n", "<br>")


def _recipient_language(recipient_email: str | None) -> str:
    if not recipient_email:
        return "en"
    row = fetch_one("SELECT preferred_language FROM users WHERE lower(email) = lower(:e)", {"e": recipient_email})
    return email_language(row["preferred_language"] if row else None)


def render_email(body_html: str, recipient_email: str | None = None) -> str:
    """Embrulha `body_html` (já pronto — parágrafos/links que cada
    função de e-mail monta, sem mudança nenhuma) com o layout
    compartilhado (molde da aba Código + valores da aba Formulário).
    Chamado automaticamente por `send_email()` — nunca precisa ser
    chamado à mão em outro lugar.

    {{BODY}} é substituído POR ÚLTIMO de propósito: se o corpo de um
    e-mail específico contiver, por acaso, o texto literal de um dos
    outros placeholders (ex.: um título de vaga com "{{LOGO}}" dentro,
    caso extremo mas possível), ele não é tocado de novo — os outros
    placeholders já foram trocados antes do corpo entrar no molde.
    """
    settings = get_email_layout_settings()
    accent = settings["email_layout_accent_color"]

    logo_html = ""
    logo_url = settings["email_layout_logo_url"]
    if logo_url and SITE_BASE_URL:
        full_logo_url = logo_url if logo_url.startswith("http") else f"{SITE_BASE_URL}{logo_url}"
        logo_html = (
            f'<img src="{escape(full_logo_url, quote=True)}" alt="VokalBoard" '
            f'style="max-height:40px; vertical-align:middle; margin-right:10px;">'
        )

    template = settings["email_layout_template_html"] or DEFAULT_TEMPLATE_HTML
    template = template.replace("{{ACCENT}}", accent)
    template = template.replace("{{LOGO}}", logo_html)
    template = template.replace("{{EMOJI}}", escape(settings["email_layout_header_emoji"]))
    lang = _recipient_language(recipient_email)
    signature = settings["email_layout_signature"]
    if signature.strip() in _BUILTIN_SIGNATURES:
        signature = _SIGNATURE_BY_LANG[lang]
    footer = settings["email_layout_footer"]
    if footer.strip() in _BUILTIN_FOOTERS:
        footer = _FOOTER_BY_LANG[lang]
    template = template.replace("{{SIGNATURE}}", _nl2br(signature))
    template = template.replace("{{FOOTER}}", _nl2br(footer))
    template = template.replace(REQUIRED_TOKEN, body_html)
    return template

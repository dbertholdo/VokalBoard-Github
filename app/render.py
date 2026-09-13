"""
Wrapper fino em volta do Jinja2Templates do FastAPI para injetar, em
todo template renderizado: as ferramentas de tradução (`t`) e o idioma
atual (`lang`); os links para trocar de idioma mantendo a página e os
filtros atuais; o token CSRF do formulário (`csrf_token` — veja
app/csrf.py); e, se houver alguém logado, a contagem de mensagens não
lidas (`unread_count`), usada no badge do menu.
"""
from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.i18n import translate, SUPPORTED_LANGUAGES
from app.csrf import get_or_create_csrf_token
from app.database import fetch_one
from app.captcha import HONEYPOT_FIELD, TURNSTILE_SITE_KEY, captcha_enabled

templates = Jinja2Templates(directory="app/templates")


def render(request: Request, template_name: str, context: dict | None = None, status_code: int = 200):
    context = dict(context or {})
    lang = getattr(request.state, "lang", "de")

    context["request"] = request
    context["lang"] = lang
    context["t"] = lambda key: translate(key, lang)
    context["lang_urls"] = {
        code: str(request.url.include_query_params(lang=code)) for code in SUPPORTED_LANGUAGES
    }
    context["csrf_token"] = get_or_create_csrf_token(request)

    # Anti-bot: disponível em TODO template (honeypot_field é o nome
    # do campo-armadilha; turnstile_* só tem efeito se configurado —
    # ver app/captcha.py). Só os formulários mais visados por bots
    # (cadastro, "esqueci minha senha") de fato usam isso.
    context["honeypot_field"] = HONEYPOT_FIELD
    context["captcha_enabled"] = captcha_enabled()
    context["turnstile_site_key"] = TURNSTILE_SITE_KEY

    user_id = request.session.get("user_id")
    context["unread_count"] = 0
    if user_id:
        row = fetch_one(
            "SELECT count(*) AS n FROM messages WHERE recipient_id = :id AND recipient_status = 'active' AND read_at IS NULL",
            {"id": user_id},
        )
        context["unread_count"] = row["n"] if row else 0

    return templates.TemplateResponse(template_name, context, status_code=status_code)

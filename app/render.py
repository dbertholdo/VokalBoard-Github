"""
Wrapper fino em volta do Jinja2Templates do FastAPI para injetar, em
todo template renderizado: as ferramentas de tradução (`t`) e o idioma
atual (`lang`); os links para trocar de idioma mantendo a página e os
filtros atuais; o token CSRF do formulário (`csrf_token` — veja
app/csrf.py); e, se houver alguém logado, a contagem de mensagens não
lidas (`unread_count`), usada no badge do menu.
"""
from datetime import datetime, timedelta, timezone

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.i18n import translate, SUPPORTED_LANGUAGES
from app.csrf import get_or_create_csrf_token
from app.database import fetch_one, execute
from app.captcha import HONEYPOT_FIELD, TURNSTILE_SITE_KEY, captcha_enabled
from app.financial_settings import is_capitalismo_mode_enabled, get_subscription_prices_cents

templates = Jinja2Templates(directory="app/templates")

# "Usuários ativos agora" (painel de Análise de Dados do admin) usa
# users.last_seen_at. Atualizar isso a CADA página carregada seria um
# UPDATE a mais em toda requisição — desnecessário, já que "ativo nos
# últimos 60 min" não precisa de precisão ao segundo. Por isso só
# atualiza de novo depois desse intervalo (mesmo padrão de "cooldown"
# usado em profile_views/site_visits).
_LAST_SEEN_UPDATE_COOLDOWN = timedelta(minutes=5)
_LAST_SEEN_SESSION_KEY = "last_seen_updated_at"


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
    # Usado nos poucos <script nonce="..."> inline do site (ver
    # SecurityHeadersMiddleware em app/main.py, que gera um valor novo
    # por requisição e monta o cabeçalho Content-Security-Policy) —
    # "" como fallback pra qualquer chamada de render() que por algum
    # motivo não passe por aquele middleware (ex: alguns testes).
    context["csp_nonce"] = getattr(request.state, "csp_nonce", "")

    # Anti-bot: disponível em TODO template (honeypot_field é o nome
    # do campo-armadilha; turnstile_* só tem efeito se configurado —
    # ver app/captcha.py). Só os formulários mais visados por bots
    # (cadastro, "esqueci minha senha") de fato usam isso.
    context["honeypot_field"] = HONEYPOT_FIELD
    context["captcha_enabled"] = captcha_enabled()
    context["turnstile_site_key"] = TURNSTILE_SITE_KEY

    # Modo Capitalismo: enquanto desligado (padrão), capitalismo_mode_enabled
    # é False e nenhum template mostra nada relacionado a cobrança — nem
    # o banner de assinatura, nem preço. Ver app/financial_settings.py
    # e a Zona Vermelha (app/routers/financial_routes.py).
    context["capitalismo_mode_enabled"] = is_capitalismo_mode_enabled()
    context["subscription_prices"] = get_subscription_prices_cents()

    user_id = request.session.get("user_id")
    context["unread_count"] = 0
    context["has_active_subscription"] = False
    if user_id:
        row = fetch_one(
            "SELECT count(*) AS n FROM messages WHERE recipient_id = :id AND recipient_status = 'active' AND read_at IS NULL",
            {"id": user_id},
        )
        context["unread_count"] = row["n"] if row else 0

        if context["capitalismo_mode_enabled"]:
            sub = fetch_one(
                "SELECT id FROM subscriptions WHERE user_id = :id AND is_active = TRUE AND (expires_at IS NULL OR expires_at > now())",
                {"id": user_id},
            )
            context["has_active_subscription"] = sub is not None

        now = datetime.now(timezone.utc)
        last_updated = request.session.get(_LAST_SEEN_SESSION_KEY)
        should_update = True
        if last_updated:
            try:
                should_update = (now - datetime.fromisoformat(last_updated)) > _LAST_SEEN_UPDATE_COOLDOWN
            except ValueError:
                should_update = True
        if should_update:
            request.session[_LAST_SEEN_SESSION_KEY] = now.isoformat()
            execute("UPDATE users SET last_seen_at = now() WHERE id = :id", {"id": user_id})

    return templates.TemplateResponse(template_name, context, status_code=status_code)

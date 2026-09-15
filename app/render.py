"""
Thin wrapper around FastAPI's Jinja2Templates to inject, into every
rendered template: the translation tools (`t`) and the current
language (`lang`); the links to switch language while keeping the
page and current filters; the form's CSRF token (`csrf_token` — see
app/csrf.py); and, if someone is logged in, the unread message count
(`unread_count`), used in the menu badge.
"""
from datetime import datetime, timedelta, timezone

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.i18n import translate, SUPPORTED_LANGUAGES, LANGUAGE_META
from app.csrf import get_or_create_csrf_token
from app.database import fetch_one, execute
from app.captcha import HONEYPOT_FIELD, TURNSTILE_SITE_KEY, captcha_enabled
from app.financial_settings import is_capitalismo_mode_enabled, get_subscription_prices_cents

templates = Jinja2Templates(directory="app/templates")

# "Active users now" (the admin's Analytics panel) uses
# users.last_seen_at. Updating this on EVERY page load would be one
# more UPDATE on every request — unnecessary, since "active in the
# last 60 min" doesn't need second-level precision. So it only
# updates again after this interval (the same "cooldown" pattern used
# in profile_views/site_visits).
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
    context["language_meta"] = LANGUAGE_META
    context["supported_languages"] = SUPPORTED_LANGUAGES
    context["csrf_token"] = get_or_create_csrf_token(request)
    # Used in the site's few inline <script nonce="..."> tags (see
    # SecurityHeadersMiddleware in app/main.py, which generates a new
    # value per request and builds the Content-Security-Policy
    # header) — "" as a fallback for any render() call that for some
    # reason doesn't go through that middleware (e.g. some tests).
    context["csp_nonce"] = getattr(request.state, "csp_nonce", "")

    # Anti-bot: available in EVERY template (honeypot_field is the
    # name of the trap field; turnstile_* only has an effect if
    # configured — see app/captcha.py). Only the forms most targeted
    # by bots (sign-up, "forgot my password") actually use this.
    context["honeypot_field"] = HONEYPOT_FIELD
    context["captcha_enabled"] = captcha_enabled()
    context["turnstile_site_key"] = TURNSTILE_SITE_KEY

    # Capitalism Mode: while off (the default), capitalismo_mode_enabled
    # is False and no template shows anything related to billing —
    # neither the subscription banner nor a price. See
    # app/financial_settings.py and the Red Zone
    # (app/routers/financial_routes.py).
    context["capitalismo_mode_enabled"] = is_capitalismo_mode_enabled()
    context["subscription_prices"] = get_subscription_prices_cents()

    # Used by the sidebar (base.html): inside /admin or /financeiro
    # it switches content (admin-only links) instead of showing
    # Start/Jobs/My profile like on any other page — computed here,
    # once, instead of in every route.
    path = request.url.path
    context["is_admin_area"] = path.startswith("/admin") or path.startswith("/financeiro")

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

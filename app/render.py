"""
Thin wrapper around FastAPI's Jinja2Templates to inject, into every
rendered template: the translation tools (`t`) and the current
language (`lang`); the links to switch language while keeping the
page and current filters; the form's CSRF token (`csrf_token` — see
app/csrf.py); and, if someone is logged in, the unread message count
(`unread_count`), used in the menu badge.
"""
from app.seo import GOOGLE_SITE_VERIFICATION, page_links, public_base
from app.match_service import count_pending_for_user
from datetime import datetime, timedelta, timezone

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.i18n import translate, SUPPORTED_LANGUAGES, LANGUAGE_META
from app.i18n_locales import page_language
from app.messenger import unread_counts, unread_messages_notification
from app.csrf import get_or_create_csrf_token
from app.database import fetch_one, execute
from app.captcha import HONEYPOT_FIELD, TURNSTILE_SITE_KEY, captcha_enabled
from app.financial_settings import is_capitalismo_mode_enabled, get_subscription_prices_cents
from app.banners import visible_banners
from app.fees import format_fee as _format_fee
from app.match_evaluations import get_pending_evaluations
from app.invoice_match_drafts import count_pending_actions
from app.notas_wallet import format_notas as _format_notas
from app.mascot_moments import pending_reminder_key
from app.notification_center import get_unread_count as _get_notification_unread_count
from app.notification_center import (
    get_recent_notifications,
    profile_incomplete_notification,
    render_notification_title,
    notification_style,
    notification_relative_time,
)

templates = Jinja2Templates(directory="app/templates")
# Clock times in the site's zone (the DB stores UTC) — see app/messenger.local_time.
from app.messenger import local_time as _local_time  # noqa: E402
templates.env.filters["local_time"] = _local_time

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
    # Admin pages stay English for languages added after the core five
    # (es/zh/ko/ro — see app/i18n_locales.py); `lang` itself (picker, cookie)
    # remains the viewer's choice.
    text_lang = page_language(lang, template_name)

    context["request"] = request
    context["lang"] = lang
    context["page_status"] = status_code
    context["seo"] = page_links(request, lang)  # canonical + hreflang (app/seo.py)
    context["seo_base"] = public_base(request)
    context["google_site_verification"] = GOOGLE_SITE_VERIFICATION
    context["t"] = lambda key: translate(key, text_lang)
    # FIX (19/09/2026, Daniel: "a área Admin/God Mode precisa
    # NECESSARIAMENTE ser em inglês somente") — a handful of admin
    # templates (admin.html, admin_posts.html, admin_user_detail.html)
    # were reusing public-facing i18n keys (by_author, eval_category_*,
    # eval_tier_*, ...) through the normal t() call, which follows the
    # VIEWER's own site language — so an admin who browses the rest of
    # the site in Portuguese would see those few admin strings in
    # Portuguese too. t_en() reuses the exact same TRANSLATIONS dict
    # (never a duplicated hardcoded string to drift out of sync) but
    # always resolves to English, independent of `lang` above — admin
    # templates use this instead of t() for any shared key. See
    # AI_CHANGELOG.md for the full list of call sites fixed.
    context["t_en"] = lambda key: translate(key, "en")
    # P3.E: templates call format_fee(amount, currency, negotiable) —
    # the "A negociar" label is already resolved to the current
    # language here, so app/fees.py itself never has to import i18n.
    context["format_fee"] = lambda amount, currency, negotiable: _format_fee(
        amount, currency, negotiable, translate("fee_negotiable_label", text_lang)
    )
    # P5 Etapa 1 (18/09/2026): Notas agora suportam fração (0,50 Nota
    # por vaga postada) — format_notas() mostra inteiro sem decimais
    # ("3") e fração com vírgula ("0,50"), disponível em qualquer
    # template que precise exibir um valor de Notas.
    context["format_notas"] = _format_notas
    # Central de Notificações (19/09/2026, task #50): lets base.html
    # render a notification's title without importing app.i18n itself.
    context["render_notification_title"] = lambda n: render_notification_title(n, context["t"])
    # Dropdown redesign (19/09/2026) — per-row icon badge color/icon by
    # notification type, and a "20m ago"/"1h ago" relative time label.
    # See app/notification_center.py for both.
    context["notification_style"] = notification_style
    context["notification_relative_time"] = lambda n: notification_relative_time(n["created_at"], context["t"])
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
    admin_user = context.get("user")
    if context["is_admin_area"] and admin_user and (admin_user.get("role_level") or 0) >= 2:
        from app.admin_nav import admin_attention_counts
        context.setdefault("admin_counts", admin_attention_counts())
    context["site_banners"] = [] if context["is_admin_area"] else visible_banners(context.get("user"))

    # Part 2 backlog item 4 (19/09/2026) — Acolhedor mascot toast: a
    # one-shot flag set by app/routers/auth_routes.py right after a
    # successful login, popped (read + cleared) here so it fires
    # exactly once, on the very next page render, wherever the login
    # redirect lands — never again until the next login. See
    # app/mascot_moments.py for the full mascot-moments writeup.
    context["mascot_welcome_name"] = None
    if request.session.pop("show_welcome_toast", False):
        welcome_user = context.get("user")
        context["mascot_welcome_name"] = welcome_user["full_name"] if welcome_user else None

    user_id = request.session.get("user_id")
    context["unread_count"] = 0
    context["pending_invitations_count"] = 0
    context["has_active_subscription"] = False
    context["mascot_reminder_key"] = None
    if user_id:
        # Messenger: unread chat messages + pending requests (app/messenger.py).
        message_counts = unread_counts(user_id)
        context["unread_count"] = message_counts["inbox"] + message_counts["requests"]

        # P3.B nav badge: convites recebidos (I'm the artist, someone
        # else started it) + candidaturas recebidas (I'm the
        # contractor of the vacancy's listing, and the artist started
        # it) — the two cases where I'M the one who owes a response.
        context["pending_invitations_count"] = count_pending_for_user(user_id)

        # P3.F nav badge: quantos Matches dentro da janela de 14 dias eu
        # ainda não avaliei (ver app/match_evaluations.py). Não faz
        # SELECT nenhum em match_evaluations além disso — nunca expõe
        # nota/avaliador de ninguém, só uma contagem.
        context["pending_evaluations_count"] = len(get_pending_evaluations(user_id))

        # P4 Etapa 3 nav badge: rascunhos de Rechnung de Match onde é a
        # vez desta pessoa agir (ver app/invoice_match_drafts.py).
        context["pending_invoice_actions_count"] = count_pending_actions(user_id)

        # Central de Notificações (19/09/2026, task #50) — see
        # app/notification_center.py. This is a separate, real list of
        # discrete events (bell dropdown), NOT the same thing as the
        # live pending-count badges above. The one synthetic item
        # (incomplete profile) is merged in here at read time, ahead
        # of the stored ones, so the template never has to know the
        # difference.
        context["notification_unread_count"] = _get_notification_unread_count(user_id)
        notifications = list(get_recent_notifications(user_id))
        synthetic_notification = profile_incomplete_notification(context["user"]) if context.get("user") else None
        if synthetic_notification:
            notifications.insert(0, synthetic_notification)
            context["notification_unread_count"] += 1
        # Messenger: a message unread for 5+ minutes shows up here too.
        unread_messages = unread_messages_notification(user_id)
        if unread_messages:
            notifications.insert(0, unread_messages)
            context["notification_unread_count"] += 1
        context["notifications"] = notifications

        # Atento mascot toast (Part 2 backlog item 4, 19/09/2026): shown
        # once per session, reusing the two counts above (no extra
        # query for those) — only runs the (cheap) profile-completeness
        # check when both are already zero. See app/mascot_moments.py.
        if not request.session.get("mascot_reminder_shown") and context.get("user"):
            reminder_key = pending_reminder_key(
                context["user"], context["pending_evaluations_count"], context["pending_invitations_count"]
            )
            if reminder_key:
                context["mascot_reminder_key"] = reminder_key
                request.session["mascot_reminder_shown"] = True

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

    # Starlette 1.x requires Request as the first argument. Keeping this
    # compatibility point central prevents every route from depending on the
    # template engine's calling convention.
    return templates.TemplateResponse(request, template_name, context, status_code=status_code)

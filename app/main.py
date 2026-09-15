import os
import re
import secrets
import sys
import traceback
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

from app.avatars import AVATAR_DIR, STORAGE_EXTENSION
from app.post_images import POST_IMAGE_DIR, STORAGE_EXTENSION as POST_IMAGE_STORAGE_EXTENSION
from app.auth import get_current_user
from app.database import engine, fetch_all, execute
from app.i18n import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE, LANGUAGE_META, translate
from app.render import render, templates
from app.routers import auth_routes, listings_routes, profile_routes, messages_routes, legal_routes, admin_routes, financial_routes, search_people_routes, notas_routes

load_dotenv()

app = FastAPI(title="VokalBoard")

_DEFAULT_SECRET_KEY = "dev-secret-key-change-in-production"
if os.getenv("SECRET_KEY", _DEFAULT_SECRET_KEY) == _DEFAULT_SECRET_KEY:
    # Loud log warning — easy to forget to change this when setting up
    # a platform like Railway/Render for the first time. Doesn't stop
    # the app from booting (we don't want to block deploys), just
    # warns as loudly as possible.
    print(
        "!! WARNING: SECRET_KEY is not set (using the default development "
        "value). Generate a real key with "
        "`python -c \"import secrets; print(secrets.token_hex(32))\"` and "
        "set the SECRET_KEY environment variable before going to production.",
        file=sys.stderr,
    )


# True in production (Railway sets this via an environment variable —
# see .env.example) makes the session cookie only be sent over HTTPS,
# and enables the HSTS header below (see SecurityHeadersMiddleware).
# Defaults to False so running the project locally without HTTPS
# doesn't break.
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Response headers that don't change anything visually, but close
    off a few classic browser attack vectors:

    - X-Content-Type-Options: stops the browser from "guessing" a
      file's type (e.g. treating an upload as executable HTML/JS).
    - X-Frame-Options: stops the site from being embedded inside
      another site's <iframe> (protects against "clickjacking" — a
      malicious site overlaying invisible buttons on top of yours).
    - Referrer-Policy: when someone clicks a link that leaves
      VokalBoard, the destination site only gets the origin domain,
      not the full URL (which could contain something sensitive,
      like a token).
    - Permissions-Policy: turns off browser access to camera/
      microphone/geolocation — the site never uses any of that.
    - Strict-Transport-Security (only when SESSION_COOKIE_SECURE=true,
      i.e. in production with real HTTPS): tells the browser to
      ALWAYS use HTTPS for this domain from now on, even if someone
      types "http://" by mistake.
    - Content-Security-Policy: tells the browser exactly where
      scripts/styles/images/etc are allowed to come from — even if an
      XSS manages to inject HTML into the page (e.g. a field that
      escaped due to some bug), the browser refuses to EXECUTE a
      <script> that isn't tagged with the right "nonce" (only the
      server knows each request's nonce, generated below).

    The site has a few inline <script> tags in templates (the flying
    bird, the animated background, the captcha widget — see
    base.html / _captcha_fields.html), so script-src uses
    'nonce-<value>' (not 'unsafe-inline') — every <script> needs the
    nonce="{{ csp_nonce }}" attribute (see app/render.py, which
    injects csp_nonce into every template from
    request.state.csp_nonce, generated below). style-src still keeps
    'unsafe-inline' on purpose: the site uses plenty of inline
    style="..." for dynamic bits (e.g. the bar widths on
    /admin/analytics), and nonce doesn't cover style attributes —
    only <script>/<style> as elements.
    """

    async def dispatch(self, request: Request, call_next):
        # A new value per REQUEST (not per process) — so nobody can
        # "reuse" a nonce seen in a previous response to slip a
        # malicious script into a different one.
        request.state.csp_nonce = secrets.token_urlsafe(16)

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{request.state.csp_nonce}' https://challenges.cloudflare.com; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-src https://challenges.cloudflare.com; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'self';"
        )
        if SESSION_COOKIE_SECURE:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


# Paths that don't count as a real "visit" for the Analytics dashboard
# counter (static files, health check, robots/sitemap, and the admin
# routes themselves — so the number isn't inflated by the admin's own
# browsing).
_VISIT_TRACKING_SKIP_PREFIXES = ("/static", "/avatars", "/health", "/robots.txt", "/sitemap.xml", "/admin", "/financeiro")
_VISIT_SESSION_KEY = "last_site_visit_logged_at"
_VISIT_COOLDOWN = timedelta(hours=12)


class VisitTrackingMiddleware(BaseHTTPMiddleware):
    """
    Counts overall site visits (see the site_visits table in
    db/schema.sql) — used in the admin "Analytics" dashboard to
    understand peak time-of-day / day-of-week / day-of-month usage.

    Deliberately does NOT store an IP or anything that identifies the
    person — it only counts 1 visit per browser session every 12h
    (same "cooldown" pattern already used in profile_views), along
    with the language and the domain the person came from (e.g.
    "google.com"), never the full URL. No cookie banner needed: this
    isn't cross-site tracking or a personal profile, just an
    aggregate count.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        path = request.url.path
        if request.method == "GET" and not path.startswith(_VISIT_TRACKING_SKIP_PREFIXES):
            last_logged = request.session.get(_VISIT_SESSION_KEY)
            now = datetime.now(timezone.utc)
            should_log = True
            if last_logged:
                try:
                    should_log = (now - datetime.fromisoformat(last_logged)) > _VISIT_COOLDOWN
                except ValueError:
                    should_log = True

            if should_log:
                request.session[_VISIT_SESSION_KEY] = now.isoformat()
                referrer_domain = None
                referer_header = request.headers.get("referer", "")
                if referer_header:
                    try:
                        parsed_host = urlparse(referer_header).netloc
                        if parsed_host and parsed_host != request.url.netloc:
                            referrer_domain = parsed_host[:255]
                    except ValueError:
                        referrer_domain = None
                execute(
                    """
                    INSERT INTO site_visits (lang, referrer_domain, is_authenticated)
                    VALUES (:lang, :referrer_domain, :is_authenticated)
                    """,
                    {
                        "lang": request.cookies.get("lang", DEFAULT_LANGUAGE)[:5],
                        "referrer_domain": referrer_domain,
                        "is_authenticated": bool(request.session.get("user_id")),
                    },
                )

        return response


class LanguageMiddleware(BaseHTTPMiddleware):
    """
    Decides the current request's language and stores it in
    `request.state.lang`.

    Priority: ?lang=de|en in the URL (in which case it also sets a
    cookie for future visits) > an already-saved "lang" cookie >
    German as the default, since the site's main audience is in
    Germany.
    """

    async def dispatch(self, request: Request, call_next):
        query_lang = request.query_params.get("lang")
        cookie_lang = request.cookies.get("lang")

        if query_lang in SUPPORTED_LANGUAGES:
            lang = query_lang
        elif cookie_lang in SUPPORTED_LANGUAGES:
            lang = cookie_lang
        else:
            lang = DEFAULT_LANGUAGE

        request.state.lang = lang
        response = await call_next(request)

        if query_lang in SUPPORTED_LANGUAGES and query_lang != cookie_lang:
            response.set_cookie("lang", query_lang, max_age=60 * 60 * 24 * 365, samesite="lax")

        return response


# Order matters here: the LAST "add_middleware" call is the OUTERMOST
# one (runs first for the request, last for the response) — see
# https://www.starlette.io/middleware/#multiple-middleware.
# SessionMiddleware needs to be the outermost of all of ours, because
# both VisitTrackingMiddleware and the routes (login, CSRF, etc.)
# read/write request.session — if SessionMiddleware didn't "wrap" the
# others from the outside, those writes would be lost and would never
# turn into a real cookie on the response.
app.add_middleware(LanguageMiddleware)
app.add_middleware(VisitTrackingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "dev-secret-key-change-in-production"),
    same_site="lax",
    https_only=SESSION_COOKIE_SECURE,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Profile pictures do NOT live inside /static — on purpose, so
# AVATAR_DIR (app/avatars.py) can point outside app/static (e.g. a
# persistent Volume mounted at /data/avatars on Railway) without
# having to reconfigure StaticFiles for it. This route serves the
# files from wherever AVATAR_DIR points to.
_AVATAR_FILENAME_RE = re.compile(r"^\d+" + re.escape(STORAGE_EXTENSION) + r"$")


@app.get("/avatars/{filename}")
def serve_avatar(filename: str):
    if not _AVATAR_FILENAME_RE.match(filename):
        raise HTTPException(status_code=404)
    path = os.path.join(AVATAR_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "public, max-age=86400"})


# Images embedded inside posts (WordPress-style editor — see
# app/post_images.py and POST /admin/posts/upload-image in
# app/routers/admin_routes.py). Same scheme as /avatars: its own
# route (not StaticFiles) so POST_IMAGE_DIR can point outside
# app/static/, and the filename is validated before it becomes a disk
# path.
_POST_IMAGE_FILENAME_RE = re.compile(r"^[A-Za-z0-9]+" + re.escape(POST_IMAGE_STORAGE_EXTENSION) + r"$")


@app.get("/post-images/{filename}")
def serve_post_image(filename: str):
    if not _POST_IMAGE_FILENAME_RE.match(filename):
        raise HTTPException(status_code=404)
    path = os.path.join(POST_IMAGE_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/robots.txt")
def robots_txt(request: Request):
    """
    SEO: tells crawlers (Google etc.) what they can/can't index and
    where the sitemap is. We block private/no-search-value areas
    (login, registration, messages, own profile, admin) — not because
    they're secret (robots.txt is public), but to avoid wasting
    Google's "crawl budget" on pages that require login anyway.
    """
    base = str(request.base_url).rstrip("/")
    lines = [
        "User-agent: *",
        "Disallow: /admin",
        "Disallow: /financeiro",
        "Disallow: /login",
        "Disallow: /register",
        "Disallow: /messages",
        "Disallow: /profile",
        "Disallow: /my-listings",
        "Disallow: /my-favorites",
        "Disallow: /forgot-password",
        "Disallow: /reset-password",
        # Public profiles: deliberately OUTSIDE the sitemap and blocked
        # here too (see also the <meta name="robots" content="noindex">
        # in public_profile.html) — a real person's name + city
        # shouldn't be permanently searchable on Google. They stay
        # reachable normally via a direct link inside the site.
        "Disallow: /users",
        "",
        f"Sitemap: {base}/sitemap.xml",
        "",
    ]
    return PlainTextResponse("\n".join(lines))


@app.get("/sitemap.xml")
def sitemap_xml(request: Request):
    """
    SEO: list of URLs for Google to index, with each one's last
    modified date — helps the crawler know what's new/changed without
    having to revisit the whole site every time. Includes the static
    (fixed) pages + every active listing + every public profile (only
    for people who verified their email and haven't deleted their
    account).
    """
    base = str(request.base_url).rstrip("/")
    urls: list[dict] = []

    for path, changefreq, priority in [
        ("/", "daily", "1.0"),
        ("/board", "daily", "0.9"),
        ("/impressum", "yearly", "0.2"),
        ("/datenschutz", "yearly", "0.2"),
        ("/code-of-conduct", "yearly", "0.2"),
    ]:
        urls.append({"loc": f"{base}{path}", "lastmod": None, "changefreq": changefreq, "priority": priority})

    listings = fetch_all(
        """
        SELECT l.id, l.updated_at
        FROM listings l
        JOIN users u ON u.id = l.author_id AND u.deleted_at IS NULL
        WHERE l.is_active = TRUE
        ORDER BY l.updated_at DESC
        """
    )
    for row in listings:
        urls.append({
            "loc": f"{base}/listings/{row['id']}",
            "lastmod": row["updated_at"].date().isoformat() if row["updated_at"] else None,
            "changefreq": "weekly",
            "priority": "0.7",
        })

    # Public profiles (/users/{id}) are deliberately left OUT of the
    # sitemap — see the matching comment in robots_txt() above.

    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        xml_parts.append("  <url>")
        xml_parts.append(f"    <loc>{u['loc']}</loc>")
        if u["lastmod"]:
            xml_parts.append(f"    <lastmod>{u['lastmod']}</lastmod>")
        xml_parts.append(f"    <changefreq>{u['changefreq']}</changefreq>")
        xml_parts.append(f"    <priority>{u['priority']}</priority>")
        xml_parts.append("  </url>")
    xml_parts.append("</urlset>")

    return Response(content="\n".join(xml_parts), media_type="application/xml")


app.include_router(auth_routes.router)
app.include_router(listings_routes.router)
app.include_router(profile_routes.router)
app.include_router(messages_routes.router)
app.include_router(legal_routes.router)
app.include_router(admin_routes.router)
app.include_router(financial_routes.router)
app.include_router(search_people_routes.router)
app.include_router(notas_routes.router)


# ------------------------------------------------------------
# Error pages that look like the site, instead of FastAPI's raw
# default JSON ({"detail": "Not Found"}) — reuses the same generic
# "title + message + link" template already used in
# auth_message.html (see app/routers/auth_routes.py, e.g. an invalid
# reset link).
# ------------------------------------------------------------

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Runs INSIDE our SessionMiddleware (see the middleware-order
    comment further up) — meaning request.session is normally
    available here, so it's safe to use app.render.render() (it
    injects t()/csrf_token/etc just like any regular page).
    """
    user = get_current_user(request)
    if exc.status_code == 404:
        context = {
            "user": user,
            "title_key": "error_404_title",
            "message_key": "error_404_message",
            "link_url": "/",
            "link_label_key": "error_back_home",
        }
    else:
        lang = getattr(request.state, "lang", DEFAULT_LANGUAGE)
        context = {
            "user": user,
            "title_key": "error_generic_title",
            "message_key": "error_generic_message",
            "message_extra": translate("error_generic_message", lang).replace("{status}", str(exc.status_code)),
            "link_url": "/",
            "link_label_key": "error_back_home",
        }
    return render(request, "auth_message.html", context, status_code=exc.status_code)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Safety net for a real error (an unexpected bug), not just "page
    not found". Two important things:

    1. Logs the full traceback to stderr (shows up in Railway's
       logs) — without this, a production error would fail silently
       for the admin, and only the person browsing would see
       something broken.
    2. NEVER shows the raw exception's stack trace/message to the
       person browsing (could leak internal system details) — just a
       generic message.

    Runs in the OUTERMOST middleware of all (ServerErrorMiddleware,
    outside even our own SessionMiddleware — see
    https://www.starlette.io/exceptions/) — by the time it gets here,
    the exception has already "unwound" past SessionMiddleware/
    LanguageMiddleware without going through them normally, so
    (unlike the HTTPException handler above) we CANNOT rely on
    request.session or request.state.lang. That's why the page is
    built by hand here, reading the language straight from the
    cookie (which doesn't depend on any middleware).
    """
    print(f"!! UNHANDLED ERROR in {request.method} {request.url.path}:", file=sys.stderr)
    traceback.print_exc()

    lang = request.cookies.get("lang")
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE

    response = templates.TemplateResponse(
        request,
        "auth_message.html",
        {
            "user": None,
            "lang": lang,
            "t": lambda key: translate(key, lang),
            "lang_urls": {code: str(request.url.include_query_params(lang=code)) for code in SUPPORTED_LANGUAGES},
            "language_meta": LANGUAGE_META,
            "supported_languages": SUPPORTED_LANGUAGES,
            "csp_nonce": getattr(request.state, "csp_nonce", ""),
            "title_key": "error_500_title",
            "message_key": "error_500_message",
            "link_url": "/",
            "link_label_key": "error_back_home",
        },
        status_code=500,
    )
    # This handler runs in the OUTERMOST middleware of all (see the
    # SecurityHeadersMiddleware docstring above) — its response does
    # NOT go through the regular SecurityHeadersMiddleware, so the
    # basic security headers are repeated here by hand (CSP is left
    # out on purpose: without the header the browser still applies
    # the right nonce anyway, so there's no risk).
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.get("/health")
def health_check():
    """
    Health check for the deploy platform (Railway/Render). Also tests
    the database connection — without that, the health check would
    say "ok" even with Postgres down, which isn't very useful.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ok"}
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "unreachable", "detail": str(exc)},
        )

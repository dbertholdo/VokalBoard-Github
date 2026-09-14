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
from app.auth import get_current_user
from app.database import engine, fetch_all, execute
from app.i18n import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE, translate
from app.render import render, templates
from app.routers import auth_routes, listings_routes, profile_routes, messages_routes, legal_routes, admin_routes, financial_routes

load_dotenv()

app = FastAPI(title="VokalBoard")

_DEFAULT_SECRET_KEY = "dev-secret-key-troque-em-producao"
if os.getenv("SECRET_KEY", _DEFAULT_SECRET_KEY) == _DEFAULT_SECRET_KEY:
    # Aviso alto no log — fácil de esquecer de trocar isso ao configurar
    # uma plataforma como Railway/Render pela primeira vez. Não impede
    # o app de subir (não queremos travar deploys), só avisa bem alto.
    print(
        "!! AVISO: SECRET_KEY não configurada (usando o valor padrão de "
        "desenvolvimento). Gere uma chave real com "
        "`python -c \"import secrets; print(secrets.token_hex(32))\"` e "
        "configure a variável de ambiente SECRET_KEY antes de ir para produção.",
        file=sys.stderr,
    )


# True em produção (Railway define isso via variável de ambiente — ver
# .env.example) faz o cookie de sessão só ser enviado em HTTPS, e ativa
# o cabeçalho HSTS abaixo (ver SecurityHeadersMiddleware). Fica False
# por padrão pra não quebrar quem roda o projeto localmente sem HTTPS.
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Cabeçalhos de resposta que não mudam nada visualmente, mas fecham
    algumas portas clássicas de ataque no navegador:

    - X-Content-Type-Options: impede o navegador de "adivinhar" o tipo
      de um arquivo (ex: tratar um upload como HTML/JS executável).
    - X-Frame-Options: impede que o site seja colocado dentro de um
      <iframe> de outro site (protege contra "clickjacking" — um site
      malicioso sobrepondo botões invisíveis por cima do seu).
    - Referrer-Policy: quando alguém clica um link que sai do
      VokalBoard, o site de destino recebe só o domínio de origem, não
      a URL completa (que poderia conter algo sensível, tipo um token).
    - Permissions-Policy: desliga o acesso a câmera/microfone/
      geolocalização pelo navegador — o site nunca usa nada disso.
    - Strict-Transport-Security (só quando SESSION_COOKIE_SECURE=true,
      ou seja, em produção com HTTPS de verdade): diz ao navegador pra
      SEMPRE usar HTTPS neste domínio dali pra frente, mesmo que
      alguém digite "http://" por engano.
    - Content-Security-Policy: diz ao navegador exatamente de onde
      pode vir script/estilo/imagem/etc — mesmo que um XSS consiga
      injetar HTML na página (ex: um campo que escapou por algum
      bug), o navegador se recusa a EXECUTAR um <script> que não
      esteja marcado com o "nonce" certo (só o servidor conhece o
      nonce de cada requisição, gerado aqui embaixo).

    O site tem alguns <script> inline nos templates (passarinho
    voador, fundo animado, widget de captcha — ver base.html /
    _captcha_fields.html), então script-src usa 'nonce-<valor>' (não
    'unsafe-inline') — cada <script> precisa do atributo
    nonce="{{ csp_nonce }}" (ver app/render.py, que injeta csp_nonce
    em todo template a partir de request.state.csp_nonce, gerado
    abaixo). style-src continua com 'unsafe-inline' de propósito: o
    site usa bastante style="..." inline pra coisas dinâmicas (ex: a
    largura das barrinhas em /admin/analytics), e nonce não cobre
    atributos style — só <script>/<style> como elemento.
    """

    async def dispatch(self, request: Request, call_next):
        # Um valor novo por REQUISIÇÃO (não por processo) — assim
        # alguém não consegue "reaproveitar" um nonce visto numa
        # resposta anterior pra colar um script malicioso numa outra.
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


# Caminhos que não contam como "visita" de verdade pro contador do
# painel de Análise de Dados (arquivo estático, checagem de saúde,
# robots/sitemap, e as próprias rotas do admin — pra não inflar o
# número com o próprio administrador navegando).
_VISIT_TRACKING_SKIP_PREFIXES = ("/static", "/avatars", "/health", "/robots.txt", "/sitemap.xml", "/admin", "/financeiro")
_VISIT_SESSION_KEY = "last_site_visit_logged_at"
_VISIT_COOLDOWN = timedelta(hours=12)


class VisitTrackingMiddleware(BaseHTTPMiddleware):
    """
    Conta visitas gerais ao site (ver tabela site_visits em
    db/schema.sql) — usado no painel "Análise de Dados" do admin pra
    entender horário do dia / dia da semana / dia do mês de maior uso.

    De propósito NÃO guarda IP nem nada que identifique a pessoa — só
    conta 1 visita por sessão de navegador a cada 12h (mesmo padrão de
    "cooldown" já usado em profile_views), junto com o idioma e o
    domínio de onde a pessoa veio (ex: "google.com"), nunca a URL
    completa. Não precisa de banner de cookie: não é rastreamento
    entre sites nem perfil de pessoa, é só uma contagem agregada.
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
    Decide o idioma da requisição atual e o guarda em `request.state.lang`.

    Prioridade: ?lang=de|en na URL (e nesse caso grava um cookie para as
    próximas visitas) > cookie "lang" já salvo > alemão como padrão,
    já que o público principal do site está na Alemanha.
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


# Ordem importa aqui: o último "add_middleware" chamado é o mais
# EXTERNO (roda primeiro pra requisição, por último pra resposta) —
# ver https://www.starlette.io/middleware/#multiple-middleware.
# SessionMiddleware precisa ser o mais externo de todos os nossos,
# porque tanto VisitTrackingMiddleware quanto as rotas (login, CSRF
# etc.) leem/escrevem em request.session — se SessionMiddleware não
# "envolvesse" os outros por fora, essas escritas se perderiam e
# nunca virariam cookie de verdade na resposta.
app.add_middleware(LanguageMiddleware)
app.add_middleware(VisitTrackingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "dev-secret-key-troque-em-producao"),
    same_site="lax",
    https_only=SESSION_COOKIE_SECURE,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Fotos de perfil NÃO ficam dentro de /static — de propósito, pra
# AVATAR_DIR (app/avatars.py) poder apontar pra fora de app/static
# (ex: um Volume persistente montado em /data/avatars no Railway),
# sem precisar reconfigurar o StaticFiles pra isso. Essa rota serve
# os arquivos de onde quer que AVATAR_DIR esteja apontando.
_AVATAR_FILENAME_RE = re.compile(r"^\d+" + re.escape(STORAGE_EXTENSION) + r"$")


@app.get("/avatars/{filename}")
def serve_avatar(filename: str):
    if not _AVATAR_FILENAME_RE.match(filename):
        raise HTTPException(status_code=404)
    path = os.path.join(AVATAR_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/robots.txt")
def robots_txt(request: Request):
    """
    SEO: diz aos crawlers (Google etc.) o que pode/não pode indexar e
    onde está o sitemap. Bloqueamos áreas privadas/sem valor de busca
    (login, cadastro, mensagens, perfil próprio, admin) — não porque
    sejam secretas (robots.txt é público), mas pra não desperdiçar o
    "crawl budget" do Google em páginas que exigem login mesmo.
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
        # Perfis públicos: de propósito FORA do sitemap e daqui pra baixo
        # (ver também o <meta name="robots" content="noindex"> em
        # public_profile.html) — nome + cidade de uma pessoa real não
        # deveria ficar pesquisável no Google pra sempre. Continuam
        # acessíveis normalmente por link direto dentro do site.
        "Disallow: /users",
        "",
        f"Sitemap: {base}/sitemap.xml",
        "",
    ]
    return PlainTextResponse("\n".join(lines))


@app.get("/sitemap.xml")
def sitemap_xml(request: Request):
    """
    SEO: lista de URLs pro Google indexar, com a data da última
    alteração de cada uma — ajuda o crawler a saber o que é novo/mudou
    sem precisar visitar o site inteiro toda vez. Inclui as páginas
    estáticas (fixas) + cada anúncio ativo + cada perfil público
    (só de quem verificou o e-mail e não excluiu a conta).
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

    # Perfis públicos (/users/{id}) ficam DE FORA do sitemap de propósito
    # — ver o comentário equivalente em robots_txt() acima.

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


# ------------------------------------------------------------
# Páginas de erro com a cara do site, em vez do JSON cru padrão do
# FastAPI ({"detail": "Not Found"}) — reaproveita o mesmo template
# genérico "título + mensagem + link" já usado em auth_message.html
# (ver app/routers/auth_routes.py, ex: link de reset inválido).
# ------------------------------------------------------------

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Roda DENTRO do nosso SessionMiddleware (ver comentário sobre ordem
    dos middlewares mais acima) — ou seja, request.session já está
    disponível normalmente aqui, então dá pra usar app.render.render()
    sem problema (ele injeta t()/csrf_token/etc como em qualquer
    página normal).
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
    Rede de segurança pra erro de verdade (bug não previsto), não só
    "página não encontrada". Duas coisas importantes:

    1. Loga o traceback completo no stderr (aparece nos logs do
       Railway) — sem isso, um erro em produção passaria em silêncio
       pro admin, só a pessoa navegando veria algo quebrado.
    2. NUNCA mostra o stack trace/mensagem crua da exceção pra quem
       está navegando (poderia vazar detalhe interno do sistema) — só
       uma mensagem genérica.

    Roda no middleware mais EXTERNO de todos (ServerErrorMiddleware,
    por fora até do nosso SessionMiddleware — ver
    https://www.starlette.io/exceptions/) — quando chega aqui, a
    exceção já "desenrolou" SessionMiddleware/LanguageMiddleware sem
    passar por eles normalmente, então (ao contrário do handler de
    HTTPException acima) NÃO dá pra contar com request.session ou
    request.state.lang. Por isso monta a página na mão, lendo o
    idioma direto do cookie (isso não depende de middleware nenhum).
    """
    print(f"!! ERRO NÃO TRATADO em {request.method} {request.url.path}:", file=sys.stderr)
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
            "csp_nonce": getattr(request.state, "csp_nonce", ""),
            "title_key": "error_500_title",
            "message_key": "error_500_message",
            "link_url": "/",
            "link_label_key": "error_back_home",
        },
        status_code=500,
    )
    # Esse handler roda no middleware mais EXTERNO de todos (ver
    # docstring do SecurityHeadersMiddleware acima) — a resposta dele
    # NÃO passa pelo SecurityHeadersMiddleware normal, então os
    # cabeçalhos básicos de segurança são repetidos aqui na mão (CSP
    # fica de fora de propósito: sem isso o navegador aplicaria o
    # nonce certo mesmo sem o cabeçalho, então não há risco).
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.get("/health")
def health_check():
    """
    Checagem de saúde pra plataforma de deploy (Railway/Render). Também
    testa a conexão com o banco — sem isso, o healthcheck diria "ok"
    mesmo com o Postgres fora do ar, o que não ajuda muito.
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

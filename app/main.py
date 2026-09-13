import os
import sys

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

from app.database import engine
from app.i18n import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE
from app.routers import auth_routes, listings_routes, profile_routes, messages_routes, legal_routes, admin_routes

load_dotenv()

app = FastAPI(title="Maestro & Cantor")

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


app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "dev-secret-key-troque-em-producao"),
    same_site="lax",
)
app.add_middleware(LanguageMiddleware)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth_routes.router)
app.include_router(listings_routes.router)
app.include_router(profile_routes.router)
app.include_router(messages_routes.router)
app.include_router(legal_routes.router)
app.include_router(admin_routes.router)


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

import html as html_module
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse

from app.database import fetch_one, execute_returning, execute
from app.auth import hash_password, verify_password, get_current_user
from app.render import render
from app.csrf import verify_csrf
from app.email import send_email
from app.avatars import save_avatar
from app.referrals import generate_referral_code, resolve_referrer
from app.routers.profile_routes import parse_hashtags, parse_audio_links, set_audio_links, MAX_BIO_LENGTH
from app.captcha import is_bot, verify_turnstile
from app.locations import COUNTRY_OPTIONS, STATE_OPTIONS, get_city_options

router = APIRouter()

# Mapeia a opção escolhida no formulário de registro ("categoria") para
# um par (role, nome do tipo de voz). O(a) usuário(a) escolhe direto
# "Soprano", "Alto", "Tenor", "Baixo" ou "Dirigent(in)" — não precisamos
# de dois campos separados (role + voz) na tela de cadastro.
CATEGORY_TO_ROLE = {
    "soprano": "singer",
    "alto": "singer",
    "tenor": "singer",
    "baixo": "singer",
    "conductor": "conductor",
}
CATEGORY_TO_VOICE_NAME = {
    "soprano": "Soprano",
    "alto": "Alto",
    "tenor": "Tenor",
    "baixo": "Baixo",
}

VERIFICATION_TOKEN_HOURS = 48
RESET_TOKEN_HOURS = 2


def _expires_at(hours: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def send_verification_email(request: Request, user_id: int, email: str, full_name: str) -> None:
    token = secrets.token_urlsafe(32)
    execute(
        "INSERT INTO email_verification_tokens (user_id, token, expires_at) VALUES (:user_id, :token, :expires_at)",
        {"user_id": user_id, "token": token, "expires_at": _expires_at(VERIFICATION_TOKEN_HOURS)},
    )
    verify_url = f"{str(request.base_url).rstrip('/')}/verify-email?token={token}"
    html = f"""
        <p>Hallo {html_module.escape(full_name)},</p>
        <p>Bitte bestätige deine E-Mail-Adresse für Maestro &amp; Cantor:</p>
        <p><a href="{verify_url}">{verify_url}</a></p>
        <p>Dieser Link ist {VERIFICATION_TOKEN_HOURS} Stunden gültig.</p>
        <hr>
        <p>(EN) Please confirm your email address for Maestro &amp; Cantor using the link above.
        This link is valid for {VERIFICATION_TOKEN_HOURS} hours.</p>
    """
    send_email(email, "Bestätige deine E-Mail-Adresse — Maestro & Cantor", html)


def send_password_reset_email(request: Request, user_id: int, email: str, full_name: str) -> None:
    token = secrets.token_urlsafe(32)
    execute(
        "INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (:user_id, :token, :expires_at)",
        {"user_id": user_id, "token": token, "expires_at": _expires_at(RESET_TOKEN_HOURS)},
    )
    reset_url = f"{str(request.base_url).rstrip('/')}/reset-password?token={token}"
    html = f"""
        <p>Hallo {html_module.escape(full_name)},</p>
        <p>Klicke auf den folgenden Link, um ein neues Passwort festzulegen:</p>
        <p><a href="{reset_url}">{reset_url}</a></p>
        <p>Dieser Link ist {RESET_TOKEN_HOURS} Stunden gültig. Wenn du das nicht angefordert hast, ignoriere diese E-Mail.</p>
        <hr>
        <p>(EN) Click the link above to set a new password. Valid for {RESET_TOKEN_HOURS} hours.
        If you didn't request this, just ignore this email.</p>
    """
    send_email(email, "Passwort zurücksetzen — Maestro & Cantor", html)


def _register_context(request: Request, error: str | None = None, ref: str = ""):
    return {
        "user": None,
        "error": error,
        "max_bio_length": MAX_BIO_LENGTH,
        "ref": ref,
        "country_options": COUNTRY_OPTIONS,
        "state_options": STATE_OPTIONS,
        "city_options": get_city_options(),
    }


@router.get("/register", response_class=HTMLResponse)
def register_form(request: Request, ref: str = ""):
    return render(request, "register.html", _register_context(request, ref=ref))


@router.post("/register")
async def register_submit(
    request: Request,
    csrf_token: str = Form(""),
    category: str = Form(...),
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    city: str = Form(""),
    state: str = Form(""),
    country: str = Form("DE"),
    phone: str = Form(""),
    bio: str = Form(""),
    composer_hashtags: str = Form(""),
    audio_links: str = Form(""),
    ensemble_name: str = Form(""),
    ref: str = Form(""),
    avatar: UploadFile | None = File(None),
    website: str = Form(""),  # honeypot — ver app/captcha.py, nunca preenchido por gente de verdade
    cf_turnstile_response: str = Form("", alias="cf-turnstile-response"),
):
    verify_csrf(request, csrf_token)

    # Anti-bot: campo-armadilha preenchido, ou token do Turnstile
    # inválido (quando configurado) — trata como se fosse um envio
    # normal (mesmo redirecionamento de sucesso), só que SEM criar a
    # conta. Não dá nenhuma pista pro bot sobre o motivo da rejeição.
    if is_bot(website) or not verify_turnstile(cf_turnstile_response):
        return RedirectResponse(url="/", status_code=303)

    if category not in CATEGORY_TO_ROLE:
        return render(request, "register.html", _register_context(request, error="register_error_invalid_category", ref=ref), status_code=400)

    if country not in COUNTRY_OPTIONS:
        return render(request, "register.html", _register_context(request, error="register_error_invalid_country", ref=ref), status_code=400)

    existing = fetch_one("SELECT id FROM users WHERE email = :email", {"email": email})
    if existing:
        return render(
            request,
            "register.html",
            _register_context(request, error="register_error_duplicate", ref=ref),
            status_code=400,
        )

    role = CATEGORY_TO_ROLE[category]
    bio = bio.strip()[:MAX_BIO_LENGTH]
    referred_by_user_id = resolve_referrer(ref)

    new_user = execute_returning(
        """
        INSERT INTO users (email, password_hash, full_name, role, city, state, country, phone, referral_code, referred_by_user_id)
        VALUES (:email, :password_hash, :full_name, :role, :city, :state, :country, :phone, :referral_code, :referred_by_user_id)
        RETURNING id
        """,
        {
            "email": email,
            "password_hash": hash_password(password),
            "full_name": full_name,
            "role": role,
            "city": city or None,
            "state": state or None,
            "country": country,
            "phone": phone or None,
            "referral_code": generate_referral_code(),
            "referred_by_user_id": referred_by_user_id,
        },
    )
    user_id = new_user["id"]

    # Foto de perfil é opcional no cadastro — se vier um arquivo
    # inválido (tipo/tamanho), simplesmente ignora em vez de travar o
    # cadastro inteiro por causa da foto; a pessoa pode tentar de novo
    # depois em /profile.
    if avatar is not None and avatar.filename:
        avatar_url = await save_avatar(user_id, avatar)
        if avatar_url:
            execute("UPDATE users SET avatar_url = :avatar_url WHERE id = :id", {"avatar_url": avatar_url, "id": user_id})

    if role == "singer":
        voice_type = fetch_one(
            "SELECT id FROM voice_types WHERE name = :name", {"name": CATEGORY_TO_VOICE_NAME[category]}
        )
        execute(
            """
            INSERT INTO singer_profiles (user_id, voice_type_id, bio)
            VALUES (:user_id, :voice_type_id, :bio)
            """,
            {
                "user_id": user_id,
                "voice_type_id": voice_type["id"] if voice_type else None,
                "bio": bio or None,
            },
        )

        for tag in parse_hashtags(composer_hashtags):
            execute(
                "INSERT INTO singer_composer_tags (user_id, tag) VALUES (:user_id, :tag)",
                {"user_id": user_id, "tag": tag},
            )

        set_audio_links(user_id, parse_audio_links(audio_links))
    else:
        execute(
            """
            INSERT INTO conductor_profiles (user_id, ensemble_name, bio)
            VALUES (:user_id, :ensemble_name, :bio)
            """,
            {"user_id": user_id, "ensemble_name": ensemble_name or None, "bio": bio or None},
        )

    send_verification_email(request, user_id, email, full_name)

    request.session["user_id"] = user_id
    return RedirectResponse(url="/", status_code=303)


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return render(request, "login.html", {"user": None, "error": None})


@router.post("/login")
def login_submit(request: Request, csrf_token: str = Form(""), email: str = Form(...), password: str = Form(...)):
    verify_csrf(request, csrf_token)

    # Nota: aqui buscamos mesmo contas com deleted_at preenchido — de
    # propósito, pra poder diferenciar "senha errada" de "essa conta
    # foi excluída, você quer reativar?" no passo seguinte.
    user = fetch_one(
        "SELECT id, password_hash, deleted_at FROM users WHERE email = :email", {"email": email}
    )
    if not user or not verify_password(password, user["password_hash"]):
        return render(request, "login.html", {"user": None, "error": "login_error"}, status_code=400)

    if user["deleted_at"]:
        # Conta "excluída" (soft delete, mantida 6 meses) — não loga
        # direto, oferece reativação em vez disso.
        request.session["pending_reactivation_user_id"] = user["id"]
        return RedirectResponse(url="/reactivate-account", status_code=303)

    request.session["user_id"] = user["id"]
    return RedirectResponse(url="/", status_code=303)


@router.get("/reactivate-account", response_class=HTMLResponse)
def reactivate_account_form(request: Request):
    pending_id = request.session.get("pending_reactivation_user_id")
    if not pending_id:
        return RedirectResponse(url="/login", status_code=303)
    return render(request, "reactivate_account.html", {"user": None})


@router.post("/reactivate-account")
def reactivate_account_submit(request: Request, csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)

    pending_id = request.session.get("pending_reactivation_user_id")
    if not pending_id:
        return RedirectResponse(url="/login", status_code=303)

    execute("UPDATE users SET deleted_at = NULL WHERE id = :id", {"id": pending_id})
    del request.session["pending_reactivation_user_id"]
    request.session["user_id"] = pending_id
    return RedirectResponse(url="/", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@router.get("/verify-email", response_class=HTMLResponse)
def verify_email(request: Request, token: str = ""):
    row = fetch_one(
        "SELECT id, user_id, expires_at, used_at FROM email_verification_tokens WHERE token = :token",
        {"token": token},
    )
    now = datetime.now(timezone.utc)
    valid = row and not row["used_at"] and row["expires_at"] > now

    if valid:
        execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": row["user_id"]})
        execute("UPDATE email_verification_tokens SET used_at = now() WHERE id = :id", {"id": row["id"]})

    context = {
        "user": get_current_user(request),
        "title_key": "verify_success_title" if valid else "verify_invalid_title",
        "message_key": "verify_success_message" if valid else "verify_invalid_message",
        "link_url": "/",
        "link_label_key": "back_to_board",
    }
    return render(request, "auth_message.html", context)


@router.post("/resend-verification")
def resend_verification(request: Request, csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)

    user = get_current_user(request)
    if user and not user["email_verified"]:
        send_verification_email(request, user["id"], user["email"], user["full_name"])
    return RedirectResponse(url="/", status_code=303)


@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_form(request: Request):
    return render(request, "forgot_password.html", {"user": None})


@router.post("/forgot-password")
def forgot_password_submit(
    request: Request,
    csrf_token: str = Form(""),
    email: str = Form(...),
    website: str = Form(""),  # honeypot — ver app/captcha.py
    cf_turnstile_response: str = Form("", alias="cf-turnstile-response"),
):
    verify_csrf(request, csrf_token)

    if is_bot(website) or not verify_turnstile(cf_turnstile_response):
        # Mesma resposta de sempre (não revela que foi barrado por
        # anti-bot) — só que sem mandar nenhum e-mail de verdade.
        context = {
            "user": None,
            "title_key": "forgot_password_sent_title",
            "message_key": "forgot_password_sent_message",
            "link_url": "/login",
            "link_label_key": "back_to_login",
        }
        return render(request, "auth_message.html", context)

    user = fetch_one("SELECT id, full_name FROM users WHERE email = :email", {"email": email})
    if user:
        send_password_reset_email(request, user["id"], email, user["full_name"])

    # Mesma mensagem sempre, exista ou não a conta — evita que alguém
    # use este formulário pra descobrir quais e-mails estão cadastrados.
    context = {
        "user": None,
        "title_key": "forgot_password_sent_title",
        "message_key": "forgot_password_sent_message",
        "link_url": "/login",
        "link_label_key": "back_to_login",
    }
    return render(request, "auth_message.html", context)


@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_form(request: Request, token: str = ""):
    row = fetch_one(
        "SELECT id, expires_at, used_at FROM password_reset_tokens WHERE token = :token",
        {"token": token},
    )
    now = datetime.now(timezone.utc)
    valid = row and not row["used_at"] and row["expires_at"] > now

    if not valid:
        context = {
            "user": None,
            "title_key": "reset_password_invalid_title",
            "message_key": "reset_password_invalid_message",
            "link_url": "/forgot-password",
            "link_label_key": "forgot_password_title",
        }
        return render(request, "auth_message.html", context)

    return render(request, "reset_password.html", {"user": None, "token": token, "error": None})


@router.post("/reset-password")
def reset_password_submit(request: Request, csrf_token: str = Form(""), token: str = Form(...), password: str = Form(...)):
    verify_csrf(request, csrf_token)

    row = fetch_one(
        "SELECT id, user_id, expires_at, used_at FROM password_reset_tokens WHERE token = :token",
        {"token": token},
    )
    now = datetime.now(timezone.utc)
    valid = row and not row["used_at"] and row["expires_at"] > now

    if not valid:
        context = {
            "user": None,
            "title_key": "reset_password_invalid_title",
            "message_key": "reset_password_invalid_message",
            "link_url": "/forgot-password",
            "link_label_key": "forgot_password_title",
        }
        return render(request, "auth_message.html", context)

    execute(
        "UPDATE users SET password_hash = :password_hash WHERE id = :id",
        {"password_hash": hash_password(password), "id": row["user_id"]},
    )
    execute("UPDATE password_reset_tokens SET used_at = now() WHERE id = :id", {"id": row["id"]})

    context = {
        "user": None,
        "title_key": "reset_password_success_title",
        "message_key": "reset_password_success_message",
        "link_url": "/login",
        "link_label_key": "back_to_login",
    }
    return render(request, "auth_message.html", context)

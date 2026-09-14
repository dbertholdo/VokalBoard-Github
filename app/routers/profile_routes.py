import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Form, UploadFile, File, BackgroundTasks
from fastapi.responses import RedirectResponse, HTMLResponse, Response

from app.database import fetch_all, fetch_one, execute
from app.auth import get_current_user, hash_password, verify_password
from app.render import render
from app.csrf import verify_csrf
from app.avatars import save_avatar, remove_existing_avatar
from app.referrals import ensure_referral_code, get_referral_stats
from app.badges import get_user_badges, with_profile_complete, check_and_notify_new_badges
from app.locations import COUNTRY_OPTIONS, STATE_OPTIONS, get_city_options
from app.password_policy import password_error

router = APIRouter()

MAX_COMPOSER_TAGS = 10
MAX_BIO_LENGTH = 1000
MAX_AUDIO_LINKS = 3
MAX_RATING_COMMENT = 500

# Janela de "cooldown" pra contagem de visitas de perfil: a mesma sessão
# (mesmo navegador) só gera uma nova linha em profile_views por perfil
# a cada 12h, mesmo que a pessoa dê F5 várias vezes.
VIEW_COOLDOWN_SECONDS = 12 * 60 * 60

# Plataformas de rede social aceitas — conjunto fixo (não é um campo de
# texto livre) pra poder mostrar sempre só o nome da rede ("Instagram",
# "Facebook"...) em vez do link completo, e manter a visão do perfil
# despoluída, como pedido.
SOCIAL_PLATFORMS = ["website", "facebook", "instagram", "twitter", "whatsapp"]


def parse_hashtags(raw: str) -> list[str]:
    """
    Recebe algo como "#Mozart, Verdi #Puccini" e devolve uma lista
    limpa e sem duplicatas, com no máximo MAX_COMPOSER_TAGS itens.

    Aceita vírgula ou espaço como separador, e o "#" é opcional.
    """
    if not raw:
        return []
    parts = raw.replace(",", " ").split()
    seen: dict[str, str] = {}
    for part in parts:
        tag = part.lstrip("#").strip()
        if not tag:
            continue
        key = tag.lower()
        if key not in seen:
            seen[key] = tag[:50]
    return list(seen.values())[:MAX_COMPOSER_TAGS]


def parse_audio_links(raw: str) -> list[str]:
    """
    Recebe links de "Audiobeispiel" separados por vírgula e/ou quebra
    de linha (ex: link do YouTube, SoundCloud etc.) e devolve até
    MAX_AUDIO_LINKS URLs válidas (começando com http:// ou https://).
    Links inválidos são simplesmente ignorados, sem travar o cadastro.
    """
    if not raw:
        return []
    parts = raw.replace(",", "\n").splitlines()
    links: list[str] = []
    for part in parts:
        url = part.strip()
        if url.startswith("http://") or url.startswith("https://"):
            links.append(url[:500])
        if len(links) >= MAX_AUDIO_LINKS:
            break
    return links


def get_singer_profile(user_id: int) -> dict | None:
    return fetch_one(
        """
        SELECT sp.voice_type_id, sp.fach, sp.bio, vt.name AS voice_type_name
        FROM singer_profiles sp
        LEFT JOIN voice_types vt ON vt.id = sp.voice_type_id
        WHERE sp.user_id = :user_id
        """,
        {"user_id": user_id},
    )


def get_conductor_profile(user_id: int) -> dict | None:
    return fetch_one(
        "SELECT ensemble_name, bio FROM conductor_profiles WHERE user_id = :user_id",
        {"user_id": user_id},
    )


def get_composer_tags(user_id: int) -> list[str]:
    rows = fetch_all(
        "SELECT tag FROM singer_composer_tags WHERE user_id = :user_id ORDER BY tag",
        {"user_id": user_id},
    )
    return [r["tag"] for r in rows]


def get_audio_links(user_id: int) -> list[str]:
    rows = fetch_all(
        "SELECT url FROM singer_audio_links WHERE user_id = :user_id ORDER BY id",
        {"user_id": user_id},
    )
    return [r["url"] for r in rows]


def set_audio_links(user_id: int, links: list[str]) -> None:
    execute("DELETE FROM singer_audio_links WHERE user_id = :user_id", {"user_id": user_id})
    for url in links:
        execute(
            "INSERT INTO singer_audio_links (user_id, url) VALUES (:user_id, :url)",
            {"user_id": user_id, "url": url},
        )


def get_social_links(user_id: int) -> dict[str, str]:
    rows = fetch_all(
        "SELECT platform, url FROM user_social_links WHERE user_id = :user_id",
        {"user_id": user_id},
    )
    return {r["platform"]: r["url"] for r in rows}


def set_social_links(user_id: int, links: dict[str, str]) -> None:
    """
    `links` é {plataforma: url}; plataformas ausentes ou com URL vazia
    são removidas. Só aceita http(s) — evita gente colando "@usuario"
    sem link de verdade, que quebraria o botão na hora de exibir.
    """
    execute("DELETE FROM user_social_links WHERE user_id = :user_id", {"user_id": user_id})
    for platform, url in links.items():
        url = (url or "").strip()
        if platform not in SOCIAL_PLATFORMS or not url:
            continue
        if not (url.startswith("http://") or url.startswith("https://")):
            continue
        execute(
            "INSERT INTO user_social_links (user_id, platform, url) VALUES (:user_id, :platform, :url)",
            {"user_id": user_id, "platform": platform, "url": url[:500]},
        )


def get_my_ratings(user_id: int) -> list[dict]:
    """
    Avaliações RECEBIDAS por essa pessoa — só chamado a partir de
    /profile (a própria pessoa vendo o que ela mesma recebeu). Nunca
    chamado a partir de /users/{id} (perfil público) nem de nenhum
    outro lugar visível a terceiros.
    """
    return fetch_all(
        """
        SELECT r.stars, r.comment, r.created_at, u.full_name AS rater_name, r.rater_id
        FROM ratings r
        JOIN users u ON u.id = r.rater_id
        WHERE r.rated_id = :user_id
        ORDER BY r.created_at DESC
        """,
        {"user_id": user_id},
    )


def get_rating_summary(user_id: int) -> dict:
    row = fetch_one(
        "SELECT COUNT(*) AS n, AVG(stars)::numeric(3,1) AS avg_stars FROM ratings WHERE rated_id = :user_id",
        {"user_id": user_id},
    )
    return {"count": row["n"] if row else 0, "avg_stars": row["avg_stars"] if row else None}


def get_rating_given(rater_id: int, rated_id: int) -> dict | None:
    return fetch_one(
        "SELECT stars, comment FROM ratings WHERE rater_id = :rater_id AND rated_id = :rated_id",
        {"rater_id": rater_id, "rated_id": rated_id},
    )


# Itens que contam pro indicador de "perfil completo" em /profile — cada
# um vale o mesmo peso (simples de explicar: "8 de 10 itens = 80%").
# A ideia (pedida) é reforçar que um perfil mais completo passa mais
# confiança pra quem visita e melhora o que a Home consegue "casar"
# automaticamente (voz, cidade, composer tags entram no matching).
def compute_profile_completeness(user: dict, role_profile: dict | None, composer_tags: list,
                                  audio_links: list, social_links: dict) -> dict:
    items = [
        ("avatar", bool(user.get("avatar_url"))),
        ("city", bool(user.get("city"))),
        ("phone", bool(user.get("phone"))),
        ("bio", bool(role_profile and role_profile.get("bio"))),
        ("social_link", bool(social_links)),
    ]
    if user["role"] == "singer":
        items.append(("voice_type", bool(role_profile and role_profile.get("voice_type_id"))))
        items.append(("composer_tags", bool(composer_tags)))
        items.append(("audio_links", bool(audio_links)))
    else:
        items.append(("ensemble_name", bool(role_profile and role_profile.get("ensemble_name"))))

    done = sum(1 for _, ok in items if ok)
    total = len(items)
    missing = [key for key, ok in items if not ok]
    percent = round((done / total) * 100) if total else 0
    return {"percent": percent, "done": done, "total": total, "missing": missing}


def get_blocked_users(user_id: int) -> list[dict]:
    return fetch_all(
        """
        SELECT u.id, u.full_name, bu.reason, bu.created_at
        FROM blocked_users bu
        JOIN users u ON u.id = bu.blocked_id
        WHERE bu.blocker_id = :user_id
        ORDER BY bu.created_at DESC
        """,
        {"user_id": user_id},
    )


def _my_profile_context(request: Request, user: dict, error: str | None = None, saved: bool = False) -> dict:
    singer_profile = get_singer_profile(user["id"]) if user["role"] == "singer" else None
    conductor_profile = get_conductor_profile(user["id"]) if user["role"] == "conductor" else None
    composer_tags = get_composer_tags(user["id"]) if user["role"] == "singer" else []
    audio_links = get_audio_links(user["id"]) if user["role"] == "singer" else []
    social_links = get_social_links(user["id"])
    role_profile = singer_profile if user["role"] == "singer" else conductor_profile

    referral_code = ensure_referral_code(user["id"], user.get("referral_code"))
    user["referral_code"] = referral_code
    referral_url = f"{str(request.base_url).rstrip('/')}/register?ref={referral_code}"

    completeness = compute_profile_completeness(user, role_profile, composer_tags, audio_links, social_links)
    badges = with_profile_complete(get_user_badges(user["id"]), completeness["percent"])

    return {
        "user": user,
        "referral_url": referral_url,
        "referral_count": get_referral_stats(user["id"])["count"],
        "blocked_users": get_blocked_users(user["id"]),
        "badges": badges,
        "voice_types": fetch_all("SELECT id, name FROM voice_types ORDER BY sort_order"),
        "singer_profile": singer_profile,
        "conductor_profile": conductor_profile,
        "composer_tags": composer_tags,
        "audio_links": audio_links,
        "social_links": social_links,
        "social_platforms": SOCIAL_PLATFORMS,
        # Avaliações recebidas — SÓ aparecem aqui, na própria página
        # de perfil da pessoa (privado, nunca em /users/{id}).
        "my_ratings": get_my_ratings(user["id"]),
        "rating_summary": get_rating_summary(user["id"]),
        "completeness": completeness,
        "max_bio_length": MAX_BIO_LENGTH,
        "max_composer_tags": MAX_COMPOSER_TAGS,
        "max_audio_links": MAX_AUDIO_LINKS,
        "country_options": COUNTRY_OPTIONS,
        "state_options": STATE_OPTIONS,
        "city_options": get_city_options(),
        "error": error,
        "saved": saved,
    }


@router.get("/profile", response_class=HTMLResponse)
def my_profile(request: Request, background_tasks: BackgroundTasks):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    # Checagem "preguiçosa" de badges com nível que dependem só do
    # tempo passando (aniversário) ou de dados que mudam fora de uma
    # ação direta (visitas) — como o projeto não usa nenhum cron
    # interno, a gente aproveita a visita mais natural e frequente
    # (a própria pessoa abrindo o perfil) pra recalcular e, se for o
    # caso, mandar o e-mail de "novo badge".
    background_tasks.add_task(check_and_notify_new_badges, user["id"], str(request.base_url))

    context = _my_profile_context(request, user, saved=request.query_params.get("saved") == "1")
    return render(request, "profile.html", context)


@router.post("/profile")
async def update_profile(
    request: Request,
    background_tasks: BackgroundTasks,
    csrf_token: str = Form(""),
    bio: str = Form(""),
    city: str = Form(""),
    state: str = Form(""),
    country: str = Form("DE"),
    voice_type_id: str = Form(""),
    fach: str = Form(""),
    ensemble_name: str = Form(""),
    composer_hashtags: str = Form(""),
    audio_links: str = Form(""),
    social_website: str = Form(""),
    social_facebook: str = Form(""),
    social_instagram: str = Form(""),
    social_twitter: str = Form(""),
    social_whatsapp: str = Form(""),
    notify_matches: str = Form(""),
    notify_messages: str = Form(""),
    remove_avatar: str = Form(""),
    avatar: UploadFile | None = File(None),
):
    verify_csrf(request, csrf_token)

    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    bio = bio.strip()[:MAX_BIO_LENGTH]

    if country not in COUNTRY_OPTIONS:
        context = _my_profile_context(request, user, error="register_error_invalid_country")
        return render(request, "profile.html", context, status_code=400)

    execute(
        """
        UPDATE users
        SET notify_matches = :notify_matches, notify_messages = :notify_messages,
            city = :city, state = :state, country = :country
        WHERE id = :id
        """,
        {
            "notify_matches": bool(notify_matches),
            "notify_messages": bool(notify_messages),
            "city": city or None,
            "state": state or None,
            "country": country,
            "id": user["id"],
        },
    )

    if remove_avatar:
        remove_existing_avatar(user["id"])
        execute("UPDATE users SET avatar_url = NULL WHERE id = :id", {"id": user["id"]})
    elif avatar is not None and avatar.filename:
        new_avatar_url = await save_avatar(user["id"], avatar)
        if new_avatar_url:
            execute("UPDATE users SET avatar_url = :avatar_url WHERE id = :id", {"avatar_url": new_avatar_url, "id": user["id"]})
        else:
            # Arquivo inválido (tipo não suportado ou grande demais) —
            # não trava o resto do salvamento, só ignora a foto e avisa.
            context = _my_profile_context(request, get_current_user(request), error="profile_avatar_invalid")
            return render(request, "profile.html", context, status_code=400)

    set_social_links(user["id"], {
        "website": social_website,
        "facebook": social_facebook,
        "instagram": social_instagram,
        "twitter": social_twitter,
        "whatsapp": social_whatsapp,
    })

    if user["role"] == "singer":
        execute(
            """
            UPDATE singer_profiles
            SET voice_type_id = :voice_type_id, fach = :fach, bio = :bio
            WHERE user_id = :user_id
            """,
            {
                "voice_type_id": int(voice_type_id) if voice_type_id else None,
                "fach": fach or None,
                "bio": bio or None,
                "user_id": user["id"],
            },
        )

        tags = parse_hashtags(composer_hashtags)
        execute("DELETE FROM singer_composer_tags WHERE user_id = :user_id", {"user_id": user["id"]})
        for tag in tags:
            execute(
                "INSERT INTO singer_composer_tags (user_id, tag) VALUES (:user_id, :tag)",
                {"user_id": user["id"], "tag": tag},
            )

        set_audio_links(user["id"], parse_audio_links(audio_links))
    else:
        execute(
            """
            UPDATE conductor_profiles
            SET ensemble_name = :ensemble_name, bio = :bio
            WHERE user_id = :user_id
            """,
            {"ensemble_name": ensemble_name or None, "bio": bio or None, "user_id": user["id"]},
        )

    background_tasks.add_task(check_and_notify_new_badges, user["id"], str(request.base_url))
    return RedirectResponse(url="/profile?saved=1", status_code=303)


@router.get("/profile/change-password", response_class=HTMLResponse)
def change_password_form(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return render(request, "change_password.html", {"user": user, "error": None})


@router.post("/profile/change-password")
def change_password_submit(
    request: Request,
    csrf_token: str = Form(""),
    current_password: str = Form(...),
    new_password: str = Form(...),
):
    verify_csrf(request, csrf_token)
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    row = fetch_one("SELECT password_hash FROM users WHERE id = :id", {"id": user["id"]})
    if not row or not verify_password(current_password, row["password_hash"]):
        return render(
            request, "change_password.html",
            {"user": user, "error": "change_password_wrong_current"},
            status_code=400,
        )

    pw_error = password_error(new_password)
    if pw_error:
        return render(
            request, "change_password.html",
            {"user": user, "error": pw_error},
            status_code=400,
        )

    execute(
        "UPDATE users SET password_hash = :hash WHERE id = :id",
        {"hash": hash_password(new_password), "id": user["id"]},
    )
    return RedirectResponse(url="/profile?saved=1", status_code=303)


@router.post("/profile/delete-account")
def delete_account_submit(request: Request, csrf_token: str = Form(""), current_password: str = Form(...)):
    """
    Soft delete: marca deleted_at = now() e derruba a sessão. A conta
    fica "invisível" (get_current_user, joins de autor etc. filtram
    deleted_at IS NULL) mas os dados continuam no banco por 6 meses —
    se a pessoa tentar logar de novo nesse período, cai no fluxo de
    reativação (ver /reactivate-account em auth_routes.py). Depois de
    6 meses, um script externo (scripts/purge_deleted_accounts.py)
    apaga definitivamente — sem cron dentro do app, como o resto do
    projeto.
    """
    verify_csrf(request, csrf_token)
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    row = fetch_one("SELECT password_hash FROM users WHERE id = :id", {"id": user["id"]})
    if not row or not verify_password(current_password, row["password_hash"]):
        context = _my_profile_context(request, user, error="delete_account_wrong_password")
        return render(request, "profile.html", context, status_code=400)

    execute("UPDATE users SET deleted_at = now() WHERE id = :id", {"id": user["id"]})
    request.session.clear()
    return RedirectResponse(url="/?account_deleted=1", status_code=303)


@router.get("/profile/export")
def export_my_data(request: Request):
    """
    Exportação de dados (GDPR Art. 20 — direito à portabilidade): um
    JSON com tudo que a pessoa tem cadastrado no sistema, pra baixar.
    Deliberadamente NÃO inclui password_hash (não é "seu dado" no
    sentido de portabilidade, é um segredo de autenticação) nem dados
    de outras pessoas além do que já é necessário pra dar contexto às
    próprias mensagens/avaliações dela.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    user_id = user["id"]

    account = fetch_one(
        "SELECT id, email, full_name, role, city, phone, email_verified, avatar_url, notify_matches, notify_messages, created_at FROM users WHERE id = :id",
        {"id": user_id},
    )
    listings = fetch_all(
        "SELECT id, listing_type, title, description, city, state, country, repertoire, venue, fee, ensemble_type, event_date, is_active, created_at FROM listings WHERE author_id = :id ORDER BY created_at",
        {"id": user_id},
    )
    messages_sent = fetch_all(
        "SELECT id, recipient_id, listing_id, body, created_at FROM messages WHERE sender_id = :id ORDER BY created_at",
        {"id": user_id},
    )
    messages_received = fetch_all(
        "SELECT id, sender_id, listing_id, body, created_at, read_at FROM messages WHERE recipient_id = :id ORDER BY created_at",
        {"id": user_id},
    )
    ratings_received = get_my_ratings(user_id)
    ratings_given = fetch_all(
        "SELECT rated_id, stars, comment, created_at FROM ratings WHERE rater_id = :id ORDER BY created_at",
        {"id": user_id},
    )
    saved_listings = fetch_all(
        "SELECT listing_id, created_at FROM saved_listings WHERE user_id = :id ORDER BY created_at",
        {"id": user_id},
    )

    export = {
        "account": account,
        "singer_profile": get_singer_profile(user_id) if user["role"] == "singer" else None,
        "conductor_profile": get_conductor_profile(user_id) if user["role"] == "conductor" else None,
        "composer_tags": get_composer_tags(user_id) if user["role"] == "singer" else [],
        "audio_links": get_audio_links(user_id) if user["role"] == "singer" else [],
        "social_links": get_social_links(user_id),
        "listings_posted": listings,
        "messages_sent": messages_sent,
        "messages_received": messages_received,
        "ratings_received": ratings_received,
        "ratings_given": ratings_given,
        "saved_listings": saved_listings,
    }

    body = json.dumps(export, indent=2, ensure_ascii=False, default=str)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="vokalboard-dados-{user_id}.json"'},
    )


@router.post("/users/{user_id}/block")
def block_user(request: Request, user_id: int, csrf_token: str = Form(""), reason: str = Form("")):
    """
    Bloquear alguém: a partir de agora nenhum dos dois lados consegue
    mandar mensagem pro outro (checado em messages_routes.py), e os
    anúncios da pessoa bloqueada somem do /board e dos matches da Home
    pra quem bloqueou (ver os filtros NOT EXISTS em listings_routes.py).
    Motivo é opcional aqui (diferente da denúncia de anúncio, que exige
    motivo) — bloquear é uma decisão pessoal, não precisa justificar.
    """
    verify_csrf(request, csrf_token)
    viewer = get_current_user(request)
    if not viewer:
        return RedirectResponse(url="/login", status_code=303)
    if viewer["id"] == user_id:
        return RedirectResponse(url=f"/users/{user_id}", status_code=303)

    target = fetch_one("SELECT id FROM users WHERE id = :id", {"id": user_id})
    if target:
        execute(
            """
            INSERT INTO blocked_users (blocker_id, blocked_id, reason) VALUES (:blocker_id, :blocked_id, :reason)
            ON CONFLICT (blocker_id, blocked_id) DO NOTHING
            """,
            {"blocker_id": viewer["id"], "blocked_id": user_id, "reason": reason.strip()[:500] or None},
        )
    return RedirectResponse(url=f"/users/{user_id}?blocked=1", status_code=303)


@router.post("/users/{user_id}/unblock")
def unblock_user(request: Request, user_id: int, csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)
    viewer = get_current_user(request)
    if not viewer:
        return RedirectResponse(url="/login", status_code=303)

    execute(
        "DELETE FROM blocked_users WHERE blocker_id = :blocker_id AND blocked_id = :blocked_id",
        {"blocker_id": viewer["id"], "blocked_id": user_id},
    )
    referer = request.headers.get("referer", "")
    if "/profile" in referer:
        return RedirectResponse(url="/profile", status_code=303)
    return RedirectResponse(url=f"/users/{user_id}", status_code=303)


@router.post("/users/{user_id}/rate")
def rate_user(
    request: Request,
    user_id: int,
    csrf_token: str = Form(""),
    stars: int = Form(...),
    comment: str = Form(""),
    listing_id: str = Form(""),
):
    verify_csrf(request, csrf_token)
    viewer = get_current_user(request)
    if not viewer:
        return RedirectResponse(url="/login", status_code=303)
    if viewer["id"] == user_id:
        return RedirectResponse(url=f"/users/{user_id}", status_code=303)
    if stars < 0 or stars > 5:
        return RedirectResponse(url=f"/users/{user_id}", status_code=303)

    rated_exists = fetch_one("SELECT id FROM users WHERE id = :id AND deleted_at IS NULL", {"id": user_id})
    if not rated_exists:
        return RedirectResponse(url="/board", status_code=303)

    listing_id_val = int(listing_id) if listing_id.strip().isdigit() else None
    comment_val = comment.strip()[:MAX_RATING_COMMENT] or None

    execute(
        """
        INSERT INTO ratings (rater_id, rated_id, listing_id, stars, comment)
        VALUES (:rater_id, :rated_id, :listing_id, :stars, :comment)
        ON CONFLICT (rater_id, rated_id)
        DO UPDATE SET stars = :stars, comment = :comment, listing_id = :listing_id, updated_at = now()
        """,
        {
            "rater_id": viewer["id"],
            "rated_id": user_id,
            "listing_id": listing_id_val,
            "stars": stars,
            "comment": comment_val,
        },
    )
    return RedirectResponse(url=f"/users/{user_id}?rated=1", status_code=303)


@router.get("/users/{user_id}", response_class=HTMLResponse)
def public_profile(request: Request, user_id: int, background_tasks: BackgroundTasks):
    profile_user = fetch_one(
        "SELECT id, full_name, role, city, phone, avatar_url FROM users WHERE id = :id", {"id": user_id}
    )

    singer_profile = None
    conductor_profile = None
    composer_tags = []
    audio_links = []
    if profile_user:
        if profile_user["role"] == "singer":
            singer_profile = get_singer_profile(user_id)
            composer_tags = get_composer_tags(user_id)
            audio_links = get_audio_links(user_id)
        else:
            conductor_profile = get_conductor_profile(user_id)

        # Log de visita — não aparece em nenhuma tela, é só pra você
        # (admin) consultar direto no banco. Não conta a própria pessoa
        # visitando o próprio perfil.
        #
        # Pra evitar que dar F5 na página infle a contagem, cada sessão
        # (cookie de navegador, já usado pra login/CSRF) só conta como
        # uma nova visita a este perfil uma vez a cada VIEW_COOLDOWN.
        # Não é à prova de tudo (limpar cookies ou usar aba anônima
        # contorna), mas isso é aceitável pra uma métrica leve — não
        # vale a pena rastrear IP pra fechar essa brecha por completo,
        # o que iria contra a linha "profile_views é privado e mínimo"
        # do projeto.
        viewer = get_current_user(request)
        if not viewer or viewer["id"] != user_id:
            session_key = f"viewed_profile_{user_id}"
            last_viewed = request.session.get(session_key)
            now_ts = datetime.now(timezone.utc).timestamp()
            if not last_viewed or (now_ts - last_viewed) > VIEW_COOLDOWN_SECONDS:
                request.session[session_key] = now_ts
                execute(
                    "INSERT INTO profile_views (profile_user_id, viewer_user_id) VALUES (:profile_id, :viewer_id)",
                    {"profile_id": user_id, "viewer_id": viewer["id"] if viewer else None},
                )
                # A visita pode ter feito o DONO do perfil cruzar um
                # patamar de "views" (100/500/1000) — checa e avisa ELE,
                # não quem está visitando.
                background_tasks.add_task(check_and_notify_new_badges, user_id, str(request.base_url))

    listings = fetch_all(
        """
        SELECT id, title, listing_type, city, created_at,
            CASE
                WHEN event_date IS NULL THEN NULL
                WHEN event_date < CURRENT_DATE THEN 'past'
                WHEN event_date <= CURRENT_DATE + INTERVAL '7 days' THEN 'soon'
                ELSE 'upcoming'
            END AS event_status
        FROM listings
        WHERE author_id = :author_id AND is_active = TRUE
        ORDER BY created_at DESC
        """,
        {"author_id": user_id},
    )

    viewer = get_current_user(request)

    # Redes sociais: só fazem sentido mostrar quando o perfil não está
    # "locked" (visitante logado), senão ficaria mais um dado exposto
    # de graça pra quem não se cadastrou.
    social_links = get_social_links(user_id) if profile_user and viewer is not None else {}

    # Avaliação que EU (viewer) já dei pra essa pessoa, pra pré-preencher
    # o formulário de avaliação. Isso é diferente de "avaliações que essa
    # pessoa recebeu" (my_ratings/rating_summary) — aquilo é privado e
    # NUNCA aparece aqui, só em /profile (a própria pessoa vendo o que
    # recebeu). Aqui só existe o widget pra dar/atualizar uma nota.
    rating_given = None
    can_rate = False
    is_blocked = False
    # Bloqueio precisa ser invisível dos DOIS lados, senão não adianta
    # muito — se eu bloqueei alguém (ou fui bloqueado por ela), nenhum
    # dos dois deveria conseguir ver o perfil do outro, não só trocar
    # mensagem. "blocked_either_way" cobre os dois sentidos.
    blocked_either_way = False
    if profile_user and viewer is not None and viewer["id"] != user_id:
        can_rate = True
        rating_given = get_rating_given(viewer["id"], user_id)
        blocked_row = fetch_one(
            "SELECT 1 FROM blocked_users WHERE blocker_id = :blocker_id AND blocked_id = :blocked_id",
            {"blocker_id": viewer["id"], "blocked_id": user_id},
        )
        is_blocked = blocked_row is not None

        blocked_other_way = fetch_one(
            "SELECT 1 FROM blocked_users WHERE blocker_id = :blocker_id AND blocked_id = :blocked_id",
            {"blocker_id": user_id, "blocked_id": viewer["id"]},
        )
        blocked_either_way = is_blocked or (blocked_other_way is not None)

    # Badges: só os desbloqueados aparecem no perfil público (o perfil
    # não fica cheio de "conquistas travadas" pra quem visita) — a
    # própria pessoa vê todos, travados e não, em /profile.
    badges = []
    if profile_user and not blocked_either_way:
        role_profile_for_badges = singer_profile if profile_user["role"] == "singer" else conductor_profile
        completeness_pct = compute_profile_completeness(
            profile_user, role_profile_for_badges, composer_tags, audio_links, social_links
        )["percent"]
        all_badges = with_profile_complete(get_user_badges(user_id), completeness_pct)
        badges = [b for b in all_badges if b["unlocked"]]

    context = {
        "user": viewer,
        "profile_user": profile_user,
        "singer_profile": singer_profile,
        "conductor_profile": conductor_profile,
        "composer_tags": composer_tags,
        "audio_links": audio_links,
        "social_links": social_links,
        "social_platforms": SOCIAL_PLATFORMS,
        "can_rate": can_rate,
        "rating_given": rating_given,
        "is_blocked": is_blocked,
        "blocked_either_way": blocked_either_way,
        "badges": badges,
        "listings": listings,
        # Freemium: sem login só dá pra ver nome/papel/cidade — bio,
        # hashtags, links de áudio e anúncios ficam atrás do cadastro.
        "locked": viewer is None,
    }
    return render(request, "public_profile.html", context)

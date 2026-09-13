"""
Badges: "conquistas" simples.

Os badges em si são CALCULADOS na hora a partir do que já existe
(indicações, anúncios, mensagens, perfil completo, visitas, tempo de
conta) — nenhuma regra fica guardada em tabela. A tabela user_badges
só registra QUANDO cada badge/nível foi desbloqueado pela primeira
vez, pra (1) poder mandar o e-mail de "novo badge" uma única vez por
degrau, e (2) badges com nível (visitas, aniversário) guardarem cada
degrau já alcançado.

Gamificação LEVE, sem ranking nem comparação entre pessoas — nada de
"fulano tem mais badges que ciclano" em lugar nenhum, é só
reconhecimento individual. O badge de visitas mostra só "passou de X",
nunca o número exato — de propósito, pra manter profile_views privado.
"""
import html as html_module

from app.database import fetch_one, fetch_all, execute
from app.email import send_email

# Ordem do maior pro menor: pegamos só o degrau mais alto já alcançado
# (em vez de mostrar 3 badges de visita ao mesmo tempo).
VIEW_MILESTONES = [
    (1000, "gold"),
    (500, "silver"),
    (100, "bronze"),
]


def _referral_count(user_id: int) -> int:
    return fetch_one(
        "SELECT COUNT(*) AS n FROM users WHERE referred_by_user_id = :id AND email_verified = TRUE",
        {"id": user_id},
    )["n"]


def _listing_count(user_id: int) -> int:
    return fetch_one("SELECT COUNT(*) AS n FROM listings WHERE author_id = :id", {"id": user_id})["n"]


def _message_sent_count(user_id: int) -> int:
    return fetch_one("SELECT COUNT(*) AS n FROM messages WHERE sender_id = :id", {"id": user_id})["n"]


def _view_count(user_id: int) -> int:
    return fetch_one("SELECT COUNT(*) AS n FROM profile_views WHERE profile_user_id = :id", {"id": user_id})["n"]


def _has_fast_response(user_id: int) -> bool:
    """
    Já respondeu alguma mensagem em até 24h pelo menos uma vez: existe
    uma mensagem M1 recebida por essa pessoa e uma mensagem M2, dela
    para quem mandou M1, criada depois de M1 e dentro de 24h.
    """
    row = fetch_one(
        """
        SELECT 1
        FROM messages m1
        JOIN messages m2
            ON m2.sender_id = m1.recipient_id
           AND m2.recipient_id = m1.sender_id
           AND m2.created_at > m1.created_at
           AND m2.created_at <= m1.created_at + INTERVAL '24 hours'
        WHERE m1.recipient_id = :user_id
        LIMIT 1
        """,
        {"user_id": user_id},
    )
    return row is not None


def _years_on_site(user_id: int) -> int:
    row = fetch_one(
        "SELECT EXTRACT(YEAR FROM age(now(), created_at))::int AS years FROM users WHERE id = :id",
        {"id": user_id},
    )
    return row["years"] if row and row["years"] else 0


def get_user_badges(user_id: int) -> list[dict]:
    badges = [
        {"key": "referral", "icon": "🎁", "unlocked": _referral_count(user_id) > 0, "tier": ""},
        {"key": "listing", "icon": "📋", "unlocked": _listing_count(user_id) > 0, "tier": ""},
        {"key": "contact", "icon": "✉️", "unlocked": _message_sent_count(user_id) > 0, "tier": ""},
        {"key": "fast_response", "icon": "⚡", "unlocked": _has_fast_response(user_id), "tier": ""},
        # "profile_complete" é preenchido por with_profile_complete() —
        # quem chama já calcula completeness pra outros fins (a barra
        # de progresso em /profile), não faz sentido calcular de novo.
        {"key": "profile_complete", "icon": "✨", "unlocked": False, "tier": ""},
    ]

    views_badge = {"key": "views", "icon": "👀", "unlocked": False, "tier": None}
    view_count = _view_count(user_id)
    for threshold, tier in VIEW_MILESTONES:
        if view_count >= threshold:
            views_badge = {"key": "views", "icon": "👀", "unlocked": True, "tier": tier, "threshold": threshold}
            break
    badges.append(views_badge)

    years = _years_on_site(user_id)
    anniversary_badge = {"key": "anniversary", "icon": "🎂", "unlocked": years >= 1, "tier": str(years) if years >= 1 else "", "years": years}
    badges.append(anniversary_badge)

    return badges


def with_profile_complete(badges: list[dict], completeness_percent: int) -> list[dict]:
    """Preenche o badge de 'perfil 100%' — completeness já é calculada em profile_routes.py."""
    for b in badges:
        if b["key"] == "profile_complete":
            b["unlocked"] = completeness_percent >= 100
    return badges


def check_and_notify_new_badges(user_id: int, base_url: str) -> None:
    """
    Compara os badges atuais com o que já está registrado em
    user_badges e, para cada um novo, grava a linha e manda um e-mail
    avisando. Chamado (via BackgroundTask, pra não atrasar a resposta)
    depois de ações que podem desbloquear um badge — ver os pontos de
    chamada em profile_routes.py, listings_routes.py e
    messages_routes.py.

    De propósito, não recebe completeness pronto (chama de novo aqui
    dentro) — assim essa função pode ser chamada de qualquer lugar sem
    precisar recalcular tudo manualmente antes.
    """
    from app.routers.profile_routes import (
        get_singer_profile, get_conductor_profile, get_composer_tags,
        get_audio_links, get_social_links, compute_profile_completeness,
    )

    user = fetch_one("SELECT * FROM users WHERE id = :id", {"id": user_id})
    if not user:
        return

    singer_profile = get_singer_profile(user_id) if user["role"] == "singer" else None
    conductor_profile = get_conductor_profile(user_id) if user["role"] == "conductor" else None
    composer_tags = get_composer_tags(user_id) if user["role"] == "singer" else []
    audio_links = get_audio_links(user_id) if user["role"] == "singer" else []
    social_links = get_social_links(user_id)
    role_profile = singer_profile if user["role"] == "singer" else conductor_profile
    completeness = compute_profile_completeness(user, role_profile, composer_tags, audio_links, social_links)

    badges = with_profile_complete(get_user_badges(user_id), completeness["percent"])

    already = fetch_all(
        "SELECT badge_key, tier FROM user_badges WHERE user_id = :id", {"id": user_id}
    )
    already_set = {(r["badge_key"], r["tier"]) for r in already}

    for b in badges:
        if not b["unlocked"]:
            continue
        tier = b.get("tier") or ""
        if (b["key"], tier) in already_set:
            continue

        execute(
            """
            INSERT INTO user_badges (user_id, badge_key, tier, notified_at)
            VALUES (:user_id, :badge_key, :tier, now())
            ON CONFLICT (user_id, badge_key, tier) DO NOTHING
            """,
            {"user_id": user_id, "badge_key": b["key"], "tier": tier},
        )

        profile_url = f"{base_url.rstrip('/')}/profile"
        badge_name_de, badge_name_en = _badge_names(b)
        safe_name = html_module.escape(user["full_name"])
        html = f"""
            <p>Hallo {safe_name},</p>
            <p>Du hast eine neue Auszeichnung freigeschaltet: <strong>{badge_name_de}</strong> 🎉</p>
            <p><a href="{profile_url}">{profile_url}</a></p>
            <hr>
            <p>(EN) You've unlocked a new badge: <strong>{badge_name_en}</strong> 🎉<br>
            <a href="{profile_url}">{profile_url}</a></p>
        """
        send_email(user["email"], "Neue Auszeichnung freigeschaltet — VokalBoard", html)


def _badge_names(b: dict) -> tuple[str, str]:
    names = {
        "referral": ("Botschafter(in)", "Ambassador"),
        "listing": ("Erste Anzeige", "First listing"),
        "contact": ("Kontaktfreudig", "Reached out"),
        "fast_response": ("Schnelle Antwort", "Fast response"),
        "profile_complete": ("Profil komplett", "Complete profile"),
        "views": ("Gefragt", "In demand"),
        "anniversary": ("Jahrestag", "Anniversary"),
    }
    de, en = names.get(b["key"], (b["key"], b["key"]))
    if b["key"] == "views" and b.get("threshold"):
        de += f" ({b['threshold']}+)"
        en += f" ({b['threshold']}+)"
    if b["key"] == "anniversary" and b.get("years"):
        de += f" ({b['years']} {'Jahr' if b['years'] == 1 else 'Jahre'})"
        en += f" ({b['years']} {'year' if b['years'] == 1 else 'years'})"
    return de, en

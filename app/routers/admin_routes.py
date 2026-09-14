"""
Painel de administração — visão geral (denúncias/bloqueios/números,
só leitura) + gestão de usuários (/admin/users), que já permite agir
de verdade: confirmar e-mail manualmente, mandar link de redefinição
de senha, promover/remover admin, desativar/reativar ou apagar uma
conta pra sempre. Não substitui o Adminer (ver docker-compose.yml,
serviço "adminer") pra edições mais profundas/pontuais no banco, mas
cobre as ações do dia a dia sem precisar abrir SQL.

Proteção: users.is_admin (ver db/schema.sql). Não existe cadastro de
admin pela interface — o PRIMEIRO admin vira admin só via UPDATE
direto no banco:

    UPDATE users SET is_admin = TRUE WHERE email = 'seu-email@exemplo.com';

(ver README, seção "Nível de admin"). Depois disso, promover outras
pessoas já pode ser feito por aqui (/admin/users/{id}).
"""
from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse

from app.database import fetch_all, fetch_one, execute, execute_returning
from app.auth import get_current_user
from app.render import render
from app.csrf import verify_csrf
from app.routers.auth_routes import send_password_reset_email
from app.permissions import require_level, sync_is_admin_flag, LEVEL_COMUM, LEVEL_MODERADOR, LEVEL_ADMIN, LEVEL_GOD
from app.richtext import sanitize_post_body
from app.post_images import save_post_image

router = APIRouter()

POST_TITLE_MAX_LENGTH = 150
# Bem maior que antes (era 4000): o corpo agora guarda HTML do editor
# (tags de formatação + <img src="/post-images/..."> contam caracteres
# também), não só texto puro — ver app/richtext.py.
POST_BODY_MAX_LENGTH = 20000

ADMIN_USERS_PAGE_SIZE = 30

# Coluna/expressão usada em ORDER BY para cada opção de ordenação —
# uma allowlist fixa, nunca o valor cru da query string, pra não abrir
# brecha de SQL injection via parâmetro de URL.
ADMIN_USER_SORT_OPTIONS = {
    "newest": "u.created_at DESC",
    "rating": "avg_rating DESC NULLS LAST, rating_count DESC",
    "views": "profile_views DESC",
    "engagement": "messages_received DESC",
    "name": "u.full_name ASC",
}


def require_admin(request: Request) -> dict | None:
    """Devolve o usuário logado se ele tiver nível >= 2 (admin), senão None.

    Continua se chamando require_admin (em vez de renomear pra
    require_level_2 em todo lugar) pra não precisar tocar nas 15
    chamadas já espalhadas por este arquivo — mas por baixo já usa a
    escala de níveis (ver app/permissions.py). Nível 3 (god mode)
    também passa aqui, já que 3 >= 2.
    """
    return require_level(request, LEVEL_ADMIN)


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    # Nível 1 (moderador) já entra aqui — o painel /admin em si é só
    # leitura (números + fila de denúncias/bloqueios), sem nenhuma ação
    # sobre usuário/post/financeiro. As telas que fazem algo de fato
    # (/admin/users, /admin/posts) continuam exigindo require_admin
    # (nível 2+) em cada uma delas.
    admin = require_level(request, LEVEL_MODERADOR)
    if not admin:
        # De propósito NÃO diferencia "não é admin" de "página não
        # existe" pra quem está tentando adivinhar a URL — só manda
        # pra home, sem nenhuma mensagem de erro específica.
        return RedirectResponse(url="/", status_code=303)

    stats = {
        "users": fetch_one("SELECT COUNT(*) AS n FROM users WHERE deleted_at IS NULL")["n"],
        "listings": fetch_one("SELECT COUNT(*) AS n FROM listings WHERE is_active = TRUE")["n"],
        "messages": fetch_one("SELECT COUNT(*) AS n FROM messages")["n"],
        "blocked_pairs": fetch_one("SELECT COUNT(*) AS n FROM blocked_users")["n"],
        "open_reports": fetch_one("SELECT COUNT(*) AS n FROM listing_reports")["n"],
    }

    reports = fetch_all(
        """
        SELECT lr.id, lr.reason, lr.created_at,
               l.id AS listing_id, l.title AS listing_title,
               ru.full_name AS reporter_name,
               au.full_name AS author_name
        FROM listing_reports lr
        JOIN listings l ON l.id = lr.listing_id
        JOIN users ru ON ru.id = lr.reporter_id
        JOIN users au ON au.id = l.author_id
        ORDER BY lr.created_at DESC
        LIMIT 50
        """
    )

    blocks = fetch_all(
        """
        SELECT bu.id, bu.reason, bu.created_at,
               bkr.full_name AS blocker_name, bkd.full_name AS blocked_name
        FROM blocked_users bu
        JOIN users bkr ON bkr.id = bu.blocker_id
        JOIN users bkd ON bkd.id = bu.blocked_id
        ORDER BY bu.created_at DESC
        LIMIT 50
        """
    )

    context = {
        "user": admin,
        "stats": stats,
        "reports": reports,
        "blocks": blocks,
    }
    return render(request, "admin.html", context)


@router.get("/admin/users", response_class=HTMLResponse)
def admin_users_list(request: Request, q: str = "", sort: str = "newest", page: int = 1):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)

    sort = sort if sort in ADMIN_USER_SORT_OPTIONS else "newest"
    page = max(page, 1)
    offset = (page - 1) * ADMIN_USERS_PAGE_SIZE
    search = f"%{q.strip()}%" if q.strip() else "%"

    # Subconsultas agregadas (visitas ao perfil, nota média/qtd de
    # avaliações RECEBIDAS, mensagens recebidas) juntadas por LEFT JOIN
    # pra não sumir com usuário que ainda não tem nenhuma delas.
    base_query = f"""
        SELECT u.id, u.full_name, u.email, u.role, u.city, u.state, u.country,
               u.is_admin, u.role_level, u.email_verified, u.deleted_at, u.created_at,
               COALESCE(pv.profile_views, 0) AS profile_views,
               COALESCE(r.avg_rating, NULL) AS avg_rating,
               COALESCE(r.rating_count, 0) AS rating_count,
               COALESCE(m.messages_received, 0) AS messages_received
        FROM users u
        LEFT JOIN (
            SELECT profile_user_id, COUNT(*) AS profile_views
            FROM profile_views GROUP BY profile_user_id
        ) pv ON pv.profile_user_id = u.id
        LEFT JOIN (
            SELECT rated_id, AVG(stars)::numeric(3,2) AS avg_rating, COUNT(*) AS rating_count
            FROM ratings GROUP BY rated_id
        ) r ON r.rated_id = u.id
        LEFT JOIN (
            SELECT recipient_id, COUNT(*) AS messages_received
            FROM messages GROUP BY recipient_id
        ) m ON m.recipient_id = u.id
        WHERE u.full_name ILIKE :search OR u.email ILIKE :search
        ORDER BY {ADMIN_USER_SORT_OPTIONS[sort]}
        LIMIT :limit OFFSET :offset
    """  # nosec B608 - ORDER BY vem só de ADMIN_USER_SORT_OPTIONS (allowlist fixa,
         # `sort` já validado contra as chaves dela ali em cima); os valores de
         # busca de verdade (search, limit, offset) vão todos por parâmetro.
    users = fetch_all(base_query, {"search": search, "limit": ADMIN_USERS_PAGE_SIZE, "offset": offset})

    total = fetch_one(
        "SELECT COUNT(*) AS n FROM users WHERE full_name ILIKE :search OR email ILIKE :search",
        {"search": search},
    )["n"]

    context = {
        "user": admin,
        "users": users,
        "q": q,
        "sort": sort,
        "page": page,
        "total": total,
        "page_size": ADMIN_USERS_PAGE_SIZE,
        "has_next": offset + ADMIN_USERS_PAGE_SIZE < total,
        "has_prev": page > 1,
        "sort_options": list(ADMIN_USER_SORT_OPTIONS.keys()),
    }
    return render(request, "admin_users.html", context)


@router.get("/admin/users/{user_id}", response_class=HTMLResponse)
def admin_user_detail(request: Request, user_id: int):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)

    target = fetch_one("SELECT * FROM users WHERE id = :id", {"id": user_id})
    if not target:
        return RedirectResponse(url="/admin/users", status_code=303)

    stats = {
        "profile_views": fetch_one(
            "SELECT COUNT(*) AS n FROM profile_views WHERE profile_user_id = :id", {"id": user_id}
        )["n"],
        "avg_rating": fetch_one(
            "SELECT AVG(stars)::numeric(3,2) AS n FROM ratings WHERE rated_id = :id", {"id": user_id}
        )["n"],
        "rating_count": fetch_one(
            "SELECT COUNT(*) AS n FROM ratings WHERE rated_id = :id", {"id": user_id}
        )["n"],
        "listings": fetch_one(
            "SELECT COUNT(*) AS n FROM listings WHERE author_id = :id AND is_active = TRUE", {"id": user_id}
        )["n"],
        "messages_sent": fetch_one(
            "SELECT COUNT(*) AS n FROM messages WHERE sender_id = :id", {"id": user_id}
        )["n"],
        "messages_received": fetch_one(
            "SELECT COUNT(*) AS n FROM messages WHERE recipient_id = :id", {"id": user_id}
        )["n"],
    }

    recent_ratings = fetch_all(
        """
        SELECT rt.stars, rt.comment, rt.created_at, u.full_name AS rater_name
        FROM ratings rt JOIN users u ON u.id = rt.rater_id
        WHERE rt.rated_id = :id ORDER BY rt.created_at DESC LIMIT 20
        """,
        {"id": user_id},
    )

    context = {
        "user": admin,
        "target": target,
        "stats": stats,
        "recent_ratings": recent_ratings,
        "is_self": target["id"] == admin["id"],
    }
    return render(request, "admin_user_detail.html", context)


@router.post("/admin/users/{user_id}/verify-email")
def admin_verify_email(request: Request, user_id: int, csrf_token: str = Form(...)):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    return RedirectResponse(url=f"/admin/users/{user_id}", status_code=303)


@router.post("/admin/users/{user_id}/send-reset")
def admin_send_reset(request: Request, user_id: int, csrf_token: str = Form(...)):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    target = fetch_one("SELECT id, email, full_name FROM users WHERE id = :id", {"id": user_id})
    if target:
        send_password_reset_email(request, target["id"], target["email"], target["full_name"])
    return RedirectResponse(url=f"/admin/users/{user_id}?reset_sent=1", status_code=303)


@router.post("/admin/users/{user_id}/toggle-admin")
def admin_toggle_admin(request: Request, user_id: int, csrf_token: str = Form(...)):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    # Proteção contra auto-remoção: um admin não pode tirar o próprio
    # acesso por aqui (pra evitar que a última conta admin se tranque
    # fora sem querer). Pra remover a si mesmo, precisa ser outro admin.
    if user_id == admin["id"]:
        return RedirectResponse(url=f"/admin/users/{user_id}?self_demote_blocked=1", status_code=303)

    target = fetch_one("SELECT role_level FROM users WHERE id = :id", {"id": user_id})
    if not target:
        return RedirectResponse(url="/admin/users", status_code=303)

    # Alterna só entre comum (0) e admin (2) — promover alguém a god
    # mode (3, com acesso à Zona Vermelha) é uma ação à parte, mais
    # sensível, e só outro god mode pode fazer (ver admin_toggle_god
    # abaixo). Se a pessoa já era nível 3, um toggle por aqui a
    # rebaixa pra 0 (não deixa "meio promovida" em 2).
    new_level = LEVEL_COMUM if target["role_level"] >= LEVEL_ADMIN else LEVEL_ADMIN
    execute("UPDATE users SET role_level = :level WHERE id = :id", {"level": new_level, "id": user_id})
    sync_is_admin_flag(user_id, new_level)
    return RedirectResponse(url=f"/admin/users/{user_id}", status_code=303)


@router.post("/admin/users/{user_id}/toggle-god-mode")
def admin_toggle_god_mode(request: Request, user_id: int, csrf_token: str = Form(...)):
    """Promove/rebaixa entre admin (2) e god mode (3) — a Zona Vermelha
    só é visível a nível 3. De propósito só outro god mode pode fazer
    isso (não basta ser admin comum), pra não virar uma porta lateral
    de acesso ao painel financeiro.
    """
    admin = require_level(request, LEVEL_GOD)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    if user_id == admin["id"]:
        return RedirectResponse(url=f"/admin/users/{user_id}?self_demote_blocked=1", status_code=303)

    target = fetch_one("SELECT role_level FROM users WHERE id = :id", {"id": user_id})
    if not target or target["role_level"] < LEVEL_ADMIN:
        # Só promove/rebaixa quem já é admin (2) — pra virar god mode
        # primeiro precisa ser admin normal, um passo de cada vez.
        return RedirectResponse(url=f"/admin/users/{user_id}", status_code=303)

    new_level = LEVEL_ADMIN if target["role_level"] >= LEVEL_GOD else LEVEL_GOD
    execute("UPDATE users SET role_level = :level WHERE id = :id", {"level": new_level, "id": user_id})
    sync_is_admin_flag(user_id, new_level)
    return RedirectResponse(url=f"/admin/users/{user_id}", status_code=303)


@router.post("/admin/users/{user_id}/deactivate")
def admin_deactivate(request: Request, user_id: int, csrf_token: str = Form(...)):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    if user_id == admin["id"]:
        return RedirectResponse(url=f"/admin/users/{user_id}?self_demote_blocked=1", status_code=303)

    execute("UPDATE users SET deleted_at = now() WHERE id = :id", {"id": user_id})
    return RedirectResponse(url=f"/admin/users/{user_id}", status_code=303)


@router.post("/admin/users/{user_id}/reactivate")
def admin_reactivate(request: Request, user_id: int, csrf_token: str = Form(...)):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    execute("UPDATE users SET deleted_at = NULL WHERE id = :id", {"id": user_id})
    return RedirectResponse(url=f"/admin/users/{user_id}", status_code=303)


@router.post("/admin/users/{user_id}/delete-forever")
def admin_delete_forever(request: Request, user_id: int, csrf_token: str = Form(...)):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    if user_id == admin["id"]:
        return RedirectResponse(url=f"/admin/users/{user_id}?self_demote_blocked=1", status_code=303)

    # Apagamento de verdade (DELETE, não soft-delete) — os FOREIGN KEYs
    # em anúncios/mensagens/avaliações/denúncias já são ON DELETE CASCADE
    # ou SET NULL (ver db/schema.sql), então isso limpa tudo relacionado
    # à conta automaticamente. Irreversível.
    execute("DELETE FROM users WHERE id = :id", {"id": user_id})
    return RedirectResponse(url="/admin/users?deleted=1", status_code=303)


# Nomes dos dias da semana pro EXTRACT(dow ...) do Postgres, que
# devolve 0 = domingo, 1 = segunda, ..., 6 = sábado.
_WEEKDAY_NAMES = {
    "de": ["Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"],
    "en": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
}


@router.get("/admin/analytics", response_class=HTMLResponse)
def admin_analytics(request: Request):
    """
    Painel "Análise de Dados" — só leitura, pensado pra dar um
    termômetro de uso do site (quando o pessoal mais visita, de onde
    vem, quem volta) sem precisar mexer em SQL toda vez.

    Todas as consultas aqui são agregadas (contagens/médias) — nunca
    mostra qual PESSOA visitou o quê; site_visits (ver db/schema.sql)
    já é registrado sem guardar identidade de propósito.
    """
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)

    lang = getattr(request.state, "lang", "de")

    # --- Visitas gerais: hoje / semana / mês / ano ------------------
    visits_totals = fetch_one(
        """
        SELECT
            COUNT(*) FILTER (WHERE visited_at >= date_trunc('day', now())) AS today,
            COUNT(*) FILTER (WHERE visited_at >= date_trunc('week', now())) AS this_week,
            COUNT(*) FILTER (WHERE visited_at >= date_trunc('month', now())) AS this_month,
            COUNT(*) FILTER (WHERE visited_at >= date_trunc('year', now())) AS this_year,
            COUNT(*) AS all_time
        FROM site_visits
        """
    )

    # --- Termômetro: dia da semana / hora do dia / dia do mês -------
    # "Média" = total de visitas naquele grupo ÷ quantos dias-calendário
    # distintos esse grupo já apareceu na tabela — assim um domingo que
    # só existe há 2 semanas de dados não fica sub-representado frente
    # a uma segunda-feira com 8 semanas de histórico.
    by_weekday_raw = fetch_all(
        """
        SELECT
            EXTRACT(dow FROM visited_at)::int AS dow,
            COUNT(*) AS total,
            COUNT(DISTINCT date_trunc('day', visited_at)) AS distinct_days
        FROM site_visits
        GROUP BY dow
        ORDER BY dow
        """
    )
    weekday_names = _WEEKDAY_NAMES.get(lang, _WEEKDAY_NAMES["de"])
    by_weekday = [
        {
            "label": weekday_names[row["dow"]],
            "total": row["total"],
            "avg": round(row["total"] / row["distinct_days"], 1) if row["distinct_days"] else 0,
        }
        for row in by_weekday_raw
    ]

    by_hour_raw = fetch_all(
        """
        SELECT EXTRACT(hour FROM visited_at)::int AS hour, COUNT(*) AS total
        FROM site_visits GROUP BY hour ORDER BY hour
        """
    )
    by_hour = {row["hour"]: row["total"] for row in by_hour_raw}
    max_hour_total = max(by_hour.values()) if by_hour else 0
    by_hour_chart = [
        {"hour": h, "total": by_hour.get(h, 0), "pct": round(100 * by_hour.get(h, 0) / max_hour_total) if max_hour_total else 0}
        for h in range(24)
    ]

    by_day_of_month_raw = fetch_all(
        """
        SELECT EXTRACT(day FROM visited_at)::int AS dom, COUNT(*) AS total
        FROM site_visits GROUP BY dom ORDER BY dom
        """
    )
    by_day_of_month = {row["dom"]: row["total"] for row in by_day_of_month_raw}
    max_dom_total = max(by_day_of_month.values()) if by_day_of_month else 0
    by_day_of_month_chart = [
        {"day": d, "total": by_day_of_month.get(d, 0), "pct": round(100 * by_day_of_month.get(d, 0) / max_dom_total) if max_dom_total else 0}
        for d in range(1, 32)
    ]

    # --- Usuários ativos ---------------------------------------------
    active_users = fetch_one(
        """
        SELECT
            COUNT(*) FILTER (WHERE last_seen_at >= now() - interval '5 minutes') AS active_now,
            COUNT(*) FILTER (WHERE last_seen_at >= now() - interval '60 minutes') AS active_last_hour
        FROM users WHERE deleted_at IS NULL
        """
    )

    # --- Cadastrados por cidade / estado / país / voz -----------------
    by_city = fetch_all(
        """
        SELECT city, COUNT(*) AS n FROM users
        WHERE deleted_at IS NULL AND city IS NOT NULL AND city <> ''
        GROUP BY city ORDER BY n DESC LIMIT 15
        """
    )
    by_state = fetch_all(
        """
        SELECT state, COUNT(*) AS n FROM users
        WHERE deleted_at IS NULL AND state IS NOT NULL AND state <> ''
        GROUP BY state ORDER BY n DESC LIMIT 15
        """
    )
    by_country = fetch_all(
        "SELECT country, COUNT(*) AS n FROM users WHERE deleted_at IS NULL GROUP BY country ORDER BY n DESC"
    )
    by_voice_type = fetch_all(
        """
        SELECT vt.name, COUNT(*) AS n
        FROM singer_profiles sp
        JOIN users u ON u.id = sp.user_id AND u.deleted_at IS NULL
        LEFT JOIN voice_types vt ON vt.id = sp.voice_type_id
        GROUP BY vt.name ORDER BY n DESC
        """
    )

    # --- Funil de conversão -------------------------------------------
    funnel = fetch_one(
        """
        SELECT
            COUNT(*) AS registered,
            COUNT(*) FILTER (WHERE email_verified) AS verified,
            COUNT(DISTINCT l.author_id) AS posted_listing
        FROM users u
        LEFT JOIN listings l ON l.author_id = u.id
        WHERE u.deleted_at IS NULL
        """
    )

    # --- Taxa de resposta de mensagens ---------------------------------
    # Conta por PAR de pessoas (não por mensagem individual): das
    # conversas que já trocaram pelo menos 1 mensagem, quantas tiveram
    # resposta (mensagem nos dois sentidos)?
    reply_stats = fetch_one(
        """
        WITH pairs AS (
            SELECT LEAST(sender_id, recipient_id) AS a, GREATEST(sender_id, recipient_id) AS b, sender_id
            FROM messages
        ),
        conversations AS (
            SELECT a, b, COUNT(DISTINCT sender_id) AS distinct_senders
            FROM pairs GROUP BY a, b
        )
        SELECT
            COUNT(*) AS total_conversations,
            COUNT(*) FILTER (WHERE distinct_senders = 2) AS replied_conversations
        FROM conversations
        """
    )
    reply_rate_pct = (
        round(100 * reply_stats["replied_conversations"] / reply_stats["total_conversations"])
        if reply_stats["total_conversations"] else None
    )

    # --- Distribuição de notas e de tipo de anúncio --------------------
    ratings_distribution = fetch_all(
        "SELECT stars, COUNT(*) AS n FROM ratings GROUP BY stars ORDER BY stars DESC"
    )
    listing_type_distribution = fetch_all(
        "SELECT listing_type, COUNT(*) AS n FROM listings WHERE is_active = TRUE GROUP BY listing_type ORDER BY n DESC"
    )

    # --- Retenção -------------------------------------------------------
    # % de quem se cadastrou há X dias ou mais e ainda deu sinal de vida
    # (last_seen_at) X dias DEPOIS do cadastro.
    retention = fetch_one(
        """
        SELECT
            COUNT(*) FILTER (WHERE created_at <= now() - interval '7 days') AS eligible_7d,
            COUNT(*) FILTER (
                WHERE created_at <= now() - interval '7 days' AND last_seen_at >= created_at + interval '7 days'
            ) AS retained_7d,
            COUNT(*) FILTER (WHERE created_at <= now() - interval '30 days') AS eligible_30d,
            COUNT(*) FILTER (
                WHERE created_at <= now() - interval '30 days' AND last_seen_at >= created_at + interval '30 days'
            ) AS retained_30d
        FROM users WHERE deleted_at IS NULL
        """
    )
    retention_7d_pct = round(100 * retention["retained_7d"] / retention["eligible_7d"]) if retention["eligible_7d"] else None
    retention_30d_pct = round(100 * retention["retained_30d"] / retention["eligible_30d"]) if retention["eligible_30d"] else None

    # --- Idioma e origem do tráfego --------------------------------------
    by_lang = fetch_all("SELECT lang, COUNT(*) AS n FROM site_visits GROUP BY lang ORDER BY n DESC")
    by_referrer = fetch_all(
        """
        SELECT COALESCE(referrer_domain, '(direto / desconhecido)') AS origem, COUNT(*) AS n
        FROM site_visits GROUP BY referrer_domain ORDER BY n DESC LIMIT 15
        """
    )

    context = {
        "user": admin,
        "visits_totals": visits_totals,
        "by_weekday": by_weekday,
        "by_hour_chart": by_hour_chart,
        # Mesmo dado de by_weekday/by_hour_chart, só no formato
        # {label, value} que app/static/js/financial-charts.js espera
        # pro seletor barra/pizza/linha (ver Zona Vermelha).
        "by_weekday_json": [{"label": w["label"], "value": w["avg"]} for w in by_weekday],
        "by_hour_json": [{"label": f"{h['hour']:02d}:00", "value": h["total"]} for h in by_hour_chart if h["total"] > 0],
        "by_day_of_month_chart": by_day_of_month_chart,
        "active_users": active_users,
        "by_city": by_city,
        "by_state": by_state,
        "by_country": by_country,
        "by_voice_type": by_voice_type,
        "funnel": funnel,
        "reply_rate_pct": reply_rate_pct,
        "reply_stats": reply_stats,
        "ratings_distribution": ratings_distribution,
        "listing_type_distribution": listing_type_distribution,
        "retention_7d_pct": retention_7d_pct,
        "retention_30d_pct": retention_30d_pct,
        "retention": retention,
        "by_lang": by_lang,
        "by_referrer": by_referrer,
    }
    return render(request, "admin_analytics.html", context)


# ------------------------------------------------------------
# Posts (feed de avisos/parcerias/dicas na home) — só admin cria,
# edita ou despublica. Ver db/schema.sql (tabela posts) e
# app/routers/listings_routes.py::home() (onde o feed é lido de volta).
# ------------------------------------------------------------

@router.get("/admin/posts", response_class=HTMLResponse)
def admin_posts_list(request: Request):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)

    posts = fetch_all(
        """
        SELECT p.id, p.title, p.body, p.is_published, p.created_at, u.full_name AS author_name
        FROM posts p
        JOIN users u ON u.id = p.author_id
        ORDER BY p.created_at DESC
        """
    )
    context = {
        "user": admin,
        "posts": posts,
        "created": request.query_params.get("created") == "1",
        "title_max": POST_TITLE_MAX_LENGTH,
        "body_max": POST_BODY_MAX_LENGTH,
    }
    return render(request, "admin_posts.html", context)


@router.post("/admin/posts")
def admin_posts_create(
    request: Request,
    csrf_token: str = Form(...),
    title: str = Form(...),
    body: str = Form(...),
):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    title = title.strip()
    body = body.strip()
    if not title or not body:
        return RedirectResponse(url="/admin/posts?error=empty", status_code=303)
    if len(title) > POST_TITLE_MAX_LENGTH or len(body) > POST_BODY_MAX_LENGTH:
        # Não cortamos o HTML no limite (poderia partir uma tag no meio
        # e sobrar marcação quebrada) — pede pra pessoa encurtar e
        # reenviar, em vez disso.
        return RedirectResponse(url="/admin/posts?error=too_long", status_code=303)

    # O editor (app/static/js/post-editor.js) manda HTML puro — só
    # passa daqui pra frente o que estiver na lista permitida (ver
    # app/richtext.py); qualquer <script>/onclick/etc é removido, não
    # escapado (os templates usam {{ post.body | safe }}).
    body = sanitize_post_body(body)
    if not body.strip():
        return RedirectResponse(url="/admin/posts?error=empty", status_code=303)

    execute_returning(
        "INSERT INTO posts (author_id, title, body) VALUES (:author_id, :title, :body) RETURNING id",
        {"author_id": admin["id"], "title": title, "body": body},
    )
    return RedirectResponse(url="/admin/posts?created=1", status_code=303)


@router.post("/admin/posts/upload-image")
async def admin_posts_upload_image(request: Request, image: UploadFile = File(...)):
    """
    Chamada pelo botão de imagem do editor (app/static/js/post-editor.js,
    via fetch/FormData) — devolve {"url": "/post-images/..."} pra
    inserir no texto, ou 400 se o arquivo não for uma imagem válida.
    Exige o mesmo CSRF token de qualquer outro POST (mandado no header
    X-CSRF-Token, já que aqui é fetch() e não um <form> normal).
    """
    admin = require_admin(request)
    if not admin:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    verify_csrf(request, request.headers.get("x-csrf-token", ""))

    url = await save_post_image(image)
    if not url:
        return JSONResponse({"error": "invalid_image"}, status_code=400)
    return JSONResponse({"url": url})


@router.post("/admin/posts/{post_id}/toggle-publish")
def admin_posts_toggle_publish(request: Request, post_id: int, csrf_token: str = Form(...)):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    execute("UPDATE posts SET is_published = NOT is_published WHERE id = :id", {"id": post_id})
    return RedirectResponse(url="/admin/posts", status_code=303)


@router.post("/admin/posts/{post_id}/delete")
def admin_posts_delete(request: Request, post_id: int, csrf_token: str = Form(...)):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    execute("DELETE FROM posts WHERE id = :id", {"id": post_id})
    return RedirectResponse(url="/admin/posts", status_code=303)

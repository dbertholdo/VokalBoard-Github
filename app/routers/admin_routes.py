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
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse

from app.database import fetch_all, fetch_one, execute
from app.auth import get_current_user
from app.render import render
from app.csrf import verify_csrf
from app.routers.auth_routes import send_password_reset_email

router = APIRouter()

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
    """Devolve o usuário logado se ele for admin, senão None."""
    user = get_current_user(request)
    if not user or not user.get("is_admin"):
        return None
    return user


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    admin = require_admin(request)
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
               u.is_admin, u.email_verified, u.deleted_at, u.created_at,
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
    """
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

    execute("UPDATE users SET is_admin = NOT is_admin WHERE id = :id", {"id": user_id})
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

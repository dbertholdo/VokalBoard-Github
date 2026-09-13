"""
Painel de administração MÍNIMO, só leitura — não substitui o Adminer
(ver docker-compose.yml, serviço "adminer"), que continua sendo o
lugar certo pra editar dados diretamente. Isso aqui é só uma telinha
rápida de triagem (denúncias recentes, bloqueios, números gerais) pra
não precisar abrir o Adminer/psql toda vez só pra dar uma olhada.

Proteção: users.is_admin (ver db/schema.sql). Não existe cadastro de
admin pela interface — vira admin só via UPDATE direto no banco:

    UPDATE users SET is_admin = TRUE WHERE email = 'seu-email@exemplo.com';

(ver README, seção "Nível de admin").
"""
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, HTMLResponse

from app.database import fetch_all, fetch_one
from app.auth import get_current_user
from app.render import render

router = APIRouter()


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

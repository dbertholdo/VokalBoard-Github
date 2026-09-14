"""
Níveis de acesso administrativo (ver users.role_level em db/schema.sql):

    0 = comum       — usuário normal, sem nenhum acesso a /admin
    1 = moderador   — só a fila de denúncias/bloqueios (leitura + agir
                       sobre denúncias), sem mexer em usuários nem em
                       nada financeiro
    2 = admin       — tudo que o painel /admin já fazia antes de ter
                       níveis: usuários, posts, análise de dados
    3 = god mode    — único nível que enxerga a Zona Vermelha (Modo
                       Capitalismo, preço de assinatura, painel
                       financeiro) — ver app/routers/financial_routes.py

Cada nível inclui as permissões dos níveis abaixo dele (é uma escala,
não categorias separadas).
"""
from fastapi import Request

from app.auth import get_current_user, verify_password
from app.database import execute, fetch_one
from app.client_ip import get_client_ip

LEVEL_COMUM = 0
LEVEL_MODERADOR = 1
LEVEL_ADMIN = 2
LEVEL_GOD = 3


def require_level(request: Request, min_level: int) -> dict | None:
    """Devolve o usuário logado se o nível dele for >= min_level, senão None.

    De propósito devolve só None (não levanta exceção, não diferencia
    "não logado" de "nível insuficiente") — cada rota decide o que
    fazer, geralmente redirecionando pra "/" sem mensagem específica,
    mesmo padrão que o require_admin original já usava.
    """
    user = get_current_user(request)
    if not user or (user.get("role_level") or 0) < min_level:
        return None
    return user


def sync_is_admin_flag(user_id: int, new_role_level: int) -> None:
    """Mantém a coluna legada is_admin em sincronia com role_level.

    is_admin continua existindo (telas antigas, README, o próprio
    require_admin de nível 2) — sempre que role_level muda por aqui,
    is_admin acompanha: True para nível >= 2, False abaixo disso.
    """
    execute(
        "UPDATE users SET is_admin = :is_admin WHERE id = :id",
        {"is_admin": new_role_level >= LEVEL_ADMIN, "id": user_id},
    )


def reauthenticate(request: Request, user: dict, password: str) -> bool:
    """Confirma a senha atual de novo (step-up auth), pro mesmo padrão
    já usado em /profile/delete-account. Usado antes de qualquer ação
    dentro da Zona Vermelha — ligar/desligar o Modo Capitalismo, mudar
    preço — mesmo que a pessoa já esteja logada como god mode.
    """
    row = fetch_one("SELECT password_hash FROM users WHERE id = :id", {"id": user["id"]})
    if not row:
        return False
    return verify_password(password, row["password_hash"])


def log_audit_action(request: Request, actor: dict | None, action: str, details: str = "") -> None:
    """Grava uma linha no audit_log — chamado depois de toda ação da
    Zona Vermelha, sucesso ou falha de reautenticação (pra também ficar
    registrada uma tentativa que falhou na senha).
    """
    execute(
        """
        INSERT INTO audit_log (actor_user_id, action, details, ip_address)
        VALUES (:actor_id, :action, :details, :ip)
        """,
        {
            "actor_id": actor["id"] if actor else None,
            "action": action,
            "details": details,
            "ip": get_client_ip(request),
        },
    )

"""
Moderação de denúncias — P6 (18/09/2026).

Pedido do Daniel (painel de Admin): "resposta a denúncias e
notificação ao usuário quando denúncia for aceita". Antes desta
etapa, `listing_reports` só armazenava a denúncia (ver
app/routers/listings_routes.py `report_listing()`) — sem status, sem
quem revisou, sem notificar ninguém; só dava pra consultar direto no
banco (Adminer). Isso já era mostrado (read-only) no dashboard do
Admin (`/admin`, "Recent reports").

Esta etapa fecha o loop: aceitar ou rejeitar uma denúncia marca
`status`/`resolved_at`/`resolved_by_user_id` (migration
`db/migrations/2026-09-18_p6_admin_report_moderation.sql`) e devolve
os dados que a rota precisa pra notificar quem denunciou (ver
`report_resolved_email()` em app/email_localization.py e as rotas
POST /admin/reports/{id}/accept|reject em app/routers/admin_routes.py).

Decisão: "o usuário" que recebe a notificação de RESULTADO é QUEM
DENUNCIOU (o reporter) — é o padrão mais comum de "resposta a uma
denúncia" (confirmar pra quem denunciou que foi revisado), tanto ao
aceitar quanto ao rejeitar.

Segunda etapa, mesmo dia — "no botão de denúncia precisamos definir
alguma forma de warning/punição/banimento": aceitar uma denúncia agora
também pode aplicar uma PUNIÇÃO ao autor do anúncio denunciado (não
ao reporter), escolhida no mesmo formulário, com 3 níveis:

  - `warning` — só notifica o autor por e-mail (nenhum efeito na
    conta). Fica registrado em `moderation_actions` mesmo assim, pra
    dar pra ver o histórico depois (ex.: "3 avisos" no mini card do
    Admin).
  - `suspend` — reaproveita o MESMO mecanismo de "Deactivate account"
    que já existia (`users.deleted_at`) — o próprio autor pode
    reverter fazendo login de novo (ver app/routers/auth_routes.py,
    fluxo de reativação). "Temporária" no sentido de que a pessoa
    mesma pode desfazer, não que expira sozinha num prazo.
  - `ban` — DIFERENTE de suspender: além de `deleted_at` (esconde tudo
    pelos mesmos filtros que já existiam), grava `users.banned_at` —
    login NÃO oferece reativação pra uma conta banida (checado
    explicitamente antes do fluxo de reativação), e só um Admin
    reverte, manualmente, via unban_user() abaixo. O e-mail continua
    ocupado pra sempre (a conta nunca é apagada de verdade só por
    isso), então não dá pra recriar uma conta nova com o mesmo e-mail
    — checagem que já existia em /register (email é UNIQUE).
"""
from app.database import fetch_one, execute

REPORT_STATUSES = ("open", "accepted", "rejected")
PUNISHMENT_TYPES = ("warning", "suspend", "ban")


def get_open_reports(limit: int = 50) -> list[dict]:
    from app.database import fetch_all

    return fetch_all(
        """
        SELECT lr.id, lr.reason, lr.created_at, lr.status,
               l.id AS listing_id, l.title AS listing_title,
               ru.full_name AS reporter_name,
               au.full_name AS author_name
        FROM listing_reports lr
        JOIN visible_listings l ON l.id = lr.listing_id
        JOIN users ru ON ru.id = lr.reporter_id
        JOIN users au ON au.id = l.author_id
        WHERE lr.status = 'open'
        ORDER BY lr.created_at ASC
        LIMIT :limit
        """,
        {"limit": limit},
    )


def resolve_report(report_id: int, accepted: bool, admin_id: int) -> dict | None:
    """Marca a denúncia como aceita/rejeitada. Retorna um dict com o
    necessário pra notificar quem denunciou (reporter_id,
    reporter_name, reporter_email, preferred_language, listing_title)
    E, pra quando `accepted` vier acompanhado de uma punição, os dados
    do AUTOR do anúncio (author_id, author_name, author_email,
    author_preferred_language) — ou None se a denúncia não existir ou
    já tiver sido resolvida (evita notificar/punir duas vezes por um
    duplo clique/retry)."""
    report = fetch_one(
        """
        SELECT lr.id, lr.status, lr.reporter_id,
               ru.full_name AS reporter_name, ru.email AS reporter_email,
               ru.preferred_language,
               l.title AS listing_title,
               au.id AS author_id, au.full_name AS author_name, au.email AS author_email,
               au.preferred_language AS author_preferred_language
        FROM listing_reports lr
        JOIN users ru ON ru.id = lr.reporter_id
        JOIN listings l ON l.id = lr.listing_id
        JOIN users au ON au.id = l.author_id
        WHERE lr.id = :id
        """,
        {"id": report_id},
    )
    if not report or report["status"] != "open":
        return None

    new_status = "accepted" if accepted else "rejected"
    execute(
        """
        UPDATE listing_reports
        SET status = :status, resolved_at = now(), resolved_by_user_id = :admin_id
        WHERE id = :id
        """,
        {"status": new_status, "admin_id": admin_id, "id": report_id},
    )
    return report


def apply_moderation_punishment(user_id: int, punishment: str, report_id: int, admin_id: int) -> None:
    """Aplica a punição escolhida ao aceitar uma denúncia (ver
    PUNISHMENT_TYPES acima pro que cada nível faz). Sempre grava uma
    linha em `moderation_actions`, mesmo pro `warning` (que não muda a
    conta) — é o que permite ver o histórico depois."""
    if punishment not in PUNISHMENT_TYPES:
        raise ValueError(f"apply_moderation_punishment: nível inválido: {punishment!r}")

    if punishment == "suspend":
        execute("UPDATE users SET deleted_at = now() WHERE id = :id", {"id": user_id})
    elif punishment == "ban":
        execute(
            "UPDATE users SET deleted_at = now(), banned_at = now(), banned_by_user_id = :admin_id WHERE id = :id",
            {"admin_id": admin_id, "id": user_id},
        )
    # "warning" não muda a conta — só o registro abaixo.

    execute(
        """
        INSERT INTO moderation_actions (user_id, report_id, action_type, admin_id)
        VALUES (:user_id, :report_id, :action_type, :admin_id)
        """,
        {"user_id": user_id, "report_id": report_id, "action_type": punishment, "admin_id": admin_id},
    )


def unban_user(user_id: int) -> None:
    """Reverte um banimento — SEMPRE manual (nunca automático, nunca
    por expiração). Também limpa `deleted_at`: um banimento sempre
    desativa a conta junto (ver apply_moderation_punishment), então
    desfazer o ban também reativa, num passo só — sem isso a conta
    ficaria "desbanida" mas ainda escondida/em fluxo de reativação."""
    execute(
        "UPDATE users SET banned_at = NULL, banned_by_user_id = NULL, deleted_at = NULL WHERE id = :id",
        {"id": user_id},
    )


def get_moderation_history(user_id: int, limit: int = 20) -> list[dict]:
    from app.database import fetch_all

    return fetch_all(
        """
        SELECT ma.action_type, ma.created_at, admin.full_name AS admin_name
        FROM moderation_actions ma
        LEFT JOIN users admin ON admin.id = ma.admin_id
        WHERE ma.user_id = :id
        ORDER BY ma.created_at DESC
        LIMIT :limit
        """,
        {"id": user_id, "limit": limit},
    )

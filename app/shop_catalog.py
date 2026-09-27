"""
Catálogo da loja de Notas — P5 Loja.

Painel de Admin (18/09/2026): antes desta etapa o catálogo era uma
lista fixa no Python (`REDEMPTION_CATALOG` em
`app/routers/notas_routes.py`). Pra dar ao Admin controle real de
ativar/desativar um item (ex.: em caso de bug) sem precisar de
deploy, preço e estado (ativo/inativo) passaram a viver na tabela
`shop_catalog_items` — ver
`db/migrations/2026-09-18_p5_loja_admin_catalog.sql`.

CRUD de itens (18/09/2026, mesmo dia): "colocar forma de adicionar
itens à loja, mudar descrição e título de itens, como uma loja
normal" — título, descrição e ícone também passaram a viver no
banco (`db/migrations/2026-09-18_p5_loja_catalog_crud.sql`), editáveis
pelo Admin em UM idioma só (decisão do Daniel via AskUserQuestion —
mostra igual pra todo mundo, não precisa traduzir toda vez). Um item
NOVO criado pelo Admin é um **voucher genérico**: só debita Notas e
fica registrado no histórico — sem efeito automático no sistema
(quem cumpre é o Admin, manualmente, fora do site). O único efeito
programado em código continua sendo o do item que já existia
(`profile_highlight_7d`, estende `profile_highlighted_until`) — ver
`ITEM_EFFECTS` abaixo e `redeem_notas()` em
`app/routers/notas_routes.py`. `title`/`description` NULL num item
significa "ainda usa o texto de `app/i18n.py`" — só o item que já
existia de início cai nesse caso (item novo sempre preenche os dois,
já que não tem entrada no i18n pra usar de fallback).

Também vive aqui a definição de "transação da loja" usada pelo
histórico geral do Admin (`get_shop_history`): resgates de catálogo
(`redeem_<item_key>`) e compra de urgência (`urgency_purchase`) —
NÃO inclui bônus de indicação, recompensa por vaga postada ou
recompensa de Match urgente, que não são compras.
"""
import re
import unicodedata
from decimal import Decimal

from sqlalchemy import text

from app.database import engine, fetch_all, fetch_one, execute_returning

# Metadados de EFEITO por item — não administráveis pelo Admin (é
# lógica de produto, não configuração). Só o item que já existia de
# início tem um aqui; item novo criado pelo Admin nunca aparece nesse
# dicionário, então vira um voucher genérico (sem efeito automático).
ITEM_EFFECTS = {
    "profile_highlight_7d": {
        "days": 7,
    },
}

# Ícones que o Admin pode escolher ao criar/editar um item — lista
# fechada e validada no servidor (nunca um id arbitrário vindo do
# Form), pra loja não acabar linkando um #icon-... que não existe em
# icons.svg. Um subconjunto de app/static/img/icons.svg que faz
# sentido pra "prêmio"/"vantagem".
ALLOWED_ICONS = (
    "icon-gift", "icon-sparkle", "icon-star", "icon-crown", "icon-trophy",
    "icon-tip", "icon-music", "icon-mic", "icon-card", "icon-money",
    "icon-party", "icon-book", "icon-scroll",
)
DEFAULT_ICON = "icon-gift"

MAX_TITLE_LENGTH = 150
MAX_DESCRIPTION_LENGTH = 500

# Reasons no credit_ledger que representam uma COMPRA na loja (débito
# iniciado pelo próprio usuário) — usado pra filtrar o histórico geral
# do Admin. "redeem_" é um prefixo (um por item_key do catálogo);
# "urgency_purchase" é fixo (ver app/urgency.py).
_SHOP_REASON_PREFIX = "redeem_"
_SHOP_FIXED_REASONS = ("urgency_purchase",)


def is_shop_reason(reason: str) -> bool:
    return reason.startswith(_SHOP_REASON_PREFIX) or reason in _SHOP_FIXED_REASONS


def _slugify(title: str) -> str:
    """"Convite especial!" -> "convite_especial" — usado só pra gerar
    o item_key de um item novo (nunca exibido, é só um identificador
    interno)."""
    normalized = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_")
    return slug or "item"


def _unique_item_key(title: str) -> str:
    base = _slugify(title)[:40]  # deixa espaço pro sufixo numérico, item_key é VARCHAR(50)
    candidate = base
    suffix = 2
    while fetch_one("SELECT 1 FROM shop_catalog_items WHERE item_key = :key", {"key": candidate}):
        candidate = f"{base}_{suffix}"[:50]
        suffix += 1
    return candidate


def _clean_catalog_row(row: dict) -> dict:
    """Junta a linha do banco com o efeito de código (se houver) —
    formato comum devolvido por get_active_catalog()/get_redeemable_item()."""
    effect = ITEM_EFFECTS.get(row["item_key"], {})
    return {
        "key": row["item_key"],
        "cost": row["cost"],
        "icon": row["icon"],
        "title": row["title"],
        "description": row["description"],
        **effect,
    }


def get_active_catalog() -> list[dict]:
    """Itens ativos — usado pela página pública /notas. Inclui
    vouchers genéricos (sem efeito de código) normalmente."""
    rows = fetch_all(
        "SELECT item_key, cost, icon, title, description FROM shop_catalog_items "
        "WHERE active = TRUE ORDER BY id"
    )
    return [_clean_catalog_row(row) for row in rows]


def get_redeemable_item(item_key: str) -> dict | None:
    """Item ativo pronto pro fluxo de resgate (preço + efeito, se
    houver), ou None se não existir ou estiver desativado — usado por
    redeem_notas() ANTES de debitar."""
    row = fetch_one(
        "SELECT item_key, cost, icon, title, description FROM shop_catalog_items "
        "WHERE item_key = :key AND active = TRUE",
        {"key": item_key},
    )
    if not row:
        return None
    return _clean_catalog_row(row)


def list_all_catalog_items() -> list[dict]:
    """Todos os itens (ativos e inativos) — usado pelo painel de
    Admin (/admin/loja)."""
    return fetch_all(
        "SELECT id, item_key, cost, active, title, description, icon, updated_at "
        "FROM shop_catalog_items ORDER BY id"
    )


def get_catalog_titles_by_key() -> dict[str, str | None]:
    """{item_key: title} de TODOS os itens (mesmo inativos) — usado
    pra mostrar o nome certo no extrato/ledger mesmo se o item já
    tiver sido desativado depois. title None = ainda usa o texto do
    i18n (o template cai pro t('notas_item_<key>_title')) — só o item
    que já existia de início pode cair nesse caso."""
    rows = fetch_all("SELECT item_key, title FROM shop_catalog_items")
    return {row["item_key"]: row["title"] for row in rows}


def toggle_catalog_item_active(item_id: int) -> bool | None:
    """Inverte active/inativo de um item. Retorna o novo estado, ou
    None se o item não existir. Só bloqueia NOVOS resgates — quem já
    resgatou antes mantém o benefício normalmente (decisão do
    Daniel, 18/09/2026), então não mexe em nada além da flag."""
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "UPDATE shop_catalog_items SET active = NOT active, updated_at = now() "
                "WHERE id = :id RETURNING active"
            ),
            {"id": item_id},
        ).mappings().first()
    return row["active"] if row else None


def create_catalog_item(title: str, description: str, cost: Decimal, icon: str) -> dict:
    """Cria um item NOVO — sempre um voucher genérico (nunca tem
    entrada em ITEM_EFFECTS, então não faz nada automático ao ser
    resgatado, só debita Notas e registra no histórico). title/
    description são obrigatórios aqui (ao contrário do item que já
    existia, um item novo não tem entrada no i18n pra cair como
    fallback)."""
    title = title.strip()[:MAX_TITLE_LENGTH]
    description = description.strip()[:MAX_DESCRIPTION_LENGTH]
    icon = icon if icon in ALLOWED_ICONS else DEFAULT_ICON
    item_key = _unique_item_key(title or "item")
    row = execute_returning(
        """
        INSERT INTO shop_catalog_items (item_key, cost, active, title, description, icon)
        VALUES (:key, :cost, TRUE, :title, :description, :icon)
        RETURNING id, item_key
        """,
        {"key": item_key, "cost": cost, "title": title, "description": description, "icon": icon},
    )
    return dict(row)


def update_catalog_item(item_id: int, title: str, description: str, cost: Decimal, icon: str) -> bool:
    """Atualiza título/descrição/preço/ícone de um item já existente
    (ativo/inativo não muda aqui — isso é o toggle_catalog_item_active
    separado). A partir do momento em que o Admin edita, o item passa
    a usar o texto do banco (title/description deixam de ser NULL,
    mesmo pro item que ainda usava o i18n)."""
    title = title.strip()[:MAX_TITLE_LENGTH]
    description = description.strip()[:MAX_DESCRIPTION_LENGTH]
    icon = icon if icon in ALLOWED_ICONS else DEFAULT_ICON
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                UPDATE shop_catalog_items
                SET title = :title, description = :description, cost = :cost, icon = :icon, updated_at = now()
                WHERE id = :id
                """
            ),
            {"id": item_id, "title": title, "description": description, "cost": cost, "icon": icon},
        )
    return result.rowcount > 0


def grant_catalog_item_to_user(user_id: int, item_key: str, admin_id: int, admin_note: str) -> bool:
    """Issues an active catalog item to a specific user directly,
    bypassing the self-purchase flow in redeem_notas() (P6 close-out,
    19/09/2026 — /financeiro/conceder). Unlike a real redemption, this
    never touches the user's balance (delta stays 0): it's a
    comp/grant, not a purchase paid with their own Notas. Still
    inserts one credit_ledger row with reason=f"redeem_{item_key}" so
    it shows up in the normal shop history/extrato exactly like a real
    redemption would, and applies the same ITEM_EFFECTS side effect
    (e.g. extending profile_highlighted_until) inside the same
    transaction, mirroring redeem_notas() in app/routers/notas_routes.py.
    Returns False if the item doesn't exist or is inactive (nothing is
    inserted in that case)."""
    from datetime import datetime, timedelta, timezone

    item = get_redeemable_item(item_key)
    if not item:
        return False

    with engine.begin() as conn:
        account = conn.execute(
            text("SELECT profile_highlighted_until FROM users WHERE id = :id FOR UPDATE"),
            {"id": user_id},
        ).mappings().first()
        if not account:
            return False

        conn.execute(
            text(
                """
                INSERT INTO credit_ledger (user_id, delta, reason, reference_id, admin_note)
                VALUES (:uid, 0, :reason, :admin_id, :note)
                """
            ),
            {"uid": user_id, "reason": f"redeem_{item_key}", "admin_id": admin_id, "note": admin_note},
        )

        if "days" in item:
            now = datetime.now(timezone.utc)
            current_until = account["profile_highlighted_until"]
            base = current_until if current_until and current_until > now else now
            conn.execute(
                text("UPDATE users SET profile_highlighted_until = :until WHERE id = :id"),
                {"until": base + timedelta(days=item["days"]), "id": user_id},
            )
    return True


SHOP_HISTORY_PAGE_SIZE = 30


def get_shop_history(limit: int = SHOP_HISTORY_PAGE_SIZE, offset: int = 0) -> list[dict]:
    """Transações da loja (todos os usuários), mais recentes
    primeiro — usado pelo "histórico geral" do Admin. Junta com
    `users` pra mostrar nome/e-mail em vez de só o id."""
    rows = fetch_all(
        """
        SELECT cl.id, cl.delta, cl.reason, cl.reference_id, cl.created_at,
               u.id AS user_id, u.full_name AS user_name, u.email AS user_email
        FROM credit_ledger cl
        JOIN users u ON u.id = cl.user_id
        WHERE cl.reason LIKE :prefix OR cl.reason = ANY(:fixed_reasons)
        ORDER BY cl.created_at DESC, cl.id DESC
        LIMIT :limit OFFSET :offset
        """,
        {
            "prefix": f"{_SHOP_REASON_PREFIX}%",
            "fixed_reasons": list(_SHOP_FIXED_REASONS),
            "limit": limit,
            "offset": offset,
        },
    )
    return rows


def count_shop_history() -> int:
    row = fetch_one(
        """
        SELECT COUNT(*) AS n FROM credit_ledger
        WHERE reason LIKE :prefix OR reason = ANY(:fixed_reasons)
        """,
        {"prefix": f"{_SHOP_REASON_PREFIX}%", "fixed_reasons": list(_SHOP_FIXED_REASONS)},
    )
    return row["n"] if row else 0


def redeem_item(user_id: int, item_key: str, idempotency_token: str = "") -> tuple[str, dict | None]:
    """Redeems a catalog item in ONE transaction (2026-09-27 cleanup): debit +
    the item's effect commit together, so a failure can no longer leave Notas
    spent without the reward. The user row is locked before the double-submit
    check, so two quick clicks serialize: the second sees the first's key and
    is a no-op (it used to be able to stack a second 7-day highlight).
    Returns (status, item) — status: 'redeemed', 'replay', 'not_found', 'insufficient'."""
    from app.notas_wallet import debit_in_tx  # local import: notas_wallet imports this module

    idem_key = f"redeem_{item_key}_{idempotency_token}" if idempotency_token else None
    with engine.begin() as conn:
        item = conn.execute(
            text("SELECT item_key, cost, title FROM shop_catalog_items WHERE item_key = :key AND active = TRUE"),
            {"key": item_key},
        ).mappings().first()
        if not item:
            return "not_found", None
        item = dict(item)
        conn.execute(text("SELECT 1 FROM users WHERE id = :id FOR UPDATE"), {"id": user_id})
        if idem_key and conn.execute(
            text("SELECT 1 FROM credit_ledger WHERE user_id = :uid AND idempotency_key = :key"),
            {"uid": user_id, "key": idem_key},
        ).first():
            return "replay", item
        if not debit_in_tx(conn, user_id, item["cost"], reason=f"redeem_{item_key}", idempotency_key=idem_key):
            return "insufficient", item
        effect = ITEM_EFFECTS.get(item_key)
        if effect and "days" in effect:
            # Profile highlight: extends a running highlight, otherwise starts now.
            conn.execute(
                text(
                    """UPDATE users SET profile_highlighted_until =
                           GREATEST(COALESCE(profile_highlighted_until, now()), now()) + make_interval(days => :days)
                       WHERE id = :id"""
                ),
                {"days": effect["days"], "id": user_id},
            )
    return "redeemed", item

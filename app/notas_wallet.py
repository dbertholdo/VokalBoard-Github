"""
Fundação antifraude do sistema de Notas — P5 Etapa 1 (18/09/2026).

Funções reaproveitáveis para QUALQUER crédito/débito de Notas daqui em
diante (loja, urgência, assinatura, recompensas automáticas), seguindo
as regras fixas já registradas no plano ("Antifraude na loja e na
assinatura", P5):

  1. Saldo nunca fica negativo por corrida (race condition):
     `debit_notas_atomic()` trava a linha do usuário (`SELECT ... FOR
     UPDATE`) ANTES de somar o ledger e decidir — nunca lê o saldo
     numa consulta e debita numa segunda sem lock, senão duas compras
     simultâneas no mesmo saldo baixo poderiam ambas passar.
  2. Preço nunca vem do cliente: quem chama `debit_notas_atomic()`
     sempre passa um `amount` calculado no servidor (uma constante,
     uma config, uma tabela de preços) — isso é responsabilidade de
     quem chama, não deste módulo, mas o módulo nunca aceita um valor
     "total" ou "preço final" vindo direto de Form()/JS.
  3. Idempotência: `credit_notas()`/`debit_notas_atomic()` aceitam
     `idempotency_key` opcional — uma chamada repetida com a mesma
     chave (ex.: duplo clique, F5, retry de rede) nunca gera uma
     segunda linha no `credit_ledger`. Reforçado por um índice único
     parcial no banco (`idx_credit_ledger_user_idempotency`), não só
     por uma checagem em Python — evita duplicidade mesmo sob corrida
     entre duas chamadas concorrentes com a mesma chave.

Quem NÃO precisa passar por aqui: o resgate de itens do catálogo em
`app/routers/notas_routes.py` (`redeem_notas()`) já trava a linha do
usuário e faz um efeito colateral (estender `profile_highlighted_until`)
na MESMA transação do débito — deliberadamente deixado como está nesta
etapa (fora de escopo, sem teste automatizado prévio cobrindo esse
fluxo, risco desnecessário mexer agora). Fica como um bom próximo passo
reaproveitar este módulo lá também, quando o catálogo crescer.

Notas v2 (2026-09-26, docs/specs/NOTAS_V2.md) — every credit is a "lot"
with a category: PURCHASED (paid with money, never expires) or EARNED
(bonus/reward/grant, expires 18 months after it was credited). Debits are
allocated to lots — purchased first, then earned by soonest expiry — and
recorded in credit_lot_usage. The spendable balance ignores earned lots
past their expiry even before the expiry job has written them off. A
debit allowed to go negative (Stripe refund/chargeback) leaves a "debt"
that the next credit pays off first. All writes go through this module;
callers already inside a transaction use credit_in_tx()/debit_in_tx().
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import text

from app.database import engine, fetch_one
from app.notification_center import create_notification


def format_notas(value) -> str:
    """
    Formata um valor de Notas pra exibição: inteiro sem casas decimais
    ("3", "-3"), fracionado com vírgula e 2 casas ("0,50") — mesmo
    padrão de vírgula decimal já usado pro dinheiro em app/fees.py.
    """
    value = Decimal(value)
    if value == value.to_integral_value():
        return str(int(value))
    return f"{value:.2f}".replace(".", ",")


PURCHASED = "purchased"
EARNED = "earned"
EARNED_LIFETIME = "18 months"  # user-facing rule (Terms §2); keep in sync with /agb


# ---------------------------------------------------------------------------
# Internal helpers — always called with the user's row already locked.
# ---------------------------------------------------------------------------

def _lock_user(conn, user_id: int) -> bool:
    return conn.execute(text("SELECT id FROM users WHERE id = :id FOR UPDATE"), {"id": user_id}).first() is not None


def _lots(conn, user_id: int, include_expired: bool = False) -> list[dict]:
    """Credit lots with an unspent remainder, in spend order."""
    expiry_filter = "" if include_expired else "AND (l.expires_at IS NULL OR l.expires_at > now())"
    rows = conn.execute(
        text(
            f"""
            SELECT l.id, l.category, l.expires_at, l.delta - COALESCE(u.used, 0) AS remaining
            FROM credit_ledger l
            LEFT JOIN LATERAL (
                SELECT SUM(amount) AS used FROM credit_lot_usage WHERE lot_id = l.id
            ) u ON TRUE
            WHERE l.user_id = :uid AND l.delta > 0 AND l.delta - COALESCE(u.used, 0) > 0
              {expiry_filter}
            ORDER BY (l.category = 'earned'), l.expires_at NULLS FIRST, l.created_at, l.id
            """  # nosec B608 - expiry_filter is one of two fixed literals
        ),
        {"uid": user_id},
    ).mappings().all()
    return [dict(r) for r in rows]


def _debts(conn, user_id: int) -> list[dict]:
    """Debits not (fully) covered by any lot, oldest first."""
    rows = conn.execute(
        text(
            """
            SELECT d.id, -d.delta - COALESCE(u.used, 0) AS uncovered
            FROM credit_ledger d
            LEFT JOIN LATERAL (
                SELECT SUM(amount) AS used FROM credit_lot_usage WHERE debit_id = d.id
            ) u ON TRUE
            WHERE d.user_id = :uid AND d.delta < 0 AND -d.delta - COALESCE(u.used, 0) > 0
            ORDER BY d.id
            """
        ),
        {"uid": user_id},
    ).mappings().all()
    return [dict(r) for r in rows]


def _allocate(conn, debit_id: int, amount: Decimal, lots: list[dict]) -> Decimal:
    """Consumes `amount` from `lots` (mutated in place); returns what stayed uncovered."""
    need = Decimal(amount)
    for lot in lots:
        if need <= 0:
            break
        take = min(need, lot["remaining"])
        if take <= 0:
            continue
        conn.execute(
            text("INSERT INTO credit_lot_usage (debit_id, lot_id, amount) VALUES (:d, :l, :a)"),
            {"d": debit_id, "l": lot["id"], "a": take},
        )
        lot["remaining"] -= take
        need -= take
    return need


def _settle_debts(conn, user_id: int) -> None:
    debts = _debts(conn, user_id)
    if not debts:
        return
    lots = _lots(conn, user_id)
    for debt in debts:
        if _allocate(conn, debt["id"], debt["uncovered"], lots) > 0:
            break  # lots exhausted


def _balances(conn, user_id: int) -> dict:
    lots = _lots(conn, user_id)
    purchased = sum((l["remaining"] for l in lots if l["category"] == PURCHASED), Decimal("0"))
    earned = sum((l["remaining"] for l in lots if l["category"] == EARNED), Decimal("0"))
    debt = sum((d["uncovered"] for d in _debts(conn, user_id)), Decimal("0"))
    earned_lots = [l for l in lots if l["category"] == EARNED and l["expires_at"]]
    next_expiry = None
    if earned_lots:
        first_day = min(l["expires_at"] for l in earned_lots).date()
        amount = sum((l["remaining"] for l in earned_lots if l["expires_at"].date() == first_day), Decimal("0"))
        next_expiry = {"date": first_day, "amount": amount}
    return {
        "purchased": purchased, "earned": earned, "debt": debt,
        "total": purchased + earned - debt, "next_expiry": next_expiry,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_balances(user_id: int) -> dict:
    """{purchased, earned, debt, total, next_expiry: {date, amount} | None}."""
    with engine.connect() as conn:
        return _balances(conn, user_id)


def get_credit_balance(user_id: int) -> Decimal:
    """Spendable balance (earned lots past expiry excluded, debt subtracted)."""
    return get_balances(user_id)["total"]


def count_credits_since(user_id: int, reason: str, since) -> int:
    """Quantas linhas de crédito (delta > 0) com esse `reason` esse
    usuário recebeu desde `since` — usado por regras de teto/antifraude
    de recompensas automáticas (ex.: no máx. 3 vagas recompensadas por
    semana)."""
    row = fetch_one(
        """
        SELECT COUNT(*) AS n FROM credit_ledger
        WHERE user_id = :uid AND reason = :reason AND delta > 0 AND created_at >= :since
        """,
        {"uid": user_id, "reason": reason, "since": since},
    )
    return row["n"] if row else 0


def credit_in_tx(
    conn, user_id: int, amount, reason: str, category: str = EARNED,
    reference_id: int | None = None, idempotency_key: str | None = None,
    admin_note: str | None = None, expires_at: datetime | None = None,
) -> int | None:
    """Inserts a credit lot inside the caller's transaction and pays off any
    debt first. Returns the new ledger id, or None if `idempotency_key`
    was already used (nothing inserted). Earned lots expire after
    EARNED_LIFETIME unless an explicit `expires_at` is given."""
    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValueError("credit_in_tx: amount must be positive")
    if category not in (PURCHASED, EARNED):
        raise ValueError(f"credit_in_tx: unknown category {category!r}")
    _lock_user(conn, user_id)
    new_id = conn.execute(
        text(
            f"""
            INSERT INTO credit_ledger
                (user_id, delta, reason, reference_id, idempotency_key, admin_note, category, expires_at)
            VALUES (:uid, :delta, :reason, :ref_id, :key, :note, :category,
                    CASE WHEN :category = 'earned'
                         THEN COALESCE(CAST(:expires_at AS TIMESTAMPTZ), now() + interval '{EARNED_LIFETIME}')
                    END)
            ON CONFLICT (user_id, idempotency_key) WHERE idempotency_key IS NOT NULL DO NOTHING
            RETURNING id
            """  # nosec B608 - EARNED_LIFETIME is a module constant
        ),
        {
            "uid": user_id, "delta": amount, "reason": reason, "ref_id": reference_id,
            "key": idempotency_key, "note": admin_note, "category": category, "expires_at": expires_at,
        },
    ).scalar_one_or_none()
    if new_id is not None:
        _settle_debts(conn, user_id)
    return new_id


def credit_notas(
    user_id: int,
    amount: Decimal | str | int,
    reason: str,
    reference_id: int | None = None,
    idempotency_key: str | None = None,
    admin_note: str | None = None,
    category: str = EARNED,
) -> bool:
    """
    Credita Notas (delta positivo). Retorna True se creditou, False se
    `idempotency_key` já tinha sido usado antes pra esse usuário (nesse
    caso NADA é inserido de novo — não é um erro, é o comportamento
    esperado de idempotência).

    `admin_note` (opcional): justificativa em texto livre digitada por
    um Admin — usado só pela concessão avulsa
    (/financeiro/conceder, P6, 19/09/2026); None pra qualquer outro
    crédito automático do sistema.

    `category` (Notas v2): EARNED by default (rewards, referrals, grants);
    PURCHASED only for real money (Stripe).
    """
    with engine.begin() as conn:
        new_id = credit_in_tx(
            conn, user_id, amount, reason, category=category, reference_id=reference_id,
            idempotency_key=idempotency_key, admin_note=admin_note,
        )
    if new_id is not None:
        # Central de Notificações (task #50): one hook for every credit.
        create_notification(
            user_id, "notas_credited", "notification_notas_credited",
            {"amount": format_notas(Decimal(str(amount))), "reason": reason}, link_url="/notas",
        )
    return new_id is not None


def debit_in_tx(
    conn, user_id: int, amount, reason: str, reference_id: int | None = None,
    idempotency_key: str | None = None, admin_note: str | None = None,
    allow_negative: bool = False,
) -> bool:
    """Debits inside the caller's transaction, allocating purchased lots
    first, then earned ones by soonest expiry. Returns False (nothing
    written) if the spendable balance is too low — unless
    `allow_negative` (Stripe refunds/chargebacks), which records the
    shortfall as a debt. Idempotent: a reused key returns True."""
    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValueError("debit_in_tx: amount must be positive")
    if not _lock_user(conn, user_id):
        return False
    if idempotency_key:
        already = conn.execute(
            text("SELECT id FROM credit_ledger WHERE user_id = :uid AND idempotency_key = :key"),
            {"uid": user_id, "key": idempotency_key},
        ).first()
        if already:
            return True
    _expire_user_lots(conn, user_id)
    if not allow_negative and _balances(conn, user_id)["total"] < amount:
        return False
    debit_id = conn.execute(
        text(
            """
            INSERT INTO credit_ledger (user_id, delta, reason, reference_id, idempotency_key, admin_note)
            VALUES (:uid, :delta, :reason, :ref_id, :key, :note)
            RETURNING id
            """
        ),
        {
            "uid": user_id, "delta": -amount, "reason": reason, "ref_id": reference_id,
            "key": idempotency_key, "note": admin_note,
        },
    ).scalar_one()
    _allocate(conn, debit_id, amount, _lots(conn, user_id))
    return True


def debit_notas_atomic(
    user_id: int,
    amount: Decimal | str | int,
    reason: str,
    reference_id: int | None = None,
    idempotency_key: str | None = None,
    admin_note: str | None = None,
) -> bool:
    """
    Debita Notas SÓ SE o saldo gastável alcançar `amount` — tudo dentro
    da mesma transação que trava a linha do usuário. Retorna False sem
    debitar nada se o saldo for insuficiente; idempotente por
    `idempotency_key`. Notas v2: see debit_in_tx() for the spend order.
    """
    with engine.begin() as conn:
        return debit_in_tx(
            conn, user_id, amount, reason, reference_id=reference_id,
            idempotency_key=idempotency_key, admin_note=admin_note,
        )


# ---------------------------------------------------------------------------
# Expiry of earned lots
# ---------------------------------------------------------------------------

def _expire_user_lots(conn, user_id: int) -> int:
    """Writes off the unspent remainder of this user's expired earned lots
    (one 'earned_expired' debit per lot). User row must be locked."""
    expired = conn.execute(
        text(
            """
            SELECT l.id, l.delta - COALESCE((SELECT SUM(amount) FROM credit_lot_usage WHERE lot_id = l.id), 0) AS remaining
            FROM credit_ledger l
            WHERE l.user_id = :uid AND l.category = 'earned' AND l.expires_at <= now()
            """
        ),
        {"uid": user_id},
    ).mappings().all()
    count = 0
    for lot in expired:
        if lot["remaining"] <= 0:
            continue
        debit_id = conn.execute(
            text(
                """
                INSERT INTO credit_ledger (user_id, delta, reason, reference_id, idempotency_key)
                VALUES (:uid, :delta, 'earned_expired', :lot, :key)
                ON CONFLICT (user_id, idempotency_key) WHERE idempotency_key IS NOT NULL DO NOTHING
                RETURNING id
                """
            ),
            {"uid": user_id, "delta": -lot["remaining"], "lot": lot["id"], "key": f"earned_expired:{lot['id']}"},
        ).scalar_one_or_none()
        if debit_id is not None:
            _allocate(conn, debit_id, lot["remaining"], [{"id": lot["id"], "remaining": lot["remaining"]}])
            count += 1
    return count


def expire_due_lots(conn) -> int:
    """For the hourly worker: writes off every expired earned remainder,
    one user at a time (each user's row locked). Returns lots expired."""
    user_ids = conn.execute(
        text(
            """
            SELECT DISTINCT l.user_id FROM credit_ledger l
            WHERE l.category = 'earned' AND l.expires_at <= now()
              AND l.delta > COALESCE((SELECT SUM(amount) FROM credit_lot_usage WHERE lot_id = l.id), 0)
            """
        )
    ).scalars().all()
    total = 0
    for user_id in user_ids:
        if _lock_user(conn, user_id):
            total += _expire_user_lots(conn, user_id)
    return total


# ---------------------------------------------------------------------------
# Refunds of a debit (admin "Reembolsar" / estornos)
# ---------------------------------------------------------------------------

def refund_ledger_entry(ledger_id: int, admin_id: int | None) -> tuple[bool, int | None]:
    """Reembolsa UMA linha de débito específica do credit_ledger,
    creditando o mesmo valor de volta pro mesmo usuário. Dois pontos de
    entrada — /admin/users/{id} (nível Admin) e /financeiro/estornos
    (God Mode) — e a regra (só débito, só idempotente, nunca um valor
    vindo do formulário) vive só aqui.

    Notas v2: the amount goes back to the categories it came from —
    purchased stays purchased; earned comes back with its original expiry,
    or a fresh 18 months if that lot has expired meanwhile (goodwill).
    Anything the debit never covered (debt) comes back as earned.

    Retorna (sucesso, user_id) — user_id é None se a linha não existir
    ou não for um débito (não reembolsável); nesse caso nada é
    creditado.
    """
    entry = fetch_one("SELECT id, user_id, delta FROM credit_ledger WHERE id = :id", {"id": ledger_id})
    if not entry or entry["delta"] >= 0:
        return False, None
    user_id = entry["user_id"]
    total = -entry["delta"]
    main_key = f"admin_refund_{ledger_id}"
    with engine.begin() as conn:
        _lock_user(conn, user_id)
        if conn.execute(
            text("SELECT 1 FROM credit_ledger WHERE user_id = :uid AND idempotency_key = :key"),
            {"uid": user_id, "key": main_key},
        ).first():
            return False, user_id
        usage = conn.execute(
            text(
                """
                SELECT l.category, l.expires_at, (l.expires_at > now()) AS still_valid, u.amount
                FROM credit_lot_usage u JOIN credit_ledger l ON l.id = u.lot_id
                WHERE u.debit_id = :id
                """
            ),
            {"id": ledger_id},
        ).mappings().all()
        purchased = sum((u["amount"] for u in usage if u["category"] == PURCHASED), Decimal("0"))
        earned = total - purchased  # earned lots + any uncovered debt
        valid_expiries = [u["expires_at"] for u in usage if u["category"] == EARNED and u["still_valid"]]
        keep_expiry = max(valid_expiries) if valid_expiries else None
        parts = [p for p in ((PURCHASED, purchased, None), (EARNED, earned, keep_expiry)) if p[1] > 0]
        for index, (category, amount, expires_at) in enumerate(parts):
            credit_in_tx(
                conn, user_id, amount, "admin_refund", category=category, reference_id=ledger_id,
                idempotency_key=main_key if index == 0 else f"{main_key}:{category}",
                expires_at=expires_at,
            )
    create_notification(
        user_id, "notas_credited", "notification_notas_credited",
        {"amount": format_notas(total), "reason": "admin_refund"}, link_url="/notas",
    )
    return True, user_id

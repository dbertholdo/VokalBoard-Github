"""Shared accounting rules for the stateless and Match Rechnung flows.

This module deliberately receives only identifiers, dates and invoice numbers.
The sensitive form payload stays in memory (avulso) or in the encrypted Match
draft, never in these accounting records.
"""
import re
from datetime import date

from sqlalchemy import text

from app.database import engine, fetch_one
from app.feature_usage import record_feature_usage

FREE_INVOICES_PER_MONTH = 5
_INVOICE_NUMBER_RE = re.compile(r"^(?P<year>\d{4})-(?P<sequence>\d{4,})$")

# Etapa 3 do P4 (18/09/2026): selo pessoal e PRIVADO (só o próprio dono
# vê, nunca o perfil público nem o Admin agindo por outra pessoa) —
# bronze/prata/ouro/platina em 1/10/50/100 Rechnungen emitidas NA VIDA
# (Avulso + Match somados — o Daniel disse "tanto faz" se junta ou
# separa, e os dois fluxos já passam por consume_invoice_generation()
# abaixo, então somar é o caminho natural, sem duplicar contabilidade
# numa tabela nova). Ao contrário do selo "estilo Uber" do P3.F
# (app/match_evaluations.py), este é um MARCO — só sobe, nunca desce,
# igual aos badges de app/badges.py; fica fora daquele módulo só porque
# é privado, não público. Do mais alto pro mais baixo, primeiro que
# bater vale.
INVOICE_COUNT_MILESTONES = [(100, "platinum"), (50, "gold"), (10, "silver"), (1, "bronze")]


class InvoiceCreditUnavailable(ValueError):
    """Raised when the monthly allowance and purchased credit balance are zero."""


def suggested_invoice_number(user_id: int, invoice_year: int) -> str:
    row = fetch_one(
        """
        SELECT last_number FROM invoice_number_sequences
        WHERE user_id = :user_id AND invoice_year = :invoice_year
        """,
        {"user_id": user_id, "invoice_year": invoice_year},
    )
    next_number = (row["last_number"] if row else 0) + 1
    return f"{invoice_year}-{next_number:04d}"


def record_invoice_number(user_id: int, invoice_number: str) -> None:
    """Advance the per-user sequence when a valid edited number is confirmed.

    A user may use a different format, but it must not lower their automatic
    next suggestion. Only the standard YYYY-NNNN form participates in that
    automatic sequence.
    """
    match = _INVOICE_NUMBER_RE.fullmatch(invoice_number.strip())
    if not match:
        return
    invoice_year = int(match.group("year"))
    sequence = int(match.group("sequence"))
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO invoice_number_sequences (user_id, invoice_year, last_number)
                VALUES (:user_id, :invoice_year, :sequence)
                ON CONFLICT (user_id, invoice_year) DO UPDATE
                SET last_number = GREATEST(invoice_number_sequences.last_number, EXCLUDED.last_number)
                """
            ),
            {"user_id": user_id, "invoice_year": invoice_year, "sequence": sequence},
        )


def consume_invoice_generation(user_id: int, generated_on: date) -> str:
    """Atomically consume a free monthly generation or one purchased credit.

    The account row lock serializes simultaneous confirmations by the same
    person. The caller must invoke this only after the PDF delivery succeeds,
    so a mail provider outage does not consume an invoice generation.
    """
    usage_month = generated_on.replace(day=1)
    with engine.begin() as conn:
        account = conn.execute(
            text("SELECT id FROM users WHERE id = :user_id FOR UPDATE"),
            {"user_id": user_id},
        ).mappings().first()
        if not account:
            raise ValueError("Invoice owner does not exist")

        free = conn.execute(
            text(
                """
                INSERT INTO invoice_monthly_usage (user_id, usage_month, free_used)
                VALUES (:user_id, :usage_month, 1)
                ON CONFLICT (user_id, usage_month) DO UPDATE
                SET free_used = invoice_monthly_usage.free_used + 1
                WHERE invoice_monthly_usage.free_used < :free_limit
                RETURNING free_used
                """
            ),
            {"user_id": user_id, "usage_month": usage_month, "free_limit": FREE_INVOICES_PER_MONTH},
        ).scalar_one_or_none()
        if free is not None:
            result = "free"
        else:
            purchased_balance = conn.execute(
                text("SELECT COALESCE(SUM(delta), 0) FROM purchased_invoice_credits WHERE user_id = :user_id"),
                {"user_id": user_id},
            ).scalar_one()
            if purchased_balance <= 0:
                raise InvoiceCreditUnavailable("No free or purchased invoice generation is available")

            conn.execute(
                text(
                    """
                    INSERT INTO purchased_invoice_credits (user_id, delta, reason)
                    VALUES (:user_id, -1, 'invoice_generation')
                    """
                ),
                {"user_id": user_id},
            )
            result = "purchased"

    # Etapa 3 do P4: conta como 1 uso do Rechnungmaker pro contador de
    # "ferramentas mais usadas" do Admin — só depois que a transação
    # acima já commitou (uma Rechnung de verdade foi consumida), numa
    # transação própria e curta (mesmo padrão de record_invoice_number()
    # em app/invoice_match_drafts.py).
    record_feature_usage("rechnungmaker", generated_on)
    return result


def get_lifetime_invoice_count(user_id: int) -> int:
    """Quantas Rechnungen esta conta já emitiu de verdade na vida —
    Avulso + Match somados (os dois passam por consume_invoice_generation
    acima). Cada linha contada aqui já é uma Rechnung entregue, nunca um
    rascunho/tentativa."""
    free_total = fetch_one(
        "SELECT COALESCE(SUM(free_used), 0) AS n FROM invoice_monthly_usage WHERE user_id = :user_id",
        {"user_id": user_id},
    )["n"]
    purchased_total = fetch_one(
        """
        SELECT COUNT(*) AS n FROM purchased_invoice_credits
        WHERE user_id = :user_id AND delta = -1 AND reason = 'invoice_generation'
        """,
        {"user_id": user_id},
    )["n"]
    return int(free_total) + int(purchased_total)


def get_personal_invoice_badge(user_id: int) -> dict:
    """Selo pessoal e privado (ver INVOICE_COUNT_MILESTONES acima) —
    {"count": int, "tier": "bronze"|"silver"|"gold"|"platinum"|None}."""
    count = get_lifetime_invoice_count(user_id)
    tier = None
    for threshold, name in INVOICE_COUNT_MILESTONES:
        if count >= threshold:
            tier = name
            break
    return {"count": count, "tier": tier}

"""Shared accounting rules for the stateless and Match Rechnung flows.

This module deliberately receives only identifiers, dates and invoice numbers.
The sensitive form payload stays in memory (avulso) or in the encrypted Match
draft, never in these accounting records.
"""
import re
from datetime import date

from sqlalchemy import text

from app.database import engine, fetch_one

FREE_INVOICES_PER_MONTH = 5
_INVOICE_NUMBER_RE = re.compile(r"^(?P<year>\d{4})-(?P<sequence>\d{4,})$")


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
            return "free"

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
        return "purchased"

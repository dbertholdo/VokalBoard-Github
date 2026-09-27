"""
Automatic permanent erasure of deactivated accounts (Daniel, 2026-09-26).

A user who deletes their account can reactivate it — Notas included —
for 6 months. After that, nothing about them is kept ("no storage"):
the user row and everything that cascades from it, their Matches (and
through them evaluations and Match invoice drafts), and their avatar
file on disk. Legally required payment records live in Stripe and the
accountant's system, never here (docs/specs/NOTAS_V2.md, D7).

Runs inside the hourly retention worker (app/retention_worker.py), so it
needs no separate service. `scripts/purge_deleted_accounts.py` is a thin
manual wrapper around the same function (e.g. for --dry-run).

Logs and return values carry counts only — never names or e-mails.
"""
import logging

from sqlalchemy import text

from app.avatars import remove_existing_avatar

log = logging.getLogger(__name__)

REACTIVATION_WINDOW = "6 months"  # user-facing promise; keep in sync with the deletion notice

# job_matches / Match invoice tables reference users with ON DELETE RESTRICT on
# purpose (an accepted job must not vanish by accident during normal use).
# Erasure is deliberate, so those rows go first; evaluations, drafts and
# ephemeral invoices tied to the match cascade from job_matches.
_PRE_DELETE = (
    "DELETE FROM invoice_match_drafts WHERE :uid IN (contractor_user_id, issuer_user_id, requested_by_user_id)",
    "DELETE FROM ephemeral_match_invoices WHERE created_by_user_id = :uid",
    "DELETE FROM job_matches WHERE :uid IN (artist_user_id, contractor_user_id)",
)


def erase_account(conn, user_id: int) -> None:
    """Hard-deletes one account (and its Matches/Match invoices first — they
    block the delete on purpose). Shared by the 6-month purge and the admin's
    "Delete forever"."""
    for statement in _PRE_DELETE:
        conn.execute(text(statement), {"uid": user_id})
    conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})


def expired_account_ids(conn) -> list[int]:
    rows = conn.execute(
        text(f"SELECT id FROM users WHERE deleted_at IS NOT NULL "
             f"AND deleted_at + interval '{REACTIVATION_WINDOW}' <= now() ORDER BY id")  # nosec B608 - module constant
    )
    return [r[0] for r in rows]


def purge_expired_accounts(conn, dry_run: bool = False) -> dict:
    """Erases every account past the reactivation window. Each account runs
    in its own savepoint, so one failure never blocks the others."""
    ids = expired_account_ids(conn)
    if dry_run:
        return {"accounts_due": len(ids)}
    purged, failed = 0, 0
    for user_id in ids:
        try:
            with conn.begin_nested():
                erase_account(conn, user_id)
            remove_existing_avatar(user_id)
            purged += 1
        except Exception:
            failed += 1
            log.exception("Account purge failed for user id %s; will retry next run", user_id)
    return {"accounts_purged": purged, "accounts_failed": failed}

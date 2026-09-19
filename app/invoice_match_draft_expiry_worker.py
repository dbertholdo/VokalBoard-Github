"""Hourly job: closes Match-Rechnungen rascunhos (invoice_match_drafts)
that went unconfirmed past their expires_at (7 days from creation — see
app/invoice_deadlines.py:match_draft_expiry).

Decisão registrada (Daniel, 18/09/2026, Etapa 2 do P4):
- Apagar o rascunho direto, mesmo padrão Zero-Storage do resto do
  sistema (confirm_and_send/cancel_draft também apagam a linha, nunca
  deixam em status 'expired' primeiro).
- Avisar as DUAS partes por e-mail que o rascunho expirou, convidando a
  pedir de novo se ainda for necessário.

Same shape as app/invitation_expiry_worker.py e
app/match_evaluation_reminder_worker.py on purpose — one advisory lock
per job (id 8303, diferente dos outros pra nunca brigarem),
--once/--dry-run pra rodadas manuais, loop+sleep pra worker parado.
Tudo roda na MESMA conexão/transação (igual o reminder worker) pra
"mandar e-mail" e "apagar o rascunho" nunca dessincronizarem entre si.
"""
import argparse
import logging
import time

from sqlalchemy import text

from app.database import engine
from app.email import send_email
from app.email_localization import match_invoice_expired_email

log = logging.getLogger(__name__)


def _expired_rows(conn):
    return conn.execute(
        text(
            """
            SELECT d.id AS draft_id, d.match_id,
                   COALESCE(m.listing_snapshot->>'title', l.title) AS production_title,
                   issuer.id AS issuer_id, issuer.full_name AS issuer_name,
                   issuer.email AS issuer_email, issuer.preferred_language AS issuer_lang,
                   contractor.id AS contractor_id, contractor.full_name AS contractor_name,
                   contractor.email AS contractor_email, contractor.preferred_language AS contractor_lang
            FROM invoice_match_drafts d
            JOIN job_matches m ON m.id = d.match_id
            LEFT JOIN listings l ON l.id = m.listing_id
            JOIN users issuer ON issuer.id = d.issuer_user_id AND issuer.deleted_at IS NULL
            JOIN users contractor ON contractor.id = d.contractor_user_id AND contractor.deleted_at IS NULL
            WHERE d.status IN ('awaiting_issuer', 'awaiting_contractor')
              AND d.expires_at <= now()
            """
        )
    ).mappings().all()


def run_invoice_draft_expiry(connection=None, dry_run=False, base_url=""):
    if connection is None:
        with engine.begin() as conn:
            return run_invoice_draft_expiry(conn, dry_run, base_url)
    conn = connection
    if not conn.execute(text("SELECT pg_try_advisory_xact_lock(8303,1)")).scalar():
        return {"skipped": True}

    rows = _expired_rows(conn)
    if dry_run:
        return {"expired": len(rows)}

    url = f"{base_url}rechnungmaker?tab=match"
    for row in rows:
        title = row["production_title"] or ""
        for lang, name, email in (
            (row["issuer_lang"], row["issuer_name"], row["issuer_email"]),
            (row["contractor_lang"], row["contractor_name"], row["contractor_email"]),
        ):
            subject, html = match_invoice_expired_email(lang, name, title, url)
            send_email(email, subject, html)
        conn.execute(text("DELETE FROM invoice_match_drafts WHERE id = :id"), {"id": row["draft_id"]})
    return {"expired": len(rows)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--base-url", default="https://vokalboard.example/")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            log.info("Invoice draft expiry counts: %s", run_invoice_draft_expiry(dry_run=args.dry_run, base_url=args.base_url))
        except Exception:
            log.exception("Invoice draft expiry job failed; transaction rolled back")
            if args.once or args.dry_run:
                raise
        if args.once or args.dry_run:
            break
        time.sleep(3600)

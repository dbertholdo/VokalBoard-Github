"""Hourly job: manda um lembrete extra pros perfis compatíveis quando
uma vaga URGENTE completa 6h sem Match — P5 Etapa 2 (18/09/2026).

Decisão confirmada com o Daniel: reforça a urgência sem spammar quem
já recebeu o alerta original de "nova vaga compatível" na hora da
publicação — o lembrete só sai UMA VEZ por vaga (urgent_reminder_sent_at
garante isso) e só se ainda não tiver Match nenhum.

Mesmo formato de app/invoice_match_draft_expiry_worker.py e demais
workers do site: um lock consultivo próprio (id 8304, nunca colide com
os outros: 8301 convites, 8302 lembrete de avaliação, 8303 expiração
de rascunho de Rechnung), --once/--dry-run pra rodadas manuais,
loop+sleep pra worker parado.
"""
import argparse
import logging
import time

from sqlalchemy import text

from app.database import engine
from app.notifications import notify_urgent_listing_reminder

log = logging.getLogger(__name__)


def _due_rows(conn):
    return conn.execute(
        text(
            """
            SELECT l.id, l.listing_type, l.title, l.city, l.author_id, l.voice_type_id
            FROM listings l
            WHERE l.is_urgent = TRUE
              AND l.is_active = TRUE
              AND l.urgent_marked_at <= now() - interval '6 hours'
              AND l.urgent_reminder_sent_at IS NULL
              AND NOT EXISTS (SELECT 1 FROM job_matches m WHERE m.listing_id = l.id)
            """
        )
    ).mappings().all()


def run_urgent_listing_reminder(connection=None, dry_run=False, base_url=""):
    if connection is None:
        with engine.begin() as conn:
            return run_urgent_listing_reminder(conn, dry_run, base_url)
    conn = connection
    if not conn.execute(text("SELECT pg_try_advisory_xact_lock(8304,1)")).scalar():
        return {"skipped": True}

    rows = _due_rows(conn)
    if dry_run:
        return {"reminded": len(rows)}

    for row in rows:
        notify_urgent_listing_reminder(
            base_url, row["id"], row["listing_type"], row["title"],
            row["city"], row["author_id"], row["voice_type_id"],
        )
        conn.execute(
            text("UPDATE listings SET urgent_reminder_sent_at = now() WHERE id = :id"),
            {"id": row["id"]},
        )
    return {"reminded": len(rows)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--base-url", default="https://vokalboard.example/")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            log.info("Urgent listing reminder counts: %s", run_urgent_listing_reminder(dry_run=args.dry_run, base_url=args.base_url))
        except Exception:
            log.exception("Urgent listing reminder job failed; transaction rolled back")
            if args.once or args.dry_run:
                raise
        if args.once or args.dry_run:
            break
        time.sleep(3600)

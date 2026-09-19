"""Hourly job: sends the "avalie o match" reminder e-mail once per side
of a Match, once the evaluation window has opened (event_date already
passed — see app/match_evaluations.py) and that side hasn't sent their
evaluation yet. Marks job_matches.artist_eval_reminder_sent_at /
contractor_eval_reminder_sent_at so it's never sent twice.

Same shape as app/invitation_expiry_worker.py and app/retention_worker.py
on purpose — one advisory lock per job (a different lock id), --once/
--dry-run for manual runs, loop+sleep for a standing worker. Everything
runs through the SAME transaction/connection (unlike some other workers)
so the "mark as sent" update can't race with a re-run of this job.

Never mentions any evaluation ALREADY received — the reminder is only
ever "please rate {name}", nothing about what score exists (evaluations
are secret, see app/match_evaluations.py).
"""
import argparse
import logging
import time
from sqlalchemy import text
from app.database import engine
from app.email import send_email
from app.email_localization import match_evaluation_reminder_email
from app.match_evaluations import EVALUATION_WINDOW_DAYS

log = logging.getLogger(__name__)


def _pending_side_rows(conn, side: str):
    """side is 'artist' or 'contractor' — matches where THAT side hasn't
    evaluated the other yet, the window is still open, and the reminder
    for that side hasn't been sent."""
    other = "contractor" if side == "artist" else "artist"
    return conn.execute(
        text(
            f"""
            SELECT m.id AS match_id, m.{side}_user_id AS recipient_id,
                   recipient.full_name AS recipient_name, recipient.email AS recipient_email,
                   recipient.preferred_language, other_u.full_name AS counterpart_name
            FROM job_matches m
            JOIN listings l ON l.id = m.listing_id
            JOIN users recipient ON recipient.id = m.{side}_user_id AND recipient.deleted_at IS NULL
            JOIN users other_u ON other_u.id = m.{other}_user_id
            WHERE m.status != 'cancelled'
              AND m.{side}_eval_reminder_sent_at IS NULL
              AND l.event_date IS NOT NULL
              AND l.event_date <= CURRENT_DATE
              AND l.event_date >= CURRENT_DATE - INTERVAL '{EVALUATION_WINDOW_DAYS} days'
              AND NOT EXISTS (
                  SELECT 1 FROM match_evaluations me
                  WHERE me.match_id = m.id AND me.rater_id = m.{side}_user_id
              )
            """  # nosec B608 - side/other are hardcoded to 'artist'/'contractor', never user input.
        )
    ).mappings().all()


def run_evaluation_reminders(connection=None, dry_run=False, base_url=""):
    if connection is None:
        with engine.begin() as conn:
            return run_evaluation_reminders(conn, dry_run, base_url)
    conn = connection
    if not conn.execute(text("SELECT pg_try_advisory_xact_lock(8302,1)")).scalar():
        return {"skipped": True}

    sent = 0
    for side in ("artist", "contractor"):
        for row in _pending_side_rows(conn, side):
            sent += 1
            if dry_run:
                continue
            first_name = (row["counterpart_name"] or "").split(" ")[0] or row["counterpart_name"]
            subject, html = match_evaluation_reminder_email(
                row["preferred_language"], row["recipient_name"], first_name,
                f"{base_url}profile/matches",
            )
            send_email(row["recipient_email"], subject, html)
            conn.execute(
                text(f"UPDATE job_matches SET {side}_eval_reminder_sent_at = now() WHERE id = :id"),  # nosec B608 - side is hardcoded.
                {"id": row["match_id"]},
            )
    return {"reminders_sent": sent}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--base-url", default="https://vokalboard.example/")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            log.info("Evaluation reminder counts: %s", run_evaluation_reminders(dry_run=args.dry_run, base_url=args.base_url))
        except Exception:
            log.exception("Evaluation reminder job failed; transaction rolled back")
            if args.once or args.dry_run:
                raise
        if args.once or args.dry_run:
            break
        time.sleep(3600)

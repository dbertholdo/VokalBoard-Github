"""Hourly job: sends any active periodic mail (app/periodic_mails.py)
whose next_send_at has arrived, to the admin team (role_level >= 2,
email_verified, not deleted), then reschedules it forward by its own
frequency (daily/weekly/monthly) — P0 backlog item, built 19/09/2026
at Daniel's request ("build other periodic mails... see the active
ones, edit, delete or pause them").

Same shape as every other worker in this app — one advisory lock
(id 8305; 8301-8304 already taken, see
app/urgent_listing_reminder_worker.py's docstring), --once/--dry-run
for manual runs, loop+sleep for a standing worker. Not registered in
docker-compose.yml, matching every worker here except retention (see
the "Não registrado em docker-compose.yml" note in AI_CHANGELOG.md,
2026-09-18, match_evaluation_reminder_worker entry) — same open item,
not re-solved here.

Sends run inside the same locked transaction as the reschedule
(same pattern as app/urgent_listing_reminder_worker.py) — each
send_email() call is synchronous (one HTTP request per recipient, no
batching), which is fine at admin-team volume but would need
revisiting before this scope ever grows to "all users".
"""
import argparse
import logging
import time

from sqlalchemy import text

from app.database import engine
from app.email import send_email

log = logging.getLogger(__name__)

# Interval per frequency, passed as a bound parameter (never pasted into SQL).
_FREQUENCY_STEP = {"daily": "1 day", "weekly": "7 days", "monthly": "1 month"}

_FREQUENCY_INTERVAL_SQL = {
    "daily": "interval '1 day'",
    "weekly": "interval '7 days'",
    "monthly": "interval '1 month'",
}


def _due_mails(conn):
    return conn.execute(
        text(
            """
            SELECT id, name, subject, body_html, frequency
            FROM periodic_mails
            WHERE is_active = TRUE AND next_send_at <= now()
            FOR UPDATE
            """
        )
    ).mappings().all()


def _admin_recipients(conn):
    return conn.execute(
        text(
            "SELECT email FROM users WHERE role_level >= 2 AND email_verified = TRUE AND deleted_at IS NULL"
        )
    ).mappings().all()


def run_periodic_mails(connection=None, dry_run=False):
    if connection is None:
        with engine.begin() as conn:
            return run_periodic_mails(conn, dry_run)
    conn = connection
    if not conn.execute(text("SELECT pg_try_advisory_xact_lock(8305,1)")).scalar():
        return {"skipped": True}

    due = _due_mails(conn)
    if dry_run:
        return {"due": len(due)}

    recipients = _admin_recipients(conn) if due else []
    emails_sent = 0
    for mail in due:
        for recipient in recipients:
            send_email(recipient["email"], mail["subject"], mail["body_html"])
            emails_sent += 1
        conn.execute(
            text(
                """
                UPDATE periodic_mails
                SET last_sent_at = now(), next_send_at = now() + CAST(:step AS interval)
                WHERE id = :id
                """
            ),
            {"id": mail["id"], "step": _FREQUENCY_STEP[mail["frequency"]]},
        )
    return {"mails_sent": len(due), "emails_sent": emails_sent}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            log.info("Periodic mail counts: %s", run_periodic_mails(dry_run=args.dry_run))
        except Exception:
            log.exception("Periodic mail job failed; transaction rolled back")
            if args.once or args.dry_run:
                raise
        if args.once or args.dry_run:
            break
        time.sleep(3600)

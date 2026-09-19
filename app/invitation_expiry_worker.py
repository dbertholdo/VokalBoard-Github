"""Hourly job: closes job_invitations (convites/candidaturas) that
went unanswered past their expires_at (48h, or 6h before the event —
see app/match_service.py:create_invitation / invitation_expiry).

Same shape as app/retention_worker.py on purpose — one advisory lock
per job (a different lock id, so the two never block each other),
--once/--dry-run for manual runs, loop+sleep for a standing worker.

Deliberately does nothing to listing_vacancies.filled_slots — an
expired invitation was never accepted, so no slot was ever claimed.
"""
import argparse
import logging
import time
from sqlalchemy import text
from app.database import engine

log = logging.getLogger(__name__)


def run_invitation_expiry(connection=None, dry_run=False):
    if connection is None:
        with engine.begin() as conn:
            return run_invitation_expiry(conn, dry_run)
    conn = connection
    if not conn.execute(text('SELECT pg_try_advisory_xact_lock(8301,1)')).scalar():
        return {'skipped': True}

    count = conn.execute(
        text("SELECT count(*) FROM job_invitations WHERE status = 'pending' AND expires_at <= now()")
    ).scalar()
    if dry_run:
        return {'expired': count}

    conn.execute(
        text("UPDATE job_invitations SET status = 'expired', responded_at = now() WHERE status = 'pending' AND expires_at <= now()")
    )
    return {'expired': count}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            log.info('Invitation expiry counts: %s', run_invitation_expiry(dry_run=args.dry_run))
        except Exception:
            log.exception('Invitation expiry failed; transaction rolled back')
            if args.once or args.dry_run:
                raise
        if args.once or args.dry_run:
            break
        time.sleep(3600)

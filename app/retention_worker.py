"""Hourly lifecycle job. Views enforce visibility immediately, even between runs.

Use --once for an explicit single run or --dry-run to inspect counts without writes.
No body, attachment, title or contact data is copied into lifecycle audit logs.
"""
import argparse
import logging
import time
from sqlalchemy import text
from app.account_purge import purge_expired_accounts
from app.database import engine

log = logging.getLogger(__name__)


def run_retention(connection=None, dry_run=False):
    if connection is None:
        with engine.begin() as conn:
            return run_retention(conn, dry_run)
    conn = connection
    if not conn.execute(text('SELECT pg_try_advisory_xact_lock(8202,1)')).scalar():
        return {'skipped': True}
    counts = {}
    predicates = {
        'listings': "COALESCE(available_until,event_date)+30 <= CURRENT_DATE",
        'messages': "activity_at + interval '30 days' <= now()",
    }
    archive_dates = {
        'listings': '(COALESCE(available_until,event_date)+30)::timestamptz',
        'messages': "activity_at + interval '30 days'",
    }
    for table, predicate in predicates.items():
        counts[table+'_archive'] = conn.execute(text(f'SELECT count(*) FROM {table} WHERE archived_at IS NULL AND {predicate}')).scalar()
        counts[table+'_purge'] = conn.execute(text(f"SELECT count(*) FROM {table} WHERE COALESCE(archived_at,{archive_dates[table]})+interval '60 days' <= now()")).scalar()
    # Central de Notificações (19/09/2026, task #50) — Daniel: "mesmo
    # espírito do Zero-Storage": READ notifications older than 30 days
    # get purged; UNREAD ones are never touched no matter how old, so
    # this is a direct DELETE, not the archive-then-purge two-step the
    # tables above use (there's no "final snapshot" worth keeping for
    # a notification once it's been read and aged out).
    counts['notifications_purge'] = conn.execute(
        text("SELECT count(*) FROM notifications WHERE read_at IS NOT NULL AND read_at + interval '30 days' <= now()")
    ).scalar()
    # Accounts past the 6-month reactivation window are erased automatically
    # (Daniel, 2026-09-26) — see app/account_purge.py.
    counts.update(purge_expired_accounts(conn, dry_run=dry_run))
    if dry_run:
        return counts
    # Capture final job details before removal; the Match itself and participants remain.
    conn.execute(text('''UPDATE job_matches m SET listing_snapshot=jsonb_build_object(
        'title',l.title,'event_date',l.event_date,'fee',l.fee)
        FROM listings l WHERE l.id=m.listing_id AND (
        (l.archived_at IS NULL AND COALESCE(l.available_until,l.event_date)+30 <= CURRENT_DATE)
        OR l.archived_at+interval '60 days' <= now())'''))
    conn.execute(text('''UPDATE listings SET archived_at=(COALESCE(available_until,event_date)+30)::timestamptz,
        is_active=FALSE WHERE archived_at IS NULL AND COALESCE(available_until,event_date)+30<=CURRENT_DATE'''))
    conn.execute(text("UPDATE messages SET archived_at=activity_at+interval '30 days' WHERE archived_at IS NULL AND activity_at+interval '30 days'<=now()"))
    # Delete messages first to avoid changing their conversation association unnecessarily.
    for table in ('messages', 'listings'):
        conn.execute(text(f"DELETE FROM {table} WHERE archived_at+interval '60 days'<=now()"))
    conn.execute(text("DELETE FROM notifications WHERE read_at IS NOT NULL AND read_at + interval '30 days' <= now()"))
    return counts


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            log.info('Retention counts: %s', run_retention(dry_run=args.dry_run))
        except Exception:
            log.exception('Retention failed; transaction rolled back')
            if args.once or args.dry_run:
                raise
        if args.once or args.dry_run:
            break
        time.sleep(3600)

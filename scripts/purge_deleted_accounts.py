"""
PERMANENTLY deletes accounts that were removed (soft delete,
`users.deleted_at` set) more than 6 months ago.

Why a separate script, and not a job inside the app?
---------------------------------------------------------
The rest of the project deliberately avoids any job/cron running
*inside* the app itself (see EVENT_STATUS_SQL and the archiving of
past events in app/routers/listings_routes.py, which prefer to
compute everything "at query time" instead of a background worker).
A permanent data deletion is too sensitive an operation to leave
tied to a long-running process inside FastAPI — it's simpler, safer
and easier to audit to run this as a standalone script, triggered
from outside (the OS's cron, or manually).

How to schedule it (example with Linux cron, once a day at 4am):
    0 4 * * * cd /path/to/project && ./venv/bin/python scripts/purge_deleted_accounts.py >> /var/log/maestro_purge.log 2>&1

Manual usage:
    python scripts/purge_deleted_accounts.py           # actually deletes
    python scripts/purge_deleted_accounts.py --dry-run # only shows who would be deleted
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

# Ensures "app" (the project's package) is found even when running
# this script from inside scripts/ (e.g. `python scripts/purge_deleted_accounts.py`).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import fetch_all, execute

RETENTION_MONTHS = 6


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Only lists who would be deleted, without actually deleting.",
    )
    args = parser.parse_args()

    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_MONTHS * 30)

    candidates = fetch_all(
        "SELECT id, email, full_name, deleted_at FROM users WHERE deleted_at IS NOT NULL AND deleted_at < :cutoff",
        {"cutoff": cutoff},
    )

    if not candidates:
        print("No accounts have passed the 6-month deletion window. Nothing to do.")
        return

    print(f"{len(candidates)} account(s) past the retention window (deleted before {cutoff.date()}):")
    for row in candidates:
        print(f"  - #{row['id']} {row['email']} ({row['full_name']}) — deleted on {row['deleted_at']}")

    if args.dry_run:
        print("\n--dry-run: nothing was deleted.")
        return

    for row in candidates:
        # ON DELETE CASCADE on related tables (singer_profiles,
        # conductor_profiles, listings, messages, user_social_links,
        # ratings etc — see db/schema.sql) takes care of the rest.
        execute("DELETE FROM users WHERE id = :id", {"id": row["id"]})

    print(f"\n{len(candidates)} account(s) permanently deleted.")


if __name__ == "__main__":
    main()

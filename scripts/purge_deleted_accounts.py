"""
Manual trigger for the account purge — normally NOT needed.

Since 2026-09-26 accounts deactivated more than 6 months ago are erased
automatically by the hourly retention worker (app/retention_worker.py →
app/account_purge.py). Use this only to inspect or force a run:

    python scripts/purge_deleted_accounts.py --dry-run   # how many are due
    python scripts/purge_deleted_accounts.py             # erase them now
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.account_purge import purge_expired_accounts  # noqa: E402
from app.database import engine  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Only count accounts due, delete nothing.")
    args = parser.parse_args()
    with engine.begin() as conn:
        print(purge_expired_accounts(conn, dry_run=args.dry_run))


if __name__ == "__main__":
    main()

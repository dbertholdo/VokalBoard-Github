"""Hourly job: credits the "publicar vaga" Notas reward — Part 2
backlog item 2 (19/09/2026), see app/listing_rewards.py for the full
design writeup (amount per listing type, weekly cap, the 48h minimum
active time and its urgent-listing exception).

Same format as the other 6 workers: its own advisory lock (id 8306 —
never collides with 8202 retention, 8301 invitations, 8302 evaluation
reminders, 8303 invoice draft expiry, 8304 urgent listing reminders,
8305 periodic mails), --once/--dry-run for manual runs, loop+sleep
when left running.

Each due listing is processed independently — award_listing_posted_reward()
never raises (it just returns False when the type isn't eligible or the
weekly cap is hit), so one listing's outcome never affects the next.
"""
import argparse
import logging
import time

from sqlalchemy import text

from app.database import engine
from app.listing_rewards import award_listing_posted_reward, find_reward_eligible_listings

log = logging.getLogger(__name__)


def run_listing_rewards(connection=None, dry_run=False):
    if connection is None:
        with engine.begin() as conn:
            return run_listing_rewards(conn, dry_run)
    conn = connection
    if not conn.execute(text("SELECT pg_try_advisory_xact_lock(8306,1)")).scalar():
        return {"skipped": True}

    rows = find_reward_eligible_listings(conn)
    if dry_run:
        return {"eligible": len(rows)}

    awarded = 0
    for row in rows:
        if award_listing_posted_reward(row["author_id"], row["id"], row["listing_type"]):
            awarded += 1
    return {"eligible": len(rows), "awarded": awarded}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            log.info("Listing reward counts: %s", run_listing_rewards(dry_run=args.dry_run))
        except Exception:
            log.exception("Listing reward job failed; transaction rolled back")
            if args.once or args.dry_run:
                raise
        if args.once or args.dry_run:
            break
        time.sleep(3600)

"""Admin navigation helpers (docs/specs/ADMIN_REORG.md, 2026-09-27).

The grouped admin sidebar shows how much is waiting in each place; these
counts come from one small query per admin page view (admins only)."""
from app.database import fetch_one


def admin_attention_counts() -> dict:
    row = fetch_one(
        """
        SELECT (SELECT count(*) FROM listing_reports WHERE status = 'open') AS listing_reports,
               (SELECT count(*) FROM message_reports WHERE status = 'open') AS message_reports,
               (SELECT count(*) FROM support_tickets WHERE status = 'open') AS tickets
        """
    )
    counts = dict(row) if row else {"listing_reports": 0, "message_reports": 0, "tickets": 0}
    counts["reports"] = counts["listing_reports"] + counts["message_reports"]
    from app.referrals import count_flagged_referrals  # tolerates the 2026-09-28 migration missing
    counts["referrals"] = count_flagged_referrals()
    from app.match_cancellation import count_open_reviews  # tolerates the 2026-09-28 migration missing
    counts["cancellations"] = count_open_reviews()
    return counts

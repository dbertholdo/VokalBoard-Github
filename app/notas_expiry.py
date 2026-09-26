"""
Earned-Notas expiry job (Notas v2, docs/specs/NOTAS_V2.md — N3).

Runs inside the hourly retention worker (no separate service):
1. writes off the unspent remainder of every earned lot past its
   18-month expiry (`expire_due_lots` in app/notas_wallet.py);
2. warns users 30 days ahead — one Notification Center entry + one
   e-mail per user per 30 days, covering every lot that expires soon.

The ledger stays append-only: "already warned" is read from the
notifications table, not stamped on ledger rows.
"""
import logging
from decimal import Decimal

from sqlalchemy import text

from app.email import send_email
from app.email_layout import SITE_BASE_URL
from app.email_localization import notas_expiring_email
from app.notas_wallet import expire_due_lots, format_notas
from app.notification_center import create_notification

log = logging.getLogger(__name__)

NOTICE_DAYS = 30


def _users_to_warn(conn) -> list[dict]:
    rows = conn.execute(
        text(
            f"""
            SELECT u.id, u.email, u.full_name, u.preferred_language,
                   MIN(l.expires_at) AS first_expiry,
                   SUM(l.delta - COALESCE(used.total, 0)) AS amount
            FROM credit_ledger l
            JOIN users u ON u.id = l.user_id AND u.deleted_at IS NULL
            LEFT JOIN LATERAL (
                SELECT SUM(amount) AS total FROM credit_lot_usage WHERE lot_id = l.id
            ) used ON TRUE
            WHERE l.category = 'earned'
              AND l.expires_at > now() AND l.expires_at <= now() + interval '{NOTICE_DAYS} days'
              AND l.delta - COALESCE(used.total, 0) > 0
              AND NOT EXISTS (
                  SELECT 1 FROM notifications n
                  WHERE n.user_id = u.id AND n.type = 'notas_expiring'
                    AND n.created_at > now() - interval '{NOTICE_DAYS} days'
              )
            GROUP BY u.id
            """  # nosec B608 - NOTICE_DAYS is a module constant
        )
    ).mappings().all()
    return [dict(r) for r in rows]


def run_notas_expiry(conn, dry_run: bool = False) -> dict:
    if dry_run:
        return {"expiry_notices_due": len(_users_to_warn(conn))}
    expired = expire_due_lots(conn)
    notices = 0
    for user in _users_to_warn(conn):
        amount = format_notas(Decimal(user["amount"]))
        date = user["first_expiry"].strftime("%d.%m.%Y")
        create_notification(
            user["id"], "notas_expiring", "notification_notas_expiring",
            {"amount": amount, "date": date}, link_url="/notas",
        )
        try:
            subject, html = notas_expiring_email(
                user["preferred_language"], user["full_name"], amount, date, f"{SITE_BASE_URL}/notas",
            )
            send_email(user["email"], subject, html)
        except Exception:
            log.exception("Notas expiry e-mail failed for user id %s", user["id"])
        notices += 1
    return {"earned_lots_expired": expired, "expiry_notices": notices}

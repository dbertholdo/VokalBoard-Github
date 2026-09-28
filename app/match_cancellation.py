"""Cancelling a confirmed Match (2026-09-28, HANDOFF 5b — Daniel's rules).

- Either side may cancel, only until 7 days before the event; after that the
  option is gone and the page says to contact the other person directly.
- A reason of at least 50 characters is required; the other side gets an
  e-mail + notification, admins get a notification and review it.
- The vacancy slot opens again (listing un-paused), any invoice draft is
  dropped, and an urgent-listing Match reward is taken back.
- Admins may warn the person who cancelled; 3 warnings = 30 days without
  new Matches (no applying, inviting or accepting).

Everything checks `feature_ready()` first: until the 2026-09-28 migration is
applied, there is simply no cancel option and nobody is ever blocked.
"""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text

from app.database import engine, fetch_all, fetch_one
from app.notas_wallet import debit_in_tx
from app.schema_features import has_columns
from app.urgency import URGENCY_MATCH_REWARD_NOTAS

CANCEL_MIN_DAYS_BEFORE = 7
REASON_MIN_LENGTH = 50
REASON_MAX_LENGTH = 2000
WARNINGS_PER_BLOCK = 3
BLOCK_DAYS = 30


def feature_ready() -> bool:
    return has_columns("match_cancellations", "reason", "outcome") and has_columns("users", "matches_blocked_until")


def cancel_state(status: str, event_date, today: date | None = None) -> str:
    """'allowed' | 'too_late' (event less than a week away) | 'closed'."""
    if status != "confirmed":
        return "closed"
    if event_date is None:
        return "allowed"
    if isinstance(event_date, str):
        try:
            event_date = date.fromisoformat(event_date[:10])
        except ValueError:
            return "allowed"
    today = today or date.today()
    if event_date < today:
        return "closed"
    return "allowed" if (event_date - today).days >= CANCEL_MIN_DAYS_BEFORE else "too_late"


def blocked_until(user_id: int) -> datetime | None:
    """When a 3-warning block ends, or None if the person may start Matches."""
    if not feature_ready():
        return None
    row = fetch_one("SELECT matches_blocked_until AS until FROM users WHERE id = :id", {"id": user_id})
    until = row["until"] if row else None
    return until if until and until > datetime.now(timezone.utc) else None


def cancel_match(match_id: int, user_id: int, reason: str, today: date | None = None) -> dict:
    """{"ok": True, "other_user_id", "cancellation_id", "title"} or {"ok": False, "error": i18n key}."""
    reason = (reason or "").strip()
    if not feature_ready():
        return {"ok": False, "error": "match_cancel_error"}
    if len(reason) < REASON_MIN_LENGTH:
        return {"ok": False, "error": "match_cancel_error_reason"}
    with engine.begin() as conn:
        m = conn.execute(
            text(
                """SELECT m.id, m.status, m.vacancy_id, m.listing_id, m.artist_user_id, m.contractor_user_id,
                          COALESCE(m.listing_snapshot->>'title', l.title) AS title,
                          COALESCE(NULLIF(m.listing_snapshot->>'event_date', '')::date, l.event_date) AS event_date
                   FROM job_matches m LEFT JOIN listings l ON l.id = m.listing_id
                   WHERE m.id = :id FOR UPDATE OF m"""
            ),
            {"id": match_id},
        ).mappings().first()
        if not m or user_id not in (m["artist_user_id"], m["contractor_user_id"]):
            return {"ok": False, "error": "match_cancel_error"}
        state = cancel_state(m["status"], m["event_date"], today)
        if state != "allowed":
            return {"ok": False, "error": "match_cancel_too_late" if state == "too_late" else "match_cancel_error"}
        other = m["contractor_user_id"] if user_id == m["artist_user_id"] else m["artist_user_id"]

        conn.execute(text("UPDATE job_matches SET status = 'cancelled' WHERE id = :id"), {"id": match_id})
        # The slot opens again, and a listing paused because it was full goes live.
        conn.execute(
            text("UPDATE listing_vacancies SET filled_slots = filled_slots - 1 WHERE id = :id AND filled_slots > 0"),
            {"id": m["vacancy_id"]},
        )
        conn.execute(text("UPDATE listings SET is_active = TRUE WHERE id = :id AND is_active = FALSE"), {"id": m["listing_id"]})
        conn.execute(text("DELETE FROM invoice_match_drafts WHERE match_id = :id"), {"id": match_id})
        # The urgent-listing reward only exists "if the Match happens" (match_service).
        if conn.execute(
            text("SELECT 1 FROM credit_ledger WHERE idempotency_key = :k"), {"k": f"urgency_match_reward:{match_id}"}
        ).first():
            debit_in_tx(conn, m["contractor_user_id"], URGENCY_MATCH_REWARD_NOTAS, "urgency_match_reward_reversed",
                        reference_id=match_id, idempotency_key=f"urgency_match_reward_reversed:{match_id}",
                        allow_negative=True)
        cancellation_id = conn.execute(
            text(
                """INSERT INTO match_cancellations (match_id, cancelled_by, other_user_id, reason)
                   VALUES (:m, :by, :other, :reason) RETURNING id"""
            ),
            {"m": match_id, "by": user_id, "other": other, "reason": reason[:REASON_MAX_LENGTH]},
        ).scalar_one()
    return {"ok": True, "other_user_id": other, "cancellation_id": cancellation_id, "title": m["title"]}


# --- admin review ------------------------------------------------------------

def count_open_reviews() -> int:
    if not feature_ready():
        return 0
    return fetch_one("SELECT count(*) AS n FROM match_cancellations WHERE reviewed_at IS NULL")["n"]


def list_cancellations(open_only: bool = True, limit: int = 100) -> list[dict]:
    if not feature_ready():
        return []
    return fetch_all(
        """
        SELECT c.id, c.match_id, c.reason, c.created_at, c.reviewed_at, c.outcome,
               c.cancelled_by, by_u.full_name AS cancelled_by_name, other.full_name AS other_name,
               COALESCE(m.listing_snapshot->>'title', l.title) AS title,
               COALESCE(NULLIF(m.listing_snapshot->>'event_date', '')::date, l.event_date) AS event_date,
               (SELECT count(*) FROM match_warnings w WHERE w.user_id = c.cancelled_by) AS warnings,
               by_u.matches_blocked_until AS blocked_until
        FROM match_cancellations c
        JOIN job_matches m ON m.id = c.match_id
        LEFT JOIN listings l ON l.id = m.listing_id
        LEFT JOIN users by_u ON by_u.id = c.cancelled_by
        LEFT JOIN users other ON other.id = c.other_user_id
        WHERE (:open_only = FALSE OR c.reviewed_at IS NULL)
        ORDER BY c.created_at DESC LIMIT :limit
        """,
        {"open_only": open_only, "limit": limit},
    )


def dismiss(cancellation_id: int, admin_id: int) -> bool:
    with engine.begin() as conn:
        return conn.execute(
            text("""UPDATE match_cancellations SET reviewed_at = now(), reviewed_by = :a, outcome = 'dismissed'
                    WHERE id = :id AND reviewed_at IS NULL"""),
            {"id": cancellation_id, "a": admin_id},
        ).rowcount == 1


def warn(cancellation_id: int, admin_id: int, note: str = "") -> dict | None:
    """Warns whoever cancelled. Returns {"user_id", "warnings", "blocked_until"}
    (blocked_until set when this warning completes a set of 3), or None."""
    with engine.begin() as conn:
        row = conn.execute(
            text("""UPDATE match_cancellations SET reviewed_at = now(), reviewed_by = :a, outcome = 'warned'
                    WHERE id = :id AND reviewed_at IS NULL AND cancelled_by IS NOT NULL RETURNING cancelled_by"""),
            {"id": cancellation_id, "a": admin_id},
        ).first()
        if not row:
            return None
        user_id = row[0]
        conn.execute(text("SELECT id FROM users WHERE id = :id FOR UPDATE"), {"id": user_id})
        conn.execute(
            text("INSERT INTO match_warnings (user_id, cancellation_id, note, issued_by) VALUES (:u, :c, :n, :a)"),
            {"u": user_id, "c": cancellation_id, "n": (note or "").strip()[:1000] or None, "a": admin_id},
        )
        total = conn.execute(text("SELECT count(*) FROM match_warnings WHERE user_id = :u"), {"u": user_id}).scalar_one()
        uncounted = conn.execute(
            text("SELECT id FROM match_warnings WHERE user_id = :u AND counted_in_block = FALSE ORDER BY id"), {"u": user_id}
        ).scalars().all()
        until = None
        if len(uncounted) >= WARNINGS_PER_BLOCK:
            until = datetime.now(timezone.utc) + timedelta(days=BLOCK_DAYS)
            conn.execute(text("UPDATE users SET matches_blocked_until = :t WHERE id = :u"), {"t": until, "u": user_id})
            conn.execute(text("UPDATE match_warnings SET counted_in_block = TRUE WHERE id = ANY(:ids)"),
                         {"ids": list(uncounted[:WARNINGS_PER_BLOCK])})
    return {"user_id": user_id, "warnings": total, "blocked_until": until,
            "towards_next_block": 0 if until else len(uncounted)}


def list_blocked_users() -> list[dict]:
    if not feature_ready():
        return []
    return fetch_all(
        """SELECT u.id, u.full_name, u.matches_blocked_until AS blocked_until,
                  (SELECT count(*) FROM match_warnings w WHERE w.user_id = u.id) AS warnings
           FROM users u WHERE u.matches_blocked_until > now() ORDER BY u.matches_blocked_until"""
    )


def lift_block(user_id: int) -> bool:
    """Daniel 2026-09-28: admins can "unban" early. Past warnings stay on record
    (they already counted towards this block, so they don't count again)."""
    if not feature_ready():
        return False
    with engine.begin() as conn:
        return conn.execute(
            text("UPDATE users SET matches_blocked_until = NULL WHERE id = :id AND matches_blocked_until > now()"),
            {"id": user_id},
        ).rowcount == 1

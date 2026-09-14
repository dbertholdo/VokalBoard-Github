"""
Progressive login-attempt lockout (protection against brute-force
attacks), stored in the login_lockouts table (see db/schema.sql).

Rule: 5 consecutive wrong-password attempts -> locks out login for
that email for 5 minutes. If the person gets it wrong again after the
lockout ends, the next one is 10 minutes; then 1 hour; then 24 hours —
and it stays at 24h if they keep getting it wrong beyond that. Getting
the password right resets everything (the row is deleted, back to the
initial stage).

Stored by email (not by user_id) deliberately: this way the lockout
also applies to attempts against an email that doesn't even have an
account here, without giving any extra hint to someone trying to guess
whether that email is registered or not.
"""
from datetime import datetime, timedelta, timezone

from app.database import fetch_one, execute

MAX_ATTEMPTS_PER_STAGE = 5

# Duration of each lockout, in minutes, per stage (0 = first lockout
# the person hits, 1 = second, ...). Stays locked at the list's last
# value if they keep getting it wrong beyond that.
LOCKOUT_MINUTES_BY_STAGE = [5, 10, 60, 60 * 24]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def check_lockout(email: str) -> int | None:
    """
    Returns how many seconds remain until the lockout ends, or None if
    this email isn't currently locked out (never seen before, or the
    previous lockout has already expired).
    """
    row = fetch_one("SELECT locked_until FROM login_lockouts WHERE email = :email", {"email": email})
    if not row or not row["locked_until"]:
        return None

    remaining = (row["locked_until"] - _now()).total_seconds()
    return int(remaining) if remaining > 0 else None


def record_failure(email: str) -> None:
    """
    Records a wrong-password attempt. If this attempt reaches the
    current stage's limit (MAX_ATTEMPTS_PER_STAGE), activates the
    lockout with that stage's duration and advances to the next one
    (longer, up to the LOCKOUT_MINUTES_BY_STAGE ceiling).
    """
    row = fetch_one(
        "SELECT failed_count, stage FROM login_lockouts WHERE email = :email", {"email": email}
    )
    failed_count = (row["failed_count"] if row else 0) + 1
    stage = row["stage"] if row else 0

    locked_until = None
    if failed_count >= MAX_ATTEMPTS_PER_STAGE:
        stage_index = min(stage, len(LOCKOUT_MINUTES_BY_STAGE) - 1)
        locked_until = _now() + timedelta(minutes=LOCKOUT_MINUTES_BY_STAGE[stage_index])
        stage = min(stage + 1, len(LOCKOUT_MINUTES_BY_STAGE) - 1)
        failed_count = 0

    execute(
        """
        INSERT INTO login_lockouts (email, failed_count, stage, locked_until, updated_at)
        VALUES (:email, :failed_count, :stage, :locked_until, now())
        ON CONFLICT (email) DO UPDATE SET
            failed_count = :failed_count,
            stage = :stage,
            locked_until = :locked_until,
            updated_at = now()
        """,
        {"email": email, "failed_count": failed_count, "stage": stage, "locked_until": locked_until},
    )


def reset(email: str) -> None:
    """Resets the attempt history — called when login succeeds."""
    execute("DELETE FROM login_lockouts WHERE email = :email", {"email": email})

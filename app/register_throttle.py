"""
Brake against mass creation of fake accounts by script — by IP,
deliberately much gentler than the login lockout (see
app/login_throttle.py): here a shared network (several people on the
same college Wi-Fi, office, or mobile carrier with NAT) is common and
shouldn't block real people from signing up.

Rule: at most MAX_REGISTRATIONS_PER_WINDOW accounts created from the
same IP within WINDOW_MINUTES — after that, it asks to wait for the
window to pass (it resets itself, no one is blocked "forever").

Important: this only kicks in on the FINAL STEP of /register (account
created successfully). It NEVER affects login, resending the
verification e-mail, or password reset — no one is ever prevented
from accessing their own account or recovering access because of this.
"""
from datetime import datetime, timedelta, timezone

from app.database import fetch_one, execute

MAX_REGISTRATIONS_PER_WINDOW = 5
WINDOW_MINUTES = 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_registration_throttled(ip_address: str) -> bool:
    """True if this IP has already created too many accounts in the current window."""
    row = fetch_one(
        "SELECT attempt_count, window_started_at FROM registration_attempts WHERE ip_address = :ip",
        {"ip": ip_address},
    )
    if not row:
        return False

    window_expired = (_now() - row["window_started_at"]) > timedelta(minutes=WINDOW_MINUTES)
    if window_expired:
        return False

    return row["attempt_count"] >= MAX_REGISTRATIONS_PER_WINDOW


def record_registration(ip_address: str) -> None:
    """Called only after an account IS CREATED successfully — adds 1 to the current window's counter."""
    row = fetch_one(
        "SELECT attempt_count, window_started_at FROM registration_attempts WHERE ip_address = :ip",
        {"ip": ip_address},
    )

    window_expired = row and (_now() - row["window_started_at"]) > timedelta(minutes=WINDOW_MINUTES)

    if not row or window_expired:
        execute(
            """
            INSERT INTO registration_attempts (ip_address, attempt_count, window_started_at)
            VALUES (:ip, 1, now())
            ON CONFLICT (ip_address) DO UPDATE SET attempt_count = 1, window_started_at = now()
            """,
            {"ip": ip_address},
        )
    else:
        execute(
            "UPDATE registration_attempts SET attempt_count = attempt_count + 1 WHERE ip_address = :ip",
            {"ip": ip_address},
        )

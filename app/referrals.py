"""
"Invite a friend": each person has a unique short code
(referral_code), used in a link like /register?ref=CODE. When
someone signs up arriving through that link, we store who referred
them (referred_by_user_id) — this lets us count how many people each
person brought in.
"""
import secrets
import string

from app.database import fetch_one, execute

CODE_ALPHABET = string.ascii_uppercase + string.digits
CODE_LENGTH = 7


def generate_referral_code() -> str:
    """Generates a random code and makes sure it's unique in the database (retries on a rare collision)."""
    for _ in range(10):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        existing = fetch_one("SELECT id FROM users WHERE referral_code = :code", {"code": code})
        if not existing:
            return code
    # Practically impossible to reach here (7 characters in base36 = over
    # 78 billion combinations), but as a safeguard this never blocks signup.
    return secrets.token_urlsafe(6).upper()[:CODE_LENGTH]


def get_referral_stats(user_id: int) -> dict:
    row = fetch_one(
        "SELECT referral_code FROM users WHERE id = :id", {"id": user_id}
    )
    # Only counts referrals that verified their e-mail — without this,
    # it would be trivial to "inflate" your own counter (and the
    # referral badge) by creating several fake accounts through your
    # own link, since creating an account requires nothing beyond an
    # e-mail. Verifying the e-mail doesn't stop 100% of abuse, but
    # it's already a real barrier.
    count_row = fetch_one(
        "SELECT COUNT(*) AS n FROM users WHERE referred_by_user_id = :id AND email_verified = TRUE",
        {"id": user_id},
    )
    return {
        "code": row["referral_code"] if row else None,
        "count": count_row["n"] if count_row else 0,
    }


def ensure_referral_code(user_id: int, current_code: str | None) -> str:
    """
    Accounts created before this feature existed (or the sample seed
    users) don't have a referral_code. Generates one the first time
    the person visits /profile, instead of requiring a separate
    migration — simpler for a learning project.
    """
    if current_code:
        return current_code
    code = generate_referral_code()
    execute("UPDATE users SET referral_code = :code WHERE id = :id", {"code": code, "id": user_id})
    return code


def resolve_referrer(ref_code: str) -> int | None:
    """Returns the id of whoever referred, based on the code in the URL (or None if invalid/empty)."""
    if not ref_code:
        return None
    row = fetch_one("SELECT id FROM users WHERE referral_code = :code", {"code": ref_code.strip().upper()})
    return row["id"] if row else None

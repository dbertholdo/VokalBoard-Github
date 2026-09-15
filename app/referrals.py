"""
"Invite a friend": each person has a unique short code
(referral_code), used in a link like /register?ref=CODE. When
someone signs up arriving through that link, we store who referred
them (referred_by_user_id) — this lets us count how many people each
person brought in.
"""
import hashlib
import secrets
import string

from app.database import fetch_one, fetch_all, execute, execute_returning

# How many verified referrals earn one "nota" (credit). Kept as a
# constant instead of a config value since changing the ratio later
# would be an intentional business decision, not a deploy-time setting.
CREDIT_REFERRALS_PER_CREDIT = 10

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


def _hash_email(email: str) -> str:
    """
    One-way (irreversible) fingerprint of an e-mail address. We never
    store the e-mail itself here — only this hash — so this table
    cannot be used to look up anyone's address, it can only answer
    "has this exact e-mail already generated a referral before?".
    """
    normalized = email.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def record_referral_verification(user_id: int) -> None:
    """
    Call this right after a user's e-mail gets verified. If they were
    referred by someone, this permanently records that referral (as an
    e-mail hash, never the e-mail itself) and, every CREDIT_REFERRALS_
    PER_CREDIT-th verified referral, credits the referrer with 1 nota.

    Antifraud: referred_email_hash is UNIQUE and this row is never
    deleted when the referred account is later removed (soft-deleted
    or hard-purged by scripts/purge_deleted_accounts.py) — only the
    referred_user_id link is cleared (ON DELETE SET NULL). This is
    what stops someone from farming credits by registering, verifying,
    deleting the account, and registering again with the same e-mail:
    the second attempt's INSERT hits the UNIQUE constraint and is
    silently ignored (ON CONFLICT DO NOTHING), so no second credit is
    ever granted for the same e-mail address.
    """
    user = fetch_one(
        "SELECT id, email, referred_by_user_id FROM users WHERE id = :id", {"id": user_id}
    )
    if not user or not user["referred_by_user_id"]:
        return

    email_hash = _hash_email(user["email"])
    inserted = execute_returning(
        """
        INSERT INTO referral_events (referrer_user_id, referred_email_hash, referred_user_id)
        VALUES (:referrer_id, :email_hash, :referred_id)
        ON CONFLICT (referred_email_hash) DO NOTHING
        RETURNING id
        """,
        {
            "referrer_id": user["referred_by_user_id"],
            "email_hash": email_hash,
            "referred_id": user_id,
        },
    )
    if not inserted:
        return  # this e-mail already generated a referral before (antifraud)

    credited_count = fetch_one(
        "SELECT COUNT(*) AS n FROM referral_events WHERE referrer_user_id = :id",
        {"id": user["referred_by_user_id"]},
    )["n"]

    if credited_count % CREDIT_REFERRALS_PER_CREDIT == 0:
        execute(
            """
            INSERT INTO credit_ledger (user_id, delta, reason, reference_id)
            VALUES (:uid, 1, 'referral_bonus', :ref_id)
            """,
            {"uid": user["referred_by_user_id"], "ref_id": inserted["id"]},
        )


def get_credit_balance(user_id: int) -> int:
    row = fetch_one(
        "SELECT COALESCE(SUM(delta), 0) AS balance FROM credit_ledger WHERE user_id = :id",
        {"id": user_id},
    )
    return row["balance"] if row else 0


def get_credit_ledger(user_id: int, limit: int = 50) -> list[dict]:
    return fetch_all(
        """
        SELECT delta, reason, created_at FROM credit_ledger
        WHERE user_id = :id ORDER BY created_at DESC LIMIT :limit
        """,
        {"id": user_id, "limit": limit},
    )


def get_referrals_until_next_credit(user_id: int) -> int:
    """How many more verified referrals until the next nota (0-9)."""
    credited_count = fetch_one(
        "SELECT COUNT(*) AS n FROM referral_events WHERE referrer_user_id = :id",
        {"id": user_id},
    )["n"]
    remainder = credited_count % CREDIT_REFERRALS_PER_CREDIT
    return CREDIT_REFERRALS_PER_CREDIT - remainder if remainder else 0


def get_hall_of_fame(user_id: int) -> list[dict]:
    """
    Private, referrer-only list of who this person referred (only
    accounts that verified their e-mail — the same rule used for the
    public referral counter and the referral badge).
    """
    return fetch_all(
        """
        SELECT id, full_name, avatar_url, city, country, created_at
        FROM users
        WHERE referred_by_user_id = :id AND email_verified = TRUE AND deleted_at IS NULL
        ORDER BY created_at DESC
        """,
        {"id": user_id},
    )

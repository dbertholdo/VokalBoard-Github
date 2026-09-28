"""
"Invite a friend": each person has a unique short code
(referral_code), used in a link like /register?ref=CODE. When
someone signs up arriving through that link, we store who referred
them (referred_by_user_id) — this lets us count how many people each
person brought in.
"""
import hashlib
import os
import secrets
import string
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.database import engine, fetch_one, fetch_all, execute, execute_returning
from app.email_identity import identity_email, is_disposable
from app.notas_wallet import credit_in_tx, credit_notas, debit_in_tx

# Old rule (still used until the 2026-09-28 migration is applied): one
# Nota per this many verified referrals.
CREDIT_REFERRALS_PER_CREDIT = 10

# Rewards v2 (2026-09-28, Daniel): 1 Nota per successful referral, paid once
# the invitee confirmed their e-mail AND shows real activity. Anti-fraud:
REWARD_NOTAS = 1
MAX_REWARDS_PER_DAY = 3          # per referrer; extra ones wait (stay pending)
MAX_REWARDS_PER_MONTH = 20
SAME_IP_FLAG_THRESHOLD = 3       # referred sign-ups from one IP -> admin review
ACTIVE_DAYS = 7                  # "real activity" without a complete profile

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


def get_referrer_preview(ref_code: str) -> dict | None:
    """Public-safe preview of who's inviting — name + avatar only, nothing
    private — shown as social proof on /register?ref=CODE ("Fulano convidou
    você"). Added 19/09/2026 (Hall da Fama polish). Deleted accounts don't
    match, same as resolve_referrer effectively treats them (a soft-deleted
    referral_code can't earn a fresh signup an inviter credit either way)."""
    if not ref_code:
        return None
    return fetch_one(
        "SELECT full_name, avatar_url FROM users WHERE referral_code = :code AND deleted_at IS NULL",
        {"code": ref_code.strip().upper()},
    )


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
    """Call right after a user's e-mail gets verified (v2 once migrated)."""
    if rewards_v2_enabled():
        _record_v2(user_id)
    else:
        _record_legacy(user_id)


def _record_legacy(user_id: int) -> None:
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
        # P5 Etapa 1 (18/09/2026): passou a usar o módulo central de
        # crédito de Notas em vez de um INSERT solto aqui — mesmo
        # efeito de antes, só centralizado (ver app/notas_wallet.py).
        # idempotency_key usa o id do referral_events, que já é único
        # por e-mail (ver antifraude documentado acima) — redundante
        # com aquela proteção, mas não custa nada ter as duas.
        credit_notas(
            user["referred_by_user_id"], 1, "referral_bonus",
            reference_id=inserted["id"], idempotency_key=f"referral_bonus:{inserted['id']}",
        )


# ---------------------------------------------------------------------------
# Rewards v2 (2026-09-28)
# ---------------------------------------------------------------------------

_V2_CHECK = {"ok": False, "checked": 0.0}


def rewards_v2_enabled() -> bool:
    """True once the 2026-09-28 migration columns exist (cached; while they
    are missing, re-checked at most once a minute)."""
    if _V2_CHECK["ok"] or (_V2_CHECK["checked"] and time.monotonic() - _V2_CHECK["checked"] < 60):
        return _V2_CHECK["ok"]
    row = fetch_one(
        """SELECT count(*) AS n FROM information_schema.columns
           WHERE table_schema = current_schema()
             AND ((table_name = 'referral_events' AND column_name IN ('status', 'rewarded_at', 'reviewed_by'))
               OR (table_name = 'users' AND column_name = 'signup_ip_hash'))"""
    )
    _V2_CHECK.update(ok=bool(row and row["n"] == 4), checked=time.monotonic())
    return _V2_CHECK["ok"]


def hash_ip(ip: str) -> str:
    """Salted, one-way: lets us compare sign-up IPs without storing them."""
    salt = os.getenv("SECRET_KEY", "")
    return hashlib.sha256(f"{salt}|{ip}".encode("utf-8")).hexdigest()


def remember_signup_ip(user_id: int, ip: str) -> None:
    """Only for referred sign-ups (the only place it's used)."""
    if ip and rewards_v2_enabled():
        execute(
            "UPDATE users SET signup_ip_hash = :h WHERE id = :id AND referred_by_user_id IS NOT NULL",
            {"h": hash_ip(ip), "id": user_id},
        )


def _record_v2(user_id: int) -> None:
    user = fetch_one("SELECT id, email, referred_by_user_id FROM users WHERE id = :id", {"id": user_id})
    if not user or not user["referred_by_user_id"]:
        return
    identity_hash = _hash_email(identity_email(user["email"]))
    legacy_hash = _hash_email(user["email"])  # rows recorded before normalization
    if fetch_one(
        "SELECT 1 FROM referral_events WHERE referred_email_hash IN (:a, :b)", {"a": identity_hash, "b": legacy_hash}
    ):
        return  # one reward per e-mail address, ever
    blocked = is_disposable(user["email"])
    inserted = execute_returning(
        """
        INSERT INTO referral_events (referrer_user_id, referred_email_hash, referred_user_id, status, flag_reason)
        VALUES (:referrer_id, :email_hash, :referred_id, :status, :reason)
        ON CONFLICT (referred_email_hash) DO NOTHING
        RETURNING id
        """,
        {"referrer_id": user["referred_by_user_id"], "email_hash": identity_hash, "referred_id": user_id,
         "status": "blocked" if blocked else "pending", "reason": "disposable_email" if blocked else None},
    )
    if inserted and not blocked:
        settle_referral(inserted["id"])


def _has_real_activity(invitee: dict) -> bool:
    """Complete profile, or came back on another day and is 7+ days old."""
    from app.mascot_moments import profile_incomplete
    if not profile_incomplete(invitee):
        return True
    created, seen = invitee["created_at"], invitee["last_seen_at"]
    now = datetime.now(timezone.utc)
    return bool(seen and now - created >= timedelta(days=ACTIVE_DAYS) and seen - created >= timedelta(days=1))


def settle_referral(event_id: int) -> str:
    """Pays a pending referral if every rule allows it now. Returns the
    event's status afterwards ('pending' = not yet; tried again later)."""
    event = fetch_one(
        "SELECT id, referrer_user_id, referred_user_id, status FROM referral_events WHERE id = :id", {"id": event_id}
    )
    if not event or event["status"] != "pending":
        return event["status"] if event else "missing"
    invitee = fetch_one(
        """SELECT id, role, avatar_url, email_verified, created_at, last_seen_at, signup_ip_hash, deleted_at
           FROM users WHERE id = :id""",
        {"id": event["referred_user_id"]},
    )
    if not invitee or invitee["deleted_at"] or not invitee["email_verified"] or not _has_real_activity(invitee):
        return "pending"
    if invitee["signup_ip_hash"]:
        same_ip = fetch_one(
            "SELECT count(*) AS n FROM users WHERE referred_by_user_id = :r AND signup_ip_hash = :h",
            {"r": event["referrer_user_id"], "h": invitee["signup_ip_hash"]},
        )["n"]
        if same_ip >= SAME_IP_FLAG_THRESHOLD:
            execute(
                "UPDATE referral_events SET status = 'flagged', flag_reason = 'same_ip' WHERE id = :id AND status = 'pending'",
                {"id": event_id},
            )
            return "flagged"
    return "rewarded" if _pay(event, enforce_limits=True) else "pending"


def _pay(event: dict, enforce_limits: bool, admin_id: int | None = None) -> bool:
    referrer = event["referrer_user_id"]
    with engine.begin() as conn:
        conn.execute(text("SELECT id FROM users WHERE id = :id FOR UPDATE"), {"id": referrer})
        if enforce_limits:
            counts = conn.execute(
                text(
                    """SELECT count(*) FILTER (WHERE rewarded_at > now() - interval '1 day') AS day,
                              count(*) FILTER (WHERE rewarded_at > now() - interval '30 days') AS month
                       FROM referral_events WHERE referrer_user_id = :r AND status IN ('rewarded', 'reversed')"""
                ),
                {"r": referrer},
            ).mappings().one()
            if counts["day"] >= MAX_REWARDS_PER_DAY or counts["month"] >= MAX_REWARDS_PER_MONTH:
                return False
        updated = conn.execute(
            text(
                """UPDATE referral_events SET status = 'rewarded', rewarded_at = now(),
                          reviewed_at = CASE WHEN CAST(:admin AS BIGINT) IS NULL THEN reviewed_at ELSE now() END,
                          reviewed_by = COALESCE(CAST(:admin AS BIGINT), reviewed_by)
                   WHERE id = :id AND status IN ('pending', 'flagged') RETURNING id"""
            ),
            {"id": event["id"], "admin": admin_id},
        ).first()
        if not updated:
            return False
        credit_in_tx(conn, referrer, REWARD_NOTAS, "referral_bonus", reference_id=event["id"],
                     idempotency_key=f"referral_bonus:{event['id']}")
    return True


def settle_for_invitee(user_id: int) -> None:
    """Hook: login and profile save of the invited person."""
    if not rewards_v2_enabled():
        return
    row = fetch_one(
        "SELECT id FROM referral_events WHERE referred_user_id = :id AND status = 'pending'", {"id": user_id}
    )
    if row:
        settle_referral(row["id"])


def settle_for_referrer(referrer_id: int) -> None:
    """Hook: the referrer opens /notas (pays what waited on limits or the 7 days)."""
    if not rewards_v2_enabled():
        return
    for row in fetch_all(
        "SELECT id FROM referral_events WHERE referrer_user_id = :id AND status = 'pending' ORDER BY id LIMIT 50",
        {"id": referrer_id},
    ):
        settle_referral(row["id"])


def count_pending_referrals(referrer_id: int) -> int:
    """Invited friends not paid yet (waiting for activity, limits or review)."""
    if not rewards_v2_enabled():
        return 0
    return fetch_one(
        "SELECT count(*) AS n FROM referral_events WHERE referrer_user_id = :id AND status IN ('pending', 'flagged')",
        {"id": referrer_id},
    )["n"]


# --- Admin review (routes re-check the password and write audit_log) ---

REVIEW_STATUSES = ("flagged", "pending", "rewarded", "blocked", "rejected", "reversed", "legacy")


def list_referral_events(status: str = "flagged", limit: int = 100) -> list[dict]:
    if not rewards_v2_enabled():
        return []
    return fetch_all(
        """
        SELECT e.id, e.status, e.flag_reason, e.credited_at, e.rewarded_at, e.reviewed_at,
               r.id AS referrer_id, r.full_name AS referrer_name,
               i.id AS invitee_id, i.full_name AS invitee_name, i.created_at AS invitee_created_at
        FROM referral_events e
        JOIN users r ON r.id = e.referrer_user_id
        LEFT JOIN users i ON i.id = e.referred_user_id
        WHERE (:status = '' OR e.status = :status)
        ORDER BY e.id DESC LIMIT :limit
        """,
        {"status": status, "limit": limit},
    )


def count_flagged_referrals() -> int:
    if not rewards_v2_enabled():
        return 0
    return fetch_one("SELECT count(*) AS n FROM referral_events WHERE status = 'flagged'")["n"]


def admin_approve(event_id: int, admin_id: int) -> bool:
    """Pays a pending/flagged referral now (skips activity and limits)."""
    event = fetch_one("SELECT id, referrer_user_id, status FROM referral_events WHERE id = :id", {"id": event_id})
    return bool(event and event["status"] in ("pending", "flagged") and _pay(event, enforce_limits=False, admin_id=admin_id))


def admin_reject(event_id: int, admin_id: int) -> bool:
    row = execute_returning(
        """UPDATE referral_events SET status = 'rejected', reviewed_at = now(), reviewed_by = :admin
           WHERE id = :id AND status IN ('pending', 'flagged') RETURNING id""",
        {"id": event_id, "admin": admin_id},
    )
    return bool(row)


def admin_reverse(event_id: int, admin_id: int) -> bool:
    """Takes a paid referral Nota back (may leave a debt if already spent)."""
    with engine.begin() as conn:
        event = conn.execute(
            text(
                """UPDATE referral_events SET status = 'reversed', reviewed_at = now(), reviewed_by = :admin
                   WHERE id = :id AND status = 'rewarded' RETURNING id, referrer_user_id"""
            ),
            {"id": event_id, "admin": admin_id},
        ).mappings().first()
        if not event:
            return False
        debit_in_tx(conn, event["referrer_user_id"], REWARD_NOTAS, "referral_reversed", reference_id=event_id,
                    idempotency_key=f"referral_reversed:{event_id}", allow_negative=True)
    return True


def get_credit_ledger(user_id: int, limit: int = 50) -> list[dict]:
    # `id` incluído (18/09/2026, painel de Admin) pra permitir reembolso
    # de uma linha específica (ver POST /admin/users/{id}/refund-notas em
    # app/routers/admin_routes.py) — não muda nada pra quem só lê o
    # extrato (ex.: /profile), que continua ignorando o campo.
    return fetch_all(
        """
        SELECT id, delta, reason, created_at, category, expires_at FROM credit_ledger
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

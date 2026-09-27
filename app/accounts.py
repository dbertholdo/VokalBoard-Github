"""Account service: e-mail normalization, account creation and auth-token helpers.

Kept out of app/routers/auth_routes.py (CLAUDE.md §4: routers only parse input
and render). Business rules for sign-up live here.
"""
import re

from sqlalchemy import text

from app.auth import hash_password, verify_password
from app.database import fetch_one, transaction
from app.login_throttle import check_lockout, record_failure

MAX_EMAIL_LENGTH = 255
MAX_NAME_LENGTH = 150
# Resend-verification / forgot-password: at most one new e-mail per account in
# this window, so the buttons can't be used to flood someone's inbox.
TOKEN_EMAIL_COOLDOWN_MINUTES = 2

# Deliberately loose (the verification e-mail is the real check): something@something.tld, no spaces.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_dummy_hash: str | None = None


def normalize_email(email: str) -> str:
    """Trim + lowercase. Every lookup and the login lockout key use this form,
    so "Ana@Example.com" and "ana@example.com" are one account (and one lockout)."""
    return (email or "").strip().lower()


def is_valid_email(email: str) -> bool:
    return len(email) <= MAX_EMAIL_LENGTH and bool(_EMAIL_RE.match(email))


def clean_full_name(full_name: str) -> str | None:
    """Collapses whitespace; None when blank or too long."""
    name = " ".join((full_name or "").split())
    return name if 0 < len(name) <= MAX_NAME_LENGTH else None


def find_user_by_email(email: str, columns: str = "id") -> dict | None:
    # lower(email): rows created before normalization may still hold mixed case.
    # `columns` is always a fixed string from our own code, never user input.
    return fetch_one(f"SELECT {columns} FROM users WHERE lower(email) = :email", {"email": normalize_email(email)})  # nosec B608


def check_password_for(user: dict | None, password: str) -> bool:
    """Verifies the password; when the account doesn't exist, still runs one bcrypt
    check so the response time doesn't reveal which e-mails are registered."""
    global _dummy_hash
    if user is None:
        if _dummy_hash is None:
            _dummy_hash = hash_password("timing-equalizer")
        verify_password(password, _dummy_hash)
        return False
    return verify_password(password, user["password_hash"])


def confirm_current_password(user: dict, password: str) -> bool:
    """Re-auth for a logged-in user (change password, delete account). Shares the
    login lockout, so a hijacked session can't be used to brute-force the password."""
    key = normalize_email(user["email"])
    if check_lockout(key) is not None:
        return False
    row = fetch_one("SELECT password_hash FROM users WHERE id = :id", {"id": user["id"]})
    if row and verify_password(password, row["password_hash"]):
        return True
    record_failure(key)
    return False


def token_recently_sent(table: str, user_id: int) -> bool:
    """True when this account got a verification/reset e-mail in the cooldown window."""
    assert table in ("email_verification_tokens", "password_reset_tokens")
    row = fetch_one(
        f"SELECT 1 FROM {table} WHERE user_id = :uid AND created_at > now() - make_interval(mins => :mins) LIMIT 1",  # nosec B608
        {"uid": user_id, "mins": TOKEN_EMAIL_COOLDOWN_MINUTES},
    )
    return row is not None


def create_account(*, email: str, password: str, full_name: str, role: str, voice_type_name: str | None,
                   city: str, state: str, country: str, phone: str, bio: str, ensemble_name: str,
                   preferred_language: str, referral_code: str, referred_by_user_id: int | None,
                   composer_tags: list[str], audio_links: list[str]) -> int:
    """Creates the user row and its role profile in ONE transaction — a failure
    halfway can no longer leave a user without a singer/conductor profile."""
    with transaction() as conn:
        user_id = conn.execute(text(
            """
            INSERT INTO users (email, password_hash, full_name, role, city, state, country, phone,
                               preferred_language, referral_code, referred_by_user_id)
            VALUES (:email, :password_hash, :full_name, :role, :city, :state, :country, :phone,
                    :preferred_language, :referral_code, :referred_by_user_id)
            RETURNING id
            """), {
            "email": normalize_email(email), "password_hash": hash_password(password), "full_name": full_name,
            "role": role, "city": city or None, "state": state or None, "country": country, "phone": phone or None,
            "preferred_language": preferred_language, "referral_code": referral_code,
            "referred_by_user_id": referred_by_user_id,
        }).scalar_one()
        if role == "singer":
            conn.execute(text(
                """
                INSERT INTO singer_profiles (user_id, voice_type_id, bio)
                VALUES (:uid, (SELECT id FROM voice_types WHERE name = :voice), :bio)
                """), {"uid": user_id, "voice": voice_type_name, "bio": bio or None})
            for tag in composer_tags:
                conn.execute(text("INSERT INTO singer_composer_tags (user_id, tag) VALUES (:uid, :tag)"),
                             {"uid": user_id, "tag": tag})
            for url in audio_links:
                conn.execute(text("INSERT INTO singer_audio_links (user_id, url) VALUES (:uid, :url)"),
                             {"uid": user_id, "url": url})
        else:
            conn.execute(text(
                "INSERT INTO conductor_profiles (user_id, ensemble_name, bio) VALUES (:uid, :ensemble, :bio)"
            ), {"uid": user_id, "ensemble": ensemble_name or None, "bio": bio or None})
    return user_id

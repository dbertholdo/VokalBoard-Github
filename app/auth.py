"""Authentication helpers: password hashing and logged-in user session."""
import bcrypt
from fastapi import Request
from app.database import fetch_one

# 2026-09-26: bcrypt directly instead of passlib (unmaintained since 2020;
# relies on the `crypt` module Python 3.13 removes). Same format as before —
# "$2b$", 12 rounds — so every existing hash keeps verifying. bcrypt only
# reads the first 72 bytes; passlib truncated silently, and so do we.
_BCRYPT_MAX_BYTES = 72


def _password_bytes(plain_password: str) -> bytes:
    return plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(_password_bytes(plain_password), bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_password_bytes(plain_password), (password_hash or "").encode("ascii"))
    except ValueError:  # malformed/unknown hash → never a match
        return False


def get_current_user(request: Request) -> dict | None:
    """Reads the user_id stored in the session (cookie) and looks up the user in the database.

    Returns None if no one is logged in — each route decides what to
    do about that (e.g. redirect to /login).
    """
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    # deleted_at IS NULL: a "deleted" account (soft delete) stops
    # counting as logged in even if the old session still exists — see
    # account deletion in profile_routes.py.
    return fetch_one(
        """
        SELECT id, email, full_name, role, city, state, country, email_verified, avatar_url,
               notify_matches, notify_messages, preferred_language, referral_code, is_admin, role_level,
               appear_in_search, profile_slug, phone, phone_visibility, profile_wizard_seen_at
        FROM users WHERE id = :id AND deleted_at IS NULL
        """,
        {"id": user_id},
    )

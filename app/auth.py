"""Authentication helpers: password hashing and logged-in user session."""
from passlib.context import CryptContext
from fastapi import Request
from app.database import fetch_one

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


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
               notify_matches, notify_messages, referral_code, is_admin, role_level
        FROM users WHERE id = :id AND deleted_at IS NULL
        """,
        {"id": user_id},
    )

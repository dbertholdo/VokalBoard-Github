"""Helpers de autenticação: hash de senha e sessão do usuário logado."""
from passlib.context import CryptContext
from fastapi import Request
from app.database import fetch_one

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def get_current_user(request: Request) -> dict | None:
    """Lê o user_id salvo na sessão (cookie) e busca o usuário no banco.

    Retorna None se não houver ninguém logado — cada rota decide o que
    fazer com isso (ex: redirecionar para /login).
    """
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    # deleted_at IS NULL: uma conta "excluída" (soft delete) deixa de
    # contar como logada mesmo que a sessão antiga ainda exista — ver
    # a exclusão de conta em profile_routes.py.
    return fetch_one(
        """
        SELECT id, email, full_name, role, city, state, country, email_verified, avatar_url,
               notify_matches, notify_messages, referral_code, is_admin, role_level
        FROM users WHERE id = :id AND deleted_at IS NULL
        """,
        {"id": user_id},
    )

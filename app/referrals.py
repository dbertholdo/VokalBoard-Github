"""
"Convide um amigo": cada pessoa tem um código curto único
(referral_code), usado num link tipo /register?ref=CODE. Quando
alguém se cadastra chegando por esse link, guardamos quem indicou
(referred_by_user_id) — dá pra contar quantas pessoas cada um trouxe.
"""
import secrets
import string

from app.database import fetch_one, execute

CODE_ALPHABET = string.ascii_uppercase + string.digits
CODE_LENGTH = 7


def generate_referral_code() -> str:
    """Gera um código aleatório e garante que é único no banco (tenta de novo em caso de colisão rara)."""
    for _ in range(10):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        existing = fetch_one("SELECT id FROM users WHERE referral_code = :code", {"code": code})
        if not existing:
            return code
    # Praticamente impossível de chegar aqui (7 caracteres em base36 = mais
    # de 78 bilhões de combinações), mas por segurança nunca trava o cadastro.
    return secrets.token_urlsafe(6).upper()[:CODE_LENGTH]


def get_referral_stats(user_id: int) -> dict:
    row = fetch_one(
        "SELECT referral_code FROM users WHERE id = :id", {"id": user_id}
    )
    # Só conta indicações que verificaram o e-mail — sem isso, seria
    # trivial "inflar" o próprio contador (e o badge de indicação)
    # criando várias contas falsas pelo próprio link, já que criar
    # conta não exige nada além de um e-mail. Verificar o e-mail não
    # impede 100% do abuso, mas já é uma barreira real.
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
    Contas criadas antes desse recurso existir (ou os usuários de
    exemplo do seed) não têm referral_code. Gera um na primeira vez
    que a pessoa acessa /profile, em vez de exigir uma migração
    separada — mais simples para um projeto de aprendizado.
    """
    if current_code:
        return current_code
    code = generate_referral_code()
    execute("UPDATE users SET referral_code = :code WHERE id = :id", {"code": code, "id": user_id})
    return code


def resolve_referrer(ref_code: str) -> int | None:
    """Devolve o id de quem indicou, a partir do código na URL (ou None se inválido/vazio)."""
    if not ref_code:
        return None
    row = fetch_one("SELECT id FROM users WHERE referral_code = :code", {"code": ref_code.strip().upper()})
    return row["id"] if row else None

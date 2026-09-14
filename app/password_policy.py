"""
Regra de senha: pelo menos 6 caracteres, com 1 letra, 1 número e 1
caractere especial.

O conjunto de caracteres especiais aceitos foi escolhido pra dar o
MENOR problema possível: nenhum deles quebra formulário HTML, URL,
copiar/colar ou teclado (ABNT2 ou QWERTY) — evitamos coisas como aspas
(' e ") ou barra invertida (\\), que às vezes dão dor de cabeça em
algum sistema por aí. Isso é só validação de formato; a senha em si
nunca é guardada em texto puro (ver app/auth.py — sempre com bcrypt).
"""
import re

MIN_LENGTH = 6
SPECIAL_CHARS = "!@#$%^&*()-_=+"

_HAS_LETTER = re.compile(r"[A-Za-zÀ-ÿ]")
_HAS_DIGIT = re.compile(r"[0-9]")
_HAS_SPECIAL = re.compile(r"[" + re.escape(SPECIAL_CHARS) + r"]")


def password_error(password: str) -> str | None:
    """
    Devolve a CHAVE de tradução do erro (ver app/i18n.py) se a senha
    não cumprir a regra, ou None se estiver tudo certo.
    """
    if len(password) < MIN_LENGTH:
        return "password_error_length"
    if not _HAS_LETTER.search(password):
        return "password_error_letter"
    if not _HAS_DIGIT.search(password):
        return "password_error_digit"
    if not _HAS_SPECIAL.search(password):
        return "password_error_special"
    return None

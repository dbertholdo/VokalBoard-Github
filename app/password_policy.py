"""
Password rule: at least 6 characters, with 1 letter, 1 digit and 1
special character.

The set of accepted special characters was chosen to cause the
LEAST possible trouble: none of them break an HTML form, a URL,
copy/paste, or a keyboard layout — we avoid things like quotes
(' and ") or a backslash (\\), which sometimes cause headaches on
some system out there. This is just format validation; the password
itself is never stored in plain text (see app/auth.py — always with
bcrypt).
"""
import re

MIN_LENGTH = 6
SPECIAL_CHARS = "!@#$%^&*()-_=+"

_HAS_LETTER = re.compile(r"[A-Za-zÀ-ÿ]")
_HAS_DIGIT = re.compile(r"[0-9]")
_HAS_SPECIAL = re.compile(r"[" + re.escape(SPECIAL_CHARS) + r"]")


def password_error(password: str) -> str | None:
    """
    Returns the error translation KEY (see app/i18n.py) if the
    password doesn't meet the rule, or None if everything checks out.
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

"""
Spoken languages the person selects on their profile (P2.B) — a
*different* concept from `app.i18n.SUPPORTED_LANGUAGES`, which is the
language the SITE ITSELF is displayed in. This module is about the
human languages a singer/conductor can communicate in, shown as
information on their profile.

Fixed list per the plan: the 10 most spoken languages in Europe,
deliberately including Portuguese even though a strict by-native-
speakers ranking would leave it just outside the top 10 — plus an
"Outra" (custom, free-text) option. A person can pick up to
MAX_SPOKEN_LANGUAGES total (1 + up to 3 extra fields, per the plan),
and remove any of them.
"""
from app.database import fetch_all, execute

# code -> {de, en, fr, it, pt} display names, same shape as other
# translated option lists in this codebase (see app.locations).
SPOKEN_LANGUAGE_OPTIONS = {
    "de": {"de": "Deutsch", "en": "German", "fr": "Allemand", "it": "Tedesco", "pt": "Alemão"},
    "en": {"de": "Englisch", "en": "English", "fr": "Anglais", "it": "Inglese", "pt": "Inglês"},
    "fr": {"de": "Französisch", "en": "French", "fr": "Français", "it": "Francese", "pt": "Francês"},
    "it": {"de": "Italienisch", "en": "Italian", "fr": "Italien", "it": "Italiano", "pt": "Italiano"},
    "es": {"de": "Spanisch", "en": "Spanish", "fr": "Espagnol", "it": "Spagnolo", "pt": "Espanhol"},
    "pt": {"de": "Portugiesisch", "en": "Portuguese", "fr": "Portugais", "it": "Portoghese", "pt": "Português"},
    "pl": {"de": "Polnisch", "en": "Polish", "fr": "Polonais", "it": "Polacco", "pt": "Polonês"},
    "ro": {"de": "Rumänisch", "en": "Romanian", "fr": "Roumain", "it": "Rumeno", "pt": "Romeno"},
    "ru": {"de": "Russisch", "en": "Russian", "fr": "Russe", "it": "Russo", "pt": "Russo"},
    "uk": {"de": "Ukrainisch", "en": "Ukrainian", "fr": "Ukrainien", "it": "Ucraino", "pt": "Ucraniano"},
}

# Extra pseudo-code for "type your own" — not a real ISO code, kept
# short/distinct so it can never collide with one.
OTHER_LANGUAGE_CODE = "other"

MAX_SPOKEN_LANGUAGES = 4  # 1 + up to 3 extra fields, per the plan
MAX_CUSTOM_NAME_LENGTH = 100


def spoken_language_name(code: str, custom_name: str | None, ui_lang: str) -> str:
    """Display name for one saved row, in the viewer's current UI
    language (falls back to English, then to the custom name itself for
    'other')."""
    if code == OTHER_LANGUAGE_CODE:
        return (custom_name or "").strip() or "?"
    names = SPOKEN_LANGUAGE_OPTIONS.get(code)
    if not names:
        return code
    return names.get(ui_lang) or names.get("en") or code


def get_spoken_languages(user_id: int) -> list[dict]:
    return fetch_all(
        """
        SELECT language_code, custom_name
        FROM user_spoken_languages
        WHERE user_id = :user_id
        ORDER BY sort_order, id
        """,
        {"user_id": user_id},
    )


def get_spoken_language_names(user_id: int, ui_lang: str) -> list[str]:
    rows = get_spoken_languages(user_id)
    return [spoken_language_name(r["language_code"], r["custom_name"], ui_lang) for r in rows]


def set_spoken_languages(user_id: int, entries: list[tuple[str, str]]) -> None:
    """
    `entries` is a list of (language_code, custom_name) tuples, already
    validated by the caller (valid codes, custom_name only paired with
    OTHER_LANGUAGE_CODE, at most MAX_SPOKEN_LANGUAGES, no exact
    duplicates) — this function just replaces the stored set.
    """
    execute("DELETE FROM user_spoken_languages WHERE user_id = :user_id", {"user_id": user_id})
    for position, (code, custom_name) in enumerate(entries[:MAX_SPOKEN_LANGUAGES]):
        execute(
            """
            INSERT INTO user_spoken_languages (user_id, language_code, custom_name, sort_order)
            VALUES (:user_id, :language_code, :custom_name, :sort_order)
            """,
            {
                "user_id": user_id,
                "language_code": code,
                "custom_name": custom_name,
                "sort_order": position,
            },
        )


def parse_spoken_languages_form(codes: list[str], custom_names: list[str]) -> list[tuple[str, str | None]]:
    """
    Turns the parallel `spoken_language_code` / `spoken_language_custom`
    repeated form fields into a clean, validated list of
    (code, custom_name) tuples ready for set_spoken_languages().

    Rows with an empty code are skipped (an unused extra field).
    Duplicate fixed-language codes are dropped (keeps the first).
    "other" rows with an empty custom name are also skipped — a free-text
    language with no name would just show "?" and isn't useful to save.
    """
    valid_codes = set(SPOKEN_LANGUAGE_OPTIONS.keys()) | {OTHER_LANGUAGE_CODE}
    seen_fixed = set()
    result: list[tuple[str, str | None]] = []
    for i, raw_code in enumerate(codes):
        code = (raw_code or "").strip()
        if not code or code not in valid_codes:
            continue
        custom_name = (custom_names[i].strip() if i < len(custom_names) and custom_names[i] else "")[:MAX_CUSTOM_NAME_LENGTH]
        if code == OTHER_LANGUAGE_CODE:
            if not custom_name:
                continue
            result.append((code, custom_name))
        else:
            if code in seen_fixed:
                continue
            seen_fixed.add(code)
            result.append((code, None))
        if len(result) >= MAX_SPOKEN_LANGUAGES:
            break
    return result

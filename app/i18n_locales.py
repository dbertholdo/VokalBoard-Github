"""
External locale files for languages added after the five core ones.

The core languages (de/en/fr/it/pt) stay inline in app/i18n.py. Every
other language lives in app/locales/<lang>.json as a flat
{i18n_key: translated_text} map, merged into TRANSLATIONS at import
time. A key missing from the file simply falls back to English in
translate(), so a language can be filled in gradually.

Workflow and conventions: docs/I18N.md. Tooling: scripts/i18n_tool.py.
"""
import json
import re
from pathlib import Path

LOCALES_DIR = Path(__file__).resolve().parent / "locales"
CORE_LANGUAGES = ("de", "en", "fr", "it", "pt")
SOURCE_LANGUAGE = "en"  # placeholders and meaning are checked against English

_PLACEHOLDER_RE = re.compile(r"\{[a-z_]+\}")


def locale_path(lang: str) -> Path:
    return LOCALES_DIR / f"{lang}.json"


def locale_files() -> list[str]:
    """Language codes that have a locale file, sorted."""
    return sorted(p.stem for p in LOCALES_DIR.glob("*.json"))


def load_locale(lang: str) -> dict[str, str]:
    path = locale_path(lang)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_locale(lang: str, entries: dict[str, str]) -> None:
    """Sorted keys, UTF-8 (not \\u-escaped), LF endings — keeps diffs small."""
    text = json.dumps(dict(sorted(entries.items())), ensure_ascii=False, indent=2) + "\n"
    locale_path(lang).write_text(text, encoding="utf-8", newline="\n")


def placeholders(text: str) -> set[str]:
    return set(_PLACEHOLDER_RE.findall(text or ""))


def validate_entries(entries: dict, translations: dict) -> list[str]:
    """Problems that would break rendering or silently drop data."""
    errors = []
    for key, text in entries.items():
        if key not in translations:
            errors.append(f"{key}: unknown i18n key (removed or misspelled?)")
            continue
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{key}: empty or non-string translation")
            continue
        expected = placeholders(translations[key].get(SOURCE_LANGUAGE, ""))
        if placeholders(text) != expected:
            errors.append(f"{key}: placeholders {sorted(placeholders(text))} != English {sorted(expected)}")
    return errors


def merge_into(translations: dict) -> None:
    """Adds every valid locale-file entry to TRANSLATIONS (in place).
    Invalid entries are skipped here and reported by the test suite."""
    for lang in locale_files():
        entries = load_locale(lang)
        bad = {e.split(":", 1)[0] for e in validate_entries(entries, translations)}
        for key, text in entries.items():
            if key not in bad:
                translations[key][lang] = text


def coverage(lang: str, translations: dict) -> tuple[int, int]:
    """(translated keys, total keys) for a language."""
    done = sum(1 for entry in translations.values() if entry.get(lang))
    return done, len(translations)

"""
Translation workflow tool for languages stored in app/locales/<lang>.json.

Usage (from the repo root):
  python scripts/i18n_tool.py status
      Coverage per language + any invalid locale entries.
  python scripts/i18n_tool.py todo zh [--limit 80] [--out batch.json]
      Next batch of untranslated keys, with English (source) and German
      (context) text, as JSON. Translate the "translation" fields.
  python scripts/i18n_tool.py apply zh batch.json
      Validates a filled batch (known key, non-empty, same {placeholders}
      as English) and merges it into app/locales/zh.json. Accepts either
      the `todo` format or a plain {key: text} map. Invalid entries are
      reported and skipped; nothing else is touched.
  python scripts/i18n_tool.py check
      Exit code 1 if any locale file has invalid entries (for CI).

Batches keep AI/translator sessions small: translate ~80 keys, apply,
repeat. See docs/I18N.md for conventions and the glossary.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.i18n import SUPPORTED_LANGUAGES, TRANSLATIONS  # noqa: E402
from app.i18n_locales import (  # noqa: E402
    CORE_LANGUAGES, SOURCE_LANGUAGE, coverage, load_locale, locale_files, save_locale, validate_entries,
)


def cmd_status(_args) -> int:
    langs = list(dict.fromkeys(list(SUPPORTED_LANGUAGES) + locale_files()))
    problems = 0
    for lang in langs:
        done, total = coverage(lang, TRANSLATIONS)
        source = "inline" if lang in CORE_LANGUAGES else ("file" if lang in locale_files() else "MISSING FILE")
        registered = "" if lang in SUPPORTED_LANGUAGES else "  (not in SUPPORTED_LANGUAGES)"
        print(f"{lang:>3}  {done:>4}/{total}  {100 * done / total:5.1f}%  [{source}]{registered}")
        if lang not in CORE_LANGUAGES:
            errors = validate_entries(load_locale(lang), TRANSLATIONS)
            problems += len(errors)
            for e in errors:
                print(f"      ! {e}")
    return 1 if problems else 0


def cmd_todo(args) -> int:
    existing = load_locale(args.lang)
    missing = [k for k in sorted(TRANSLATIONS) if not existing.get(k)]
    batch = {
        k: {"en": TRANSLATIONS[k].get(SOURCE_LANGUAGE, ""), "de": TRANSLATIONS[k].get("de", ""), "translation": ""}
        for k in missing[: args.limit]
    }
    text = json.dumps(batch, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"{len(batch)} keys written to {args.out} ({len(missing)} still missing for {args.lang})")
    else:
        print(text)
    return 0


def cmd_apply(args) -> int:
    raw = json.loads(Path(args.file).read_text(encoding="utf-8"))
    incoming = {k: (v.get("translation", "") if isinstance(v, dict) else v) for k, v in raw.items()}
    incoming = {k: v for k, v in incoming.items() if isinstance(v, str) and v.strip()}
    errors = validate_entries(incoming, TRANSLATIONS)
    bad = {e.split(":", 1)[0] for e in errors}
    for e in errors:
        print(f"skipped  {e}")
    locale = load_locale(args.lang)
    good = {k: v.strip() for k, v in incoming.items() if k not in bad}
    locale.update(good)
    save_locale(args.lang, locale)
    done = sum(1 for k in TRANSLATIONS if locale.get(k))
    print(f"applied {len(good)} keys to app/locales/{args.lang}.json — now {done}/{len(TRANSLATIONS)}")
    return 1 if errors else 0


def cmd_check(_args) -> int:
    failed = False
    for lang in locale_files():
        for e in validate_entries(load_locale(lang), TRANSLATIONS):
            print(f"{lang}: {e}")
            failed = True
    return 1 if failed else 0


def main() -> int:
    # Windows consoles default to cp1252, which can't print CJK text.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    todo = sub.add_parser("todo")
    todo.add_argument("lang")
    todo.add_argument("--limit", type=int, default=80)
    todo.add_argument("--out")
    apply = sub.add_parser("apply")
    apply.add_argument("lang")
    apply.add_argument("file")
    sub.add_parser("check")
    args = parser.parse_args()
    return {"status": cmd_status, "todo": cmd_todo, "apply": cmd_apply, "check": cmd_check}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())

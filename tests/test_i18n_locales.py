"""Guards for the external locale files (app/locales/<lang>.json) and
for adding languages safely — see docs/I18N.md. Database-free."""
import inspect

from app import email_localization
from app.email_localization import EMAIL_LANGUAGES
from app.i18n import SUPPORTED_LANGUAGES, TRANSLATIONS, translate
from app.i18n_locales import CORE_LANGUAGES, load_locale, locale_files, merge_into, validate_entries


def test_every_non_core_language_has_a_locale_file():
    missing = [lang for lang in SUPPORTED_LANGUAGES if lang not in CORE_LANGUAGES and lang not in locale_files()]
    assert not missing, f"create app/locales/<lang>.json for {missing}"


def test_locale_files_have_no_invalid_entries():
    errors = {lang: validate_entries(load_locale(lang), TRANSLATIONS) for lang in locale_files()}
    assert not any(errors.values()), errors


def test_translate_uses_locale_text_and_falls_back_to_english():
    for lang in locale_files():
        locale = load_locale(lang)
        for key in ("nav_login", "nav_board", "nav_logout"):
            assert translate(key, lang) == (locale.get(key) or TRANSLATIONS[key]["en"])


def test_merge_skips_invalid_entries(tmp_path, monkeypatch):
    import app.i18n_locales as loc
    (tmp_path / "xx.json").write_text(
        '{"nav_login": "OK", "nav_board": "", "no_such_key": "x"}', encoding="utf-8"
    )
    monkeypatch.setattr(loc, "LOCALES_DIR", tmp_path)
    table = {"nav_login": {"en": "Log in"}, "nav_board": {"en": "Jobs"}}
    merge_into(table)
    assert table == {"nav_login": {"en": "Log in", "xx": "OK"}, "nav_board": {"en": "Jobs"}}


def test_placeholders_must_match_english():
    table = {"k": {"en": "Hi {name}"}}
    assert validate_entries({"k": "Hallo {name}"}, table) == []
    assert validate_entries({"k": "Hallo"}, table)
    assert validate_entries({"k": "Hallo {nome}"}, table)


def test_every_email_template_covers_every_email_language():
    """Adding a code to EMAIL_LANGUAGES without adding its copy to every
    e-mail function would KeyError at send time — catch it here."""
    dummies = {str: "x", int: 1, bool: True}
    # Arguments that select a copy variant: exercise every variant.
    variants = {"punishment": ("warning", "suspend", "ban")}
    for name, fn in inspect.getmembers(email_localization, inspect.isfunction):
        params = inspect.signature(fn).parameters
        if fn.__module__ != email_localization.__name__ or "language" not in params:
            continue
        variant_param = next((p for p in params if p in variants), None)
        for lang in EMAIL_LANGUAGES:
            for variant in variants.get(variant_param, (None,)):
                kwargs = {
                    p.name: (lang if p.name == "language" else dummies.get(p.annotation, "x"))
                    for p in params.values() if p.default is inspect.Parameter.empty
                }
                if variant_param:
                    kwargs[variant_param] = variant
                subject, body = fn(**kwargs)
                assert subject and body, (name, lang, variant)

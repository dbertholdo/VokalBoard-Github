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


def test_admin_pages_stay_english_for_added_languages_only():
    """Daniel, 2026-09-26: added languages (es/zh/ko/ro) are for the public
    site only; the admin area stays English. Core languages keep their
    existing admin behaviour untouched."""
    from app.i18n_locales import page_language
    for template in ("admin.html", "admin_user_detail.html", "financeiro_estornos.html",
                     "financial_dashboard.html", "zona_vermelha.html"):
        for lang in SUPPORTED_LANGUAGES:
            expected = lang if lang in CORE_LANGUAGES else "en"
            assert page_language(lang, template) == expected, (template, lang)
    for template in ("home.html", "board.html", "listing_form.html", "notas.html", "assinar_stub.html"):
        for lang in SUPPORTED_LANGUAGES:
            assert page_language(lang, template) == lang, (template, lang)


def test_spanish_is_registered_as_an_added_language():
    from app.i18n import LANGUAGE_META
    assert "es" in SUPPORTED_LANGUAGES and "es" in LANGUAGE_META and "es" not in CORE_LANGUAGES


def test_locale_files_contain_no_admin_only_keys():
    from app.i18n_locales import admin_only_keys
    admin_only = admin_only_keys(TRANSLATIONS)
    leaked = {lang: sorted(set(load_locale(lang)) & admin_only) for lang in locale_files()}
    assert not any(leaked.values()), leaked


def test_admin_page_ignores_added_language_but_public_page_uses_it(client, monkeypatch):
    """End to end: a Spanish translation shows on public pages, never on
    admin pages; Portuguese (core) admin behaviour is unchanged."""
    from app.database import execute
    from tests.test_security import login, register_test_user

    monkeypatch.setitem(TRANSLATIONS["nav_logout"], "es", "SALIR_ES_MARKER")
    user_id, email, password = register_test_user(client, full_name="I18n Admin Scope")
    execute("UPDATE users SET role_level = 3, email_verified = TRUE WHERE id = :id", {"id": user_id})
    login(client, email, password)

    public = client.get("/board?lang=es")
    assert "SALIR_ES_MARKER" in public.text
    admin = client.get("/admin?lang=es")
    assert admin.status_code == 200
    assert "SALIR_ES_MARKER" not in admin.text and "Log out" in admin.text
    admin_pt = client.get("/admin?lang=pt")
    assert "Sair" in admin_pt.text  # core language admin behaviour untouched

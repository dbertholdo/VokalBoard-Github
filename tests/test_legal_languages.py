"""6a (2026-09-28): Code of Conduct in every language; German/English-only legal pages say so."""
from markupsafe import escape  # same escaping as the templates

import pytest

from app.i18n import SUPPORTED_LANGUAGES, translate


@pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
def test_code_of_conduct_is_in_every_language(client, lang):
    client.cookies.clear()
    page = client.get(f"/code-of-conduct?lang={lang}").text
    for n in range(1, 8):
        assert str(escape(translate(f"conduct_r{n}_title", lang))) in page
    if lang != "de":
        assert "Sei respektvoll" not in page  # no German fallback any more


def test_legal_pages_show_the_binding_notice_only_for_other_languages(client):
    client.cookies.clear()
    assert "legal-lang-notice" in client.get("/agb?lang=pt").text
    assert "Seule la version allemande fait foi" in client.get("/datenschutz?lang=fr").text
    assert 'href="/widerruf?lang=en"' in client.get("/widerruf?lang=ko").text
    for lang in ("de", "en"):
        assert "legal-lang-notice" not in client.get(f"/agb?lang={lang}").text

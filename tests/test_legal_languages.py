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


def test_legal_pages_are_german_only_with_a_notice_for_other_languages(client):
    """Daniel 2026-09-29: only the German text exists and is valid; no English version."""
    client.cookies.clear()
    for path in ("/agb", "/datenschutz", "/widerruf"):
        de = client.get(f"{path}?lang=de").text
        assert "legal-lang-notice" not in de
        en = client.get(f"{path}?lang=en").text
        assert "legal-lang-notice" in en and "The German version is binding; this English version" not in en
        assert '<div lang="de">' in en
    assert str(escape(translate("legal_german_only_notice", "fr"))) in client.get("/datenschutz?lang=fr").text
    assert "?lang=en" not in client.get("/widerruf?lang=ko").text.split("legal-lang-notice")[1][:300]


def test_impressum_and_privacy_are_complete(client):
    """Legal check L2/L3 (2026-09-29): real operator data, § 5 DDG, no placeholders."""
    client.cookies.clear()
    for path in ("/impressum", "/datenschutz"):
        page = client.get(f"{path}?lang=de").text
        assert "FILL IN" not in page and "NOCH MIT ANWALT" not in page and "Brasil" not in page
        assert "Daniel Bachhuber" in page and "81669 München" in page
        assert "daniel (a) vokalboard.com" in page and "daniel@vokalboard.com" not in page  # Daniel: against spam
        assert "legal-lang-notice" in client.get(f"{path}?lang=en").text
    assert "§ 5 DDG" in client.get("/impressum").text and "TMG" not in client.get("/impressum").text
    privacy = client.get("/datenschutz").text
    for must in ("Art. 21 DSGVO", "BayLDA", "Cloudflare", "Railway", "Resend", "Stripe", "TDDDG"):
        assert must in privacy

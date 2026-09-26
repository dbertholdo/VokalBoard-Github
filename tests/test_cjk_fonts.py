"""Self-hosted CJK fonts: shipped with their license, loaded only on zh/ko pages."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "app" / "static" / "fonts" / "noto-cjk"
CSS = ROOT / "app" / "static" / "css" / "fonts-cjk.css"


def test_cjk_font_files_and_license_present():
    assert "SIL Open Font License" in (FONT_DIR / "LICENSE.txt").read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    for url in re.findall(r"url\('/static/fonts/noto-cjk/([^']+)'\)", css):
        assert (FONT_DIR / url).is_file(), url


@pytest.mark.parametrize("lang", ["zh", "ko"])
def test_ui_subset_covers_every_locale_char(lang):
    # A new translation with a char outside the "ui" subset means the fonts need regenerating
    # (scripts/subset_cjk_fonts.py) — otherwise that char silently falls back to a system font.
    family = "Noto Sans SC" if lang == "zh" else "Noto Sans KR"
    css = CSS.read_text(encoding="utf-8")
    covered = set()
    for fam, ranges in re.findall(r"font-family:'([^']+)'.*?unicode-range:([^;]+);", css):
        if fam != family:
            continue
        for part in ranges.split(","):
            lo, _, hi = part.strip()[2:].partition("-")
            covered.update(range(int(lo, 16), int(hi or lo, 16) + 1))
    texts = json.loads((ROOT / "app" / "locales" / f"{lang}.json").read_text(encoding="utf-8")).values()
    missing = {c for c in "".join(t for t in texts if isinstance(t, str)) if ord(c) >= 0x2E80 and ord(c) not in covered}
    assert not missing, f"regenerate CJK fonts, missing: {''.join(sorted(missing))}"


def test_cjk_stylesheet_only_on_cjk_pages(client):
    for lang, expected in (("zh", True), ("ko", True), ("de", False), ("es", False)):
        html = client.get(f"/?lang={lang}").text
        assert ("/static/css/fonts-cjk.css" in html) is expected, lang

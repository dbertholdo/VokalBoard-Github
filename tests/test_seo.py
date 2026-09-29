"""SEO basics (2026-09-28, HANDOFF 4b; app/seo.py)."""
import json
import re

from app.database import execute
from tests.test_security import register_test_user
from tests.test_urgency_match_reward import _make_vacancy


def _jsonld(html):
    return [json.loads(m) for m in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S)]


def _title(html):
    return re.search(r"<title>(.*?)</title>", html, re.S).group(1).strip()


def test_home_has_keyword_title_description_alternates_and_site_data(client):
    client.cookies.clear()
    html = client.get("/?lang=en").text
    assert _title(html) == "VokalBoard — Music jobs &amp; auditions for singers and conductors"
    assert 'name="description" content="Find music jobs, auditions' in html
    assert '<link rel="canonical" href="http://testserver/?lang=en">' in html
    assert 'hreflang="de" href="http://testserver/"' in html and 'hreflang="x-default"' in html
    assert 'hreflang="zh-Hans" href="http://testserver/?lang=zh"' in html
    assert "Music jobs, auditions and gigs in one place" in html
    graph = _jsonld(html)[0]["@graph"]
    assert {node["@type"] for node in graph} == {"Organization", "WebSite"}


def test_pages_use_their_own_title_now(client):
    client.cookies.clear()
    assert _title(client.get("/board?lang=en").text) == "Music jobs &amp; auditions for singers and conductors — VokalBoard"
    assert _title(client.get("/board?city=Berlin&lang=de").text).startswith("Jobs &amp; Vorsingen")
    assert '<link rel="canonical" href="http://testserver/board">' in client.get("/board?city=Berlin").text


def test_job_listing_has_google_jobs_markup_with_public_data_only(client):
    author_id, email, _ = register_test_user(client, full_name="SEO Author")
    listing_id, _ = _make_vacancy(author_id)
    client.cookies.clear()
    html = client.get(f"/listings/{listing_id}?lang=en").text
    posting = next(d for d in _jsonld(html) if d.get("@type") == "JobPosting")
    assert posting["title"] == "Sectest Reward Listing"
    assert posting["jobLocation"]["address"]["addressLocality"] == "München"
    assert posting["url"].endswith(f"/listings/{listing_id}") and "validThrough" in posting
    assert email not in html.split("</head>")[0]
    assert _title(html) == "Sectest Reward Listing — München — VokalBoard"

    # Daniel 2026-09-29: the full description is public (page and Google); contact stays locked.
    long_text = "Wir suchen eine Sopranistin für Bachs Magnificat. " * 6
    execute("UPDATE listings SET description = :d WHERE id = :id", {"d": long_text, "id": listing_id})
    html = client.get(f"/listings/{listing_id}?lang=en").text
    assert long_text.strip() in html.split("</head>")[1]
    assert long_text.strip() in next(d for d in _jsonld(html) if d.get("@type") == "JobPosting")["description"]
    assert "anon-gate-card" in html and "vacancy-apply-form" not in html

    execute("UPDATE listings SET is_active = FALSE WHERE id = :id", {"id": listing_id})  # paused = no longer a job offer
    assert not [d for d in _jsonld(client.get(f"/listings/{listing_id}").text) if d.get("@type") == "JobPosting"]


def test_sitemap_lists_language_versions_and_invoice_maker(client):
    xml = client.get("/sitemap.xml").text
    assert 'xmlns:xhtml="http://www.w3.org/1999/xhtml"' in xml
    assert "<loc>http://testserver/rechnungmaker</loc>" in xml
    assert 'hreflang="en" href="http://testserver/board?lang=en"' in xml

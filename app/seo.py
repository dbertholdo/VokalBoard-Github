"""Search-engine helpers (2026-09-28, HANDOFF 4b).

- Language versions live at ?lang=xx (German, the default, has no param),
  so every page gets a canonical URL and hreflang alternates.
- The public base URL comes from SITE_BASE_URL (behind Railway's proxy
  request.base_url can say http://); falls back to the request.
- JSON-LD (schema.org) for the site and for job listings (Google Jobs).
  Only content a logged-out visitor — i.e. Google — can see goes in.
"""
import json
import os

from fastapi import Request

from app.email_layout import SITE_BASE_URL
from app.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES

_HREFLANG = {"zh": "zh-Hans"}

# Google Search Console "HTML tag" verification: set GOOGLE_SITE_VERIFICATION in
# Railway to the content="..." value Google shows (no code change needed).
GOOGLE_SITE_VERIFICATION = os.getenv("GOOGLE_SITE_VERIFICATION", "").strip()


def public_base(request: Request) -> str:
    return SITE_BASE_URL or str(request.base_url).rstrip("/")


def lang_url(base: str, path: str, lang: str) -> str:
    return f"{base}{path}" + ("" if lang == DEFAULT_LANGUAGE else f"?lang={lang}")


def page_links(request: Request, lang: str) -> dict:
    """Canonical URL (filters/tracking params dropped) + hreflang alternates."""
    base, path = public_base(request), request.url.path
    alternates = [(_HREFLANG.get(code, code), lang_url(base, path, code)) for code in SUPPORTED_LANGUAGES]
    alternates.append(("x-default", f"{base}{path}"))
    return {"canonical": lang_url(base, path, lang), "alternates": alternates}


def _dump(data: dict) -> str:
    # "</" can't end the <script> early; the result is marked safe by the caller.
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def website_jsonld(base: str, description: str) -> str:
    return _dump({
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Organization", "@id": f"{base}/#org", "name": "VokalBoard", "url": f"{base}/",
             "logo": f"{base}/static/img/brand/icon-small-navy.svg"},
            {"@type": "WebSite", "@id": f"{base}/#website", "name": "VokalBoard", "url": f"{base}/",
             "description": description, "publisher": {"@id": f"{base}/#org"}, "inLanguage": list(SUPPORTED_LANGUAGES)},
        ],
    })


def job_posting_jsonld(listing: dict, base: str, description: str) -> str | None:
    """Google Jobs markup for an active "seeking singer/conductor" listing.
    `description` must be text a logged-out visitor sees on the page."""
    if not listing or listing.get("listing_type") not in ("seeking_singer", "seeking_conductor") or not listing.get("is_active"):
        return None
    created = listing.get("created_at")
    data = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": listing["title"],
        "description": description,
        "datePosted": created.date().isoformat() if created else None,
        "employmentType": ["CONTRACTOR", "TEMPORARY"],
        "hiringOrganization": {"@type": "Organization", "name": "VokalBoard", "sameAs": f"{base}/"},
        "jobLocation": {"@type": "Place", "address": {
            "@type": "PostalAddress", "addressLocality": listing.get("city") or None,
            "addressRegion": listing.get("state") or None, "addressCountry": listing.get("country") or None}},
        "url": f"{base}/listings/{listing['id']}",
        "directApply": False,
    }
    event_date = listing.get("event_date")
    if event_date:
        data["validThrough"] = f"{event_date.isoformat()}T23:59:59"
    return _dump({k: v for k, v in data.items() if v is not None})

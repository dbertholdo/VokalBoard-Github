"""Same-site redirect targets. Anything user- or header-controlled (a `next`
form field, the Referer header) goes through here, so the site can never be
used to bounce someone to another domain (open redirect)."""
from urllib.parse import urlsplit


def safe_path(target: str | None, default: str = "/") -> str:
    """`target` if it's a same-site path ("/..."), else `default`. A full URL
    (e.g. a Referer) is reduced to its path + query."""
    target = (target or "").strip()
    if target.startswith(("http://", "https://")):
        parts = urlsplit(target)
        target = parts.path + (f"?{parts.query}" if parts.query else "")
    if not target.startswith("/") or target.startswith("//") or "\\" in target:
        return default
    return target

"""Human visits vs bot traffic (2026-09-28, HANDOFF item 3b).

Human visits: counted only when the page's JS beacon fires (POST /visit),
so crawlers that never run JavaScript don't count; the beacon still skips
bot user agents (headless browsers announce themselves). Same privacy
rules as before: no IP, no identity, 1 visit per session every 12 h.

Bots: never in `site_visits`. Each request from a bot/empty user agent,
or a vulnerability probe (/wp-login.php, /.env ...), adds 1 to a per-day,
per-bot counter in `bot_traffic_daily` (Red Zone → Bot traffic). That
table comes from the 2026-09-28 migration; until it exists bot hits are
simply not recorded.
"""
import hashlib
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy.exc import ProgrammingError

from app.database import execute, fetch_all, fetch_one

VISIT_COOLDOWN = timedelta(hours=12)
# Cookie-free counting (legal check L4, 2026-09-29): nothing is stored in the
# visitor's browser (§ 25 TDDDG). A visitor = hash(daily random salt + IP +
# User-Agent), kept only in this process's memory; the salt is never saved and
# changes every day, so yesterday's hashes can't be linked to anyone.
_salt = {"day": None, "value": b""}
_seen: dict[str, datetime] = {}

# Named bots first (the name shown on the Bot traffic page), then generic tools.
_NAMED_BOTS = (
    "Googlebot", "bingbot", "BingPreview", "DuckDuckBot", "YandexBot", "Baiduspider", "Applebot", "PetalBot",
    "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-Web", "anthropic-ai", "PerplexityBot",
    "CCBot", "Bytespider", "Amazonbot", "meta-externalagent", "facebookexternalhit", "Twitterbot",
    "LinkedInBot", "Slackbot", "Discordbot", "TelegramBot", "WhatsApp", "SemrushBot", "AhrefsBot", "MJ12bot",
    "DotBot", "DataForSeoBot", "SeznamBot", "Sogou", "UptimeRobot", "Pingdom", "Lighthouse", "HeadlessChrome",
    "curl", "Wget", "python-requests", "python-httpx", "aiohttp", "Go-http-client", "okhttp", "Java/",
    "node-fetch", "axios", "Scrapy", "libwww-perl", "PhantomJS",
)
_NAMED_RE = re.compile("|".join(re.escape(n) for n in _NAMED_BOTS), re.IGNORECASE)
_GENERIC_RE = re.compile(r"bot|crawl|spider|slurp|scan|fetch|monitor|preview|headless|http-?client", re.IGNORECASE)
_PROBE_RE = re.compile(r"(wp-|wordpress|xmlrpc|\.php|\.env|\.git|cgi-bin|phpmyadmin|\.aspx?|/vendor/|\.sql|\.bak)", re.IGNORECASE)


def bot_name(user_agent: str | None) -> str | None:
    """Short bot label for this user agent, or None for a normal browser."""
    ua = (user_agent or "").strip()
    if not ua:
        return "(empty user agent)"
    named = _NAMED_RE.search(ua)
    if named:
        found = named.group(0).lower()
        return next(n for n in _NAMED_BOTS if n.lower() == found)
    if _GENERIC_RE.search(ua):
        return "other bot"
    return None


def is_probe(path: str) -> bool:
    """Paths only vulnerability scanners ask for (this site has no PHP/WordPress)."""
    return bool(_PROBE_RE.search(path or ""))


# --- bot counter (tolerates the table missing) ---------------------------

_TABLE = {"ok": None, "checked": 0.0}


def _bot_table_ready() -> bool:
    if _TABLE["ok"] or (_TABLE["checked"] and time.monotonic() - _TABLE["checked"] < 60):
        return bool(_TABLE["ok"])
    row = fetch_one("SELECT to_regclass('bot_traffic_daily') IS NOT NULL AS ok")
    _TABLE.update(ok=bool(row and row["ok"]), checked=time.monotonic())
    return bool(_TABLE["ok"])


def record_bot_hit(name: str) -> None:
    if not _bot_table_ready():
        return
    try:
        execute(
            """INSERT INTO bot_traffic_daily (day, bot_name, hits) VALUES (CURRENT_DATE, :name, 1)
               ON CONFLICT (day, bot_name) DO UPDATE SET hits = bot_traffic_daily.hits + 1""",
            {"name": name[:60]},
        )
    except ProgrammingError:
        _TABLE.update(ok=False, checked=time.monotonic())


def bot_traffic_summary(days: int = 30) -> dict:
    if not _bot_table_ready():
        return {"ready": False, "by_bot": [], "by_day": [], "total": 0}
    by_bot = fetch_all(
        """SELECT bot_name, SUM(hits)::int AS hits FROM bot_traffic_daily
           WHERE day > CURRENT_DATE - :days GROUP BY bot_name ORDER BY hits DESC""",
        {"days": days},
    )
    by_day = fetch_all(
        """SELECT day, SUM(hits)::int AS hits FROM bot_traffic_daily
           WHERE day > CURRENT_DATE - :days GROUP BY day ORDER BY day DESC""",
        {"days": days},
    )
    return {"ready": True, "by_bot": by_bot, "by_day": by_day, "total": sum(r["hits"] for r in by_bot)}


# --- human visits (JS beacon) ------------------------------------------

def _visitor_key(ip: str, user_agent: str, now: datetime) -> str:
    today = now.date()
    if _salt["day"] != today:
        _salt["day"], _salt["value"] = today, secrets.token_bytes(32)
        _seen.clear()  # old hashes are useless with the new salt
    return hashlib.sha256(_salt["value"] + f"{ip}|{user_agent}".encode()).hexdigest()


def record_human_visit(ip: str, user_agent: str, lang: str, referrer_url: str, own_host: str,
                       is_authenticated: bool) -> bool:
    """One visit per visitor (salted IP + browser hash, memory only) every 12 h
    and per day. Returns True if counted."""
    now = datetime.now(timezone.utc)
    key = _visitor_key(ip or "", (user_agent or "")[:300], now)
    last = _seen.get(key)
    if last and now - last <= VISIT_COOLDOWN:
        return False
    _seen[key] = now
    referrer_domain = None
    if referrer_url:
        try:
            host = urlparse(referrer_url).netloc
            if host and host != own_host:
                referrer_domain = host[:255]
        except ValueError:
            referrer_domain = None
    execute(
        "INSERT INTO site_visits (lang, referrer_domain, is_authenticated) VALUES (:lang, :ref, :auth)",
        {"lang": (lang or "")[:5] or None, "ref": referrer_domain, "auth": is_authenticated},
    )
    return True

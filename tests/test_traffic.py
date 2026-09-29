"""Human visits vs bots (2026-09-28, HANDOFF 3b; app/traffic.py)."""
from app.database import execute, fetch_one
from app.traffic import bot_name, is_probe
from tests.test_security import login, register_test_user

BROWSER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"


def _visits():
    return fetch_one("SELECT count(*) AS n FROM site_visits")["n"]


def _bot_hits(name):
    row = fetch_one("SELECT hits FROM bot_traffic_daily WHERE day = CURRENT_DATE AND bot_name = :n", {"n": name})
    return row["hits"] if row else 0


def test_bot_detection():
    assert bot_name("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)") == "Googlebot"
    assert bot_name("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2)") == "GPTBot"
    assert bot_name("python-requests/2.32") == "python-requests"
    assert bot_name("") == "(empty user agent)"
    assert bot_name("SomethingCrawler/1.0") == "other bot"
    assert bot_name(BROWSER) is None
    assert is_probe("/wp-login.php") and is_probe("/.env") and not is_probe("/board")


def test_page_views_no_longer_count_only_the_beacon_does(client):
    client.cookies.clear()
    before = _visits()
    client.get("/", headers={"User-Agent": BROWSER})
    assert _visits() == before  # a plain GET (crawler, HEAD, prefetch) never counts

    assert client.post("/visit", data={"r": "https://www.google.com/search?q=x"}, headers={"User-Agent": BROWSER}).status_code == 204
    assert _visits() == before + 1
    row = fetch_one("SELECT referrer_domain FROM site_visits ORDER BY id DESC LIMIT 1")
    assert row["referrer_domain"] == "www.google.com"
    client.post("/visit", data={"r": ""}, headers={"User-Agent": BROWSER})
    assert _visits() == before + 1  # 1 per visitor every 12 h
    assert "set-cookie" not in {k.lower() for k in client.post("/visit", data={"r": ""}, headers={"User-Agent": BROWSER}).headers}


def test_bots_go_to_their_own_counter_never_to_visits(client):
    before, gbot = _visits(), _bot_hits("Googlebot")
    client.get("/", headers={"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"})
    client.post("/visit", data={"r": ""}, headers={"User-Agent": "Mozilla/5.0 HeadlessChrome/140.0"})
    assert _bot_hits("Googlebot") == gbot + 1
    assert _visits() == before

    probes = _bot_hits("scanner (probe paths)")
    client.get("/wp-login.php", headers={"User-Agent": BROWSER})
    assert _bot_hits("scanner (probe paths)") == probes + 1


def test_bot_traffic_page_is_red_zone_only(client):
    user_id, email, password = register_test_user(client, full_name="Bot Page Admin")
    execute("UPDATE users SET email_verified = TRUE, role_level = 2 WHERE id = :id", {"id": user_id})
    login(client, email, password)
    assert client.get("/financeiro/bots", follow_redirects=False).status_code == 303  # level 2 is not enough
    execute("UPDATE users SET role_level = 3 WHERE id = :id", {"id": user_id})
    page = client.get("/financeiro/bots")
    assert page.status_code == 200 and "Bot traffic" in page.text

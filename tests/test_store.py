"""Notas Store (2026-09-28, docs/specs/STORE.md): prices and discounts,
product effects, verification review, sales stats, admin pricing. See app/store.py."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app import store
from app.database import execute, execute_returning, fetch_all, fetch_one
from app.notas_wallet import credit_notas, get_credit_balance
from tests.test_security import extract_csrf, login, register_test_user


def _user(client, notas=50, old=False):
    _reset_discounts()  # prices below assume no admin discount is running
    user_id, email, password = register_test_user(client, full_name="Store Test User")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    if old:  # welcome year over
        execute("UPDATE users SET created_at = now() - interval '400 days' WHERE id = :id", {"id": user_id})
    if notas:
        credit_notas(user_id, notas, "sectest_seed")
    return user_id, email, password


def _admin(client):
    user_id, email, password = _user(client, notas=0)
    execute("UPDATE users SET role_level = 2 WHERE id = :id", {"id": user_id})
    login(client, email, password)
    return user_id


def _listing(user_id):
    return execute_returning(
        """INSERT INTO listings (author_id, listing_type, title, description, state, country)
           VALUES (:a, 'seeking_singer', 'Store Test Listing', 'desc', 'Bayern', 'DE') RETURNING id""",
        {"a": user_id},
    )["id"]


def _reset_discounts():
    execute("UPDATE shop_catalog_items SET discount_percent = NULL, discount_from = NULL, discount_until = NULL")


def _item(key, **extra):
    return {"item_key": key, "cost": Decimal("5"), **extra}


# --- prices -----------------------------------------------------------------------

def test_welcome_discount_halves_price_except_subscription():
    now = datetime.now(timezone.utc)
    p = store.price_for(_item("super_user_1y"), now)
    assert (p["price"], p["percent"], p["kind"]) == (Decimal("2.50"), 50, "welcome")
    assert store.price_for(_item("subscription_1y"), now)["price"] == Decimal("5.00")
    assert store.price_for(_item("super_user_1y"), now - timedelta(days=400))["price"] == Decimal("5.00")


def test_bigger_discount_wins():
    now = datetime.now(timezone.utc)
    p = store.price_for(_item("super_user_1y", discount_percent=70), now)
    assert (p["price"], p["kind"]) == (Decimal("1.50"), "admin")
    p = store.price_for(_item("super_user_1y", discount_percent=20), now)
    assert (p["price"], p["kind"]) == (Decimal("2.50"), "welcome")


def test_admin_discount_window_start_and_end():
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=400)
    assert store.price_for(_item("x", discount_percent=20, discount_from=now + timedelta(days=1)), old)["percent"] == 0
    assert store.price_for(_item("x", discount_percent=20, discount_until=now - timedelta(seconds=1)), old)["percent"] == 0
    running = store.price_for(_item("x", discount_percent=20, discount_from=now - timedelta(days=1),
                                    discount_until=now + timedelta(days=1)), old)
    assert (running["price"], running["kind"]) == (Decimal("4.00"), "admin")


# --- buying ---------------------------------------------------------------------

def test_super_user_and_people_top_extend_dates(client):
    user_id, _, _ = _user(client)
    assert store.buy(user_id, "super_user_1y", "t1")[0] == "bought"
    assert store.buy(user_id, "people_top_30d", "t2")[0] == "bought"
    me = fetch_one("SELECT super_user_until, people_top_until FROM users WHERE id = :id", {"id": user_id})
    now = datetime.now(timezone.utc)
    assert me["super_user_until"] > now + timedelta(days=364)
    assert now + timedelta(days=29) < me["people_top_until"] < now + timedelta(days=31)
    assert get_credit_balance(user_id) == Decimal("50") - Decimal("2.50") - Decimal("1.00")


def test_double_click_is_a_replay_not_a_second_charge(client):
    user_id, _, _ = _user(client)
    assert store.buy(user_id, "supporter_badge", "same")[0] == "bought"
    assert store.buy(user_id, "supporter_badge", "same")[0] == "replay"
    assert store.buy(user_id, "supporter_badge", "other")[0] == "owned"
    assert get_credit_balance(user_id) == Decimal("47.50")


def test_insufficient_balance(client):
    user_id, _, _ = _user(client, notas=1, old=True)
    assert store.buy(user_id, "super_user_1y", "t")[0] == "insufficient"
    assert get_credit_balance(user_id) == Decimal("1")


def test_invoice_pack_adds_credits(client):
    user_id, _, _ = _user(client)
    store.buy(user_id, "invoice_pack_5", "a")
    store.buy(user_id, "invoice_single", "b")
    total = fetch_one("SELECT sum(delta) AS n FROM purchased_invoice_credits WHERE user_id = :u", {"u": user_id})["n"]
    assert total == 6


def test_subscription_is_365_days_full_price(client):
    user_id, _, _ = _user(client)
    assert store.buy(user_id, "subscription_1y", "s")[0] == "bought"
    sub = fetch_one("SELECT currency, price_paid_cents, expires_at FROM subscriptions WHERE user_id = :u", {"u": user_id})
    assert (sub["currency"], sub["price_paid_cents"]) == ("NTS", 0)
    assert sub["expires_at"] > datetime.now(timezone.utc) + timedelta(days=364)
    assert get_credit_balance(user_id) == Decimal("35")  # no welcome discount


def test_featured_listing_needs_own_listing_and_is_pinned(client):
    user_id, _, _ = _user(client)
    other_id, _, _ = _user(client, notas=0)
    foreign = _listing(other_id)
    assert store.buy(user_id, "featured_listing_30d", "f1", listing_id=foreign)[0] == "invalid"
    mine = _listing(user_id)
    assert store.buy(user_id, "featured_listing_30d", "f2", listing_id=mine)[0] == "bought"
    execute("DELETE FROM featured_listings WHERE listing_id <> :l", {"l": mine})
    assert store.pinned_featured_ids("l.id = :l", {"l": mine}) == [mine]


def test_people_top_sorts_first(client):
    user_id, _, _ = _user(client)
    store.buy(user_id, "people_top_30d", "p")
    rows = fetch_all(f"SELECT u.id FROM users u ORDER BY {store.people_top_order_sql('u')} u.id LIMIT 50")
    top = fetch_all("SELECT id FROM users WHERE people_top_until > now()")
    assert user_id in [r["id"] for r in rows[:len(top)]]


# --- verification -----------------------------------------------------------------

def test_verified_badge_approve_and_reject_refund(client):
    admin_id = _admin(client)
    user_id, _, _ = _user(client, old=True)
    assert store.buy(user_id, "verified_badge", "v0", proof_url="not a link")[0] == "invalid"
    assert store.buy(user_id, "verified_badge", "v1", proof_url="https://example.org/me")[0] == "bought"
    assert store.buy(user_id, "verified_badge", "v2", proof_url="https://example.org/me")[0] == "owned"  # pending
    assert get_credit_balance(user_id) == Decimal("45")
    req = fetch_one("SELECT id FROM verification_requests WHERE user_id = :u", {"u": user_id})
    assert store.review_verification(req["id"], admin_id, approve=False) == user_id
    assert get_credit_balance(user_id) == Decimal("50")
    assert store.review_verification(req["id"], admin_id, approve=True) is None  # already reviewed

    assert store.buy(user_id, "verified_badge", "v3", proof_url="https://example.org/me")[0] == "bought"
    req2 = fetch_one("SELECT id FROM verification_requests WHERE user_id = :u AND status = 'pending'", {"u": user_id})
    store.review_verification(req2["id"], admin_id, approve=True)
    assert fetch_one("SELECT verified_at FROM users WHERE id = :u", {"u": user_id})["verified_at"] is not None
    assert fetch_one(
        "SELECT 1 AS x FROM notifications WHERE user_id = :u AND title_key = 'notification_verified_approved'",
        {"u": user_id},
    )


def test_sales_stats_count_purchases_not_refunds(client):
    admin_id = _admin(client)
    user_id, _, _ = _user(client, old=True)
    before = {r["item_key"]: r["sold"] for r in store.sales_stats()}
    store.buy(user_id, "verified_badge", "s1", proof_url="https://example.org/x")
    req = fetch_one("SELECT id FROM verification_requests WHERE user_id = :u", {"u": user_id})
    store.review_verification(req["id"], admin_id, approve=False)
    store.buy(user_id, "supporter_badge", "s2")
    after = {r["item_key"]: r["sold"] for r in store.sales_stats(sort="sold_asc")}
    assert after["verified_badge"] == before["verified_badge"]
    assert after["supporter_badge"] == before["supporter_badge"] + 1


# --- routes -----------------------------------------------------------------------

def test_store_page_and_buy_route(client):
    user_id, email, password = _user(client)
    login(client, email, password)
    r = client.get("/store")
    assert r.status_code == 200
    r = client.post("/store/buy", data={"item_key": "supporter_badge", "csrf_token": extract_csrf(r.text), "token": "r1"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert fetch_one("SELECT supporter_since FROM users WHERE id = :u", {"u": user_id})["supporter_since"]


def test_notas_redeem_redirects_store_products(client):
    _, email, password = _user(client)
    login(client, email, password)
    token = extract_csrf(client.get("/notas").text)
    r = client.post("/notas/redeem", data={"item_key": "super_user_1y", "csrf_token": token}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/store")


def test_admin_pricing_route_sets_window_and_rejects_bad_dates(client):
    admin_id = _admin(client)
    item_id = fetch_one("SELECT id FROM shop_catalog_items WHERE item_key = 'supporter_badge'")["id"]
    token = extract_csrf(client.get("/admin/loja").text)
    url = f"/admin/loja/catalog/{item_id}/pricing"
    try:
        r = client.post(url, data={"cost": "6", "discount_percent": "30", "discount_from": "2026-10-10",
                                   "discount_until": "2026-10-01", "csrf_token": token}, follow_redirects=False)
        assert "error=invalid_pricing" in r.headers["location"]
        r = client.post(url, data={"cost": "6", "discount_percent": "30", "discount_from": "2026-10-01",
                                   "discount_until": "2026-10-10", "csrf_token": token}, follow_redirects=False)
        assert "error" not in r.headers["location"]
        row = fetch_one("SELECT cost, discount_percent, discount_from, discount_until FROM shop_catalog_items WHERE id = :i",
                        {"i": item_id})
        assert (row["cost"], row["discount_percent"]) == (Decimal("6"), 30)
        assert row["discount_from"] < row["discount_until"]
        assert fetch_one("SELECT 1 AS x FROM audit_log WHERE actor_user_id = :a AND action = 'store_pricing'", {"a": admin_id})
    finally:
        execute("UPDATE shop_catalog_items SET cost = 5 WHERE id = :i", {"i": item_id})
        _reset_discounts()

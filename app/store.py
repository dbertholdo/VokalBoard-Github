"""Notas Store (2026-09-28, docs/specs/STORE.md).

- Prices: the catalogue row (`shop_catalog_items.cost`) minus the bigger of
  (a) the welcome discount: −50% during the first 365 days after
  registration, on everything except the 1-year subscription, and
  (b) the item's admin discount (`discount_percent`, optional `discount_until`).
- Buying (`buy`) debits the Notas and applies the product's effect in ONE
  transaction, double-click safe (idempotency key per rendered form).
- Effects live here, one small function per product; the frame/badges/pins
  are read through the SQL fragments below by the pages that show them.

Tolerates the 2026-09-28 store migration missing: `ready()` is False, the new
products don't exist yet (they're inserted by the migration), the fragments
return FALSE and prices ignore admin discounts.
"""
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import text

from app.database import engine, fetch_all, fetch_one
from app.schema_features import has_columns

WELCOME_DISCOUNT_PERCENT = 50
WELCOME_DAYS = 365
NO_WELCOME_DISCOUNT = frozenset({"subscription_1y"})
FEATURED_PINNED_MAX = 3
PROOF_URL_MAX = 500
PROOF_NOTE_MAX = 1000

# key -> (category, days of effect or None). Order = order on /store.
PRODUCTS = {
    "super_user_1y": ("visibility", 365),
    "featured_listing_30d": ("visibility", 30),
    "people_top_30d": ("visibility", 30),
    "invoice_single": ("tools", None),
    "invoice_pack_5": ("tools", None),
    "verified_badge": ("tools", None),
    "supporter_badge": ("support", None),
    "subscription_1y": ("support", 365),
}
CATEGORIES = ("visibility", "tools", "support")
URGENT_KEY = "urgent_listing"  # bought on the listing form (app/urgency.py), priced here
URGENT_FALLBACK_COST = Decimal("1")
INVOICE_CREDITS = {"invoice_single": 1, "invoice_pack_5": 5}


def ready() -> bool:
    return has_columns("shop_catalog_items", "discount_percent", "discount_from", "discount_until") and has_columns(
        "users", "super_user_until", "people_top_until", "verified_at", "supporter_since")


# --- SQL fragments for pages that show the frame / badges / pins ----------

def super_user_sql(alias: str = "u") -> str:
    return f"({alias}.super_user_until IS NOT NULL AND {alias}.super_user_until > now())" if ready() else "FALSE"


def verified_sql(alias: str = "u") -> str:
    return f"({alias}.verified_at IS NOT NULL)" if ready() else "FALSE"


def supporter_sql(alias: str = "u") -> str:
    return f"({alias}.supporter_since IS NOT NULL)" if ready() else "FALSE"


def people_top_order_sql(alias: str = "u") -> str:
    """ORDER BY prefix: people with an active "Top of People search" first."""
    if not ready():
        return ""
    return f"({alias}.people_top_until IS NOT NULL AND {alias}.people_top_until > now()) DESC, {alias}.people_top_until ASC NULLS LAST, "


# --- prices ------------------------------------------------------------------

def _money(value) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def welcome_until(created_at) -> datetime | None:
    """End of the welcome discount for an account, or None if it's over."""
    if not created_at:
        return None
    ends = created_at + timedelta(days=WELCOME_DAYS)
    return ends if ends > datetime.now(timezone.utc) else None


def price_for(item: dict, user_created_at) -> dict:
    """{"base", "price", "percent", "kind" ('welcome'|'admin'|None), "welcome_until", "admin_until"}."""
    base = _money(item["cost"])
    now = datetime.now(timezone.utc)
    welcome = welcome_until(user_created_at) if item["item_key"] not in NO_WELCOME_DISCOUNT else None
    admin_percent = item.get("discount_percent") or 0
    admin_from, admin_until = item.get("discount_from"), item.get("discount_until")
    if (admin_until and admin_until <= now) or (admin_from and admin_from > now):
        admin_percent = 0  # outside the discount window (Daniel: start + end date)
    candidates = []
    if welcome:
        candidates.append((WELCOME_DISCOUNT_PERCENT, "welcome"))
    if admin_percent:
        candidates.append((int(admin_percent), "admin"))
    percent, kind = max(candidates) if candidates else (0, None)
    price = _money(base * (100 - percent) / 100) if percent else base
    return {"base": base, "price": price, "percent": percent, "kind": kind,
            "welcome_until": welcome, "admin_until": admin_until if kind == "admin" else None}


def _item_row(conn, key: str, active_only: bool = True):
    discount_cols = (", discount_percent, discount_from, discount_until" if ready()
                     else ", NULL AS discount_percent, NULL AS discount_from, NULL AS discount_until")
    sql = f"SELECT item_key, cost, active, title, description, icon{discount_cols} FROM shop_catalog_items WHERE item_key = :key"  # nosec B608 - fixed column lists
    if active_only:
        sql += " AND active = TRUE"
    return conn.execute(text(sql), {"key": key}).mappings().first()


def _created_at(conn, user_id: int):
    return conn.execute(text("SELECT created_at FROM users WHERE id = :id"), {"id": user_id}).scalar_one_or_none()


def urgent_price(user_id: int) -> Decimal:
    """What marking a listing urgent costs this person (after the free weekly token)."""
    with engine.connect() as conn:
        item = _item_row(conn, URGENT_KEY)
        if not item:
            return URGENT_FALLBACK_COST
        return price_for(dict(item), _created_at(conn, user_id))["price"]


# --- the store page ------------------------------------------------------------

def catalog_for(user_id: int) -> list[dict]:
    """Active products for /store with this person's price and current status."""
    if not ready():
        return []
    keys = list(PRODUCTS)
    rows = fetch_all(
        "SELECT item_key, cost, title, description, icon, discount_percent, discount_from, discount_until "
        "FROM shop_catalog_items WHERE active = TRUE AND item_key = ANY(:keys)",
        {"keys": keys},
    )
    me = fetch_one(
        """SELECT created_at, super_user_until, people_top_until, verified_at, supporter_since,
                  (SELECT status FROM verification_requests v WHERE v.user_id = u.id
                   ORDER BY v.id DESC LIMIT 1) AS verification_status,
                  (SELECT max(expires_at) FROM subscriptions s WHERE s.user_id = u.id AND s.is_active = TRUE) AS subscription_until
           FROM users u WHERE u.id = :id""",
        {"id": user_id},
    )
    now = datetime.now(timezone.utc)

    def active(ts):
        return ts if ts and ts > now else None

    status = {
        "super_user_1y": {"until": active(me["super_user_until"])},
        "people_top_30d": {"until": active(me["people_top_until"])},
        "subscription_1y": {"until": active(me["subscription_until"])},
        "verified_badge": {"owned": bool(me["verified_at"]), "pending": me["verification_status"] == "pending"},
        "supporter_badge": {"owned": bool(me["supporter_since"])},
    }
    by_key = {r["item_key"]: dict(r) for r in rows}
    items = []
    for key in keys:
        if key not in by_key:
            continue
        row = by_key[key]
        category, days = PRODUCTS[key]
        items.append({**row, "key": key, "category": category, "days": days,
                      "pricing": price_for(row, me["created_at"]), **status.get(key, {})})
    return items


def my_featurable_listings(user_id: int) -> list[dict]:
    """The person's active listings, with a running feature if any."""
    feature_join = "LEFT JOIN featured_listings f ON f.listing_id = l.id AND f.featured_until > now()" if ready() else ""
    feature_col = ", f.featured_until" if ready() else ", NULL AS featured_until"
    return fetch_all(
        f"""SELECT l.id, l.title{feature_col} FROM visible_listings l {feature_join}
            WHERE l.author_id = :id AND l.is_active = TRUE ORDER BY l.created_at DESC""",  # nosec B608 - fixed fragments
        {"id": user_id},
    )


# --- buying --------------------------------------------------------------------

def _extend(conn, column: str, user_id: int, days: int) -> None:
    conn.execute(
        text(f"UPDATE users SET {column} = GREATEST(COALESCE({column}, now()), now()) + make_interval(days => :d) WHERE id = :id"),  # nosec B608 - column from a fixed set
        {"d": days, "id": user_id},
    )


def buy(user_id: int, key: str, token: str = "", *, listing_id: int | None = None,
        proof_url: str = "", note: str = "") -> tuple[str, dict | None]:
    """Returns (status, info). status: 'bought', 'replay', 'not_found', 'insufficient',
    'invalid' (missing/foreign listing or proof link), 'owned' (badge already there / pending)."""
    from app.notas_wallet import debit_in_tx  # notas_wallet imports shop_catalog, keep import local

    if key not in PRODUCTS or not ready():
        return "not_found", None
    proof_url = (proof_url or "").strip()
    if key == "verified_badge" and not proof_url.lower().startswith(("https://", "http://")):
        return "invalid", None
    idem = f"store_{key}_{token}" if token else None
    with engine.begin() as conn:
        item = _item_row(conn, key)
        if not item:
            return "not_found", None
        item = dict(item)
        me = conn.execute(
            text("SELECT created_at, verified_at, supporter_since FROM users WHERE id = :id FOR UPDATE"),
            {"id": user_id},
        ).mappings().first()
        if not me:
            return "not_found", None
        if idem and conn.execute(
            text("SELECT 1 FROM credit_ledger WHERE user_id = :u AND idempotency_key = :k"), {"u": user_id, "k": idem}
        ).first():
            return "replay", item
        if key == "supporter_badge" and me["supporter_since"]:
            return "owned", item
        if key == "verified_badge" and (me["verified_at"] or conn.execute(
            text("SELECT 1 FROM verification_requests WHERE user_id = :u AND status = 'pending'"), {"u": user_id}
        ).first()):
            return "owned", item
        if key == "featured_listing_30d":
            own = conn.execute(
                text("SELECT 1 FROM visible_listings WHERE id = :l AND author_id = :u AND is_active = TRUE"),
                {"l": listing_id or 0, "u": user_id},
            ).first()
            if not own:
                return "invalid", item

        pricing = price_for(item, me["created_at"])
        note_txt = f"{pricing['kind']} -{pricing['percent']}%" if pricing["kind"] else None
        if pricing["price"] > 0:
            if not debit_in_tx(conn, user_id, pricing["price"], f"redeem_{key}", reference_id=listing_id,
                               idempotency_key=idem, admin_note=note_txt):
                return "insufficient", item
        debit_id = conn.execute(
            text("SELECT id FROM credit_ledger WHERE user_id = :u AND reason = :r ORDER BY id DESC LIMIT 1"),
            {"u": user_id, "r": f"redeem_{key}"},
        ).scalar_one_or_none()

        # --- effects ---
        if key == "super_user_1y":
            _extend(conn, "super_user_until", user_id, 365)
        elif key == "people_top_30d":
            _extend(conn, "people_top_until", user_id, 30)
        elif key == "featured_listing_30d":
            conn.execute(
                text("""INSERT INTO featured_listings (listing_id, featured_until) VALUES (:l, now() + interval '30 days')
                        ON CONFLICT (listing_id) DO UPDATE SET featured_until =
                            GREATEST(featured_listings.featured_until, now()) + interval '30 days'"""),
                {"l": listing_id},
            )
        elif key in INVOICE_CREDITS:
            conn.execute(
                text("INSERT INTO purchased_invoice_credits (user_id, delta, reason) VALUES (:u, :n, :r)"),
                {"u": user_id, "n": INVOICE_CREDITS[key], "r": f"store_{key}"},
            )
        elif key == "verified_badge":
            conn.execute(
                text("""INSERT INTO verification_requests (user_id, proof_url, note, debit_id)
                        VALUES (:u, :url, :note, :d)"""),
                {"u": user_id, "url": proof_url[:PROOF_URL_MAX], "note": (note or "").strip()[:PROOF_NOTE_MAX] or None,
                 "d": debit_id},
            )
        elif key == "supporter_badge":
            conn.execute(text("UPDATE users SET supporter_since = now() WHERE id = :id"), {"id": user_id})
        elif key == "subscription_1y":
            start = conn.execute(
                text("SELECT GREATEST(COALESCE(max(expires_at), now()), now()) FROM subscriptions "
                     "WHERE user_id = :u AND is_active = TRUE"), {"u": user_id},
            ).scalar_one()
            country = conn.execute(text("SELECT country FROM users WHERE id = :u"), {"u": user_id}).scalar_one_or_none()
            # Paid in Notas: no money changes hands here, so price_paid_cents = 0
            # (the Notas spent are in credit_ledger); currency 'NTS' marks it.
            conn.execute(
                text("""INSERT INTO subscriptions (user_id, price_paid_cents, currency, country, started_at, expires_at)
                        VALUES (:u, 0, 'NTS', :c, now(), :start + interval '365 days')"""),
                {"u": user_id, "c": country, "start": start},
            )
    return "bought", {**item, "pricing": pricing}


# --- admin ---------------------------------------------------------------------

def sales_stats(days: int | None = None, sort: str = "sold_desc") -> list[dict]:
    """Per item: times sold, Notas collected, buyers, last sale. Purchases only
    (admin grants have delta 0; refunded verification debits don't count)."""
    order = {
        "sold_desc": "sold DESC, notas DESC", "sold_asc": "sold ASC, notas ASC",
        "notas_desc": "notas DESC, sold DESC", "notas_asc": "notas ASC, sold ASC",
    }.get(sort, "sold DESC, notas DESC")
    since = "AND l.created_at > now() - make_interval(days => :days)" if days else ""
    rows = fetch_all(
        f"""
        SELECT c.item_key, c.cost, c.active, c.title,
               count(l.id) AS sold, COALESCE(-sum(l.delta), 0) AS notas,
               count(DISTINCT l.user_id) AS buyers, max(l.created_at) AS last_sale
        FROM shop_catalog_items c
        LEFT JOIN credit_ledger l
          ON l.delta < 0 {since}
         AND l.reason = CASE WHEN c.item_key = 'urgent_listing' THEN 'urgency_purchase' ELSE 'redeem_' || c.item_key END
         AND NOT EXISTS (SELECT 1 FROM credit_ledger r WHERE r.reason = 'store_refund' AND r.reference_id = l.id)
        GROUP BY c.item_key, c.cost, c.active, c.title
        ORDER BY {order}, c.item_key
        """,  # nosec B608 - `order` from the fixed dict above, `since` a fixed fragment
        {"days": days} if days else {},
    )
    return rows


def pending_verifications() -> list[dict]:
    if not ready():
        return []
    return fetch_all(
        """SELECT v.id, v.user_id, v.proof_url, v.note, v.created_at, u.full_name, u.role, u.city
           FROM verification_requests v JOIN users u ON u.id = v.user_id
           WHERE v.status = 'pending' ORDER BY v.created_at""")


def count_pending_verifications() -> int:
    if not ready():
        return 0
    return fetch_one("SELECT count(*) AS n FROM verification_requests WHERE status = 'pending'")["n"]


def review_verification(request_id: int, admin_id: int, approve: bool) -> int | None:
    """Approve → badge; reject → Notas refunded. Returns the user id, or None."""
    from app.notas_wallet import credit_in_tx

    with engine.begin() as conn:
        req = conn.execute(
            text("""UPDATE verification_requests SET status = :s, reviewed_at = now(), reviewed_by = :a
                    WHERE id = :id AND status = 'pending' RETURNING user_id, debit_id"""),
            {"s": "approved" if approve else "rejected", "a": admin_id, "id": request_id},
        ).mappings().first()
        if not req:
            return None
        if approve:
            conn.execute(text("UPDATE users SET verified_at = now() WHERE id = :u"), {"u": req["user_id"]})
        elif req["debit_id"]:
            paid = conn.execute(text("SELECT -delta FROM credit_ledger WHERE id = :d"), {"d": req["debit_id"]}).scalar_one_or_none()
            if paid and paid > 0:
                credit_in_tx(conn, req["user_id"], paid, "store_refund", reference_id=req["debit_id"],
                             idempotency_key=f"store_refund:{req['debit_id']}")
    from app.notification_center import create_notification
    notify = "notification_verified_approved" if approve else "notification_verified_rejected"
    create_notification(req["user_id"], "loja_redeemed", notify, {}, link_url="/store")
    return req["user_id"]


def pinned_featured_ids(where_clause: str, params: dict) -> list[int]:
    """Up to 3 random featured listings among those matching the board filters."""
    if not ready():
        return []
    rows = fetch_all(
        f"""SELECT l.id FROM visible_listings l
            JOIN featured_listings f ON f.listing_id = l.id AND f.featured_until > now()
            WHERE {where_clause} ORDER BY random() LIMIT {FEATURED_PINNED_MAX}""",  # nosec B608 - board's fixed where fragments; values in params
        params,
    )
    return [r["id"] for r in rows]

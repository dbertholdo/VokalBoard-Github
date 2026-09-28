"""
Buying Notas with Stripe (Notas v2 — N5, docs/specs/NOTAS_V2.md).

Flow: /notas/comprar-notas shows fixed bundles → the user ticks the
Terms + immediate-delivery waiver checkbox → we create a Stripe Checkout
Session with the price set HERE (price_data — never from the browser)
and redirect. Stripe's webhook (/webhooks/stripe) then credits PURCHASED
Notas exactly once, keyed by the PaymentIntent id. Card/bank data never
reaches VokalBoard; consent proof lives in the PaymentIntent metadata at
Stripe (docs/specs/NOTAS_V2.md D7 — no payment data kept here).

Availability: Stripe keys configured AND Capitalism Mode on (God Mode may
test while it's off — same rule as every other price on the site).

Env: STRIPE_SECRET_KEY (restricted key), STRIPE_WEBHOOK_SECRET.
Daniel is a Kleinunternehmer (§ 19 UStG): no VAT, Stripe Tax off.
"""
import json
import logging
import os
from datetime import datetime, timezone
from decimal import ROUND_DOWN, Decimal

from sqlalchemy import text

from app.database import engine, fetch_one
from app.financial_settings import is_capitalismo_mode_enabled
from app.notas_wallet import PURCHASED, credit_in_tx, credit_notas, debit_in_tx
from app.permissions import LEVEL_GOD

log = logging.getLogger(__name__)

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# 1 Nota = 1 EUR / 1 CHF (CLAUDE.md §1). Amounts in cents. Change prices
# here only — announce changes 4 weeks ahead (Terms §3.4).
BUNDLES = {
    "notas_10": {"notas": 10, "cents": 1000},
    "notas_25": {"notas": 25, "cents": 2500},
    "notas_50": {"notas": 50, "cents": 5000},
}
VAT_NOTE = "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet."
TERMS_VERSION = "2026-09-26"
WAIVER_VERSION = "v1.0_2026-09-26_digital_content_waiver"
_STRIPE_LOCALES = {"de", "en", "fr", "it", "pt", "es", "zh", "ko", "ro", "tr"}


def currency_for(user: dict) -> str:
    return "chf" if user.get("country") == "CH" else "eur"


def purchases_available(user: dict | None) -> bool:
    if not STRIPE_SECRET_KEY or not user:
        return False
    return is_capitalismo_mode_enabled() or (user.get("role_level") or 0) >= LEVEL_GOD


def create_checkout_url(user: dict, bundle_key: str, lang: str, base_url: str) -> str:
    """Creates a Checkout Session and returns its URL. Raises KeyError for
    an unknown bundle; Stripe errors propagate to the caller."""
    import stripe

    bundle = BUNDLES[bundle_key]
    currency = currency_for(user)
    metadata = {
        "user_id": str(user["id"]), "bundle": bundle_key, "notas": str(bundle["notas"]),
        "terms_version": TERMS_VERSION, "waiver_version": WAIVER_VERSION, "waiver_accepted": "true",
        "waiver_accepted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    session = stripe.checkout.Session.create(
        api_key=STRIPE_SECRET_KEY,
        mode="payment",
        line_items=[{
            "quantity": 1,
            "price_data": {
                "currency": currency,
                "unit_amount": bundle["cents"],
                "product_data": {"name": f"{bundle['notas']} Notas — VokalBoard"},
            },
        }],
        customer_email=user["email"],
        client_reference_id=str(user["id"]),
        metadata=metadata,
        payment_intent_data={"metadata": metadata},
        invoice_creation={"enabled": True, "invoice_data": {"footer": VAT_NOTE, "metadata": {"user_id": str(user["id"])}}},
        locale=lang if lang in _STRIPE_LOCALES else "auto",
        success_url=f"{base_url}/notas?purchase=success",
        cancel_url=f"{base_url}/notas/comprar-notas?cancelled=1",
    )
    return session.url


def verify_event(payload: bytes, signature: str) -> dict:
    """Verifies the Stripe signature and returns the event as a plain dict
    (stripe-python objects are not dicts since v15). Raises ValueError."""
    import stripe

    if not STRIPE_WEBHOOK_SECRET:
        raise ValueError("webhook secret not configured")
    try:
        stripe.Webhook.construct_event(payload, signature, STRIPE_WEBHOOK_SECRET)
    except (stripe.SignatureVerificationError, ValueError) as exc:
        raise ValueError(str(exc)) from exc
    return json.loads(payload)


# ---------------------------------------------------------------------------
# Webhook handling — every branch is idempotent (keys on the ledger).
# ---------------------------------------------------------------------------

def _purchase_row(payment_intent: str):
    return fetch_one(
        "SELECT user_id, delta FROM credit_ledger WHERE idempotency_key = :k",
        {"k": f"stripe_purchase:{payment_intent}"},
    )


def _removed_so_far(conn, user_id: int, prefix: str) -> Decimal:
    """Sum already removed for this purchase. Call it AFTER locking the user row
    in the same transaction: two refund/dispute events arriving at once used to
    both see "0 removed" and debit twice."""
    n = conn.execute(
        text("SELECT COALESCE(SUM(-delta), 0) FROM credit_ledger WHERE user_id = :u AND idempotency_key LIKE :p"),
        {"u": user_id, "p": f"{prefix}%"},
    ).scalar_one()
    return Decimal(n)


def _lock_user(conn, user_id: int) -> None:
    conn.execute(text("SELECT 1 FROM users WHERE id = :id FOR UPDATE"), {"id": user_id})


def _handle_paid_session(session) -> str:
    if session.get("payment_status") != "paid":
        return "not_paid_yet"
    meta = session.get("metadata") or {}
    if not {"user_id", "notas"} <= set(meta) or not session.get("payment_intent"):
        # Not from our checkout (e.g. a payment link made in the Stripe dashboard):
        # acknowledge it instead of a 500 that Stripe would retry for days.
        log.warning("Stripe session without VokalBoard metadata — ignored")
        return "not_ours"
    user_id, notas, payment_intent = int(meta["user_id"]), Decimal(meta["notas"]), session["payment_intent"]
    if not fetch_one("SELECT id FROM users WHERE id = :id", {"id": user_id}):
        log.warning("Paid Stripe session for missing user id %s — refund manually in Stripe", user_id)
        return "user_missing"
    credited = credit_notas(
        user_id, notas, "purchase", idempotency_key=f"stripe_purchase:{payment_intent}", category=PURCHASED,
    )
    return "credited" if credited else "duplicate"


def _handle_refund(charge) -> str:
    purchase = _purchase_row(charge["payment_intent"])
    if not purchase or not charge.get("amount"):
        return "unknown_purchase"
    notas = purchase["delta"]
    target = (notas * Decimal(charge["amount_refunded"]) / Decimal(charge["amount"])).quantize(Decimal("0.01"), ROUND_DOWN)
    prefix = f"stripe_refund:{charge['payment_intent']}:"
    with engine.begin() as conn:
        _lock_user(conn, purchase["user_id"])
        remove = target - _removed_so_far(conn, purchase["user_id"], prefix)
        if remove <= 0:
            return "nothing_to_remove"
        debit_in_tx(conn, purchase["user_id"], remove, "stripe_refund",
                    idempotency_key=f"{prefix}{charge['amount_refunded']}", allow_negative=True)
    return "debited"


def _handle_dispute_created(dispute) -> str:
    purchase = _purchase_row(dispute["payment_intent"])
    if not purchase:
        return "unknown_purchase"
    with engine.begin() as conn:
        _lock_user(conn, purchase["user_id"])
        refunded = _removed_so_far(conn, purchase["user_id"], f"stripe_refund:{dispute['payment_intent']}:")
        remove = purchase["delta"] - refunded
        if remove <= 0:
            return "nothing_to_remove"
        debit_in_tx(conn, purchase["user_id"], remove, "stripe_dispute",
                    idempotency_key=f"stripe_dispute:{dispute['id']}", allow_negative=True)
    return "debited"


def _handle_dispute_closed(dispute) -> str:
    if dispute.get("status") != "won":
        return "kept_debit"
    purchase = _purchase_row(dispute["payment_intent"])
    if not purchase:
        return "unknown_purchase"
    with engine.begin() as conn:
        _lock_user(conn, purchase["user_id"])
        removed = _removed_so_far(conn, purchase["user_id"], f"stripe_dispute:{dispute['id']}")
        if removed <= 0:
            return "nothing_to_restore"
        credit_in_tx(conn, purchase["user_id"], removed, "stripe_dispute_won", category=PURCHASED,
                     idempotency_key=f"stripe_dispute_won:{dispute['id']}")
    return "restored"


_HANDLERS = {
    "checkout.session.completed": _handle_paid_session,
    "checkout.session.async_payment_succeeded": _handle_paid_session,
    "charge.refunded": _handle_refund,
    "charge.dispute.created": _handle_dispute_created,
    "charge.dispute.closed": _handle_dispute_closed,
}


def handle_event(event) -> str:
    handler = _HANDLERS.get(event["type"])
    if handler is None:
        return "ignored"
    return handler(event["data"]["object"])

"""Notas Store pages (2026-09-28, docs/specs/STORE.md; rules in app/store.py)."""
import secrets

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import get_current_user
from app.csrf import verify_csrf
from app.i18n import translate
from app.notas_wallet import get_credit_balance
from app.notification_center import create_notification
from app.render import render
from app.store import CATEGORIES, buy, catalog_for, my_featurable_listings, ready

router = APIRouter()


@router.get("/store", response_class=HTMLResponse)
def store_page(request: Request, bought: str = "", error: str = ""):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login?next=/store", status_code=303)
    items = catalog_for(user["id"])
    return render(request, "store.html", {
        "user": user, "ready": ready(), "categories": CATEGORIES,
        "items_by_category": {c: [i for i in items if i["category"] == c] for c in CATEGORIES},
        "balance": get_credit_balance(user["id"]),
        "my_listings": my_featurable_listings(user["id"]) if items else [],
        "bought": bought, "error": error,
        # Fresh per render: a double click re-sends the same token → no double charge.
        "buy_token": secrets.token_urlsafe(16),
    })


@router.post("/store/buy")
def store_buy(request: Request, item_key: str = Form(...), csrf_token: str = Form(""), token: str = Form(""),
              listing_id: int = Form(0), proof_url: str = Form(""), note: str = Form("")):
    verify_csrf(request, csrf_token)
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login?next=/store", status_code=303)
    if not user["email_verified"]:
        return RedirectResponse(url="/?verify_required=1", status_code=303)
    status, item = buy(user["id"], item_key, token, listing_id=listing_id or None, proof_url=proof_url, note=note)
    if status in ("bought", "replay"):
        if status == "bought":
            title = (item or {}).get("title") or translate(f"notas_item_{item_key}_title", getattr(request.state, "lang", "de"))
            create_notification(user["id"], "loja_redeemed", "notification_loja_redeemed", {"item": title}, link_url="/store")
        return RedirectResponse(url=f"/store?bought={item_key}#item-{item_key}", status_code=303)
    error = {"insufficient": "notas_insufficient_balance", "invalid": "store_error_invalid",
             "owned": "store_error_owned"}.get(status, "notas_item_not_found")
    return RedirectResponse(url=f"/store?error={error}#item-{item_key}", status_code=303)

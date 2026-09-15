"""
"Notas" (credit bank) + "Hall da Fama" — the reward side of the
referral system in app/referrals.py.

Every REFERRAL_CREDIT_RATIO-th verified referral earns the referrer
1 "nota" (credit), recorded in credit_ledger. Notas can be redeemed
for items in REDEMPTION_CATALOG below. Hall da Fama is a private,
referrer-only list of who a person referred (photos included) — it
never shows anyone else's referral list, only your own.

Both pages are members-only + verified-only, same gate as /people.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse

from app.database import execute, fetch_one
from app.auth import get_current_user
from app.render import render
from app.csrf import verify_csrf
from app.referrals import (
    get_credit_balance,
    get_credit_ledger,
    get_referrals_until_next_credit,
    get_hall_of_fame,
    CREDIT_REFERRALS_PER_CREDIT,
)

router = APIRouter()

# Redemption catalog. Deliberately small for now (one item) — the
# structure (key/cost/effect) is built to grow without touching the
# route logic, just add an entry here and a branch in redeem_notas().
REDEMPTION_CATALOG = [
    {
        "key": "profile_highlight_7d",
        "cost": 3,
        "icon": "icon-sparkle",
        "days": 7,
    },
]

_CATALOG_BY_KEY = {item["key"]: item for item in REDEMPTION_CATALOG}


@router.get("/notas", response_class=HTMLResponse)
def notas_page(request: Request, redeemed: str = "", error: str = ""):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not user["email_verified"]:
        return RedirectResponse(url="/?verify_required=1", status_code=303)

    context = {
        "user": user,
        "balance": get_credit_balance(user["id"]),
        "ledger": get_credit_ledger(user["id"]),
        "catalog": REDEMPTION_CATALOG,
        "referrals_until_next_credit": get_referrals_until_next_credit(user["id"]),
        "credit_ratio": CREDIT_REFERRALS_PER_CREDIT,
        "redeemed": redeemed,
        "error": error,
    }
    return render(request, "notas.html", context)


@router.post("/notas/redeem")
def redeem_notas(request: Request, item_key: str = Form(...), csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)

    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not user["email_verified"]:
        return RedirectResponse(url="/?verify_required=1", status_code=303)

    item = _CATALOG_BY_KEY.get(item_key)
    if not item:
        return RedirectResponse(url="/notas?error=notas_item_not_found", status_code=303)

    balance = get_credit_balance(user["id"])
    if balance < item["cost"]:
        return RedirectResponse(url="/notas?error=notas_insufficient_balance", status_code=303)

    execute(
        """
        INSERT INTO credit_ledger (user_id, delta, reason)
        VALUES (:uid, :delta, :reason)
        """,
        {"uid": user["id"], "delta": -item["cost"], "reason": f"redeem_{item_key}"},
    )

    if item_key == "profile_highlight_7d":
        # Extends from the current highlight if there's still time left
        # on it (redeeming twice stacks the days), otherwise starts now.
        now = datetime.now(timezone.utc)
        current_row = fetch_one(
            "SELECT profile_highlighted_until FROM users WHERE id = :id", {"id": user["id"]}
        )
        current_until = current_row["profile_highlighted_until"] if current_row else None
        base = current_until if current_until and current_until > now else now
        new_until = base + timedelta(days=item["days"])
        execute(
            "UPDATE users SET profile_highlighted_until = :until WHERE id = :id",
            {"until": new_until, "id": user["id"]},
        )

    return RedirectResponse(url=f"/notas?redeemed={item_key}", status_code=303)


@router.get("/hall-da-fama", response_class=HTMLResponse)
def hall_da_fama(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not user["email_verified"]:
        return RedirectResponse(url="/?verify_required=1", status_code=303)

    context = {
        "user": user,
        "referred_people": get_hall_of_fame(user["id"]),
    }
    return render(request, "hall_da_fama.html", context)

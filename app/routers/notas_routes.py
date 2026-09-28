"""
"Notas" (credit bank) + "Hall da Fama" — the reward side of the
referral system in app/referrals.py.

Every REFERRAL_CREDIT_RATIO-th verified referral earns the referrer
1 "nota" (credit), recorded in credit_ledger. Notas can be redeemed
for items in the catalog (see app/shop_catalog.py — price and
active/inactive live in the shop_catalog_items table since the P5
Loja Admin panel, 18/09/2026, so an item can be turned off from
/admin/loja without a deploy). Hall da Fama is a private,
referrer-only list of who a person referred (photos included) — it
never shows anyone else's referral list, only your own.

Both pages are members-only + verified-only, same gate as /people.
"""
import random
import secrets
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse

from app.auth import get_current_user
from app.render import render
from app.csrf import verify_csrf
from app.notas_wallet import get_balances, get_credit_balance, format_notas
from app.notas_purchase import BUNDLES, create_checkout_url, currency_for, purchases_available
from app.profiles import public_base_url
from app.shop_catalog import get_active_catalog, get_catalog_titles_by_key, redeem_item
from app.notification_center import create_notification
from app.i18n import translate
from app.referrals import (
    get_credit_ledger,
    get_referrals_until_next_credit,
    get_hall_of_fame,
    ensure_referral_code,
    count_pending_referrals,
    rewards_v2_enabled,
    settle_for_referrer,
    CREDIT_REFERRALS_PER_CREDIT,
    MAX_REWARDS_PER_DAY,
    MAX_REWARDS_PER_MONTH,
)

router = APIRouter()


@router.get("/notas", response_class=HTMLResponse)
def notas_page(request: Request, redeemed: str = "", error: str = "", purchase: str = ""):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not user["email_verified"]:
        return RedirectResponse(url="/?verify_required=1", status_code=303)
    settle_for_referrer(user["id"])  # pays referrals that waited on limits / the 7 days
    referrals_v2 = rewards_v2_enabled()

    context = {
        "user": user,
        "balance": get_credit_balance(user["id"]),
        # Notas v2: purchased / earned split + next expiry (docs/specs/NOTAS_V2.md).
        "balances": get_balances(user["id"]),
        "purchase_success": purchase == "success",
        "ledger": get_credit_ledger(user["id"]),
        "catalog": get_active_catalog(),
        # Título de cada item pro extrato mostrar o nome certo mesmo
        # de itens já desativados depois de resgatados (ver
        # get_catalog_titles_by_key — None = usa o texto do i18n).
        "catalog_titles": get_catalog_titles_by_key(),
        "referrals_v2": referrals_v2,
        "referrals_until_next_credit": 0 if referrals_v2 else get_referrals_until_next_credit(user["id"]),
        "referrals_pending": count_pending_referrals(user["id"]),
        "credit_ratio": CREDIT_REFERRALS_PER_CREDIT,
        "referral_limits": {"day": MAX_REWARDS_PER_DAY, "month": MAX_REWARDS_PER_MONTH},
        "redeemed": redeemed,
        "error": error,
        # Antifraud pass, 19/09/2026: a fresh, unguessable token per page
        # render, echoed back as a hidden field on each item's redeem form
        # (see notas.html) and folded into the idempotency key below. A
        # double-click, a slow network retry, or a browser back-button
        # resubmit of the SAME rendered form now hits the same key and is
        # rejected as a duplicate instead of debiting twice — reloading the
        # page (a genuinely new redeem attempt) gets a new token, so this
        # never blocks a real second purchase, only an accidental repeat of
        # the same one.
        "redeem_idempotency_token": secrets.token_urlsafe(16),
    }
    return render(request, "notas.html", context)


@router.post("/notas/redeem")
def redeem_notas(
    request: Request,
    item_key: str = Form(...),
    csrf_token: str = Form(""),
    idempotency_token: str = Form(""),
):
    verify_csrf(request, csrf_token)

    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not user["email_verified"]:
        return RedirectResponse(url="/?verify_required=1", status_code=303)

    # Debit + effect in one transaction, double-submit safe (app/shop_catalog.redeem_item).
    status, item = redeem_item(user["id"], item_key, idempotency_token)
    if status == "not_found":
        return RedirectResponse(url="/notas?error=notas_item_not_found", status_code=303)
    if status == "insufficient":
        return RedirectResponse(url="/notas?error=notas_insufficient_balance", status_code=303)
    if status == "redeemed":
        # Bell notification only for the real first redeem, never for a replay.
        lang = getattr(request.state, "lang", "de")
        item_title = item["title"] or translate(f"notas_item_{item_key}_title", lang)
        create_notification(
            user["id"], "loja_redeemed", "notification_loja_redeemed",
            {"item": item_title}, link_url="/notas",
        )
    return RedirectResponse(url=f"/notas?redeemed={item_key}", status_code=303)


# ------------------------------------------------------------------
# "Comprar Notas que faltam" (18/09/2026) — pedido do Daniel: quando o
# saldo não é suficiente pra um item (ex.: tem 3, precisa de 11),
# oferecer comprar a diferença por um meio de pagamento. Decisão
# confirmada via AskUserQuestion: SÓ A INTERFACE por enquanto — leva a
# uma tela "em breve", mesmo padrão do /assinar (app/routers/
# financial_routes.py) — nenhuma cobrança real ainda, sem gateway de
# pagamento integrado no site (Capitalism Mode continua desligado por
# padrão). Liga o dinheiro real quando um gateway for escolhido e
# integrado — provavelmente junto com a Assinatura, que tem a mesma
# pendência.
# ------------------------------------------------------------------

# 1 Nota = 1 Euro/Franco (mesma equivalência já usada pro custo da
# urgência — ver app/urgency.py) — só pra mostrar um valor de
# referência nesta tela de espera, não é uma cobrança real ainda.
NOTAS_TO_EUR_RATE = Decimal("1")


def _buy_page(request: Request, user: dict, missing, error: str = "", cancelled: bool = False):
    """Real bundles when Stripe + Capitalism Mode allow it (Notas v2, N5);
    the original "coming soon" page otherwise."""
    context = {
        "user": user,
        "missing_notas": format_notas(missing) if missing is not None else None,
        "missing_eur": f"{missing * NOTAS_TO_EUR_RATE:.2f}".replace(".", ",") if missing is not None else None,
    }
    if not purchases_available(user):
        return render(request, "notas_comprar_stub.html", context)
    currency = currency_for(user).upper()
    context.update({
        "bundles": [
            {"key": key, "notas": b["notas"], "price": f"{b['cents'] / 100:.2f}".replace(".", ",") + f" {currency}"}
            for key, b in BUNDLES.items()
        ],
        "error": error,
        "cancelled": cancelled,
    })
    return render(request, "notas_comprar.html", context)


@router.post("/notas/comprar-notas")
def comprar_notas_checkout(
    request: Request,
    csrf_token: str = Form(...),
    bundle: str = Form(""),
    accept_terms_waiver: str = Form(""),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not user["email_verified"]:
        return RedirectResponse(url="/?verify_required=1", status_code=303)
    verify_csrf(request, csrf_token)
    if not purchases_available(user) or bundle not in BUNDLES:
        return RedirectResponse(url="/notas/comprar-notas", status_code=303)
    if accept_terms_waiver != "1":
        return _buy_page(request, user, None, error="notas_buy_waiver_required")
    base_url = public_base_url(request)
    try:
        url = create_checkout_url(user, bundle, getattr(request.state, "lang", "de"), base_url)
    except Exception:
        return _buy_page(request, user, None, error="notas_buy_error")
    return RedirectResponse(url=url, status_code=303)


@router.get("/notas/comprar-notas", response_class=HTMLResponse)
def comprar_notas_stub(request: Request, faltam: str = "", cancelled: str = ""):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not user["email_verified"]:
        return RedirectResponse(url="/?verify_required=1", status_code=303)

    try:
        missing = Decimal(faltam)
        if missing <= 0:
            missing = None
    except (InvalidOperation, ValueError):
        missing = None

    return _buy_page(request, user, missing, cancelled=cancelled == "1")


@router.get("/hall-da-fama", response_class=HTMLResponse)
def hall_da_fama(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not user["email_verified"]:
        return RedirectResponse(url="/?verify_required=1", status_code=303)

    # Hall da Fama polish, 19/09/2026: the referral link + "Convidar um
    # amigo!" CTA now live right here too (previously /profile only), so
    # someone looking at who they've already brought in can invite another
    # person without leaving the page. ensure_referral_code() is safe to
    # call repeatedly — a no-op once the user already has a code (see
    # app/referrals.py).
    referral_code = ensure_referral_code(user["id"], user.get("referral_code"))
    # Piscadinha mascot moment (Part 2 backlog item 4, 19/09/2026): one
    # of a few playful incentive lines, picked at random per page load
    # — Daniel asked for "a few more incentives here that appear
    # randomly" alongside his two given examples. See
    # app/static/img/mascot/MANIFEST.md ("never in billing, security,
    # or terms" — this page is neither, it's the invite/rewards page).
    incentive_key = random.choice([
        "hall_da_fama_incentive_1", "hall_da_fama_incentive_2",
        "hall_da_fama_incentive_3", "hall_da_fama_incentive_4",
    ])
    context = {
        "user": user,
        "referred_people": get_hall_of_fame(user["id"]),
        "referral_url": f"{public_base_url(request)}/register?ref={referral_code}",
        "incentive_key": incentive_key,
    }
    return render(request, "hall_da_fama.html", context)

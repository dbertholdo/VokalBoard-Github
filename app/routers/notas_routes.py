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
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse

from sqlalchemy import text

from app.database import engine, fetch_one
from app.auth import get_current_user
from app.render import render
from app.csrf import verify_csrf
from app.notas_wallet import get_credit_balance, format_notas, debit_notas_atomic
from app.shop_catalog import get_active_catalog, get_catalog_titles_by_key, ITEM_EFFECTS
from app.notification_center import create_notification
from app.i18n import translate
from app.referrals import (
    get_credit_ledger,
    get_referrals_until_next_credit,
    get_hall_of_fame,
    ensure_referral_code,
    CREDIT_REFERRALS_PER_CREDIT,
)

router = APIRouter()


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
        "catalog": get_active_catalog(),
        # Título de cada item pro extrato mostrar o nome certo mesmo
        # de itens já desativados depois de resgatados (ver
        # get_catalog_titles_by_key — None = usa o texto do i18n).
        "catalog_titles": get_catalog_titles_by_key(),
        "referrals_until_next_credit": get_referrals_until_next_credit(user["id"]),
        "credit_ratio": CREDIT_REFERRALS_PER_CREDIT,
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

    # Preço e ativo/inativo lidos aqui, fora da transação de débito, mas
    # isso é seguro: debit_notas_atomic() só decide com base no saldo real
    # dentro da SUA PRÓPRIA transação (trava a linha do usuário primeiro),
    # então mesmo que o Admin desative o item entre este SELECT e o débito
    # abaixo, o pior caso é debitar por um `cost` que acabou de ficar
    # obsoleto — não um débito sem lock ou um saldo negativo. A checagem
    # "active = TRUE" aqui só evita iniciar o resgate de algo já desligado.
    item_row = fetch_one(
        "SELECT cost, title FROM shop_catalog_items WHERE item_key = :key AND active = TRUE",
        {"key": item_key},
    )
    if not item_row:
        return RedirectResponse(url="/notas?error=notas_item_not_found", status_code=303)
    cost = item_row["cost"]

    # Migrated 19/09/2026 to go through app/notas_wallet.py's shared
    # atomic-debit-with-idempotency helper (see that module's docstring —
    # this endpoint was the one deliberately-deferred exception) instead of
    # hand-rolled SQL, so this flow gets the same race-condition and
    # double-submit protection as every other Notas debit in the app.
    idem_key = f"redeem_{item_key}_{idempotency_token}" if idempotency_token else None
    # debit_notas_atomic() returns True both for a fresh debit AND for a
    # replay of an already-used idempotency_key (its whole point is to make
    # a replay a safe no-op) — checked BEFORE calling it, so the side
    # effect below only runs once, on the actual first debit. Without this
    # check, a double-click on profile_highlight_7d would correctly skip
    # the second debit but still stack a second 7-day extension for free.
    already_processed = bool(
        idem_key and fetch_one(
            "SELECT id FROM credit_ledger WHERE user_id = :uid AND idempotency_key = :key",
            {"uid": user["id"], "key": idem_key},
        )
    )
    debited = debit_notas_atomic(
        user["id"], cost, reason=f"redeem_{item_key}", idempotency_key=idem_key,
    )
    if not debited:
        return RedirectResponse(url="/notas?error=notas_insufficient_balance", status_code=303)

    if not already_processed:
        # Central de Notificações (task #50) — only on the actual
        # first debit, same guard used for the profile_highlight_7d
        # side effect below, so a double-click/replay never stacks a
        # second bell notification either.
        lang = getattr(request.state, "lang", "de")
        item_title = item_row["title"] or translate(f"notas_item_{item_key}_title", lang)
        create_notification(
            user["id"], "loja_redeemed", "notification_loja_redeemed",
            {"item": item_title}, link_url="/notas",
        )

    if item_key == "profile_highlight_7d" and not already_processed:
        # Extends from the current highlight if there's still time left on
        # it (redeeming twice stacks the days), otherwise starts now. Its
        # own short transaction — the Notas debit above already committed,
        # so a failure here would leave Notas spent without the reward
        # applied; kept as a separate step (not folded into
        # debit_notas_atomic) because that helper is intentionally
        # side-effect-free and shared by callers that have no such reward.
        with engine.begin() as conn:
            account = conn.execute(
                text("SELECT profile_highlighted_until FROM users WHERE id = :id FOR UPDATE"),
                {"id": user["id"]},
            ).mappings().first()
            now = datetime.now(timezone.utc)
            current_until = account["profile_highlighted_until"] if account else None
            base = current_until if current_until and current_until > now else now
            conn.execute(
                text("UPDATE users SET profile_highlighted_until = :until WHERE id = :id"),
                {"until": base + timedelta(days=ITEM_EFFECTS["profile_highlight_7d"]["days"]), "id": user["id"]},
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


@router.get("/notas/comprar-notas", response_class=HTMLResponse)
def comprar_notas_stub(request: Request, faltam: str = ""):
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

    context = {
        "user": user,
        "missing_notas": format_notas(missing) if missing is not None else None,
        "missing_eur": f"{missing * NOTAS_TO_EUR_RATE:.2f}".replace(".", ",") if missing is not None else None,
    }
    return render(request, "notas_comprar_stub.html", context)


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
        "referral_url": f"{str(request.base_url).rstrip('/')}/register?ref={referral_code}",
        "incentive_key": incentive_key,
    }
    return render(request, "hall_da_fama.html", context)

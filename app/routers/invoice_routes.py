"""Rechnungmaker (P4): Gerador Avulso (stateless) + Match-Rechnungen
(rascunho criptografado por 7 dias — ver app/invoice_match_drafts.py)."""
from datetime import date

from fastapi import APIRouter, Form, HTTPException, Request
import re

from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse

from app.auth import get_current_user
from app.csrf import verify_csrf
from app.database import fetch_one
from app.invoice_deadlines import can_request_match_invoice
from app.invoice_match_drafts import (
    InvoiceDraftNotAllowed,
    cancel_draft,
    confirm_and_send,
    count_pending_actions,
    get_draft,
    get_form_for_issuer,
    get_preview,
    list_invoice_matches_for_user,
    notify_ready_for_review,
    notify_requested,
    request_invoice,
    save_issuer_form,
)
from app.invoice_pdf import InvoiceDocument, InvoiceValidationError, render_invoice_pdf
from app.invoice_service import (
    InvoiceCreditUnavailable,
    consume_invoice_generation,
    get_personal_invoice_badge,
    record_invoice_number,
    suggested_invoice_number,
)
from app.invoice_tax_presets import (
    STANDARD_RATE_DEFAULT, TAX_COUNTRIES, TAX_PRESET_DEFAULT, TAX_PRESET_OPTIONS, parse_tax_preset, resolve_tax,
)
from app.render import render

router = APIRouter()

# Pages that show decrypted tax/bank data must never be cached (Zero-Storage, CLAUDE.md §2).
NO_STORE = {"Cache-Control": "private, no-store"}
AVULSO_FIELDS = ("number", "issue_date", "service_date", "issuer_name", "issuer_address", "issuer_tax_id",
                 "recipient_name", "recipient_address", "service_description", "net_amount", "currency",
                 "tax_preset", "tax_custom_text", "tax_rate_override", "payment_terms", "iban", "bic",
                 "expense_travel_amount", "expense_lodging_amount")


def _pdf_filename(number: str) -> str:
    """ASCII-only, header-safe: the invoice number is free text (an umlaut or a
    quote in it used to crash or break the download header)."""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", number or "").strip("-.")[:60]
    return f"Rechnung-{safe or 'VokalBoard'}.pdf"


def _match_closed(m: dict) -> bool:
    """No invoice work on a cancelled Match or one whose invoice was already sent."""
    return m["status"] == "cancelled" or bool(m.get("invoice_sent_at"))


def _member(request: Request):
    user = get_current_user(request)
    if not user or not user["email_verified"]:
        return None
    return user


def _match_context(match_id: int, viewer_id: int) -> dict:
    """Loads the Match + listing + both users' contact/name/language, and
    404s unless the viewer is one of the two participants."""
    row = fetch_one(
        """
        SELECT m.id, m.status, m.artist_user_id, m.contractor_user_id, m.invoice_sent_at,
               COALESCE(m.listing_snapshot->>'title', l.title) AS title,
               COALESCE((m.listing_snapshot->>'event_date')::date, l.event_date) AS event_date,
               artist.full_name AS artist_name, artist.email AS artist_email, artist.preferred_language AS artist_lang,
               contractor.full_name AS contractor_name, contractor.email AS contractor_email, contractor.preferred_language AS contractor_lang
        FROM job_matches m
        LEFT JOIN listings l ON l.id = m.listing_id
        JOIN users artist ON artist.id = m.artist_user_id
        JOIN users contractor ON contractor.id = m.contractor_user_id
        WHERE m.id = :id
        """,
        {"id": match_id},
    )
    if not row or viewer_id not in (row["artist_user_id"], row["contractor_user_id"]):
        raise HTTPException(status_code=404)
    return dict(row)


# ---------------------------------------------------------------------------
# Rechnungmaker (Etapa 3, 18/09/2026): página única com 2 abas — cada uma
# com botões próprios (pedido do Daniel: "intuitiva e descomplicada", sem
# JavaScript, só navegação normal por link/query param).
# ---------------------------------------------------------------------------

@router.get("/rechnungen", response_class=HTMLResponse)
def invoice_generator_legacy_redirect(request: Request, error: str = ""):
    """URL antiga do Gerador Avulso — a Etapa 3 juntou as duas vertentes
    numa página só (/rechnungmaker). Mantido como redirect pra não
    quebrar link/favorito salvo de antes."""
    suffix = f"&error={error}" if error else ""
    return RedirectResponse(f"/rechnungmaker?tab=avulso{suffix}", status_code=303)


def _rechnungmaker_page(request: Request, user: dict, tab: str, error: str = "", values: dict | None = None, status: int = 200):
    today = date.today()
    context = {
        "user": user, "tab": tab, "error": error,
        "pending_actions_count": count_pending_actions(user["id"]),
        "personal_badge": get_personal_invoice_badge(user["id"]),
        "suggested_number": suggested_invoice_number(user["id"], today.year),
        "today": today.isoformat(),
        "tax_countries": TAX_COUNTRIES, "standard_rate_default": STANDARD_RATE_DEFAULT,
        "tax_preset_options": TAX_PRESET_OPTIONS, "tax_preset_default": TAX_PRESET_DEFAULT,
        # Zero-Storage: after an error the typed values are echoed back in THIS
        # response only (never stored), so nobody has to retype the whole invoice.
        "values": values or {},
    }
    if tab == "match":
        context["matches"] = list_invoice_matches_for_user(user["id"], today)
    return render(request, "rechnungmaker.html", context, status_code=status)


@router.get("/rechnungmaker", response_class=HTMLResponse)
def rechnungmaker(request: Request, tab: str = "match", error: str = ""):
    user = _member(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return _rechnungmaker_page(request, user, tab if tab in ("match", "avulso") else "match", error)


@router.post("/rechnungen/pdf")
async def create_invoice_pdf(request: Request, csrf_token: str = Form(...)):
    verify_csrf(request, csrf_token)
    user = _member(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    values = {k: (form.get(k) or "") for k in AVULSO_FIELDS}
    country, status, values["tax_preset"] = parse_tax_preset(values["tax_preset"])
    try:
        tax_rate, tax_note = resolve_tax(country, status, values["tax_custom_text"], values["tax_rate_override"])
        document = InvoiceDocument(
            values["number"], values["issue_date"], values["service_date"], values["issuer_name"],
            values["issuer_address"], values["issuer_tax_id"], values["recipient_name"], values["recipient_address"],
            values["service_description"], values["net_amount"], values["currency"] or "EUR", tax_rate, tax_note,
            values["payment_terms"], values["iban"], values["bic"],
            values["expense_travel_amount"] or "0", values["expense_lodging_amount"] or "0",
        )
        pdf = render_invoice_pdf(document)
    except InvoiceValidationError:
        return _rechnungmaker_page(request, user, "avulso", "inv_form_error", values, status=400)
    try:
        consume_invoice_generation(user["id"], date.today())
    except InvoiceCreditUnavailable:
        return _rechnungmaker_page(request, user, "avulso", "inv_no_credit", values, status=402)
    record_invoice_number(user["id"], values["number"])
    return StreamingResponse(iter([pdf]), media_type="application/pdf", headers={
        **NO_STORE, "Content-Disposition": f'attachment; filename="{_pdf_filename(values["number"])}"'})


# ---------------------------------------------------------------------------
# Match-Rechnungen (Etapa 1: pedir/gerar + preview + confirmar por e-mail;
# Etapa 2: worker de expiração de 7 dias; Etapa 3: aba própria em
# /rechnungmaker com badge de pendência + contador pessoal)
# ---------------------------------------------------------------------------

@router.post("/profile/matches/{match_id}/invoice/request")
def request_match_invoice(request: Request, match_id: int, csrf_token: str = Form(...)):
    verify_csrf(request, csrf_token)
    viewer = _member(request)
    if not viewer:
        return RedirectResponse("/login", status_code=303)
    m = _match_context(match_id, viewer["id"])
    if _match_closed(m):
        return RedirectResponse("/rechnungmaker?tab=match&invoice_error=1", status_code=303)
    try:
        result = request_invoice(match_id, viewer["id"], m["artist_user_id"], m["contractor_user_id"], m["event_date"])
    except InvoiceDraftNotAllowed:
        return RedirectResponse("/rechnungmaker?tab=match&invoice_error=1", status_code=303)
    if result == "created":
        is_issuer_requesting = viewer["id"] == m["contractor_user_id"]
        recipient = "artist" if is_issuer_requesting else "contractor"
        recipient_email = m[f"{recipient}_email"]
        recipient_name = m[f"{recipient}_name"]
        recipient_lang = m[f"{recipient}_lang"]
        requester_first_name = (viewer["full_name"] or "").split(" ")[0] or viewer["full_name"]
        notify_requested(recipient_email, recipient_name, recipient_lang, requester_first_name, m["title"], f"{request.base_url}rechnungmaker?tab=match")
    return RedirectResponse("/rechnungmaker?tab=match&invoice_requested=1", status_code=303)


@router.get("/profile/matches/{match_id}/invoice", response_class=HTMLResponse)
def match_invoice_form(request: Request, match_id: int, error: str = ""):
    viewer = _member(request)
    if not viewer:
        return RedirectResponse("/login", status_code=303)
    m = _match_context(match_id, viewer["id"])
    if viewer["id"] != m["artist_user_id"]:
        raise HTTPException(status_code=403)
    if _match_closed(m) or (not can_request_match_invoice(m["event_date"], date.today()) and not get_draft(match_id)):
        return RedirectResponse("/rechnungmaker?tab=match&invoice_error=1", status_code=303)
    existing = get_form_for_issuer(match_id, viewer["id"])
    response = render(request, "invoice_match_form.html", {
        "user": viewer, "match": m, "error": error, "existing": existing,
        "suggested_number": existing.get("number") or suggested_invoice_number(viewer["id"], date.today().year),
        "today": date.today().isoformat(),
        "tax_countries": TAX_COUNTRIES, "standard_rate_default": STANDARD_RATE_DEFAULT,
        "tax_preset_options": TAX_PRESET_OPTIONS, "tax_preset_default": TAX_PRESET_DEFAULT,
    })
    response.headers.update(NO_STORE)
    return response


@router.post("/profile/matches/{match_id}/invoice")
def save_match_invoice_form(
    request: Request, match_id: int, csrf_token: str = Form(...), number: str = Form(...), issue_date: str = Form(...), service_date: str = Form(...),
    issuer_name: str = Form(...), issuer_address: str = Form(...), issuer_tax_id: str = Form(...),
    recipient_name: str = Form(...), recipient_address: str = Form(...), service_description: str = Form(...),
    net_amount: str = Form(...), currency: str = Form("EUR"),
    tax_preset: str = Form(""), tax_custom_text: str = Form(""), tax_rate_override: str = Form(""),
    payment_terms: str = Form(""), iban: str = Form(""), bic: str = Form(""),
    expense_travel_amount: str = Form("0"), expense_lodging_amount: str = Form("0"),
):
    verify_csrf(request, csrf_token)
    viewer = _member(request)
    if not viewer:
        return RedirectResponse("/login", status_code=303)
    m = _match_context(match_id, viewer["id"])
    if viewer["id"] != m["artist_user_id"]:
        raise HTTPException(status_code=403)
    if _match_closed(m):
        return RedirectResponse("/rechnungmaker?tab=match&invoice_error=1", status_code=303)
    tax_country, tax_status, tax_preset = parse_tax_preset(tax_preset)
    tax_rate, tax_note = resolve_tax(tax_country, tax_status, tax_custom_text, tax_rate_override)
    payload = {
        "number": number, "issue_date": issue_date, "service_date": service_date,
        "issuer_name": issuer_name, "issuer_address": issuer_address, "issuer_tax_id": issuer_tax_id,
        "recipient_name": recipient_name, "recipient_address": recipient_address, "service_description": service_description,
        "net_amount": net_amount, "currency": currency, "tax_rate": tax_rate, "tax_note": tax_note,
        "payment_terms": payment_terms, "iban": iban, "bic": bic,
        "expense_travel_amount": expense_travel_amount, "expense_lodging_amount": expense_lodging_amount,
    }
    try:
        # Validate right away so the issuer sees a mistake immediately,
        # instead of only when the contractor tries to confirm it later.
        InvoiceDocument(**payload).validate()
        save_issuer_form(match_id, viewer["id"], m["contractor_user_id"], {**payload, "tax_preset": tax_preset}, m["event_date"])
    except (InvoiceValidationError, InvoiceDraftNotAllowed):
        return RedirectResponse(f"/profile/matches/{match_id}/invoice?error=1", status_code=303)
    issuer_first_name = (viewer["full_name"] or "").split(" ")[0] or viewer["full_name"]
    notify_ready_for_review(
        m["contractor_email"], m["contractor_name"], m["contractor_lang"],
        issuer_first_name, m["title"], f"{request.base_url}rechnungmaker?tab=match",
    )
    return RedirectResponse(f"/profile/matches/{match_id}/invoice/preview", status_code=303)


@router.get("/profile/matches/{match_id}/invoice/preview", response_class=HTMLResponse)
def match_invoice_preview(request: Request, match_id: int, error: str = ""):
    viewer = _member(request)
    if not viewer:
        return RedirectResponse("/login", status_code=303)
    m = _match_context(match_id, viewer["id"])
    preview = get_preview(match_id, viewer["id"])
    if not preview:
        return RedirectResponse("/rechnungmaker?tab=match&invoice_error=1", status_code=303)
    response = render(request, "invoice_match_preview.html", {
        "user": viewer, "match": m, "preview": preview, "error": error,
        "is_contractor": viewer["id"] == m["contractor_user_id"],
    })
    response.headers.update(NO_STORE)
    return response


@router.post("/profile/matches/{match_id}/invoice/confirm")
def confirm_match_invoice(request: Request, match_id: int, csrf_token: str = Form(...)):
    verify_csrf(request, csrf_token)
    viewer = _member(request)
    if not viewer:
        return RedirectResponse("/login", status_code=303)
    m = _match_context(match_id, viewer["id"])
    if _match_closed(m):
        return RedirectResponse("/rechnungmaker?tab=match&invoice_error=1", status_code=303)
    try:
        confirm_and_send(
            match_id, viewer["id"], date.today(),
            issuer_email=m["artist_email"], issuer_name=m["artist_name"], issuer_lang=m["artist_lang"],
            contractor_email=m["contractor_email"], contractor_name=m["contractor_name"], contractor_lang=m["contractor_lang"],
            production_title=m["title"],
        )
    except InvoiceDraftNotAllowed:
        return RedirectResponse(f"/profile/matches/{match_id}/invoice/preview?error=1", status_code=303)
    return RedirectResponse("/rechnungmaker?tab=match&invoice_sent=1", status_code=303)


@router.post("/profile/matches/{match_id}/invoice/cancel")
def cancel_match_invoice(request: Request, match_id: int, csrf_token: str = Form(...)):
    verify_csrf(request, csrf_token)
    viewer = _member(request)
    if not viewer:
        return RedirectResponse("/login", status_code=303)
    _match_context(match_id, viewer["id"])
    cancel_draft(match_id, viewer["id"])
    return RedirectResponse("/rechnungmaker?tab=match&invoice_cancelled=1", status_code=303)

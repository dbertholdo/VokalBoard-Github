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
from app.invoice_form import defaults_for, normalize, preferred, read_form, remember, to_document
from app.invoice_form_context import form_context
from app.invoice_pdf import InvoiceValidationError, render_invoice_pdf
from app.invoice_service import (
    InvoiceCreditUnavailable,
    consume_invoice_generation,
    get_personal_invoice_badge,
    record_invoice_number,
    suggested_invoice_number,
)
from app.render import render

router = APIRouter()

# Pages that show decrypted tax/bank data must never be cached (Zero-Storage, CLAUDE.md §2).
NO_STORE = {"Cache-Control": "private, no-store"}


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
               COALESCE(v.fee_amount, (m.listing_snapshot->>'fee_amount')::numeric) AS fee_amount,
               COALESCE(v.fee_currency, m.listing_snapshot->>'fee_currency') AS fee_currency,
               artist.full_name AS artist_name, artist.email AS artist_email, artist.preferred_language AS artist_lang,
               contractor.full_name AS contractor_name, contractor.email AS contractor_email, contractor.preferred_language AS contractor_lang
        FROM job_matches m
        LEFT JOIN listings l ON l.id = m.listing_id
        LEFT JOIN listing_vacancies v ON v.id = m.vacancy_id
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
    if values is None:
        values = normalize(defaults_for(user, number=suggested_invoice_number(user["id"], today.year), today=today.isoformat()))
    context = {
        "user": user, "tab": tab, "error": error,
        "pending_actions_count": count_pending_actions(user["id"]),
        "personal_badge": get_personal_invoice_badge(user["id"]),
        # Zero-Storage: after an error the typed values are echoed back in THIS
        # response only (never stored), so nobody has to retype the whole invoice.
        "values": values,
        **form_context(request),
    }
    if tab == "match":
        context["matches"] = list_invoice_matches_for_user(user["id"], today)
    return render(request, "rechnungmaker.html", context, status_code=status)


@router.get("/rechnungmaker", response_class=HTMLResponse)
def rechnungmaker(request: Request, tab: str = "match", error: str = ""):
    user = _member(request)
    if not user:
        # Item 2 (2026-09-28): show the tool blurred behind a sign-up card
        # instead of bouncing visitors to /login.
        viewer = get_current_user(request)
        today = date.today()
        return render(request, "rechnungmaker.html", {
            "user": viewer, "visitor_gate": "unverified" if viewer else "anon",
            "values": normalize({"number": f"{today.year}-001", "issue_date": today.isoformat()}),
            **form_context(request),
        })
    return _rechnungmaker_page(request, user, tab if tab in ("match", "avulso") else "match", error)


@router.post("/rechnungen/pdf")
async def create_invoice_pdf(request: Request, csrf_token: str = Form(...)):
    verify_csrf(request, csrf_token)
    user = _member(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    values = normalize(read_form(form), preferred(user)[0])
    if form.get("action") == "apply":  # no-JS country switch: re-render, nothing stored
        return _rechnungmaker_page(request, user, "avulso", "", values)
    try:
        pdf = render_invoice_pdf(to_document(values))
    except InvoiceValidationError:
        return _rechnungmaker_page(request, user, "avulso", "inv_form_error", values, status=400)
    try:
        consume_invoice_generation(user["id"], date.today())
    except InvoiceCreditUnavailable:
        return _rechnungmaker_page(request, user, "avulso", "inv_no_credit", values, status=402)
    record_invoice_number(user["id"], values["number"])
    remember(user["id"], values["country"], values["doc_lang"])
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
    if existing:
        values = normalize(existing, preferred(viewer)[0])
    else:
        values = normalize(defaults_for(viewer, number=suggested_invoice_number(viewer["id"], date.today().year),
                                        today=date.today().isoformat(), match=m))
    return _match_form_page(request, viewer, m, values, error)


def _match_form_page(request: Request, viewer: dict, m: dict, values: dict, error: str = "", status: int = 200):
    response = render(request, "invoice_match_form.html", {
        "user": viewer, "match": m, "error": error, "values": values, **form_context(request),
    }, status_code=status)
    response.headers.update(NO_STORE)
    return response


@router.post("/profile/matches/{match_id}/invoice")
async def save_match_invoice_form(request: Request, match_id: int, csrf_token: str = Form(...)):
    verify_csrf(request, csrf_token)
    viewer = _member(request)
    if not viewer:
        return RedirectResponse("/login", status_code=303)
    m = _match_context(match_id, viewer["id"])
    if viewer["id"] != m["artist_user_id"]:
        raise HTTPException(status_code=403)
    if _match_closed(m):
        return RedirectResponse("/rechnungmaker?tab=match&invoice_error=1", status_code=303)
    form = await request.form()
    values = normalize(read_form(form), preferred(viewer)[0])
    if form.get("action") == "apply":  # no-JS country switch: re-render, nothing stored
        return _match_form_page(request, viewer, m, values)
    try:
        # Validate right away so the issuer sees a mistake immediately,
        # instead of only when the contractor tries to confirm it later.
        to_document(values)
    except InvoiceValidationError:
        return _match_form_page(request, viewer, m, values, error="1", status=400)
    try:
        save_issuer_form(match_id, viewer["id"], m["contractor_user_id"], values, m["event_date"])
    except InvoiceDraftNotAllowed:
        return RedirectResponse(f"/profile/matches/{match_id}/invoice?error=1", status_code=303)
    remember(viewer["id"], values["country"], values["doc_lang"])
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

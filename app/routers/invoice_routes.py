"""Stateless, verified-member-only Rechnung generator."""
from datetime import date

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse

from app.auth import get_current_user
from app.csrf import verify_csrf
from app.invoice_pdf import InvoiceDocument, InvoiceValidationError, render_invoice_pdf
from app.invoice_service import InvoiceCreditUnavailable, consume_invoice_generation, record_invoice_number, suggested_invoice_number
from app.render import render

router = APIRouter()


def _member(request: Request):
    user = get_current_user(request)
    if not user or not user["email_verified"]:
        return None
    return user


@router.get("/rechnungen", response_class=HTMLResponse)
def invoice_generator(request: Request, error: str = ""):
    user = _member(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    today = date.today()
    return render(request, "invoice_generator.html", {
        "user": user, "error": error,
        "suggested_number": suggested_invoice_number(user["id"], today.year),
        "today": today.isoformat(),
    })


@router.post("/rechnungen/pdf")
def create_invoice_pdf(
    request: Request, csrf_token: str = Form(...), number: str = Form(...), issue_date: str = Form(...), service_date: str = Form(...),
    issuer_name: str = Form(...), issuer_address: str = Form(...), issuer_tax_id: str = Form(...),
    recipient_name: str = Form(...), recipient_address: str = Form(...), service_description: str = Form(...),
    net_amount: str = Form(...), currency: str = Form("EUR"), tax_rate: str = Form("0"), tax_note: str = Form(""),
    payment_terms: str = Form(""), iban: str = Form(""), bic: str = Form(""),
):
    verify_csrf(request, csrf_token)
    user = _member(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    try:
        document = InvoiceDocument(number, issue_date, service_date, issuer_name, issuer_address, issuer_tax_id,
            recipient_name, recipient_address, service_description, net_amount, currency, tax_rate, tax_note,
            payment_terms, iban, bic)
        pdf = render_invoice_pdf(document)
        consume_invoice_generation(user["id"], date.today())
        record_invoice_number(user["id"], number)
    except (InvoiceValidationError, InvoiceCreditUnavailable):
        return RedirectResponse("/rechnungen?error=invalid_or_no_credit", status_code=303)
    return StreamingResponse(iter([pdf]), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="Rechnung-{number}.pdf"'})

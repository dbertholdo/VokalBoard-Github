"""Rechnungmaker v2 phase 1 (2026-09-28, docs/specs/RECHNUNGMAKER_V2.md)."""
from datetime import date, timedelta
from io import BytesIO

import pytest
from cryptography.fernet import Fernet
from pypdf import PdfReader

from app.database import execute, fetch_one
from app.invoice_form import normalize, to_document
from app.invoice_pdf import InvoiceValidationError, render_invoice_pdf
from app.routers import invoice_routes
from tests.test_security import DEFAULT_PASSWORD, extract_csrf, login, register_test_user

BASE = {"number": "2026-042", "issue_date": "2026-09-28", "service_date": "2026-09-20", "issuer_name": "Ada Sängerin",
        "issuer_address": "Musterweg 1\n80331 München", "issuer_tax_id": "12/345/67890", "recipient_name": "Chor Beispiel",
        "recipient_address": "Platz 2\n10115 Berlin", "service_description": "Solo", "net_amount": "1234.5"}


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch):
    monkeypatch.setenv("INVOICE_DRAFT_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))


def _pdf_text(values):
    pdf = render_invoice_pdf(to_document(normalize(values)))
    return "\n".join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)


def test_country_rates_totals_and_legal_notes():
    doc = to_document(normalize({**BASE, "country": "AT", "tax_option": "std20"}))
    assert doc.tax_rate == "20" and doc.tax_name == "Umsatzsteuer"
    net, tax, _, _, total = doc.validate()
    assert (str(tax), str(total)) == ("246.90", "1481.40")
    klein = to_document(normalize({**BASE, "country": "DE", "tax_option": "klein", "doc_lang": "en"}))
    assert klein.tax_rate == "0" and "small business" in klein.tax_note
    ch = to_document(normalize({**BASE, "country": "CH", "tax_option": "std81"}))
    assert ch.currency == "CHF" and ch.tax_name == "MWST"


def test_pdf_uses_invoice_language_and_country_number_format():
    de = _pdf_text({**BASE, "country": "DE", "tax_option": "std19"})
    assert "Rechnung" in de and "1.234,50" in de and "20.09.2026" in de
    en = _pdf_text({**BASE, "country": "OTHER", "tax_option": "none", "doc_lang": "en", "currency": "USD"})
    assert "Invoice" in en and "1,234.50 USD" in en and "20 Sep 2026" in en
    fr_ch = _pdf_text({**BASE, "country": "CH", "tax_option": "exempt", "doc_lang": "fr"})
    assert "Facture" in fr_ch and "1'234.50" in fr_ch and "Non assujetti" in fr_ch
    assert "Rechnungmaker" in en  # product name stays German in every language


def test_reverse_charge_requires_client_vat_id():
    values = normalize({**BASE, "country": "DE", "tax_option": "reverse"})
    with pytest.raises(InvoiceValidationError):
        to_document(values)
    doc = to_document({**values, "client_vat_id": "ATU12345678"})
    assert doc.tax_rate == "0" and doc.client_vat_id == "ATU12345678" and "Reverse Charge" in doc.tax_note


def test_every_field_has_help_and_no_personal_data_in_urls(client, monkeypatch):
    user_id, email, password = register_test_user(client, full_name="Help Tester")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    page = client.get("/rechnungmaker?tab=avulso&lang=pt").text
    for field in ("country", "doc_lang", "currency", "issuer_name", "tax_id", "recipient_name", "number",
                  "service_date", "net_amount", "tax_option", "iban", "bic"):
        assert f'id="invh-{field}"' in page, field
    assert "funciona como um CPF" in page  # native pt help text
    assert 'value="Help Tester"' in page  # name pre-filled from the profile

    monkeypatch.setattr(invoice_routes, "render_invoice_pdf", lambda doc: b"%PDF-1.4")
    token = extract_csrf(page)
    data = {**BASE, "csrf_token": token, "country": "CH", "tax_option": "exempt", "iban": "CH93 0076 2011 6238 5295 7"}
    applied = client.post("/rechnungen/pdf", data={**data, "action": "apply"}, follow_redirects=False)
    assert applied.status_code == 200 and '<option value="CH" selected>' in applied.text  # no-JS switch, no redirect
    assert "CHF" in applied.text and "CH93" in applied.text
    r = client.post("/rechnungen/pdf", data=data, follow_redirects=False)
    assert r.status_code == 200 and "CH93" not in (r.headers.get("location") or "")


def test_match_invoice_prefills_fee_date_and_client(client):
    from tests.test_invoice_match_drafts import _make_match
    event = date.today() - timedelta(days=2)
    match_id, artist_id, contractor_id = _make_match(client, event)
    execute("UPDATE users SET email_verified = TRUE WHERE id IN (:a, :c)", {"a": artist_id, "c": contractor_id})
    vacancy = fetch_one("SELECT vacancy_id FROM job_matches WHERE id = :id", {"id": match_id})["vacancy_id"]
    if vacancy:
        execute("UPDATE listing_vacancies SET fee_amount = 350, fee_currency = 'CHF' WHERE id = :id", {"id": vacancy})
    else:
        execute("""UPDATE job_matches SET listing_snapshot = COALESCE(listing_snapshot, '{}'::jsonb)
                   || '{"fee_amount": "350", "fee_currency": "CHF"}'::jsonb WHERE id = :id""", {"id": match_id})
    client.cookies.clear()
    login(client, fetch_one("SELECT email FROM users WHERE id = :id", {"id": artist_id})["email"], DEFAULT_PASSWORD)
    page = client.get(f"/profile/matches/{match_id}/invoice").text
    contractor = fetch_one("SELECT full_name FROM users WHERE id = :id", {"id": contractor_id})["full_name"]
    assert 'name="net_amount" inputmode="decimal" value="350.00"' in page
    assert '<option value="CHF" selected>' in page
    assert f'name="service_date" value="{event.isoformat()}"' in page
    assert f'name="recipient_name" value="{contractor}"' in page
    assert 'id="inv-bill-partner"' in page and 'id="invh-bill_partner"' in page


def test_country_and_language_are_remembered(client, monkeypatch):
    user_id, _, _ = register_test_user(client, full_name="Prefs Tester")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    monkeypatch.setattr(invoice_routes, "render_invoice_pdf", lambda doc: b"%PDF-1.4")
    token = extract_csrf(client.get("/rechnungmaker?tab=avulso").text)
    client.post("/rechnungen/pdf", data={**BASE, "csrf_token": token, "country": "AT", "doc_lang": "it", "tax_option": "klein"})
    row = fetch_one("SELECT invoice_country, invoice_doc_lang FROM users WHERE id = :id", {"id": user_id})
    assert (row["invoice_country"], row["invoice_doc_lang"]) == ("AT", "it")
    page = client.get("/rechnungmaker?tab=avulso").text
    assert '<option value="AT" selected>' in page and '<option value="it" selected>' in page

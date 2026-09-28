"""Rechnungmaker phase 2 (2026-09-28): Swiss QR-bill + GiroCode (app/invoice_qr.py)."""
from decimal import Decimal
from io import BytesIO

from pypdf import PdfReader

from app.invoice_form import normalize, to_document
from app.invoice_pdf import render_invoice_pdf
from app.invoice_qr import epc_payload, girocode_eligible, iban_valid, parse_address, swiss_eligible

BASE = {"number": "2026-042", "issue_date": "2026-09-28", "service_date": "2026-09-20", "issuer_name": "Ada Sängerin",
        "issuer_address": "Bahnhofstrasse 12\n8001 Zürich", "issuer_tax_id": "CHE-123.456.789",
        "recipient_name": "Chor Beispiel", "recipient_address": "Platz 2\n3000 Bern", "service_description": "Solo",
        "net_amount": "1234.5"}
CH_IBAN, DE_IBAN = "CH93 0076 2011 6238 5295 7", "DE89 3704 0044 0532 0130 00"


def _pages(values):
    return PdfReader(BytesIO(render_invoice_pdf(to_document(normalize(values))))).pages


def test_address_parsing_and_iban_checks():
    assert parse_address("Bahnhofstrasse 12\n8001 Zürich") == {"street": "Bahnhofstrasse", "house_num": "12", "pcode": "8001", "city": "Zürich"}
    assert parse_address("Rue du Lac 3b, CH-1200 Genève")["pcode"] == "1200"
    assert parse_address("somewhere without a postcode") is None
    assert iban_valid(CH_IBAN) and iban_valid(DE_IBAN) and not iban_valid("DE00 1234")
    assert swiss_eligible("CHF", CH_IBAN) and not swiss_eligible("USD", CH_IBAN) and not swiss_eligible("CHF", DE_IBAN)
    assert girocode_eligible("EUR", DE_IBAN) and not girocode_eligible("CHF", DE_IBAN)


def test_epc_payload_follows_the_girocode_format():
    payload = epc_payload("Ada Sängerin", DE_IBAN, "COBADEFFXXX", Decimal("1234.5"), "Rechnungs-Nr. 2026-042")
    assert payload.split("\n") == ["BCD", "002", "1", "SCT", "COBADEFFXXX", "Ada Sängerin", "DE89370400440532013000",
                                   "EUR1234.50", "", "", "Rechnungs-Nr. 2026-042"]


def test_swiss_invoice_gets_the_qr_bill_page_in_the_invoice_language():
    pages = _pages({**BASE, "country": "CH", "tax_option": "exempt", "iban": CH_IBAN})
    assert len(pages) == 2
    last = pages[-1].extract_text()
    assert "Zahlteil" in last and "Empfangsschein" in last and "CH93 0076 2011 6238 5295 7" in last
    fr = _pages({**BASE, "country": "CH", "tax_option": "exempt", "iban": CH_IBAN, "doc_lang": "fr"})[-1].extract_text()
    assert "Section paiement" in fr


def test_no_qr_bill_without_swiss_iban_readable_address_or_for_a_qr_iban():
    assert len(_pages({**BASE, "country": "CH", "tax_option": "exempt", "iban": DE_IBAN})) == 1
    assert len(_pages({**BASE, "country": "CH", "tax_option": "exempt", "iban": CH_IBAN,
                       "issuer_address": "just a street"})) == 1
    qr_iban = "CH44 3199 9123 0008 8901 2"  # QR-IBAN: needs a QR reference we don't create
    assert len(_pages({**BASE, "country": "CH", "tax_option": "exempt", "iban": qr_iban})) == 1


def test_girocode_only_when_ticked_and_eligible():
    de = {**BASE, "country": "DE", "tax_option": "klein", "issuer_address": "Musterweg 1\n80331 München",
          "iban": DE_IBAN, "bic": "COBADEFFXXX"}
    assert "GiroCode" in _pages({**de, "girocode": "1"})[0].extract_text()
    assert "GiroCode" not in _pages(de)[0].extract_text()
    assert "GiroCode" not in _pages({**de, "girocode": "1", "currency": "USD"})[0].extract_text()

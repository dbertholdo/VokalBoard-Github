import pytest
from pypdf import PdfReader

from app.invoice_pdf import InvoiceDocument, InvoiceValidationError, render_invoice_pdf
from io import BytesIO


def invoice(**changes):
    values = {
        "number": "2026-0001", "issue_date": "17.09.2026", "service_date": "10.09.2026",
        "issuer_name": "Ada Sängerin", "issuer_address": "Musterweg 1\n80331 München",
        "issuer_tax_id": "12/345/67890", "recipient_name": "Chor Beispiel",
        "recipient_address": "Platz 2\n10115 Berlin", "service_description": "Solo im Konzert",
        "net_amount": "120.00",
    }
    values.update(changes)
    return InvoiceDocument(**values)


def test_invoice_pdf_is_created_only_in_memory():
    pdf = render_invoice_pdf(invoice(iban="DE89370400440532013000"))
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 500


def test_invoice_pdf_rejects_missing_legal_core_fields():
    with pytest.raises(InvoiceValidationError):
        render_invoice_pdf(invoice(issuer_tax_id=""))


def test_invoice_pdf_has_signature_footer_p4_todo_18_09_2026():
    """To-do do P4 (rodapé de assinatura, decisão do Daniel) — vale para
    os dois fluxos, já que os dois passam por render_invoice_pdf()."""
    pdf = render_invoice_pdf(invoice())
    text = "".join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)
    assert "Made with assistance of VokalBoard" in text
    assert "www.vokalboard.com/rechnungmaker" in text

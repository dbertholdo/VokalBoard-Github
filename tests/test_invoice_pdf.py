from decimal import Decimal

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


def test_several_service_lines_7b():
    """Daniel 2026-09-28: more than one service per invoice; tax over all of them."""
    doc = invoice(extra_services=(("Probe am Vortag", "80,50"), ("Noten einrichten", "30")), tax_rate="19")
    net, tax, travel, lodging, total = doc.validate()
    assert net == Decimal("230.50") and tax == Decimal("43.80") and total == Decimal("274.30")
    text = "".join(page.extract_text() for page in PdfReader(BytesIO(render_invoice_pdf(doc))).pages)
    assert "Solo im Konzert" in text and "Probe am Vortag" in text and "Noten einrichten" in text
    with pytest.raises(InvoiceValidationError):
        invoice(extra_services=(("", "10"),)).validate()
    with pytest.raises(InvoiceValidationError):
        invoice(extra_services=(("Extra", "abc"),)).validate()


def test_invoice_has_no_vokalboard_logo_only_the_footer_7c():
    reader = PdfReader(BytesIO(render_invoice_pdf(invoice())))
    for page in reader.pages:
        resources = page.get("/Resources") or {}
        assert not (resources.get("/XObject") or {}), "no images (logo) on the invoice"
    text = "".join(page.extract_text() for page in reader.pages)
    assert text.count("VokalBoard") == 1  # the footer line only


def test_form_reads_and_cleans_extra_services():
    from starlette.datastructures import FormData
    from app.invoice_form import normalize, read_form, to_document
    form = FormData([("service_description", "Solo"), ("net_amount", "100"),
                     ("extra_service_description", "Probe"), ("extra_service_amount", "50"),
                     ("extra_service_description", ""), ("extra_service_amount", "")])
    values = normalize(read_form(form))
    assert values["extra_services"] == [{"description": "Probe", "amount": "50"}]
    values.update({"number": "1", "issue_date": "2026-09-29", "service_date": "2026-09-29", "issuer_name": "A",
                   "issuer_address": "B", "issuer_tax_id": "C", "recipient_name": "D", "recipient_address": "E"})
    assert to_document(values).validate()[0] == Decimal("150.00")

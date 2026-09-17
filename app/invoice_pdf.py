"""Stateless PDF renderer for Rechnungen.

This renderer has no filesystem access by design.  It accepts a validated data
object and returns PDF bytes, so the caller can stream it or attach it to an
email without retaining fiscal or bank details on VokalBoard infrastructure.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors


class InvoiceValidationError(ValueError):
    pass


@dataclass(frozen=True)
class InvoiceDocument:
    number: str
    issue_date: str
    service_date: str
    issuer_name: str
    issuer_address: str
    issuer_tax_id: str
    recipient_name: str
    recipient_address: str
    service_description: str
    net_amount: str
    currency: str = "EUR"
    tax_rate: str = "0"
    tax_note: str = ""
    payment_terms: str = ""
    iban: str = ""
    bic: str = ""

    def validate(self) -> tuple[Decimal, Decimal, Decimal]:
        required = {
            "number": self.number,
            "issue_date": self.issue_date,
            "service_date": self.service_date,
            "issuer_name": self.issuer_name,
            "issuer_address": self.issuer_address,
            "issuer_tax_id": self.issuer_tax_id,
            "recipient_name": self.recipient_name,
            "recipient_address": self.recipient_address,
            "service_description": self.service_description,
        }
        if any(not str(value).strip() for value in required.values()):
            raise InvoiceValidationError("Missing required invoice information")
        if self.currency not in {"EUR", "CHF"}:
            raise InvoiceValidationError("Unsupported currency")
        try:
            net = Decimal(self.net_amount.replace(",", "."))
            rate = Decimal(self.tax_rate.replace(",", "."))
        except (InvalidOperation, AttributeError) as exc:
            raise InvoiceValidationError("Amounts must be valid numbers") from exc
        if net < 0 or rate < 0 or rate > 100:
            raise InvoiceValidationError("Amounts or tax rate are outside the allowed range")
        tax = (net * rate / Decimal("100")).quantize(Decimal("0.01"))
        return net.quantize(Decimal("0.01")), tax, (net + tax).quantize(Decimal("0.01"))


def _escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")


def render_invoice_pdf(invoice: InvoiceDocument) -> bytes:
    net, tax, total = invoice.validate()
    stream = BytesIO()
    document = SimpleDocTemplate(stream, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm, topMargin=18 * mm)
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    title = styles["Title"]
    story = [Paragraph("Rechnung", title), Spacer(1, 8 * mm)]
    story.append(Table([
        [Paragraph(f"<b>Rechnungssteller</b><br/>{_escape(invoice.issuer_name)}<br/>{_escape(invoice.issuer_address)}<br/>Steuer-Nr./USt-IdNr.: {_escape(invoice.issuer_tax_id)}", body),
         Paragraph(f"<b>Rechnungsempfänger</b><br/>{_escape(invoice.recipient_name)}<br/>{_escape(invoice.recipient_address)}", body)],
        [Paragraph(f"Rechnungsnummer: {_escape(invoice.number)}<br/>Ausstellungsdatum: {_escape(invoice.issue_date)}<br/>Leistungsdatum: {_escape(invoice.service_date)}", body), ""],
    ], colWidths=[85 * mm, 85 * mm]))
    story.append(Spacer(1, 9 * mm))
    rows = [
        ["Leistung", "Netto"],
        [Paragraph(_escape(invoice.service_description), body), f"{net:.2f} {invoice.currency}"],
        ["Umsatzsteuer" + (f" ({invoice.tax_rate}%)" if tax else ""), f"{tax:.2f} {invoice.currency}"],
        ["Gesamtbetrag", f"{total:.2f} {invoice.currency}"],
    ]
    table = Table(rows, colWidths=[120 * mm, 50 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f5f4a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d6ddd9")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e8f2ed")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(table)
    notes = [value for value in [invoice.tax_note, invoice.payment_terms, f"IBAN: {invoice.iban}" if invoice.iban else "", f"BIC: {invoice.bic}" if invoice.bic else ""] if value]
    if notes:
        story.extend([Spacer(1, 8 * mm), Paragraph("<br/>".join(_escape(note) for note in notes), body)])
    document.build(story)
    return stream.getvalue()

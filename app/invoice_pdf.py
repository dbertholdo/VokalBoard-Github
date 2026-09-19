"""Stateless PDF renderer for Rechnungen.

This renderer has no filesystem access for USER data by design — it
accepts a validated data object and returns PDF bytes, so the caller can
stream it or attach it to an email without retaining fiscal or bank
details on VokalBoard infrastructure. The one file it does read from disk
is the static VokalBoard brand logo bundled with the app (never anything
user-supplied).

Layout (redesigned 19/09/2026 to match the reference "Muster GmbH"
Rechnung pattern Daniel shared): brand header with logo, a two-column
Rechnungssteller/Rechnungsempfänger address block, a metadata bar
(Rechnungs-Nr./Rechnungsdatum/Leistungsdatum), a line-items table with
Pos./Bezeichnung/Menge/Einheit/Einzelpreis/Gesamt columns, a totals block
(Summe Netto/Umsatzsteuer/Endsumme), then the free-text notes
(Lieferbedingung-equivalent: tax note, payment terms, IBAN/BIC) and the
existing footer credit line. The data model still holds a single
service line (+ optional travel/lodging lines) rather than an arbitrary
per-item table — Daniel's request was to match the reference *pattern*,
not to add multi-line-item entry, so Menge/Einheit are synthesized
("1" / "pausch.") for the one service row rather than collected from a
new form field. Flag if that assumption is wrong and it can be revisited.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

# Brand tokens (VokalBoard identity v1.0, 19/09/2026 — see CLAUDE.md §1 and
# app/static/css/style.css :root). Kept as literal hex here since ReportLab
# has no access to CSS custom properties; keep in sync by hand if the
# palette ever changes.
_NAVY = colors.HexColor("#17283F")
_BG_MINERAL = colors.HexColor("#F5F7FA")
_ACCENT_VIOLET = colors.HexColor("#635BDE")
_GRID_LINE = colors.HexColor("#D8DEE8")
_MUTED_TEXT = colors.HexColor("#5B6B82")

_LOGO_PATH = Path(__file__).resolve().parent / "static" / "img" / "brand" / "icon-256.png"


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
    # Despesas adicionais opcionais (Fahrkosten/Übernachtungskosten) —
    # só o VALOR entra na Rechnung como linha extra; comprovante nunca é
    # anexado/armazenado pelo site (decisão do Daniel, 18/09/2026: o
    # comprovante é resolvido diretamente entre as partes, fora daqui).
    expense_travel_amount: str = "0"
    expense_lodging_amount: str = "0"

    def validate(self) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
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
            travel = Decimal(str(self.expense_travel_amount or "0").replace(",", "."))
            lodging = Decimal(str(self.expense_lodging_amount or "0").replace(",", "."))
        except (InvalidOperation, AttributeError) as exc:
            raise InvoiceValidationError("Amounts must be valid numbers") from exc
        if net < 0 or rate < 0 or rate > 100 or travel < 0 or lodging < 0:
            raise InvoiceValidationError("Amounts or tax rate are outside the allowed range")
        tax = (net * rate / Decimal("100")).quantize(Decimal("0.01"))
        net_q = net.quantize(Decimal("0.01"))
        travel_q = travel.quantize(Decimal("0.01"))
        lodging_q = lodging.quantize(Decimal("0.01"))
        total = (net_q + tax + travel_q + lodging_q).quantize(Decimal("0.01"))
        return net_q, tax, travel_q, lodging_q, total


def _escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")


def _styles():
    base = getSampleStyleSheet()
    body = base["BodyText"].clone("InvoiceBody")
    body.fontSize = 9.5
    body.leading = 13

    kicker = base["BodyText"].clone("InvoiceKicker")
    kicker.fontSize = 7.5
    kicker.leading = 10
    kicker.textColor = _MUTED_TEXT
    kicker.spaceAfter = 2

    brand = base["BodyText"].clone("InvoiceBrand")
    brand.fontName = "Helvetica-Bold"
    brand.fontSize = 13
    brand.textColor = _NAVY

    doc_title = base["BodyText"].clone("InvoiceDocTitle")
    doc_title.fontName = "Helvetica-Bold"
    doc_title.fontSize = 22
    doc_title.textColor = _NAVY
    doc_title.alignment = TA_RIGHT

    meta_label = base["BodyText"].clone("InvoiceMetaLabel")
    meta_label.fontSize = 8
    meta_label.textColor = _MUTED_TEXT

    footer = base["BodyText"].clone("InvoiceFooter")
    footer.fontSize = 7
    footer.leading = 9
    footer.alignment = TA_CENTER
    footer.textColor = _MUTED_TEXT

    notes = base["BodyText"].clone("InvoiceNotes")
    notes.fontSize = 8.5
    notes.leading = 12
    notes.textColor = _MUTED_TEXT

    return {
        "body": body, "kicker": kicker, "brand": brand, "doc_title": doc_title,
        "meta_label": meta_label, "footer": footer, "notes": notes,
    }


def _header_flowable(styles):
    """Logo + 'VokalBoard' wordmark on the left, 'Rechnung' as the
    document title on the right — the layout Daniel asked for
    ('lá em cima o logo do VokalBoard')."""
    brand_cell = [Paragraph("VokalBoard", styles["brand"])]
    if _LOGO_PATH.exists():
        logo = Image(str(_LOGO_PATH), width=9 * mm, height=9 * mm)
        brand_table = Table([[logo, Paragraph("VokalBoard", styles["brand"])]], colWidths=[11 * mm, 60 * mm])
        brand_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        brand_cell = brand_table
    header = Table([[brand_cell, Paragraph("Rechnung", styles["doc_title"])]], colWidths=[95 * mm, 75 * mm])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return header


def render_invoice_pdf(invoice: InvoiceDocument) -> bytes:
    net, tax, travel, lodging, total = invoice.validate()
    styles = _styles()
    body = styles["body"]
    stream = BytesIO()
    document = SimpleDocTemplate(stream, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    story = [_header_flowable(styles), Spacer(1, 10 * mm)]

    # Rechnungssteller / Rechnungsempfänger — two-column address block,
    # matching the reference layout's "issuer top area / recipient
    # window" pattern.
    story.append(Table([
        [
            Paragraph(f"<b>Rechnungssteller</b>", styles["kicker"]),
            Paragraph(f"<b>Rechnungsempfänger</b>", styles["kicker"]),
        ],
        [
            Paragraph(f"{_escape(invoice.issuer_name)}<br/>{_escape(invoice.issuer_address)}<br/>Steuer-Nr./USt-IdNr.: {_escape(invoice.issuer_tax_id)}", body),
            Paragraph(f"{_escape(invoice.recipient_name)}<br/>{_escape(invoice.recipient_address)}", body),
        ],
    ], colWidths=[85 * mm, 85 * mm]))
    story.append(Spacer(1, 7 * mm))

    # Metadata bar — Rechnungs-Nr./Rechnungsdatum/Leistungsdatum, in the
    # shaded strip the reference sample uses for this row.
    meta = Table([[
        Paragraph(f"<font color='#5B6B82' size=8>Rechnungs-Nr.</font><br/><b>{_escape(invoice.number)}</b>", body),
        Paragraph(f"<font color='#5B6B82' size=8>Rechnungsdatum</font><br/><b>{_escape(invoice.issue_date)}</b>", body),
        Paragraph(f"<font color='#5B6B82' size=8>Leistungsdatum</font><br/><b>{_escape(invoice.service_date)}</b>", body),
    ]], colWidths=[56.6 * mm, 56.7 * mm, 56.7 * mm])
    meta.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _BG_MINERAL),
        ("BOX", (0, 0), (-1, -1), 0.4, _GRID_LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, _GRID_LINE),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(meta)
    story.append(Spacer(1, 9 * mm))

    # Line items — Pos./Bezeichnung/Menge/Einheit/Einzelpreis/Gesamt, the
    # reference sample's item-table columns. The data model has one
    # service line (+ optional travel/lodging), so Menge/Einheit are
    # synthesized rather than collected per item.
    header_row = ["Pos.", "Bezeichnung", "Menge", "Einh.", f"E-Preis ({invoice.currency})", f"Gesamt ({invoice.currency})"]
    rows = [header_row]
    pos = 1
    rows.append([str(pos), Paragraph(_escape(invoice.service_description), body), "1", "pausch.", f"{net:.2f}", f"{net:.2f}"])
    if travel:
        pos += 1
        rows.append([str(pos), "Fahrkosten", "1", "pausch.", f"{travel:.2f}", f"{travel:.2f}"])
    if lodging:
        pos += 1
        rows.append([str(pos), "Übernachtungskosten", "1", "pausch.", f"{lodging:.2f}", f"{lodging:.2f}"])
    items = Table(rows, colWidths=[9 * mm, 70 * mm, 14 * mm, 17 * mm, 30 * mm, 30 * mm])
    items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.3, _GRID_LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _BG_MINERAL]),
    ]))
    story.append(items)
    story.append(Spacer(1, 6 * mm))

    # Totals — Summe Netto / Umsatzsteuer / Endsumme, right-aligned block.
    tax_label = "Umsatzsteuer" + (f" ({invoice.tax_rate}%)" if tax else " (0%)")
    totals_rows = [
        ["Summe Netto", f"{net:.2f} {invoice.currency}"],
        [tax_label, f"{tax:.2f} {invoice.currency}"],
        ["Endsumme", f"{total:.2f} {invoice.currency}"],
    ]
    totals = Table(totals_rows, colWidths=[40 * mm, 30 * mm], hAlign="RIGHT")
    totals.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.6, _ACCENT_VIOLET),
        ("TOPPADDING", (0, -1), (-1, -1), 5),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 11),
        ("TEXTCOLOR", (0, -1), (-1, -1), _NAVY),
        ("PADDING", (0, 0), (-1, -2), 3),
    ]))
    story.append(totals)

    # Notes — Lieferbedingung-equivalent: tax note, payment terms, IBAN/BIC.
    notes = [value for value in [invoice.tax_note, invoice.payment_terms, f"IBAN: {invoice.iban}" if invoice.iban else "", f"BIC: {invoice.bic}" if invoice.bic else ""] if value]
    if notes:
        story.extend([Spacer(1, 9 * mm), Paragraph("<br/>".join(_escape(note) for note in notes), styles["notes"])])

    # Assinatura no rodapé (to-do do P4, adicionada em 18/09/2026) — mesmo
    # texto/estilo nos dois fluxos (Avulso e Match), já que os dois passam
    # por esta mesma função de render.
    story.extend([Spacer(1, 12 * mm), Paragraph(_INVOICE_FOOTER_TEXT, styles["footer"])])
    document.build(story)
    return stream.getvalue()


_INVOICE_FOOTER_TEXT = "Made with assistance of VokalBoard - Rechnung Maker - www.vokalboard.com/rechnungmaker"

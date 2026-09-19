"""Stateless PDF renderer for a printable listing flyer (19/09/2026).

Daniel: "precisamos também de uma forma da pessoa poder baixar anúncios e
gerar um QR code nele. Pq a pessoa pode imprimir e colar em algum lugar,
as pessoas só escaneiam o QR code e pronto." — a poster-style A4 page,
big QR Code front and center linking back to the listing on the site, so
someone can print it and stick it up somewhere (a conservatory notice
board, a church bulletin board) and people just scan it.

Same shape as app/invoice_pdf.py / app/cv_pdf.py: takes a plain
dataclass built from already-fetched listing data and returns PDF bytes
in memory — nothing written to disk except reading the app's own bundled
brand logo (never anything user-supplied).
"""
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, Image

from app.qr import qr_png_bytes

_NAVY = colors.HexColor("#17283F")
_ACCENT_VIOLET = colors.HexColor("#635BDE")
_BG_MINERAL = colors.HexColor("#F5F7FA")
_MUTED_TEXT = colors.HexColor("#526176")
_LOGO_PATH = Path(__file__).resolve().parent / "static" / "img" / "brand" / "icon-256.png"


def _escape(value: str) -> str:
    return (value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@dataclass(frozen=True)
class ListingFlyerDocument:
    title: str
    type_label: str            # already-translated listing_type_* label
    listing_url: str
    voice_type: str = ""
    city: str = ""
    country: str = ""
    event_date: str = ""       # already formatted for display, or ""
    fee_text: str = ""         # already formatted (format_fee), or ""
    venue: str = ""
    scan_caption: str = "Scan the QR Code for details"


def _styles():
    base = getSampleStyleSheet()
    brand = base["BodyText"].clone("FlyerBrand")
    brand.fontName = "Helvetica-Bold"
    brand.fontSize = 13
    brand.textColor = _NAVY
    brand.alignment = TA_CENTER

    type_label = base["BodyText"].clone("FlyerTypeLabel")
    type_label.fontSize = 11
    type_label.textColor = colors.white
    type_label.alignment = TA_CENTER

    title = base["BodyText"].clone("FlyerTitle")
    title.fontName = "Helvetica-Bold"
    title.fontSize = 26
    title.leading = 31
    title.textColor = _NAVY
    title.alignment = TA_CENTER

    fact_label = base["BodyText"].clone("FlyerFactLabel")
    fact_label.fontSize = 8.5
    fact_label.textColor = _MUTED_TEXT
    fact_label.alignment = TA_CENTER

    fact_value = base["BodyText"].clone("FlyerFactValue")
    fact_value.fontName = "Helvetica-Bold"
    fact_value.fontSize = 12.5
    fact_value.textColor = _NAVY
    fact_value.alignment = TA_CENTER

    caption = base["BodyText"].clone("FlyerCaption")
    caption.fontSize = 11
    caption.textColor = _NAVY
    caption.alignment = TA_CENTER

    footer = base["BodyText"].clone("FlyerFooter")
    footer.fontSize = 8
    footer.textColor = _MUTED_TEXT
    footer.alignment = TA_CENTER

    return {
        "brand": brand, "type_label": type_label, "title": title,
        "fact_label": fact_label, "fact_value": fact_value,
        "caption": caption, "footer": footer,
    }


def render_listing_flyer_pdf(listing: ListingFlyerDocument) -> bytes:
    styles = _styles()
    stream = BytesIO()
    document = SimpleDocTemplate(
        stream, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm
    )
    story = []

    # Brand header — logo + wordmark, centered.
    if _LOGO_PATH.exists():
        logo = Image(str(_LOGO_PATH), width=10 * mm, height=10 * mm)
        brand_row = Table([[logo, Paragraph("VokalBoard", styles["brand"])]], colWidths=[12 * mm, 60 * mm])
        brand_row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(Table([[brand_row]], colWidths=[174 * mm], style=TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")])))
    else:
        story.append(Paragraph("VokalBoard", styles["brand"]))
    story.append(Spacer(1, 10 * mm))

    # Listing-type pill (navy band) — "Dirigent(in) sucht Sänger(in)" etc.
    type_pill = Table([[Paragraph(_escape(listing.type_label), styles["type_label"])]], colWidths=[100 * mm])
    type_pill.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _ACCENT_VIOLET),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 5),
        ("ROUNDEDCORNERS", [10, 10, 10, 10]),
    ]))
    story.append(Table([[type_pill]], colWidths=[174 * mm], style=TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")])))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph(_escape(listing.title), styles["title"]))
    story.append(Spacer(1, 10 * mm))

    # Facts strip — whatever applies (voice type / city / date / fee /
    # venue), skipping anything the listing didn't set.
    facts = []
    if listing.voice_type:
        facts.append(("Stimmlage", listing.voice_type))
    if listing.city or listing.country:
        facts.append(("Ort", ", ".join(b for b in [listing.city, listing.country] if b)))
    if listing.event_date:
        facts.append(("Datum", listing.event_date))
    if listing.fee_text:
        facts.append(("Honorar", listing.fee_text))
    if listing.venue:
        facts.append(("Veranstaltungsort", listing.venue))

    if facts:
        fact_cells = []
        for fact_title, value in facts:
            fact_cells.append([Paragraph(_escape(fact_title), styles["fact_label"]), Paragraph(_escape(value), styles["fact_value"])])
        # Two-column grid, wrapping every 2 facts per row for readability.
        rows = []
        for i in range(0, len(fact_cells), 2):
            pair = fact_cells[i:i + 2]
            row_cells = []
            for cell in pair:
                inner = Table([[cell[0]], [cell[1]]], colWidths=[80 * mm])
                inner.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("BOTTOMPADDING", (0, 0), (0, 0), 1)]))
                row_cells.append(inner)
            if len(row_cells) == 1:
                row_cells.append("")
            rows.append(row_cells)
        facts_table = Table(rows, colWidths=[87 * mm, 87 * mm])
        facts_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), _BG_MINERAL),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("PADDING", (0, 0), (-1, -1), 8),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#DCE2EB")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DCE2EB")),
        ]))
        story.append(facts_table)
        story.append(Spacer(1, 14 * mm))

    # Big, dominant QR Code — the whole point of the flyer.
    qr_png = qr_png_bytes(listing.listing_url, box_size=10, border=2, fill_color="#17283F")
    qr_image = Image(BytesIO(qr_png), width=70 * mm, height=70 * mm)
    qr_wrap = Table([[qr_image]], colWidths=[174 * mm])
    qr_wrap.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    story.append(qr_wrap)
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(_escape(listing.scan_caption), styles["caption"]))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(_escape(listing.listing_url), styles["footer"]))

    story.append(Spacer(1, 16 * mm))
    story.append(Paragraph("VokalBoard - www.vokalboard.com", styles["footer"]))

    document.build(story)
    return stream.getvalue()

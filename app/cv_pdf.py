"""P2 cluster (19/09/2026) — stateless PDF CV export.

Same shape as app/invoice_pdf.py: accepts a plain dataclass built from
already-fetched profile data and returns PDF bytes in memory, streamed
straight to the response (app/routers/profile_routes.py) — nothing is
written to disk except reading the user's OWN already-saved avatar file
(app/avatars.py) and the app's own brand logo, never anything new.

Redesigned 19/09/2026 (Daniel: "O perfil para download em PDF tem que
parecer esse da imagem/dos cards no perfil no final, quando baixar" — a
reference photo of a classic sidebar-style Lebenslauf, plus the actual
public-profile "id card" on this site) and to fix two bugs Daniel found:
the photo wasn't included and no QR Code was generated. The new layout
borrows from both: a navy header band shaped like the profile's own
`.id-card` (photo, name, role/voice line, badge pills, "Hervorgehobenes
Profil" banner when it applies) with a QR Code linking to the public
profile on the right — then the classic CV sections below (bio,
languages, repertoire, works, audio samples), all built strictly from
whatever the person actually filled in (no placeholder "Max
Mustermann" content — an empty section is simply skipped).
"""
import os
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib import colors
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer, ListFlowable, ListItem, Table, TableStyle, Image

from app.qr import qr_png_bytes

_NAVY = colors.HexColor("#17283F")
_ACCENT_VIOLET = colors.HexColor("#635BDE")
_ACCENT_LIGHT = colors.HexColor("#EEECFC")
_BG_MINERAL = colors.HexColor("#F5F7FA")
_MUTED_TEXT = colors.HexColor("#8290A3")  # lighter than invoice's --muted, for use on navy
_LOGO_PATH = Path(__file__).resolve().parent / "static" / "img" / "brand" / "icon-256.png"


def _escape(value: str) -> str:
    return (value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@dataclass(frozen=True)
class CvWork:
    title: str
    composer: str = ""


@dataclass(frozen=True)
class CvDocument:
    full_name: str
    role_label: str = ""         # "Sänger(in)" / "Dirigent(in)", translated
    headline: str = ""           # e.g. "Lyric Soprano" or ensemble name
    city: str = ""
    country: str = ""
    bio: str = ""
    phone: str = ""              # empty string = don't show (respects phone_visibility)
    email: str = ""
    profile_url: str = ""
    avatar_path: str = ""        # local disk path (app/avatars.py) — "" if none
    badges: list[str] = field(default_factory=list)   # already-translated labels, top 3
    is_highlighted: bool = False
    spoken_languages: list[str] = field(default_factory=list)
    composer_tags: list[str] = field(default_factory=list)
    solo_works: list[CvWork] = field(default_factory=list)
    choir_works: list[CvWork] = field(default_factory=list)
    audio_links: list[str] = field(default_factory=list)


class _CircleAvatar(Flowable):
    """A photo clipped to a circle, or — with no photo — a navy circle
    with the name's first letter in it (same fallback as the public
    profile's `.avatar-placeholder`). Platypus/reportlab has no built-in
    "rounded image" flowable, so this draws directly on the canvas with
    a clip path, the same technique used nowhere else in this codebase
    but is the standard reportlab approach for a clipped raster image.
    """

    def __init__(self, diameter: float, avatar_path: str, initial: str):
        super().__init__()
        self.diameter = diameter
        self.avatar_path = avatar_path
        self.initial = (initial or "?").upper()
        self.width = diameter
        self.height = diameter

    def draw(self):
        canv = self.canv
        d = self.diameter
        if self.avatar_path and os.path.exists(self.avatar_path):
            canv.saveState()
            path = canv.beginPath()
            path.circle(d / 2, d / 2, d / 2)
            canv.clipPath(path, stroke=0)
            try:
                canv.drawImage(self.avatar_path, 0, 0, width=d, height=d, mask="auto", preserveAspectRatio=True)
            except Exception:
                # Corrupted/unreadable avatar file — fall back to the
                # initial-letter circle rather than failing the whole
                # PDF download.
                canv.restoreState()
                self._draw_placeholder(canv, d)
                return
            canv.restoreState()
        else:
            self._draw_placeholder(canv, d)

    def _draw_placeholder(self, canv, d):
        canv.saveState()
        canv.setFillColor(_ACCENT_VIOLET)
        canv.circle(d / 2, d / 2, d / 2, stroke=0, fill=1)
        canv.setFillColor(colors.white)
        canv.setFont("Helvetica-Bold", d * 0.42)
        canv.drawCentredString(d / 2, d / 2 - d * 0.15, self.initial)
        canv.restoreState()


def _styles():
    base = getSampleStyleSheet()
    body = base["BodyText"].clone("CvBody")
    body.fontSize = 9.5
    body.leading = 13.5

    name_style = ParagraphStyle("CvName", parent=base["Title"], alignment=TA_LEFT, textColor=colors.white, fontSize=20, leading=23, spaceAfter=0)
    role_style = ParagraphStyle("CvRole", parent=body, alignment=TA_LEFT, textColor=_ACCENT_LIGHT, fontSize=11, leading=14)
    contact_style = ParagraphStyle("CvContact", parent=body, alignment=TA_LEFT, textColor=colors.white, fontSize=8.5, leading=13)
    highlight_style = ParagraphStyle("CvHighlight", parent=body, alignment=TA_LEFT, textColor=colors.HexColor("#F4C542"), fontSize=8.5, leading=12)
    badge_style = ParagraphStyle("CvBadge", parent=body, alignment=TA_CENTER, textColor=_NAVY, fontSize=7.5, leading=9)
    section_style = ParagraphStyle("CvSection", parent=base["Heading2"], textColor=_NAVY, fontSize=12.5, spaceBefore=12, spaceAfter=4)
    link_style = ParagraphStyle("CvLink", parent=body, alignment=TA_CENTER, textColor=_MUTED_TEXT, fontSize=7.5, leading=10)
    footer_style = base["BodyText"].clone("CvFooter")
    footer_style.fontSize = 7
    footer_style.leading = 9
    footer_style.alignment = TA_CENTER
    footer_style.textColor = colors.HexColor("#8290A3")

    return {
        "body": body, "name": name_style, "role": role_style, "contact": contact_style,
        "highlight": highlight_style, "badge": badge_style, "section": section_style,
        "link": link_style, "footer": footer_style,
    }


def _badge_pill(label: str, styles) -> Table:
    t = Table([[Paragraph(_escape(label), styles["badge"])]], colWidths=[None])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
    ]))
    return t


def _id_card_header(cv: CvDocument, styles):
    """Navy header band matching the public profile's `.id-card` —
    photo, name, role/voice line, badges, highlighted banner — with a
    QR Code (linking to the public profile) on the right so the PDF
    can be scanned straight back to the live profile."""
    avatar = _CircleAvatar(24 * mm, cv.avatar_path, cv.full_name[:1] if cv.full_name else "?")

    name_block = [Paragraph(_escape(cv.full_name), styles["name"])]
    role_line = " · ".join(bit for bit in [cv.role_label, cv.headline] if bit)
    if role_line:
        name_block.append(Paragraph(_escape(role_line), styles["role"]))
    if cv.is_highlighted:
        name_block.append(Spacer(1, 1.5 * mm))
        name_block.append(Paragraph("&#9733; " + _escape("Hervorgehobenes Profil"), styles["highlight"]))

    contact_bits = []
    if cv.email:
        contact_bits.append(_escape(cv.email))
    if cv.phone:
        contact_bits.append(_escape(cv.phone))
    location_bits = [b for b in (cv.city, cv.country) if b]
    if location_bits:
        contact_bits.append(_escape(", ".join(location_bits)))
    if contact_bits:
        name_block.append(Spacer(1, 2 * mm))
        name_block.append(Paragraph(" &nbsp;·&nbsp; ".join(contact_bits), styles["contact"]))

    if cv.badges:
        name_block.append(Spacer(1, 2 * mm))
        pills = [_badge_pill(b, styles) for b in cv.badges]
        badge_row = Table([pills], colWidths=[None] * len(pills), hAlign="LEFT")
        badge_row.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        name_block.append(badge_row)

    right_cell = ""
    if cv.profile_url:
        qr_png = qr_png_bytes(cv.profile_url, box_size=4, border=1, fill_color="#17283F")
        qr_image = Image(BytesIO(qr_png), width=22 * mm, height=22 * mm)
        right_cell = [qr_image, Spacer(1, 1.5 * mm), Paragraph(_escape(cv.profile_url), styles["link"])]

    header = Table(
        [[avatar, name_block, right_cell]],
        colWidths=[30 * mm, 108 * mm, 32 * mm],
    )
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 0), (2, 0), "CENTER"),
        ("LEFTPADDING", (0, 0), (0, 0), 8 * mm),
        ("PADDING", (0, 0), (-1, -1), 6 * mm),
    ]))
    return header


def render_cv_pdf(cv: CvDocument) -> bytes:
    stream = BytesIO()
    document = SimpleDocTemplate(
        stream, pagesize=A4, rightMargin=0, leftMargin=0, topMargin=0, bottomMargin=16 * mm
    )
    styles = _styles()
    body = styles["body"]
    section_style = styles["section"]

    story = [_id_card_header(cv, styles), Spacer(1, 8 * mm)]

    # Everything below the header band keeps the page's normal margins —
    # only the header itself runs edge-to-edge, so an inner-margin Table
    # wraps the rest of the content.
    inner = []

    if cv.bio:
        inner.append(Paragraph("Biografie", section_style))
        inner.append(Paragraph(_escape(cv.bio).replace("\n", "<br/>"), body))

    if cv.spoken_languages:
        inner.append(Paragraph("Sprachen", section_style))
        inner.append(Paragraph(_escape(", ".join(cv.spoken_languages)), body))

    if cv.composer_tags:
        inner.append(Paragraph("Repertoireschwerpunkt", section_style))
        inner.append(Paragraph(_escape(", ".join(cv.composer_tags)), body))

    def works_section(title: str, works: list) -> None:
        if not works:
            return
        inner.append(Paragraph(title, section_style))
        items = []
        for w in works:
            label = _escape(w.title)
            if w.composer:
                label += f" — {_escape(w.composer)}"
            items.append(ListItem(Paragraph(label, body)))
        inner.append(ListFlowable(items, bulletType="bullet", leftIndent=10))

    works_section("Solorepertoire", cv.solo_works)
    works_section("Chorrepertoire", cv.choir_works)

    if cv.audio_links:
        inner.append(Paragraph("Hörbeispiele", section_style))
        items = [ListItem(Paragraph(_escape(u), body)) for u in cv.audio_links]
        inner.append(ListFlowable(items, bulletType="bullet", leftIndent=10))

    inner_table = Table([[inner]], colWidths=[170 * mm])
    inner_table.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 20 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 20 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(inner_table)

    story.append(Spacer(1, 14 * mm))
    # FIX (19/09/2026, Daniel: "Padronizar rodapé") — was "Vokal Board"
    # (two words), inconsistent with the one-word "VokalBoard" brand
    # used everywhere else (base.html, listing_pdf.py footer/brand row).
    footer = Table([[Paragraph("VokalBoard - Trusted Member - www.vokalboard.com", styles["footer"])]], colWidths=[210 * mm])
    footer.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("PADDING", (0, 0), (-1, -1), 0)]))
    story.append(footer)

    document.build(story)
    return stream.getvalue()

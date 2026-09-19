"""P2 cluster (19/09/2026) — stateless PDF CV export.

Same shape as app/invoice_pdf.py: accepts a plain dataclass built from
already-fetched profile data and returns PDF bytes in memory, streamed
straight to the response (app/routers/profile_routes.py) — nothing is
written to disk. Only the business-card/QR half of the original P2
export item was picked by Daniel (AskUserQuestion, 19/09/2026); this
module covers the PDF CV only.
"""
from dataclasses import dataclass, field
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, ListFlowable, ListItem


def _escape(value: str) -> str:
    return (value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@dataclass(frozen=True)
class CvWork:
    title: str
    composer: str = ""


@dataclass(frozen=True)
class CvDocument:
    full_name: str
    headline: str = ""          # e.g. "Lyric Soprano" or ensemble name
    city: str = ""
    country: str = ""
    bio: str = ""
    phone: str = ""              # empty string = don't show (respects phone_visibility)
    email: str = ""
    profile_url: str = ""
    spoken_languages: list[str] = field(default_factory=list)
    composer_tags: list[str] = field(default_factory=list)
    solo_works: list[CvWork] = field(default_factory=list)
    choir_works: list[CvWork] = field(default_factory=list)
    audio_links: list[str] = field(default_factory=list)


def render_cv_pdf(cv: CvDocument) -> bytes:
    stream = BytesIO()
    document = SimpleDocTemplate(
        stream, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm
    )
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    name_style = ParagraphStyle("CvName", parent=styles["Title"], alignment=TA_CENTER, textColor=colors.HexColor("#17283F"))
    headline_style = ParagraphStyle("CvHeadline", parent=styles["BodyText"], alignment=TA_CENTER, textColor=colors.HexColor("#635BDE"))
    section_style = ParagraphStyle("CvSection", parent=styles["Heading2"], textColor=colors.HexColor("#17283F"), spaceBefore=10, spaceAfter=4)

    story = [Paragraph(_escape(cv.full_name), name_style)]
    if cv.headline:
        story.append(Paragraph(_escape(cv.headline), headline_style))
    location_bits = [b for b in (cv.city, cv.country) if b]
    if location_bits:
        story.append(Paragraph(_escape(", ".join(location_bits)), ParagraphStyle("CvLoc", parent=body, alignment=TA_CENTER)))
    story.append(Spacer(1, 6 * mm))

    contact_bits = []
    if cv.email:
        contact_bits.append(_escape(cv.email))
    if cv.phone:
        contact_bits.append(_escape(cv.phone))
    if cv.profile_url:
        contact_bits.append(_escape(cv.profile_url))
    if contact_bits:
        story.append(Paragraph(" &nbsp;·&nbsp; ".join(contact_bits), ParagraphStyle("CvContact", parent=body, alignment=TA_CENTER)))
        story.append(Spacer(1, 4 * mm))

    if cv.bio:
        story.append(Paragraph("Bio", section_style))
        story.append(Paragraph(_escape(cv.bio).replace("\n", "<br/>"), body))

    if cv.spoken_languages:
        story.append(Paragraph("Languages", section_style))
        story.append(Paragraph(_escape(", ".join(cv.spoken_languages)), body))

    if cv.composer_tags:
        story.append(Paragraph("Repertoire focus", section_style))
        story.append(Paragraph(_escape(", ".join(cv.composer_tags)), body))

    def works_section(title: str, works: list) -> None:
        if not works:
            return
        story.append(Paragraph(title, section_style))
        items = []
        for w in works:
            label = _escape(w.title)
            if w.composer:
                label += f" — {_escape(w.composer)}"
            items.append(ListItem(Paragraph(label, body)))
        story.append(ListFlowable(items, bulletType="bullet", leftIndent=10))

    works_section("Solo repertoire", cv.solo_works)
    works_section("Choir repertoire", cv.choir_works)

    if cv.audio_links:
        story.append(Paragraph("Audio samples", section_style))
        items = [ListItem(Paragraph(_escape(u), body)) for u in cv.audio_links]
        story.append(ListFlowable(items, bulletType="bullet", leftIndent=10))

    document.build(story)
    return stream.getvalue()

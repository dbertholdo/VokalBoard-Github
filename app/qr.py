"""Shared QR Code generation (19/09/2026).

Used by both the CV PDF export (app/cv_pdf.py — a QR pointing at the
person's public profile) and the listing flyer PDF (app/listing_pdf.py —
a QR pointing at the listing, meant to be printed and stuck on a wall so
people can just scan it). Kept in one place instead of duplicated so
both PDFs use the same visual style (brand navy modules, no border
noise) and the same error-correction level.

Pure Python (the `qrcode` package) + Pillow, both already dependencies —
no system package (no libqrencode, no cairo) needed, consistent with why
reportlab/nh3/etc. were picked for this stack (see requirements.txt).
"""
from io import BytesIO

import qrcode
from qrcode.constants import ERROR_CORRECT_M


def qr_png_bytes(url: str, box_size: int = 8, border: int = 2, fill_color: str = "#17283F") -> bytes:
    """Renders `url` as a PNG QR code and returns the raw bytes.

    fill_color defaults to the brand navy (--ink); a QR code's contrast
    requirement is high enough that a lighter brand color (violet) would
    risk scan reliability on a printed flyer, so navy-on-white stays the
    default rather than trying to force the full brand palette in here.
    """
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=box_size, border=border)
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image(fill_color=fill_color, back_color="white").convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()

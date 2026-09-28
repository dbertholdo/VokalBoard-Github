"""Payment QR codes on invoices — Rechnungmaker v2 phase 2 (2026-09-28).

- Swiss QR-bill (official payment part + receipt, scanned by Swiss banking
  apps): added automatically when the IBAN is Swiss/Liechtenstein, the
  currency is CHF or EUR and the addresses can be read as "Street No" +
  "Postcode City". Built with `qrbill` (MIT) as SVG and turned into a
  ReportLab drawing with `svglib` (LGPL-3.0, used as an unmodified library).
- GiroCode (EPC QR, SEPA credit transfer): optional, for EUR invoices with a
  valid SEPA IBAN. Drawn with ReportLab's own QR widget (no new package).

Anything missing or invalid → no QR code, never a failed invoice. Nothing is
stored: the codes are built in memory from the same values as the PDF
(Zero-Storage, CLAUDE.md §2).
"""
import io
import re
from decimal import Decimal

from stdnum import iban as iban_check

# SEPA scheme countries (EPC list) — GiroCode only makes sense for these.
SEPA_COUNTRIES = frozenset(
    "AD AT BE BG CH CY CZ DE DK EE ES FI FR GB GI GR HR HU IE IS IT LI LT LU LV MC MT NL NO PL PT RO SE SI SK SM VA".split()
)
_PCODE_CITY = re.compile(r"^(?:[A-Z]{1,2}-)?(\d{4,5})\s+(.+)$")
_STREET_NO = re.compile(r"^(.*?\D)\s+(\d+\s*[A-Za-z]?(?:[-/]\d+\s*[A-Za-z]?)?)$")


def clean_iban(value: str) -> str:
    return re.sub(r"\s+", "", value or "").upper()


def iban_valid(value: str) -> bool:
    return bool(value) and iban_check.is_valid(clean_iban(value))


def parse_address(text: str) -> dict | None:
    """"Musterweg 12\\n8001 Zürich" (or one line with a comma) → street, house_num,
    pcode, city. None if no "postcode city" part is found."""
    parts = [p.strip() for p in re.split(r"[\n,]+", text or "") if p.strip()]
    for i, part in enumerate(parts):
        m = _PCODE_CITY.match(part)
        if not m:
            continue
        street_line = parts[i - 1] if i > 0 else ""
        s = _STREET_NO.match(street_line)
        street, house = (s.group(1).strip(), s.group(2).strip()) if s else (street_line, "")
        return {"street": street[:70], "house_num": house[:16], "pcode": m.group(1), "city": m.group(2)[:35]}
    return None


# --- GiroCode (EPC069-12, version 002) --------------------------------------

def girocode_eligible(currency: str, iban: str) -> bool:
    return currency == "EUR" and iban_valid(iban) and clean_iban(iban)[:2] in SEPA_COUNTRIES


def epc_payload(name: str, iban: str, bic: str, amount: Decimal, remittance: str) -> str:
    """The text a GiroCode encodes (banking apps fill the transfer from it)."""
    lines = ["BCD", "002", "1", "SCT", (bic or "").replace(" ", "").upper()[:11], (name or "").strip()[:70],
             clean_iban(iban), f"EUR{Decimal(amount):.2f}", "", "", (remittance or "").strip()[:140]]
    return "\n".join(lines)


def girocode_drawing(payload: str, size_mm: float = 30):
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib.units import mm

    widget = QrCodeWidget(payload, barLevel="M")
    x0, y0, x1, y1 = widget.getBounds()
    size = size_mm * mm
    drawing = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
    drawing.add(widget)
    return drawing


# --- Swiss QR-bill -------------------------------------------------------------

def swiss_eligible(currency: str, iban: str) -> bool:
    return currency in ("CHF", "EUR") and iban_valid(iban) and clean_iban(iban)[:2] in ("CH", "LI")


def _is_qr_iban(iban: str) -> bool:
    """QR-IBANs (bank id 30000-31999) require a QR reference we don't generate."""
    digits = clean_iban(iban)[4:9]
    return digits.isdigit() and 30000 <= int(digits) <= 31999


def swiss_bill_drawing(*, iban: str, currency: str, amount: Decimal, creditor_name: str, creditor_address: str,
                       creditor_country: str, message: str, lang: str):
    """ReportLab drawing of the 210 × 105 mm payment part, or None."""
    if not swiss_eligible(currency, iban) or _is_qr_iban(iban):
        return None
    creditor = parse_address(creditor_address)
    if not creditor or not (creditor_name or "").strip():
        return None
    try:
        from qrbill import QRBill
        from svglib.svglib import svg2rlg
    except ImportError:  # packages missing in this environment → invoice without QR-bill
        return None
    creditor.update(name=creditor_name.strip()[:70], country=(creditor_country or clean_iban(iban)[:2])[:2])
    kwargs = {"account": clean_iban(iban), "creditor": creditor, "amount": f"{Decimal(amount):.2f}",
              "currency": currency, "additional_information": (message or "")[:140],
              "language": lang if lang in ("de", "fr", "it", "en") else "de"}
    # The payer block stays empty on purpose (allowed by the standard): the
    # client's country isn't collected, and a wrong one would be worse.
    try:
        bill = QRBill(**kwargs)
    except ValueError:
        return None
    buffer = io.StringIO()
    bill.as_svg(buffer, full_page=False)
    return svg2rlg(io.BytesIO(buffer.getvalue().encode("utf-8")))

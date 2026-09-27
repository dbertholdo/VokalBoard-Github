"""Rechnungmaker v2 — country profiles (docs/specs/RECHNUNGMAKER_V2.md, phase 1).

One entry per country decides everything country-specific about an invoice:
the tax options (with their fixed legal notes in the four invoice languages),
the tax-ID label, the default currency and invoice language, and the number
format. The form, the live preview (the same data is embedded as JSON for
app/static/js/invoice_preview.js) and the PDF (app/invoice_pdf.py) all read
this file — adding a country means adding one entry here.

The issuer's country decides the rules. Not tax advice: these are the most
common formats; the page says so. Legal wordings are the standard phrasings
(Daniel, 2026-09-27: no Steuerberater review).
"""
from datetime import date
from decimal import Decimal

COUNTRY_KEYS = ("DE", "AT", "CH", "OTHER")
DOC_LANGS = ("de", "en", "fr", "it")
CURRENCIES = ("EUR", "CHF", "USD", "GBP", "BRL")  # dropdown order (Daniel)

# ---------------------------------------------------------------------------
# Fixed legal notes, per invoice language.
# ---------------------------------------------------------------------------
NOTES = {
    "de_klein": {
        "de": "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet.",
        "en": "No VAT is charged under the small business rule (§ 19 UStG).",
        "fr": "TVA non applicable – régime des petites entreprises (§ 19 UStG).",
        "it": "IVA non applicata – regime dei piccoli imprenditori (§ 19 UStG).",
    },
    "de_cultural": {
        "de": "Umsatzsteuerfreie künstlerische Leistung gemäß § 4 Nr. 20 UStG.",
        "en": "VAT-exempt artistic service (§ 4 No. 20 UStG).",
        "fr": "Prestation artistique exonérée de TVA (§ 4 Nr. 20 UStG).",
        "it": "Prestazione artistica esente IVA (§ 4 Nr. 20 UStG).",
    },
    "de_reverse": {
        "de": "Steuerschuldnerschaft des Leistungsempfängers (Reverse Charge).",
        "en": "Reverse charge: VAT to be accounted for by the recipient.",
        "fr": "Autoliquidation : TVA due par le preneur.",
        "it": "Inversione contabile: IVA dovuta dal committente.",
    },
    "de_noneu": {
        "de": "Nicht im Inland steuerbare Leistung.",
        "en": "Not taxable in Germany (place of supply outside Germany).",
        "fr": "Prestation non imposable en Allemagne.",
        "it": "Prestazione non imponibile in Germania.",
    },
    "at_klein": {
        "de": "Umsatzsteuerfrei aufgrund der Kleinunternehmerregelung gemäß § 6 Abs. 1 Z 27 UStG.",
        "en": "VAT-exempt under the Austrian small business rule (§ 6 (1) no. 27 UStG).",
        "fr": "Exonéré de TVA – régime autrichien des petites entreprises (§ 6 al. 1 n° 27 UStG).",
        "it": "Esente IVA – regime austriaco dei piccoli imprenditori (§ 6 c. 1 n. 27 UStG).",
    },
    "at_cultural": {
        "de": "Umsatzsteuerfreie künstlerische Leistung.",
        "en": "VAT-exempt artistic service.",
        "fr": "Prestation artistique exonérée de TVA.",
        "it": "Prestazione artistica esente IVA.",
    },
    "at_reverse": {
        "de": "Übergang der Steuerschuld auf den Leistungsempfänger (Reverse Charge).",
        "en": "Reverse charge: VAT to be accounted for by the recipient.",
        "fr": "Autoliquidation : TVA due par le preneur.",
        "it": "Inversione contabile: IVA dovuta dal committente.",
    },
    "at_noneu": {
        "de": "Nicht im Inland steuerbare Leistung.",
        "en": "Not taxable in Austria (place of supply outside Austria).",
        "fr": "Prestation non imposable en Autriche.",
        "it": "Prestazione non imponibile in Austria.",
    },
    "ch_exempt": {
        "de": "Nicht mehrwertsteuerpflichtig.",
        "en": "Not registered for VAT (MWST).",
        "fr": "Non assujetti à la TVA.",
        "it": "Non assoggettato all'IVA.",
    },
}


def _opt(key, label_key, rate=None, note=None, *, client_vat=False, custom=False):
    return {"key": key, "label_key": label_key, "rate": rate, "note": note,
            "client_vat": client_vat, "custom": custom}


COUNTRIES = {
    "DE": {
        "label_key": "invc_country_de", "currency": "EUR", "doc_lang": "de", "number": ".,",
        "tax": "de", "tax_id_key": "de",
        "options": [
            _opt("klein", "invc_opt_de_klein", "0", "de_klein"),
            _opt("cultural", "invc_opt_de_cultural", "0", "de_cultural"),
            _opt("std19", "invc_opt_de_std19", "19"),
            _opt("red7", "invc_opt_de_red7", "7"),
            _opt("reverse", "invc_opt_reverse", "0", "de_reverse", client_vat=True),
            _opt("noneu", "invc_opt_de_noneu", "0", "de_noneu"),
        ],
    },
    "AT": {
        "label_key": "invc_country_at", "currency": "EUR", "doc_lang": "de", "number": ".,",
        "tax": "de", "tax_id_key": "at",
        "options": [
            _opt("klein", "invc_opt_at_klein", "0", "at_klein"),
            _opt("cultural", "invc_opt_at_cultural", "0", "at_cultural"),
            _opt("std20", "invc_opt_at_std20", "20"),
            _opt("red13", "invc_opt_at_red13", "13"),
            _opt("red10", "invc_opt_at_red10", "10"),
            _opt("reverse", "invc_opt_reverse", "0", "at_reverse", client_vat=True),
            _opt("noneu", "invc_opt_at_noneu", "0", "at_noneu"),
        ],
    },
    "CH": {
        "label_key": "invc_country_ch", "currency": "CHF", "doc_lang": "de", "number": "'.",
        "tax": "ch", "tax_id_key": "ch",
        "options": [
            _opt("exempt", "invc_opt_ch_exempt", "0", "ch_exempt"),
            _opt("std81", "invc_opt_ch_std81", "8.1"),
            _opt("red26", "invc_opt_ch_red26", "2.6"),
        ],
    },
    "OTHER": {
        "label_key": "invc_country_other", "currency": "EUR", "doc_lang": "en", "number": ",.",
        "tax": "other", "tax_id_key": "other",
        "options": [
            _opt("custom", "invc_opt_other_custom", None, None, custom=True),
            _opt("none", "invc_opt_other_none", "0"),
        ],
    },
}

# Tax name printed on the invoice ("Umsatzsteuer 19 %"), per tax family + invoice language.
TAX_NAMES = {
    "de": {"de": "Umsatzsteuer", "en": "VAT", "fr": "TVA", "it": "IVA"},
    "ch": {"de": "MWST", "en": "VAT", "fr": "TVA", "it": "IVA"},
    "other": {"de": "Steuer", "en": "Tax", "fr": "Taxe", "it": "Imposta"},
}
# Label printed next to the issuer's tax ID, per country + invoice language.
TAX_ID_LABELS = {
    "de": {"de": "Steuer-Nr./USt-IdNr.", "en": "Tax no./VAT ID", "fr": "N° fiscal/TVA", "it": "Cod. fiscale/P. IVA"},
    "at": {"de": "UID-Nr.", "en": "VAT ID (UID)", "fr": "N° TVA (UID)", "it": "P. IVA (UID)"},
    "ch": {"de": "UID/MWST-Nr.", "en": "UID/VAT no.", "fr": "IDE/N° TVA", "it": "IDI/N. IVA"},
    "other": {"de": "Steuernummer", "en": "Tax ID", "fr": "N° fiscal", "it": "Codice fiscale"},
}
# Everything else printed on the invoice, per invoice language.
DOC_LABELS = {
    "de": {"title": "Rechnung", "issuer": "Rechnungssteller", "recipient": "Rechnungsempfänger",
           "number": "Rechnungs-Nr.", "issue_date": "Rechnungsdatum", "service_date": "Leistungsdatum",
           "pos": "Pos.", "description": "Bezeichnung", "qty": "Menge", "unit": "Einh.", "unit_price": "E-Preis",
           "line_total": "Gesamt", "flat": "pausch.", "travel": "Fahrkosten", "lodging": "Übernachtungskosten",
           "net": "Summe Netto", "total": "Endsumme", "client_vat": "USt-IdNr. des Leistungsempfängers"},
    "en": {"title": "Invoice", "issuer": "From", "recipient": "Bill to",
           "number": "Invoice no.", "issue_date": "Invoice date", "service_date": "Date of performance",
           "pos": "No.", "description": "Description", "qty": "Qty", "unit": "Unit", "unit_price": "Unit price",
           "line_total": "Total", "flat": "flat", "travel": "Travel costs", "lodging": "Accommodation",
           "net": "Net total", "total": "Total due", "client_vat": "Client VAT ID"},
    "fr": {"title": "Facture", "issuer": "Émetteur", "recipient": "Destinataire",
           "number": "N° de facture", "issue_date": "Date de facture", "service_date": "Date de la prestation",
           "pos": "N°", "description": "Désignation", "qty": "Qté", "unit": "Unité", "unit_price": "Prix unit.",
           "line_total": "Total", "flat": "forfait", "travel": "Frais de déplacement", "lodging": "Hébergement",
           "net": "Total HT", "total": "Total TTC", "client_vat": "N° TVA du client"},
    "it": {"title": "Fattura", "issuer": "Emittente", "recipient": "Destinatario",
           "number": "N. fattura", "issue_date": "Data fattura", "service_date": "Data della prestazione",
           "pos": "N.", "description": "Descrizione", "qty": "Q.tà", "unit": "Unità", "unit_price": "Prezzo unit.",
           "line_total": "Totale", "flat": "forfait", "travel": "Spese di viaggio", "lodging": "Alloggio",
           "net": "Imponibile", "total": "Totale dovuto", "client_vat": "P. IVA del cliente"},
}
_MONTHS_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


# ---------------------------------------------------------------------------
# Helpers used by routes, PDF and templates
# ---------------------------------------------------------------------------

def country_or_default(value: str | None) -> str:
    return value if value in COUNTRIES else "DE"


def doc_lang_or_default(value: str | None, country: str) -> str:
    return value if value in DOC_LANGS else COUNTRIES[country_or_default(country)]["doc_lang"]


def default_option(country: str) -> str:
    """The standard-rate option (or the first one) — the safest starting point."""
    options = COUNTRIES[country_or_default(country)]["options"]
    for opt in options:
        if opt["key"].startswith("std") or opt["custom"]:
            return opt["key"]
    return options[0]["key"]


def find_option(country: str, key: str | None) -> dict:
    options = COUNTRIES[country_or_default(country)]["options"]
    return next((o for o in options if o["key"] == key), None) or find_option(country, default_option(country))


def tax_name(country: str, doc_lang: str, custom_name: str = "") -> str:
    family = COUNTRIES[country_or_default(country)]["tax"]
    if family == "other" and custom_name.strip():
        return custom_name.strip()[:40]
    return TAX_NAMES[family][doc_lang_or_default(doc_lang, country)]


def tax_id_label(country: str, doc_lang: str) -> str:
    return TAX_ID_LABELS[COUNTRIES[country_or_default(country)]["tax_id_key"]][doc_lang_or_default(doc_lang, country)]


def resolve_tax(country: str, option_key: str | None, doc_lang: str, *, custom_rate: str = "",
                custom_name: str = "", extra_note: str = "") -> dict:
    """What an invoice prints for its tax: rate, tax name, legal note (+ the
    person's own extra note), and whether the client's VAT ID is required."""
    country = country_or_default(country)
    doc_lang = doc_lang_or_default(doc_lang, country)
    opt = find_option(country, option_key)
    rate = (custom_rate or "0").strip() if opt["custom"] else opt["rate"]
    notes = [NOTES[opt["note"]][doc_lang]] if opt["note"] else []
    if extra_note.strip():
        notes.append(extra_note.strip()[:500])
    return {"option": opt["key"], "rate": rate, "name": tax_name(country, doc_lang, custom_name),
            "note": " ".join(notes), "client_vat_required": opt["client_vat"]}


def format_amount(value: Decimal, country: str) -> str:
    """1234.5 → DE/AT "1.234,50", CH "1'234.50", other "1,234.50"."""
    thousands, decimal_sep = COUNTRIES[country_or_default(country)]["number"]
    raw = f"{Decimal(value):,.2f}"  # 1,234.50
    return raw.replace(",", "\x00").replace(".", decimal_sep).replace("\x00", thousands)


def format_date(iso_value: str, doc_lang: str) -> str:
    try:
        d = date.fromisoformat((iso_value or "").strip())
    except ValueError:
        return iso_value or ""
    if doc_lang == "en":
        return f"{d.day} {_MONTHS_EN[d.month - 1]} {d.year}"
    if doc_lang == "de":
        return d.strftime("%d.%m.%Y")
    return d.strftime("%d/%m/%Y")


def client_data(translate_fn) -> dict:
    """Everything the live preview needs, as one JSON-able dict (labels already
    translated for the site language where they are UI text)."""
    return {
        "countries": {
            code: {
                "currency": c["currency"], "docLang": c["doc_lang"], "number": c["number"],
                "options": [{"key": o["key"], "label": translate_fn(o["label_key"]), "rate": o["rate"],
                             "note": o["note"], "clientVat": o["client_vat"], "custom": o["custom"]}
                            for o in c["options"]],
                "defaultOption": default_option(code),
                "taxIdLabels": TAX_ID_LABELS[c["tax_id_key"]],
                "taxNames": TAX_NAMES[c["tax"]],
            }
            for code, c in COUNTRIES.items()
        },
        "notes": NOTES,
        "docLabels": DOC_LABELS,
    }


# Old drafts (before v2) stored "COUNTRY:status" presets — map them onto v2 options.
_LEGACY_PRESETS = {
    "DE:kleinunternehmer": ("DE", "klein"), "DE:cultural": ("DE", "cultural"), "DE:standard": ("DE", "std19"),
    "AT:kleinunternehmer": ("AT", "klein"), "AT:cultural": ("AT", "cultural"), "AT:standard": ("AT", "std20"),
    "CH:kleinunternehmer": ("CH", "exempt"), "CH:cultural": ("CH", "exempt"), "CH:standard": ("CH", "std81"),
    "OTHER:other": ("OTHER", "custom"),
}


def from_legacy_preset(preset: str | None) -> tuple[str, str] | None:
    return _LEGACY_PRESETS.get(preset or "")

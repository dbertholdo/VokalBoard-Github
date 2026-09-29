"""Rechnungmaker v2 form <-> invoice (2026-09-28, docs/specs/RECHNUNGMAKER_V2.md phase 1).

One place turns the posted form (standalone generator and Match invoices use
the same fields) into a validated InvoiceDocument, fills defaults (country,
invoice language, currency, tax option, Match fee/date/client) and remembers
the person's country + invoice language. Zero-Storage (CLAUDE.md §2): the
street address, tax ID and IBAN are never saved here — only country and
invoice language, which are not sensitive.
"""
from decimal import Decimal, InvalidOperation

from app.database import execute, fetch_one
from app.invoice_countries import (
    COUNTRIES, CURRENCIES, DOC_LANGS, country_or_default, default_option, doc_lang_or_default, find_option,
    from_legacy_preset, resolve_tax,
)
from app.invoice_pdf import InvoiceDocument, InvoiceValidationError
from app.schema_features import has_columns

FIELDS = (
    "country", "doc_lang", "currency",
    "issuer_name", "issuer_address", "issuer_tax_id",
    "recipient_name", "recipient_address", "client_vat_id",
    "number", "issue_date", "service_date", "service_description",
    "net_amount", "expense_travel_amount", "expense_lodging_amount",
    "tax_option", "tax_custom_rate", "tax_custom_name", "tax_extra_note",
    "payment_terms", "iban", "bic", "girocode",
)


MAX_EXTRA_SERVICES = 19  # + the first service = 20 lines


def read_form(form) -> dict:
    """Plain dict of the known fields from a submitted form (missing -> "")."""
    values = {key: (form.get(key) or "").strip() if key not in ("issuer_address", "recipient_address") else (form.get(key) or "")
              for key in FIELDS}
    getlist = getattr(form, "getlist", None)
    if getlist:
        values["extra_services"] = [{"description": d, "amount": a} for d, a in
                                    zip(getlist("extra_service_description"), getlist("extra_service_amount"))]
    return values


def clean_extra_services(rows) -> list[dict]:
    """7b: extra service lines as [{"description", "amount"}]; fully empty rows dropped."""
    cleaned = []
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict):
            description, amount = row.get("description"), row.get("amount")
        elif isinstance(row, (list, tuple)) and len(row) == 2:
            description, amount = row
        else:
            continue
        description, amount = str(description or "").strip()[:500], str(amount or "").strip()[:20]
        if description or amount:
            cleaned.append({"description": description, "amount": amount})
    return cleaned[:MAX_EXTRA_SERVICES]


def normalize(values: dict, default_country: str = "DE") -> dict:
    """Valid country / invoice language / currency / tax option, with the
    country's defaults filled in. Old drafts (tax_preset) are mapped."""
    v = {key: values.get(key) or "" for key in FIELDS}
    legacy = from_legacy_preset(values.get("tax_preset")) if not v["tax_option"] else None
    if legacy:
        v["country"], v["tax_option"] = v["country"] or legacy[0], legacy[1]
        v["tax_extra_note"] = v["tax_extra_note"] or values.get("tax_custom_text", "")
    country = country_or_default(v["country"] or default_country)
    v["country"] = country
    v["doc_lang"] = doc_lang_or_default(v["doc_lang"], country)
    v["currency"] = v["currency"] if v["currency"] in CURRENCIES else COUNTRIES[country]["currency"]
    v["tax_option"] = find_option(country, v["tax_option"] or default_option(country))["key"]
    for amount in ("expense_travel_amount", "expense_lodging_amount"):
        v[amount] = v[amount] or "0"
    v["girocode"] = "1" if v["girocode"] in ("1", "on", "true") else ""
    v["extra_services"] = clean_extra_services(values.get("extra_services"))
    return v


def to_document(v: dict) -> InvoiceDocument:
    """Raises InvoiceValidationError for anything the PDF can't be built from."""
    tax = resolve_tax(v["country"], v["tax_option"], v["doc_lang"], custom_rate=v["tax_custom_rate"],
                      custom_name=v["tax_custom_name"], extra_note=v["tax_extra_note"])
    if tax["client_vat_required"] and not v["client_vat_id"].strip():
        raise InvoiceValidationError("Reverse charge needs the client's VAT ID")
    document = InvoiceDocument(
        v["number"], v["issue_date"], v["service_date"], v["issuer_name"], v["issuer_address"], v["issuer_tax_id"],
        v["recipient_name"], v["recipient_address"], v["service_description"], v["net_amount"], v["currency"],
        tax["rate"], tax["note"], v["payment_terms"], v["iban"], v["bic"],
        v["expense_travel_amount"], v["expense_lodging_amount"],
        country=v["country"], doc_lang=v["doc_lang"], tax_name=tax["name"],
        client_vat_id=v["client_vat_id"] if tax["client_vat_required"] else "",
        girocode="1" if v.get("girocode") else "",
        extra_services=tuple((row["description"], row["amount"]) for row in v.get("extra_services") or ()),
    )
    document.validate()
    return document


# --- remembered country + invoice language (account preference) -----------

def _profile_country(user: dict) -> str:
    code = (user.get("country") or "").upper()
    return code if code in ("DE", "AT", "CH") else "OTHER"


def preferred(user: dict) -> tuple[str, str]:
    """(country, invoice language): last used, else from the profile country."""
    if has_columns("users", "invoice_country", "invoice_doc_lang"):
        row = fetch_one("SELECT invoice_country, invoice_doc_lang FROM users WHERE id = :id", {"id": user["id"]})
        if row and row["invoice_country"] in COUNTRIES:
            country = row["invoice_country"]
            return country, doc_lang_or_default(row["invoice_doc_lang"], country)
    country = _profile_country(user)
    return country, COUNTRIES[country]["doc_lang"]


def remember(user_id: int, country: str, doc_lang: str) -> None:
    if country in COUNTRIES and doc_lang in DOC_LANGS and has_columns("users", "invoice_country", "invoice_doc_lang"):
        execute("UPDATE users SET invoice_country = :c, invoice_doc_lang = :l WHERE id = :id",
                {"c": country, "l": doc_lang, "id": user_id})


def defaults_for(user: dict, *, number: str, today: str, match: dict | None = None) -> dict:
    """Pre-filled values for an empty form (never street address / tax ID / IBAN)."""
    country, doc_lang = preferred(user)
    d = {"country": country, "doc_lang": doc_lang, "currency": COUNTRIES[country]["currency"],
         "tax_option": default_option(country), "number": number, "issue_date": today,
         "issuer_name": user.get("full_name") or ""}
    if match:
        # Daniel 2026-09-28: take the fee (and date, client, job) from the Match,
        # so nobody has to look them up in another tab.
        d["recipient_name"] = match.get("contractor_name") or ""
        d["service_description"] = match.get("title") or ""
        if match.get("event_date"):
            d["service_date"] = str(match["event_date"])
        fee = match.get("fee_amount")
        if fee is not None:
            try:
                d["net_amount"] = f"{Decimal(str(fee)):.2f}"
            except InvalidOperation:
                pass
        if match.get("fee_currency") in CURRENCIES:
            d["currency"] = match["fee_currency"]
    return d

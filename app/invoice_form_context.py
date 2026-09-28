"""Template context for the Rechnungmaker v2 form (2026-09-28).

Select options (country, invoice language, currency, tax options per
country) and the JSON the live preview reads (app/static/js/invoice_preview.js),
with UI labels and "?" help texts in the SITE language; the invoice itself
uses the invoice language (app/invoice_countries.py)."""
from fastapi import Request

from app.i18n import translate
from app.invoice_countries import COUNTRIES, COUNTRY_KEYS, CURRENCIES, DOC_LANGS, client_data

# Invoice languages are named in their own language (same in every UI language).
DOC_LANG_NAMES = {"de": "Deutsch", "en": "English", "fr": "Français", "it": "Italiano"}


def form_context(request: Request) -> dict:
    lang = getattr(request.state, "lang", "de")

    def t(key: str) -> str:
        return translate(key, lang)

    data = client_data(t)
    data["help"] = {
        "tax_id": {code: t(f"invh_tax_id_{code.lower()}") for code in COUNTRY_KEYS},
        "tax_option": {code: t(f"invh_tax_{code.lower()}") for code in COUNTRY_KEYS},
    }
    return {
        "inv_countries": [(code, t(COUNTRIES[code]["label_key"])) for code in COUNTRY_KEYS],
        "inv_doc_langs": [(code, DOC_LANG_NAMES[code]) for code in DOC_LANGS],
        "inv_currencies": CURRENCIES,
        "inv_options": {code: [(o["key"], t(o["label_key"])) for o in COUNTRIES[code]["options"]] for code in COUNTRY_KEYS},
        "inv_option_meta": {code: {o["key"]: o for o in COUNTRIES[code]["options"]} for code in COUNTRY_KEYS},
        "inv_client_data": data,
    }

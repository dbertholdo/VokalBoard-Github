"""
P3.E: structured cachê (fee_amount + fee_currency + fee_negotiable),
replacing the old free-text `fee` column — see
db/migrations/2026-09-19_p3e_structured_fees.sql.

Kept as its own tiny module (rather than duplicated in listings_routes.py
and app/vacancies.py) because BOTH `listings` and `listing_vacancies` have
their own fee_amount/fee_currency/fee_negotiable trio, and both the form
(dropdown order) and the display (listing_detail.html, listing_candidates,
invitations, my_listings, board/home) need the exact same rules.
"""
from decimal import Decimal, InvalidOperation

# Dropdown order requested by Daniel on 2026-09-18: Euro first (today's
# default market), then CHF, then Dollar, then Pound — in that order,
# even though EUR/CHF are the only two actually in use today (DE/AT/CH).
# Multi-currency is deliberately pre-built ahead of a future non-DACH
# launch.
CURRENCIES = ["EUR", "CHF", "USD", "GBP"]
DEFAULT_CURRENCY = "EUR"

CURRENCY_SYMBOLS = {"EUR": "€", "CHF": "CHF", "USD": "$", "GBP": "£"}

# Symbol placement follows the currency's own usual convention (prefixed
# for CHF/USD/GBP, suffixed for EUR) rather than one fixed layout for all
# four — this is purely display polish, doesn't affect storage or sorting.
_PREFIXED = {"CHF", "USD", "GBP"}


def parse_fee_amount(raw: str) -> Decimal | None:
    """
    Parses a form field into a Decimal with 2 decimal places, or None if
    blank. Accepts a comma OR a dot as the decimal separator (the site
    has German/Swiss/Portuguese-speaking users, who type "200,50" as
    often as "200.50"). Raises ValueError for anything else (negative,
    not a number, more than 2 decimals worth of precision lost) — the
    caller (listings_routes.py) turns that into the existing
    error_required_fields validation path, exactly like every other
    field on this form.
    """
    raw = (raw or "").strip().replace(",", ".")
    if not raw:
        return None
    try:
        value = Decimal(raw).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise ValueError("invalid fee amount")
    if value < 0:
        raise ValueError("negative fee amount")
    return value


def fee_valid(fee_amount: str, fee_negotiable: bool) -> tuple[bool, Decimal | None]:
    """
    The P3.E rule, confirmed by Daniel: for a listing_type that requires
    a fee at all (see _job_fields_valid in listings_routes.py, unchanged
    scope), exactly ONE of "a value" or "a negociar" must be given —
    never both, never neither. Returns (is_valid, parsed_amount) so the
    caller doesn't have to re-parse.
    """
    try:
        amount = parse_fee_amount(fee_amount)
    except ValueError:
        return False, None
    has_amount = amount is not None
    if has_amount == fee_negotiable:  # both True or both False — invalid either way
        return False, None
    return True, amount


def format_fee(amount, currency: str, negotiable: bool, negotiable_label: str) -> str | None:
    """
    Renders the stored fee for display. `negotiable_label` is the
    already-translated "A negociar" string (t('...') result) — this
    module doesn't import app.i18n to stay a plain, dependency-free
    formatting helper. Returns None when there's genuinely nothing to
    show (no amount, not negotiable — e.g. a self-ad listing where fee
    doesn't apply at all).
    """
    if negotiable:
        return negotiable_label
    if amount is None:
        return None
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    formatted = f"{amount:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    # The line above turns "1234.50" into "1.234,50" (German/Swiss
    # thousands-dot, comma-decimal) — matches how the site's own
    # audience writes money, regardless of which of the 4 currencies.
    if currency in _PREFIXED:
        return f"{symbol} {formatted}"
    return f"{formatted} {symbol}"

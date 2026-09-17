"""Prazos de Rechnung vinculada a um evento de Match."""
from datetime import date, datetime, timedelta

MATCH_INVOICE_WINDOW_DAYS = 7
DRAFT_WINDOW_DAYS = 7


def match_invoice_request_deadline(event_date: date) -> date:
    """The request remains available through the seventh calendar day after it."""
    return event_date + timedelta(days=MATCH_INVOICE_WINDOW_DAYS)


def can_request_match_invoice(event_date: date | None, today: date) -> bool:
    """No event date means no event-specific Rechnung can be requested."""
    return event_date is not None and today <= match_invoice_request_deadline(event_date)


def match_draft_expiry(event_date: date, created_at: datetime) -> datetime:
    """Once validly initiated, the other party receives a full seven days."""
    if created_at.tzinfo is None:
        raise ValueError("created_at must be timezone-aware")
    # event_date is intentionally accepted as context: the route must validate
    # can_request_match_invoice(event_date, today) BEFORE it creates a draft.
    # Once created, no shortening of the counter is allowed.
    _ = event_date
    return created_at + timedelta(days=DRAFT_WINDOW_DAYS)

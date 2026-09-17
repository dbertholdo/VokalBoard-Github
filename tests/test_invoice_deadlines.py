from datetime import date, datetime, timezone

from app.invoice_deadlines import (
    can_request_match_invoice,
    match_draft_expiry,
    match_invoice_request_deadline,
)


def test_match_invoice_is_available_for_seven_calendar_days_after_event():
    event_date = date(2026, 9, 1)

    assert match_invoice_request_deadline(event_date) == date(2026, 9, 8)
    assert can_request_match_invoice(event_date, date(2026, 9, 8))
    assert not can_request_match_invoice(event_date, date(2026, 9, 9))


def test_match_invoice_requires_an_event_date():
    assert not can_request_match_invoice(None, date(2026, 9, 8))


def test_draft_keeps_full_seven_days_after_valid_initiation():
    expiry = match_draft_expiry(
        date(2026, 9, 1),
        datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc),
    )

    assert expiry == datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)

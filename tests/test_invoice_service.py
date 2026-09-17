from datetime import date

import pytest

from app.database import execute, fetch_one
from app.invoice_service import (
    InvoiceCreditUnavailable,
    consume_invoice_generation,
    record_invoice_number,
    suggested_invoice_number,
)
from tests.test_security import register_test_user


def test_invoice_numbers_increment_per_user_and_year(client):
    user_id, _, _ = register_test_user(client)

    assert suggested_invoice_number(user_id, 2026) == "2026-0001"
    record_invoice_number(user_id, "2026-0001")
    assert suggested_invoice_number(user_id, 2026) == "2026-0002"
    record_invoice_number(user_id, "2026-0007")
    assert suggested_invoice_number(user_id, 2026) == "2026-0008"
    assert suggested_invoice_number(user_id, 2027) == "2027-0001"


def test_invoice_allowance_resets_each_month_and_purchased_credit_is_separate(client):
    user_id, _, _ = register_test_user(client)
    september = date(2026, 9, 17)

    assert [consume_invoice_generation(user_id, september) for _ in range(5)] == ["free"] * 5
    with pytest.raises(InvoiceCreditUnavailable):
        consume_invoice_generation(user_id, september)

    execute(
        "INSERT INTO purchased_invoice_credits (user_id, delta, reason) VALUES (:id, 2, 'purchase')",
        {"id": user_id},
    )
    assert consume_invoice_generation(user_id, september) == "purchased"
    assert consume_invoice_generation(user_id, september) == "purchased"
    with pytest.raises(InvoiceCreditUnavailable):
        consume_invoice_generation(user_id, september)

    assert consume_invoice_generation(user_id, date(2026, 10, 1)) == "free"
    usage = fetch_one(
        "SELECT free_used FROM invoice_monthly_usage WHERE user_id = :id AND usage_month = DATE '2026-10-01'",
        {"id": user_id},
    )
    assert usage["free_used"] == 1

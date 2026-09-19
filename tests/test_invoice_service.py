from datetime import date

import pytest

from app.database import execute, fetch_one
from app.invoice_service import (
    InvoiceCreditUnavailable,
    consume_invoice_generation,
    get_lifetime_invoice_count,
    get_personal_invoice_badge,
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


def test_lifetime_invoice_count_combines_free_and_purchased_p4_etapa3(client):
    """Etapa 3 do P4 (18/09/2026): o contador pessoal soma Avulso + Match
    — os dois passam por consume_invoice_generation(), então o total é
    simplesmente todo mundo que passou por ali com sucesso."""
    user_id, _, _ = register_test_user(client)
    september = date(2026, 9, 17)

    assert get_lifetime_invoice_count(user_id) == 0
    for _ in range(5):
        consume_invoice_generation(user_id, september)
    assert get_lifetime_invoice_count(user_id) == 5

    execute(
        "INSERT INTO purchased_invoice_credits (user_id, delta, reason) VALUES (:id, 3, 'purchase')",
        {"id": user_id},
    )
    consume_invoice_generation(user_id, september)
    consume_invoice_generation(user_id, september)
    assert get_lifetime_invoice_count(user_id) == 7  # 5 grátis + 2 comprados consumidos

    # Um crédito COMPRADO (delta positivo, reason='purchase') nunca conta
    # como uma Rechnung emitida — só o CONSUMO (delta=-1,
    # reason='invoice_generation') conta.
    assert get_lifetime_invoice_count(user_id) < 5 + 3


def test_personal_badge_tiers_at_milestones_p4_etapa3(client):
    user_id, _, _ = register_test_user(client)

    assert get_personal_invoice_badge(user_id) == {"count": 0, "tier": None}

    consume_invoice_generation(user_id, date(2026, 1, 1))
    assert get_personal_invoice_badge(user_id) == {"count": 1, "tier": "bronze"}

    execute(
        "INSERT INTO purchased_invoice_credits (user_id, delta, reason) VALUES (:id, 20, 'purchase')",
        {"id": user_id},
    )
    for _ in range(8):
        consume_invoice_generation(user_id, date(2026, 1, 1))
    assert get_personal_invoice_badge(user_id) == {"count": 9, "tier": "bronze"}

    consume_invoice_generation(user_id, date(2026, 1, 1))
    assert get_personal_invoice_badge(user_id) == {"count": 10, "tier": "silver"}


def test_consume_invoice_generation_records_feature_usage_p4_etapa3(client):
    from app.feature_usage import get_feature_usage_totals

    user_id, _, _ = register_test_user(client)
    before = next((f["total"] for f in get_feature_usage_totals() if f["key"] == "rechnungmaker"), 0)

    consume_invoice_generation(user_id, date(2026, 9, 17))

    after = next((f["total"] for f in get_feature_usage_totals() if f["key"] == "rechnungmaker"), 0)
    assert after == before + 1

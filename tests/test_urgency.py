"""P5 Etapa 2 (18/09/2026): Sistema de Urgência — token semanal grátis
+ compra por Notas, ver app/urgency.py."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.database import execute, execute_returning, fetch_one
from app.notas_wallet import credit_notas, get_credit_balance
from app.store import urgent_price
from app.urgency import (
    ListingNotEligible,
    UrgencyUnavailable,
    get_urgency_status,
    mark_listing_urgent,
)
from tests.test_security import register_test_user


def _make_listing(user_id: int, listing_type: str = "seeking_singer") -> int:
    if listing_type == "singer_available":
        # o trigger validate_availability() exige available_from/until
        # pra esse tipo — não é o foco do teste, só uma vaga elegível
        # ou não pra marcar urgente.
        row = execute_returning(
            """
            INSERT INTO listings (author_id, listing_type, title, description, available_from, available_until)
            VALUES (:author_id, :listing_type, 'Sectest Urgency Listing', 'desc', CURRENT_DATE, CURRENT_DATE + 7)
            RETURNING id
            """,
            {"author_id": user_id, "listing_type": listing_type},
        )
        return row["id"]
    row = execute_returning(
        """
        INSERT INTO listings (author_id, listing_type, title, description, state, country)
        VALUES (:author_id, :listing_type, 'Sectest Urgency Listing', 'desc', 'Bayern', 'DE')
        RETURNING id
        """,
        {"author_id": user_id, "listing_type": listing_type},
    )
    return row["id"]


def _clear_urgency(user_id: int):
    execute("DELETE FROM urgency_weekly_usage WHERE user_id = :id", {"id": user_id})
    execute("DELETE FROM credit_ledger WHERE user_id = :id", {"id": user_id})


def test_first_mark_of_the_week_is_free(client):
    user_id, _, _ = register_test_user(client)
    _clear_urgency(user_id)
    listing_id = _make_listing(user_id)

    assert mark_listing_urgent(user_id, listing_id) == "free"
    listing = fetch_one(
        "SELECT is_urgent, urgent_marked_at FROM listings WHERE id = :id",
        {"id": listing_id},
    )
    assert listing["is_urgent"] is True
    assert listing["urgent_marked_at"] is not None
    assert get_credit_balance(user_id) == Decimal("0")  # não custou Nota nenhuma


def test_second_mark_same_week_charges_notas(client):
    user_id, _, _ = register_test_user(client)
    _clear_urgency(user_id)
    credit_notas(user_id, 5, "sectest_seed")

    listing_1 = _make_listing(user_id)
    listing_2 = _make_listing(user_id)

    assert mark_listing_urgent(user_id, listing_1) == "free"
    assert mark_listing_urgent(user_id, listing_2) == "purchased"
    assert get_credit_balance(user_id) == Decimal("5") - urgent_price(user_id)  # Store price (welcome discount)


def test_second_mark_without_notas_raises_unavailable(client):
    user_id, _, _ = register_test_user(client)
    _clear_urgency(user_id)
    listing_1 = _make_listing(user_id)
    listing_2 = _make_listing(user_id)

    mark_listing_urgent(user_id, listing_1)
    with pytest.raises(UrgencyUnavailable):
        mark_listing_urgent(user_id, listing_2)
    # nada foi debitado por uma tentativa que falhou
    assert get_credit_balance(user_id) == Decimal("0")


def test_free_token_resets_next_week(client):
    user_id, _, _ = register_test_user(client)
    _clear_urgency(user_id)
    listing_this_week = _make_listing(user_id)
    listing_next_week = _make_listing(user_id)

    today = date.today()
    next_week = today + timedelta(days=7)

    assert mark_listing_urgent(user_id, listing_this_week, today) == "free"
    assert mark_listing_urgent(user_id, listing_next_week, next_week) == "free"


def test_wrong_listing_type_is_not_eligible(client):
    user_id, _, _ = register_test_user(client)
    _clear_urgency(user_id)
    listing_id = _make_listing(user_id, listing_type="singer_available")

    with pytest.raises(ListingNotEligible):
        mark_listing_urgent(user_id, listing_id)


def test_not_the_owner_is_not_eligible(client):
    owner_id, _, _ = register_test_user(client, full_name="Owner")
    other_id, _, _ = register_test_user(client, full_name="Other")
    listing_id = _make_listing(owner_id)

    with pytest.raises(ListingNotEligible):
        mark_listing_urgent(other_id, listing_id)


def test_already_urgent_is_not_eligible_again(client):
    user_id, _, _ = register_test_user(client)
    _clear_urgency(user_id)
    listing_id = _make_listing(user_id)

    mark_listing_urgent(user_id, listing_id)
    with pytest.raises(ListingNotEligible):
        mark_listing_urgent(user_id, listing_id)


def test_get_urgency_status_reflects_token_usage(client):
    user_id, _, _ = register_test_user(client)
    _clear_urgency(user_id)
    listing_id = _make_listing(user_id)

    assert get_urgency_status(user_id)["free_tokens_left"] == 1
    mark_listing_urgent(user_id, listing_id)
    assert get_urgency_status(user_id)["free_tokens_left"] == 0

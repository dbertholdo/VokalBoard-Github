"""P5 Etapa 1 (18/09/2026): fundação antifraude do sistema de Notas —
ver app/notas_wallet.py."""
from decimal import Decimal

from app.database import execute
from app.notas_wallet import (
    count_credits_since,
    credit_notas,
    debit_notas_atomic,
    format_notas,
    get_credit_balance,
)
from tests.test_security import register_test_user


def _clear(user_id: int):
    execute("DELETE FROM credit_ledger WHERE user_id = :id", {"id": user_id})


def test_format_notas_whole_vs_fractional():
    assert format_notas(3) == "3"
    assert format_notas(Decimal("3.00")) == "3"
    assert format_notas(Decimal("0.50")) == "0,50"
    assert format_notas(Decimal("-0.50")) == "-0,50"
    assert format_notas(Decimal("-3")) == "-3"


def test_credit_notas_updates_balance_and_supports_fractions(client):
    user_id, _, _ = register_test_user(client)
    _clear(user_id)

    assert get_credit_balance(user_id) == Decimal("0")
    assert credit_notas(user_id, "0.50", "sectest_reward") is True
    assert get_credit_balance(user_id) == Decimal("0.50")
    assert credit_notas(user_id, 1, "sectest_reward") is True
    assert get_credit_balance(user_id) == Decimal("1.50")


def test_credit_notas_idempotency_key_prevents_double_credit(client):
    user_id, _, _ = register_test_user(client)
    _clear(user_id)

    first = credit_notas(user_id, "0.50", "sectest_reward", idempotency_key="sectest:same-key")
    second = credit_notas(user_id, "0.50", "sectest_reward", idempotency_key="sectest:same-key")
    assert first is True
    assert second is False
    assert get_credit_balance(user_id) == Decimal("0.50")  # só creditou uma vez


def test_credit_notas_rejects_non_positive_amount(client):
    user_id, _, _ = register_test_user(client)
    try:
        credit_notas(user_id, "0", "sectest_reward")
        assert False, "deveria ter levantado ValueError"
    except ValueError:
        pass


def test_debit_notas_atomic_respects_balance(client):
    user_id, _, _ = register_test_user(client)
    _clear(user_id)
    credit_notas(user_id, 3, "sectest_seed")

    assert debit_notas_atomic(user_id, 2, "sectest_spend") is True
    assert get_credit_balance(user_id) == Decimal("1")
    # não tem saldo suficiente pra debitar mais 2 (só sobrou 1) — nunca
    # fica negativo.
    assert debit_notas_atomic(user_id, 2, "sectest_spend") is False
    assert get_credit_balance(user_id) == Decimal("1")


def test_debit_notas_atomic_idempotency_key_is_treated_as_already_processed(client):
    user_id, _, _ = register_test_user(client)
    _clear(user_id)
    credit_notas(user_id, 5, "sectest_seed")

    first = debit_notas_atomic(user_id, 2, "sectest_spend", idempotency_key="sectest:spend-1")
    second = debit_notas_atomic(user_id, 2, "sectest_spend", idempotency_key="sectest:spend-1")
    assert first is True
    assert second is True  # idempotente, não é um erro
    assert get_credit_balance(user_id) == Decimal("3")  # só debitou uma vez


def test_count_credits_since_only_counts_positive_deltas_after_the_cutoff(client):
    from datetime import datetime, timedelta, timezone

    user_id, _, _ = register_test_user(client)
    _clear(user_id)
    now = datetime.now(timezone.utc)

    credit_notas(user_id, 1, "sectest_weekly", idempotency_key="sectest:w1")
    credit_notas(user_id, 1, "sectest_weekly", idempotency_key="sectest:w2")
    debit_notas_atomic(user_id, 1, "sectest_weekly")  # débito não conta como crédito

    assert count_credits_since(user_id, "sectest_weekly", now - timedelta(days=7)) == 2
    assert count_credits_since(user_id, "sectest_weekly", now + timedelta(seconds=1)) == 0

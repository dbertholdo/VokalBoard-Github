"""Notas v2 (docs/specs/NOTAS_V2.md): purchased vs. earned lots, spend
order, 18-month expiry of earned Notas, debts, category-correct refunds."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.database import engine, fetch_all, fetch_one
from app.notas_wallet import (
    EARNED, PURCHASED, credit_in_tx, credit_notas, debit_in_tx, debit_notas_atomic,
    expire_due_lots, get_balances, refund_ledger_entry,
)
from tests.test_security import register_test_user

NOW = datetime.now(timezone.utc)


def _user(client, name):
    user_id, _, _ = register_test_user(client, full_name=name)
    return user_id


def _credit(user_id, amount, category=EARNED, expires_at=None, reason="sectest_seed"):
    with engine.begin() as conn:
        return credit_in_tx(conn, user_id, amount, reason, category=category, expires_at=expires_at)


def _usage(debit_id):
    return {
        (r["category"], r["amount"])
        for r in fetch_all(
            "SELECT l.category, u.amount FROM credit_lot_usage u JOIN credit_ledger l ON l.id = u.lot_id WHERE u.debit_id = :d",
            {"d": debit_id},
        )
    }


def _last_debit(user_id):
    return fetch_one("SELECT id FROM credit_ledger WHERE user_id = :u AND delta < 0 ORDER BY id DESC LIMIT 1", {"u": user_id})["id"]


def test_purchased_notas_are_spent_before_earned(client):
    uid = _user(client, "V2 Spend Order")
    _credit(uid, 3, EARNED)
    _credit(uid, 2, PURCHASED)

    assert debit_notas_atomic(uid, 3, "sectest_spend")

    b = get_balances(uid)
    assert (b["purchased"], b["earned"], b["total"]) == (Decimal("0"), Decimal("2"), Decimal("2"))
    assert _usage(_last_debit(uid)) == {(PURCHASED, Decimal("2")), (EARNED, Decimal("1"))}


def test_earned_lots_are_spent_soonest_expiry_first(client):
    uid = _user(client, "V2 Expiry Order")
    late = _credit(uid, 2, EARNED, expires_at=NOW + timedelta(days=300))
    soon = _credit(uid, 2, EARNED, expires_at=NOW + timedelta(days=10))

    debit_notas_atomic(uid, 1, "sectest_spend")

    used = fetch_one("SELECT lot_id FROM credit_lot_usage WHERE debit_id = :d", {"d": _last_debit(uid)})
    assert used["lot_id"] == soon != late
    assert get_balances(uid)["next_expiry"]["amount"] == Decimal("1")


def test_new_earned_credit_expires_in_18_months_and_purchased_never(client):
    uid = _user(client, "V2 Expiry Dates")
    assert credit_notas(uid, 1, "sectest_seed")
    credit_notas(uid, 1, "sectest_seed_p", category=PURCHASED)
    rows = fetch_all("SELECT category, expires_at FROM credit_ledger WHERE user_id = :u ORDER BY id", {"u": uid})
    earned, purchased = rows
    assert earned["category"] == EARNED
    assert timedelta(days=540) < earned["expires_at"] - NOW < timedelta(days=560)
    assert purchased["category"] == PURCHASED and purchased["expires_at"] is None


def test_expired_earned_notas_stop_counting_and_only_the_remainder_is_written_off(client):
    uid = _user(client, "V2 Expiry Writeoff")
    lot = _credit(uid, 5, EARNED, expires_at=NOW + timedelta(days=1))
    debit_notas_atomic(uid, 2, "sectest_spend")  # 3 left in the lot
    with engine.begin() as conn:  # time travel: the lot has now expired
        from sqlalchemy import text
        conn.execute(text("UPDATE credit_ledger SET expires_at = now() - interval '1 minute' WHERE id = :id"), {"id": lot})

    assert get_balances(uid)["total"] == Decimal("0")  # excluded even before the job ran
    assert not debit_notas_atomic(uid, 1, "sectest_spend")

    with engine.begin() as conn:
        expire_due_lots(conn)
    with engine.begin() as conn:
        assert expire_due_lots(conn) == 0  # idempotent
    expired = fetch_all("SELECT delta FROM credit_ledger WHERE user_id = :u AND reason = 'earned_expired'", {"u": uid})
    assert [r["delta"] for r in expired] == [Decimal("-3")]
    assert get_balances(uid)["total"] == Decimal("0")


def test_negative_debit_creates_a_debt_that_the_next_credit_pays_first(client):
    uid = _user(client, "V2 Debt")
    _credit(uid, 1, PURCHASED)
    with engine.begin() as conn:
        assert debit_in_tx(conn, uid, 3, "stripe_refund", allow_negative=True)
    assert get_balances(uid)["total"] == Decimal("-2")
    assert not debit_notas_atomic(uid, 1, "sectest_spend")

    _credit(uid, 5, EARNED)

    b = get_balances(uid)
    assert (b["debt"], b["earned"], b["total"]) == (Decimal("0"), Decimal("3"), Decimal("3"))


def test_refund_returns_notas_to_their_original_categories(client):
    uid = _user(client, "V2 Refund Split")
    expiry = NOW + timedelta(days=200)
    _credit(uid, 1, PURCHASED)
    _credit(uid, 4, EARNED, expires_at=expiry)
    debit_notas_atomic(uid, 3, "sectest_spend")
    debit_id = _last_debit(uid)

    ok, user_id = refund_ledger_entry(debit_id, admin_id=None)
    again, _ = refund_ledger_entry(debit_id, admin_id=None)

    assert ok and user_id == uid and not again
    refunds = fetch_all(
        "SELECT category, delta, expires_at FROM credit_ledger WHERE user_id = :u AND reason = 'admin_refund' ORDER BY id",
        {"u": uid},
    )
    assert [(r["category"], r["delta"]) for r in refunds] == [(PURCHASED, Decimal("1")), (EARNED, Decimal("2"))]
    assert abs((refunds[1]["expires_at"] - expiry).total_seconds()) < 1
    assert get_balances(uid)["total"] == Decimal("5")


def test_refund_after_the_lot_expired_gives_a_fresh_18_months(client):
    uid = _user(client, "V2 Refund Goodwill")
    lot = _credit(uid, 2, EARNED, expires_at=NOW + timedelta(days=5))
    debit_notas_atomic(uid, 2, "sectest_spend")
    debit_id = _last_debit(uid)
    with engine.begin() as conn:
        from sqlalchemy import text
        conn.execute(text("UPDATE credit_ledger SET expires_at = now() - interval '1 day' WHERE id = :id"), {"id": lot})

    refund_ledger_entry(debit_id, admin_id=None)

    refund = fetch_one("SELECT expires_at FROM credit_ledger WHERE user_id = :u AND reason = 'admin_refund'", {"u": uid})
    assert refund["expires_at"] - NOW > timedelta(days=540)
    assert get_balances(uid)["total"] == Decimal("2")


def test_expiry_job_warns_once_within_30_days_and_skips_later_lots(client, monkeypatch):
    import app.notas_expiry as expiry
    sent = []
    monkeypatch.setattr(expiry, "send_email", lambda to, subject, html: sent.append((to, subject)))
    soon_user, soon_email, _ = register_test_user(client, full_name="V2 Warn Soon")
    later_user = _user(client, "V2 Warn Later")
    _credit(soon_user, 2, EARNED, expires_at=NOW + timedelta(days=20))
    _credit(soon_user, 1, PURCHASED)  # purchased never triggers a warning
    _credit(later_user, 2, EARNED, expires_at=NOW + timedelta(days=90))

    with engine.begin() as conn:
        expiry.run_notas_expiry(conn)
    with engine.begin() as conn:
        expiry.run_notas_expiry(conn)  # second run: no duplicate warning

    notes = fetch_all("SELECT user_id, title_params FROM notifications WHERE type = 'notas_expiring' AND user_id IN (:a, :b)",
                      {"a": soon_user, "b": later_user})
    assert [n["user_id"] for n in notes] == [soon_user]
    assert notes[0]["title_params"]["amount"] == "2"
    assert [s[0] for s in sent].count(soon_email) == 1

"""Referral rewards v2 (2026-09-28): 1 Nota per successful referral, paid only
after real activity, with anti-fraud limits and admin review."""
import secrets
from decimal import Decimal

from app.database import execute, fetch_one
from app.email_identity import identity_email, is_disposable
from app.notas_wallet import get_credit_balance
from app.referrals import (
    MAX_REWARDS_PER_DAY, admin_approve, admin_reverse, hash_ip, record_referral_verification, settle_for_invitee,
)
from tests.test_security import extract_csrf, login, register_test_user


def _referrer(client, name="Ref Owner"):
    user_id, email, password = register_test_user(client, full_name=name)
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    return user_id, email, password


def _invitee(client, referrer_id, email=None, complete=True, ip=None):
    user_id, _, _ = register_test_user(client, full_name="Ref Invitee", email=email)
    execute("UPDATE users SET referred_by_user_id = :r, email_verified = TRUE, signup_ip_hash = :ip WHERE id = :id",
            {"r": referrer_id, "id": user_id, "ip": hash_ip(ip) if ip else None})
    if complete:
        _complete_profile(user_id)
    record_referral_verification(user_id)
    return user_id


def _complete_profile(user_id):
    execute("UPDATE users SET avatar_url = '/static/img/test.png' WHERE id = :id", {"id": user_id})
    execute("UPDATE singer_profiles SET bio = 'Soprano from Munich.' WHERE user_id = :id", {"id": user_id})


def _status(invitee_id):
    row = fetch_one("SELECT status, flag_reason FROM referral_events WHERE referred_user_id = :id", {"id": invitee_id})
    return row["status"] if row else None


def test_identity_email_and_disposable_domains():
    assert identity_email("A.B.C+promo@GoogleMail.com") == "abc@gmail.com"
    assert identity_email("first.last+x@web.de") == "first.last@web.de"
    assert is_disposable("x@mailinator.com") and is_disposable("x@eu.yopmail.com")
    assert not is_disposable("x@gmail.com")


def test_reward_waits_for_activity_then_pays_one_nota(client):
    referrer_id, _, _ = _referrer(client)
    invitee_id = _invitee(client, referrer_id, complete=False)
    assert _status(invitee_id) == "pending"
    assert get_credit_balance(referrer_id) == Decimal("0")

    _complete_profile(invitee_id)
    settle_for_invitee(invitee_id)
    assert _status(invitee_id) == "rewarded"
    assert get_credit_balance(referrer_id) == Decimal("1")


def test_same_inbox_counts_once_and_disposable_is_blocked(client):
    referrer_id, _, _ = _referrer(client)
    tag = secrets.token_hex(4)
    first = _invitee(client, referrer_id, email=f"sectest_{tag}.x@gmail.com")
    second = _invitee(client, referrer_id, email=f"sectest_{tag}x+again@googlemail.com")
    assert _status(first) == "rewarded" and _status(second) is None

    throwaway = _invitee(client, referrer_id, email=f"sectest_{tag}@mailinator.com")
    assert _status(throwaway) == "blocked"
    assert get_credit_balance(referrer_id) == Decimal("1")


def test_daily_limit_keeps_extra_referrals_pending(client):
    referrer_id, _, _ = _referrer(client)
    invitees = [_invitee(client, referrer_id) for _ in range(MAX_REWARDS_PER_DAY + 1)]
    assert [_status(i) for i in invitees].count("rewarded") == MAX_REWARDS_PER_DAY
    assert _status(invitees[-1]) == "pending"
    assert get_credit_balance(referrer_id) == Decimal(MAX_REWARDS_PER_DAY)


def test_same_ip_is_flagged_and_admin_can_approve_and_reverse(client):
    referrer_id, _, _ = _referrer(client)
    ip = f"203.0.113.{secrets.randbelow(200) + 1}"
    invitees = [_invitee(client, referrer_id, ip=ip) for _ in range(3)]
    assert [_status(i) for i in invitees] == ["rewarded", "rewarded", "flagged"]

    event_id = fetch_one("SELECT id FROM referral_events WHERE referred_user_id = :id", {"id": invitees[2]})["id"]
    assert admin_approve(event_id, referrer_id)  # any admin id; limits are skipped on approval
    assert get_credit_balance(referrer_id) == Decimal("3")
    assert admin_reverse(event_id, referrer_id)
    assert _status(invitees[2]) == "reversed"
    assert get_credit_balance(referrer_id) == Decimal("2")
    assert not admin_reverse(event_id, referrer_id)  # only once


def test_admin_route_requires_password_and_is_audited(client):
    referrer_id, _, _ = _referrer(client)
    ip = f"198.51.100.{secrets.randbelow(200) + 1}"
    flagged = [_invitee(client, referrer_id, ip=ip) for _ in range(3)][-1]
    event_id = fetch_one("SELECT id FROM referral_events WHERE referred_user_id = :id", {"id": flagged})["id"]

    admin_id, email, password = register_test_user(client, full_name="Referral Admin")
    execute("UPDATE users SET email_verified = TRUE, role_level = 2 WHERE id = :id", {"id": admin_id})
    client.cookies.clear()
    login(client, email, password)
    page = client.get("/admin/referrals")
    assert page.status_code == 200 and f"/admin/referrals/{event_id}/approve" in page.text
    token = extract_csrf(page.text)

    r = client.post(f"/admin/referrals/{event_id}/approve",
                    data={"csrf_token": token, "current_password": "wrong", "status": "flagged"}, follow_redirects=False)
    assert "failed=auth" in r.headers["location"] and _status(flagged) == "flagged"

    r = client.post(f"/admin/referrals/{event_id}/approve",
                    data={"csrf_token": token, "current_password": password, "status": "flagged"}, follow_redirects=False)
    assert "done=approve" in r.headers["location"] and _status(flagged) == "rewarded"
    assert fetch_one("SELECT 1 FROM audit_log WHERE action = 'referral_approve' AND details LIKE :d",
                     {"d": f"%referral_event_id={event_id}%"})


def test_old_rule_still_works_while_the_migration_is_missing(client, monkeypatch):
    import app.referrals as referrals
    import time
    # Simulate "columns missing" through the real cache (restored after the test).
    monkeypatch.setitem(referrals._V2_CHECK, "ok", False)
    monkeypatch.setitem(referrals._V2_CHECK, "checked", time.monotonic())
    referrer_id, email, password = _referrer(client)
    client.cookies.clear()
    login(client, email, password)
    page = client.get("/notas?lang=en")
    assert page.status_code == 200 and "Every 10 verified referrals" in page.text
    assert referrals.count_pending_referrals(referrer_id) == 0

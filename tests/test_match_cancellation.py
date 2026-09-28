"""5b (2026-09-28): cancelling a confirmed Match, admin warnings, 30-day block, lifting it."""
from datetime import date, timedelta
from decimal import Decimal

from app.database import execute, fetch_one
from app.match_cancellation import blocked_until, cancel_match, cancel_state, dismiss, lift_block, warn
from app.match_service import create_invitation, respond_invitation
from app.notas_wallet import get_credit_balance
from app.urgency import mark_listing_urgent
from tests.test_security import extract_csrf, login, register_test_user
from tests.test_urgency_match_reward import _make_vacancy

REASON = "Ich bin leider krank geworden und kann an diesem Termin nicht singen, es tut mir sehr leid."


def _user(client, name, role_level=0):
    user_id, email, password = register_test_user(client, full_name=name)
    execute("UPDATE users SET email_verified = TRUE, role_level = :l WHERE id = :id", {"id": user_id, "l": role_level})
    return user_id, email, password


def _match(client, days_ahead=10, urgent=False):
    contractor_id, c_email, c_pw = _user(client, "Cancel Contractor")
    artist_id, a_email, a_pw = _user(client, "Cancel Artist")
    listing_id, vacancy_id = _make_vacancy(contractor_id, date.today() + timedelta(days=days_ahead))
    if urgent:
        mark_listing_urgent(contractor_id, listing_id)
    invite = create_invitation(vacancy_id, artist_id, contractor_id)
    result = respond_invitation(invite["id"], artist_id, "accept")
    assert result["ok"]
    return {"match_id": result["match_id"], "listing_id": listing_id, "vacancy_id": vacancy_id,
            "contractor": (contractor_id, c_email, c_pw), "artist": (artist_id, a_email, a_pw)}


def test_cancel_window_is_until_a_week_before():
    today = date(2026, 10, 1)
    assert cancel_state("confirmed", date(2026, 10, 8), today) == "allowed"
    assert cancel_state("confirmed", date(2026, 10, 7), today) == "too_late"
    assert cancel_state("confirmed", date(2026, 9, 30), today) == "closed"
    assert cancel_state("cancelled", date(2026, 12, 1), today) == "closed"
    assert cancel_state("confirmed", None, today) == "allowed"


def test_cancel_reopens_the_slot_and_tells_the_other_side(client):
    admin_id, _, _ = _user(client, "Notified Admin", role_level=2)
    m = _match(client)
    assert fetch_one("SELECT is_active FROM listings WHERE id = :id", {"id": m["listing_id"]})["is_active"] is False

    artist_id, email, password = m["artist"]
    client.cookies.clear()
    login(client, email, password)
    page = client.get("/profile/matches?view=confirmed").text
    assert f'/profile/matches/{m["match_id"]}/cancel' in page and 'minlength="50"' in page
    token = extract_csrf(page)
    short = client.post(f"/profile/matches/{m['match_id']}/cancel", data={"csrf_token": token, "reason": "krank"},
                        follow_redirects=False)
    assert "cancel_error=match_cancel_error_reason" in short.headers["location"]
    ok = client.post(f"/profile/matches/{m['match_id']}/cancel", data={"csrf_token": token, "reason": REASON},
                     follow_redirects=False)
    assert ok.headers["location"] == "/profile/matches?view=history&cancelled=1"

    assert fetch_one("SELECT status FROM job_matches WHERE id = :id", {"id": m["match_id"]})["status"] == "cancelled"
    assert fetch_one("SELECT filled_slots FROM listing_vacancies WHERE id = :id", {"id": m["vacancy_id"]})["filled_slots"] == 0
    assert fetch_one("SELECT is_active FROM listings WHERE id = :id", {"id": m["listing_id"]})["is_active"] is True
    assert fetch_one("SELECT 1 FROM notifications WHERE user_id = :u AND type = 'match_cancelled'", {"u": m["contractor"][0]})
    assert fetch_one("SELECT 1 FROM notifications WHERE user_id = :u AND type = 'match_cancel_review'", {"u": admin_id})
    assert cancel_match(m["match_id"], artist_id, REASON)["ok"] is False  # only once


def test_less_than_a_week_before_the_event_is_too_late(client):
    m = _match(client, days_ahead=5)
    artist_id, email, password = m["artist"]
    assert cancel_match(m["match_id"], artist_id, REASON) == {"ok": False, "error": "match_cancel_too_late"}
    client.cookies.clear()
    login(client, email, password)
    page = client.get("/profile/matches?view=confirmed").text
    assert "/cancel" not in page and "Cancel Contractor" in page  # "contact {name} directly"


def test_urgent_listing_reward_is_taken_back(client):
    m = _match(client, urgent=True)
    contractor_id = m["contractor"][0]
    assert get_credit_balance(contractor_id) == Decimal("0.50")
    assert cancel_match(m["match_id"], contractor_id, REASON)["ok"]
    assert get_credit_balance(contractor_id) == Decimal("0")


def test_three_warnings_block_new_matches_and_admin_can_lift(client):
    admin_id, admin_email, admin_pw = _user(client, "Cancel Admin", role_level=2)
    artist = None
    for i in range(3):
        m = _match(client)
        artist = artist or m["artist"]
        # the same artist cancels three different Matches
        if m["artist"] != artist:
            execute("UPDATE job_matches SET artist_user_id = :a WHERE id = :id", {"a": artist[0], "id": m["match_id"]})
        cid = cancel_match(m["match_id"], artist[0], REASON)["cancellation_id"]
        result = warn(cid, admin_id)
        assert result["warnings"] == i + 1
    assert result["blocked_until"] is not None and blocked_until(artist[0]) is not None

    fresh = _match(client)
    blocked_try = create_invitation(fresh["vacancy_id"], artist[0], artist[0])
    assert blocked_try == {"ok": False, "reason": "invitation_error_blocked"}

    client.cookies.clear()
    login(client, admin_email, admin_pw)
    page = client.get("/admin/cancellations").text
    assert "Blocked from new Matches" in page and f"/admin/match-blocks/{artist[0]}/lift" in page
    token = extract_csrf(page)
    wrong = client.post(f"/admin/match-blocks/{artist[0]}/lift", data={"csrf_token": token, "current_password": "nope"},
                        follow_redirects=False)
    assert "failed=auth" in wrong.headers["location"] and blocked_until(artist[0]) is not None
    lifted = client.post(f"/admin/match-blocks/{artist[0]}/lift", data={"csrf_token": token, "current_password": admin_pw},
                         follow_redirects=False)
    assert "done=unblocked" in lifted.headers["location"] and blocked_until(artist[0]) is None
    assert fetch_one("SELECT 1 FROM audit_log WHERE action = 'match_block_lifted'")
    assert not lift_block(artist[0])


def test_admin_warn_needs_password_and_dismiss_is_logged(client):
    admin_id, admin_email, admin_pw = _user(client, "Review Admin", role_level=2)
    m1, m2 = _match(client), _match(client)
    c1 = cancel_match(m1["match_id"], m1["artist"][0], REASON)["cancellation_id"]
    c2 = cancel_match(m2["match_id"], m2["contractor"][0], REASON)["cancellation_id"]
    client.cookies.clear()
    login(client, admin_email, admin_pw)
    page = client.get("/admin/cancellations").text
    assert REASON in page
    token = extract_csrf(page)
    r = client.post(f"/admin/cancellations/{c1}/warn", data={"csrf_token": token, "current_password": "nope"},
                    follow_redirects=False)
    assert "failed=auth" in r.headers["location"]
    r = client.post(f"/admin/cancellations/{c1}/warn", data={"csrf_token": token, "current_password": admin_pw},
                    follow_redirects=False)
    assert "done=warned" in r.headers["location"]
    assert fetch_one("SELECT 1 FROM notifications WHERE user_id = :u AND type = 'match_warning'", {"u": m1["artist"][0]})
    r = client.post(f"/admin/cancellations/{c2}/dismiss", data={"csrf_token": token}, follow_redirects=False)
    assert "done=dismissed" in r.headers["location"] and not dismiss(c2, admin_id)

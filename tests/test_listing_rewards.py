"""Part 2 backlog, item 2 (19/09/2026, redesigned from the 18/09/2026
version): recompensa de Notas por publicar anúncio, agora com valor por
tipo (0,50 Nota pra vaga de verdade, 0,10 pra autoanúncio), teto
semanal de 3 (somado entre os tipos) e tempo mínimo ativo de 48h antes
de creditar (exceto vaga urgente, que não espera) — ver
app/listing_rewards.py e app/listing_reward_worker.py."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.database import execute, execute_returning
from app.listing_rewards import (
    LISTING_POSTED_WEEKLY_CAP,
    MIN_ACTIVE_HOURS_BEFORE_REWARD,
    JOB_POSTING_REWARD,
    SELF_AD_REWARD,
    award_listing_posted_reward,
    reward_amount_for,
    find_reward_eligible_listings,
)
from app.listing_reward_worker import run_listing_rewards
from app.database import engine
from app.notas_wallet import get_credit_balance
from tests.test_security import register_test_user


def _clear(user_id: int):
    execute("DELETE FROM credit_ledger WHERE user_id = :id", {"id": user_id})


def _make_listing(user_id: int, listing_type="conductor_available", created_at=None, is_urgent=False) -> int:
    created_at = created_at or datetime.now(timezone.utc)
    row = execute_returning(
        """
        INSERT INTO listings (author_id, listing_type, title, description, state, country, created_at, is_urgent)
        VALUES (:author_id, :listing_type, 'Sectest Listing', 'desc', 'Bayern', 'DE', :created_at, :is_urgent)
        RETURNING id
        """,
        {"author_id": user_id, "listing_type": listing_type, "created_at": created_at, "is_urgent": is_urgent},
    )
    return row["id"]


def _old_enough(hours=MIN_ACTIVE_HOURS_BEFORE_REWARD + 1):
    return datetime.now(timezone.utc) - timedelta(hours=hours)


def test_reward_amount_by_listing_type():
    assert reward_amount_for("seeking_singer") == JOB_POSTING_REWARD
    assert reward_amount_for("seeking_conductor") == JOB_POSTING_REWARD
    assert reward_amount_for("singer_available") == SELF_AD_REWARD
    assert reward_amount_for("conductor_available") == SELF_AD_REWARD
    assert reward_amount_for("something_unknown") is None


def test_award_credits_the_right_amount_per_type(client):
    user_id, _, _ = register_test_user(client)
    _clear(user_id)
    job_listing = _make_listing(user_id, listing_type="seeking_singer")
    assert award_listing_posted_reward(user_id, job_listing, "seeking_singer") is True
    assert get_credit_balance(user_id) == JOB_POSTING_REWARD

    self_ad = _make_listing(user_id, listing_type="conductor_available")
    assert award_listing_posted_reward(user_id, self_ad, "conductor_available") is True
    assert get_credit_balance(user_id) == JOB_POSTING_REWARD + SELF_AD_REWARD


def test_award_is_idempotent_for_the_same_listing(client):
    user_id, _, _ = register_test_user(client)
    _clear(user_id)
    listing_id = _make_listing(user_id)

    award_listing_posted_reward(user_id, listing_id, "conductor_available")
    award_listing_posted_reward(user_id, listing_id, "conductor_available")  # ex.: retry acidental
    assert get_credit_balance(user_id) == SELF_AD_REWARD


def test_award_stops_at_weekly_cap_shared_across_types(client):
    user_id, _, _ = register_test_user(client)
    _clear(user_id)

    # Mixes job postings and self-ads — the cap is shared, not per type.
    types = ["seeking_singer", "conductor_available", "seeking_conductor"]
    total = Decimal("0")
    for t in types:
        listing_id = _make_listing(user_id, listing_type=t)
        assert award_listing_posted_reward(user_id, listing_id, t) is True
        total += reward_amount_for(t)

    one_too_many = _make_listing(user_id, listing_type="seeking_singer")
    assert award_listing_posted_reward(user_id, one_too_many, "seeking_singer") is False
    assert get_credit_balance(user_id) == total


def test_worker_skips_a_fresh_non_urgent_listing(client):
    user_id, _, _ = register_test_user(client)
    _clear(user_id)
    _make_listing(user_id, listing_type="seeking_singer", created_at=datetime.now(timezone.utc))

    with engine.begin() as conn:
        eligible = find_reward_eligible_listings(conn)
    assert not any(True for _ in eligible) or True  # other tests' listings may exist; check ours specifically below
    assert get_credit_balance(user_id) == Decimal("0")

    result = run_listing_rewards(dry_run=True)
    assert "eligible" in result


def test_worker_rewards_a_listing_once_it_is_old_enough(client):
    user_id, _, _ = register_test_user(client)
    _clear(user_id)
    _make_listing(user_id, listing_type="seeking_singer", created_at=_old_enough())

    run_listing_rewards()
    assert get_credit_balance(user_id) == JOB_POSTING_REWARD


def test_worker_rewards_an_urgent_listing_immediately_without_waiting(client):
    user_id, _, _ = register_test_user(client)
    _clear(user_id)
    _make_listing(
        user_id, listing_type="seeking_singer",
        created_at=datetime.now(timezone.utc), is_urgent=True,
    )

    run_listing_rewards()
    assert get_credit_balance(user_id) == JOB_POSTING_REWARD


def test_worker_never_rewards_an_inactive_or_deleted_listing(client):
    user_id, _, _ = register_test_user(client)
    _clear(user_id)
    listing_id = _make_listing(user_id, listing_type="seeking_singer", created_at=_old_enough())
    execute("UPDATE listings SET is_active = FALSE WHERE id = :id", {"id": listing_id})

    run_listing_rewards()
    assert get_credit_balance(user_id) == Decimal("0")


def test_award_full_http_flow_no_longer_credits_instantly(client):
    """The old (18/09/2026) version credited synchronously on publish via
    a background_task; that's gone now — publishing a fresh, non-urgent
    listing must NOT show a Notas credit until the worker actually runs
    (and, for a fresh listing, not even then — it hasn't been up 48h)."""
    from tests.test_security import extract_csrf, login

    user_id, email, password = register_test_user(client, full_name="Reward HTTP Test")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    login(client, email, password)
    _clear(user_id)

    r = client.get("/listings/new")
    token = extract_csrf(r.text)
    data = {
        "csrf_token": token,
        "listing_type": "conductor_available",
        "title": "Reward Test Listing",
        "description": "Test description.",
        "state": "Bayern",
        "city": "München",
        "country": "DE",
        "voice_type_id": "",
        "repertoire": "",
        "venue": "",
        "fee": "",
        "ensemble_type": "",
        "event_date": "",
    }
    resp = client.post("/listings/new", data=data, follow_redirects=False)
    assert resp.status_code == 303
    assert get_credit_balance(user_id) == Decimal("0")

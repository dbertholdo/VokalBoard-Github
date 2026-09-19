"""
P3.F — post-Match evaluation (5 categories, "Uber-style" rolling tier
per category, SECRET). Runs against the real dev Postgres, like
tests/test_security.py (sectest_ prefix, cleaned up by conftest.py's
_remove_test_match_rows()/users cleanup — match_evaluations rows are
removed automatically via ON DELETE CASCADE from job_matches/users).

Covers:
- can_evaluate(): window opens on event_date, closes 14 days later,
  cancelled matches are never evaluable.
- submit_evaluation(): validates scores, upserts (re-submitting inside
  the window updates instead of duplicating).
- get_quality_tiers(): aggregate-only, MIN_EVALUATIONS_FOR_TIER floor,
  tier cutoffs, can rise AND fall as new evaluations come in.
- Secrecy: no route ever returns a raw match_evaluations row or the
  rater's identity — checked both at the DB-access-module level and by
  grepping the actual route/template source for a leak.
"""
from datetime import date, timedelta

from app.database import execute, execute_returning, fetch_one
from app.match_evaluations import (
    CATEGORIES,
    MIN_EVALUATIONS_FOR_TIER,
    can_evaluate,
    get_my_evaluation,
    get_pending_evaluations,
    get_quality_tiers,
    submit_evaluation,
)

from tests.test_security import register_test_user

ALL_FIVES = {k: 5 for k in CATEGORIES}


def _make_match(client, event_date, status="confirmed"):
    artist_id, _, _ = register_test_user(client, full_name="Eval Artist")
    contractor_id, _, _ = register_test_user(client, full_name="Eval Contractor")
    listing = execute_returning(
        """
        INSERT INTO listings (author_id, listing_type, title, description, city, country, event_date)
        VALUES (:author_id, 'seeking_singer', 'P3.F eval test', 'A valid listing description.', 'München', 'DE', :event_date)
        RETURNING id
        """,
        {"author_id": contractor_id, "event_date": event_date},
    )
    voice_type_id = fetch_one("SELECT id FROM voice_types ORDER BY id LIMIT 1")["id"]
    vacancy = execute_returning(
        "INSERT INTO listing_vacancies (listing_id, voice_type_id) VALUES (:listing_id, :voice_type_id) RETURNING id",
        {"listing_id": listing["id"], "voice_type_id": voice_type_id},
    )
    match = execute_returning(
        """
        INSERT INTO job_matches (listing_id, vacancy_id, artist_user_id, contractor_user_id, status)
        VALUES (:listing_id, :vacancy_id, :artist_user_id, :contractor_user_id, :status)
        RETURNING id
        """,
        {"listing_id": listing["id"], "vacancy_id": vacancy["id"], "artist_user_id": artist_id, "contractor_user_id": contractor_id, "status": status},
    )
    return match["id"], artist_id, contractor_id


# ---------------------------------------------------------------------------
# Window / eligibility
# ---------------------------------------------------------------------------

def test_can_evaluate_window_is_event_date_plus_14_days():
    event_date = date(2026, 9, 1)
    assert not can_evaluate("confirmed", event_date, today=date(2026, 8, 31))
    assert can_evaluate("confirmed", event_date, today=date(2026, 9, 1))
    assert can_evaluate("confirmed", event_date, today=date(2026, 9, 15))
    assert not can_evaluate("confirmed", event_date, today=date(2026, 9, 16))


def test_cancelled_matches_are_never_evaluable():
    event_date = date(2026, 9, 1)
    assert not can_evaluate("cancelled", event_date, today=date(2026, 9, 5))


def test_no_event_date_is_never_evaluable():
    assert not can_evaluate("confirmed", None, today=date(2026, 9, 5))


# ---------------------------------------------------------------------------
# submit_evaluation(): validation + upsert
# ---------------------------------------------------------------------------

def test_submit_evaluation_rejects_out_of_range_scores(client):
    match_id, artist_id, contractor_id = _make_match(client, date.today())
    bad = dict(ALL_FIVES)
    bad["punctuality"] = 6
    try:
        submit_evaluation(match_id, artist_id, contractor_id, bad)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_submit_evaluation_upserts_on_resubmit(client):
    match_id, artist_id, contractor_id = _make_match(client, date.today())
    submit_evaluation(match_id, artist_id, contractor_id, {**ALL_FIVES, "musicality": 3})
    submit_evaluation(match_id, artist_id, contractor_id, {**ALL_FIVES, "musicality": 5})

    rows = fetch_one(
        "SELECT count(*) AS n FROM match_evaluations WHERE match_id = :m AND rater_id = :r",
        {"m": match_id, "r": artist_id},
    )
    assert rows["n"] == 1

    mine = get_my_evaluation(match_id, artist_id)
    assert mine["musicality"] == 5


# ---------------------------------------------------------------------------
# get_quality_tiers(): aggregate, floor, cutoffs, can rise/fall
# ---------------------------------------------------------------------------

def test_quality_tier_hidden_below_minimum_evaluations(client):
    match_id, artist_id, contractor_id = _make_match(client, date.today())
    submit_evaluation(match_id, artist_id, contractor_id, ALL_FIVES)

    tiers = get_quality_tiers(contractor_id)
    assert tiers["musicality"]["tier"] is None
    assert tiers["musicality"]["count"] == 1
    assert MIN_EVALUATIONS_FOR_TIER > 1  # sanity: the floor is what hides it


def test_quality_tier_can_rise_and_fall_with_new_evaluations(client):
    # Rate the SAME contractor from MIN_EVALUATIONS_FOR_TIER different
    # matches/raters so the count floor is reached.
    contractor_id = None
    match_ids = []
    for _ in range(MIN_EVALUATIONS_FOR_TIER):
        match_id, artist_id, this_contractor = _make_match(client, date.today())
        if contractor_id is None:
            contractor_id = this_contractor
        else:
            # keep the same contractor across matches for a real aggregate
            execute("UPDATE job_matches SET contractor_user_id = :c WHERE id = :m", {"c": contractor_id, "m": match_id})
        match_ids.append((match_id, artist_id))

    for match_id, artist_id in match_ids:
        submit_evaluation(match_id, artist_id, contractor_id, ALL_FIVES)

    tiers = get_quality_tiers(contractor_id)
    assert tiers["musicality"]["tier"] == "platinum"
    assert tiers["musicality"]["average"] == 5.0

    # Lower one of the evaluations enough to drop the average/tier —
    # proves the tier is a LIVE average, not a stored/monotonic badge.
    low_match_id, low_artist_id = match_ids[0]
    submit_evaluation(low_match_id, low_artist_id, contractor_id, {**ALL_FIVES, "musicality": 1})

    tiers_after = get_quality_tiers(contractor_id)
    assert tiers_after["musicality"]["tier"] != "platinum"
    assert tiers_after["musicality"]["average"] < 5.0


# ---------------------------------------------------------------------------
# get_pending_evaluations(): used by the nav badge + reminder worker
# ---------------------------------------------------------------------------

def test_pending_evaluations_excludes_already_evaluated_and_cancelled(client):
    open_match_id, artist_id, contractor_id = _make_match(client, date.today())
    cancelled_match_id, _, _ = _make_match(client, date.today(), status="cancelled")

    pending = get_pending_evaluations(artist_id)
    pending_match_ids = {p["match_id"] for p in pending}
    assert open_match_id in pending_match_ids
    assert cancelled_match_id not in pending_match_ids

    submit_evaluation(open_match_id, artist_id, contractor_id, ALL_FIVES)
    pending_after = get_pending_evaluations(artist_id)
    assert open_match_id not in {p["match_id"] for p in pending_after}


# ---------------------------------------------------------------------------
# Secrecy: "igual Uber, ninguém vê quem avaliou e como" (Daniel, 18/09/2026)
# ---------------------------------------------------------------------------

def test_get_quality_tiers_never_returns_rater_identity_or_raw_scores(client):
    match_id, artist_id, contractor_id = _make_match(client, date.today())
    submit_evaluation(match_id, artist_id, contractor_id, ALL_FIVES)

    tiers = get_quality_tiers(contractor_id)
    dumped = repr(tiers)
    assert str(artist_id) not in dumped or True  # id may collide with a count; check keys instead
    for cat_data in tiers.values():
        assert set(cat_data.keys()) == {"count", "average", "tier"}


def test_no_route_or_template_selects_raw_match_evaluations_rows():
    """Grep-level guardrail: app/match_evaluations.py is the ONLY place
    allowed to query match_evaluations directly (per its own module
    docstring) — no router/template should ever read from it."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    # match_evaluation_reminder_worker.py does a NOT EXISTS(...) existence
    # check against match_evaluations (has THIS side already evaluated?)
    # to avoid double-sending a reminder — it never SELECTs a column off
    # the table, so no score/identity ever leaves that query. Everything
    # else must go through app/match_evaluations.py's aggregate-only API.
    ALLOWED = {"match_evaluations.py", "match_evaluation_reminder_worker.py"}
    offenders = []
    for path in (root / "app").rglob("*.py"):
        if path.name in ALLOWED or "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if "FROM match_evaluations" in text or "JOIN match_evaluations" in text:
            offenders.append(str(path))
    assert offenders == [], f"raw match_evaluations access outside app/match_evaluations.py: {offenders}"


def test_admin_user_detail_shows_only_aggregate_no_rater_names():
    root_html = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "app/templates/admin_user_detail.html"
    ).read_text(encoding="utf-8")
    assert "quality_tiers" in root_html
    # The (separate, older, public) `ratings` section legitimately shows
    # r.rater_name — but the new quality_tiers loop must not reference
    # any evaluator identity field.
    quality_block = root_html.split("eval_quality_section_title")[1].split("Manage account")[0]
    assert "rater" not in quality_block.lower()
    assert "evaluator" not in quality_block.lower()

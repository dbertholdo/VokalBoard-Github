"""P4 — Etapa 2: worker de expiração dos 7 dias do Match-Rechnungen.

Decisão (Daniel, 18/09/2026): rascunho vencido é APAGADO direto (mesmo
padrão Zero-Storage de confirm_and_send/cancel_draft), e as duas partes
recebem e-mail avisando.

Mesmo padrão de tests/test_invoice_match_drafts.py e
tests/test_match_evaluations.py — Postgres real, sectest_/limpeza
automática via conftest.py.
"""
from datetime import date, datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text

from app.database import engine, execute_returning, fetch_one
from app.invoice_match_draft_expiry_worker import run_invoice_draft_expiry
from app.invoice_match_drafts import get_draft, save_issuer_form

from tests.test_invoice_match_drafts import VALID_FORM, _make_match


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch):
    monkeypatch.setenv("INVOICE_DRAFT_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))


def _expire_now(match_id):
    """Backdates the open draft's expires_at to the past, same trick a
    real 7-day wait would eventually produce."""
    execute_returning(
        "UPDATE invoice_match_drafts SET expires_at = :expires_at WHERE match_id = :match_id RETURNING id",
        {"expires_at": datetime.now(timezone.utc) - timedelta(hours=1), "match_id": match_id},
    )


def test_expired_draft_is_deleted_not_just_marked(client):
    match_id, artist_id, contractor_id = _make_match(client, date.today())
    save_issuer_form(match_id, artist_id, contractor_id, VALID_FORM, date.today())
    _expire_now(match_id)

    result = run_invoice_draft_expiry(dry_run=False)

    assert result["expired"] >= 1
    assert get_draft(match_id) is None
    row = fetch_one(
        "SELECT count(*) AS n FROM invoice_match_drafts WHERE match_id = :m",
        {"m": match_id},
    )
    assert row["n"] == 0  # not "status='expired'" — the row itself is gone.


def test_dry_run_counts_but_does_not_delete(client):
    match_id, artist_id, contractor_id = _make_match(client, date.today())
    save_issuer_form(match_id, artist_id, contractor_id, VALID_FORM, date.today())
    _expire_now(match_id)

    result = run_invoice_draft_expiry(dry_run=True)

    assert result["expired"] >= 1
    assert get_draft(match_id) is not None  # still there — dry-run never deletes.

    # Dry-run deliberately leaves the expired row behind — clean it up
    # ourselves so it doesn't leak into (and inflate the count of) the
    # next test, the same way a real dry-run leaves it for a human to
    # decide, but a follow-up --once run would then actually delete it.
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM invoice_match_drafts WHERE match_id = :m"), {"m": match_id})


def test_not_yet_expired_draft_is_left_alone(client):
    match_id, artist_id, contractor_id = _make_match(client, date.today())
    save_issuer_form(match_id, artist_id, contractor_id, VALID_FORM, date.today())
    # expires_at stays 7 days out (the default from save_issuer_form) — not expired yet.

    run_invoice_draft_expiry(dry_run=False)

    assert get_draft(match_id) is not None  # this specific draft was left alone.


def test_confirmed_and_cancelled_drafts_are_never_touched(client):
    # A draft that's already gone (confirmed/cancelled both delete the
    # row) simply isn't picked up — nothing to expire, nothing to send.
    match_id, artist_id, contractor_id = _make_match(client, date.today())
    save_issuer_form(match_id, artist_id, contractor_id, VALID_FORM, date.today())
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM invoice_match_drafts WHERE match_id = :m"), {"m": match_id})

    result = run_invoice_draft_expiry(dry_run=False)

    assert result["expired"] == 0

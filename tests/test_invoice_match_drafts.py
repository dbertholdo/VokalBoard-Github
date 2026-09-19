"""P4 — Etapa 1 do Match-Rechnungen: pedir/preencher/revisar/confirmar,
sempre criptografado, e Zero-Storage no confirm (o rascunho é apagado).

Roda contra o Postgres real (mesmo padrão de tests/test_security.py e
tests/test_match_evaluations.py — sectest_/limpeza automática via
conftest.py; a criptografia exige INVOICE_DRAFT_ENCRYPTION_KEY, então
cada teste seta uma chave via monkeypatch, como em test_invoice_security.py.
"""
from datetime import date

import pytest
from cryptography.fernet import Fernet

from app.database import execute, execute_returning, fetch_one
from app.invoice_match_drafts import (
    InvoiceDraftNotAllowed,
    cancel_draft,
    confirm_and_send,
    get_draft,
    get_form_for_issuer,
    get_preview,
    request_invoice,
    save_issuer_form,
)

from tests.test_security import register_test_user

VALID_FORM = {
    "number": "2026-0099", "issue_date": "2026-09-18", "service_date": "2026-09-10",
    "issuer_name": "Ada Sängerin", "issuer_address": "Musterweg 1\n80331 München",
    "issuer_tax_id": "12/345/67890", "recipient_name": "Chor Beispiel",
    "recipient_address": "Platz 2\n10115 Berlin", "service_description": "Solo im Konzert",
    "net_amount": "120.00", "currency": "EUR", "tax_rate": "0", "tax_note": "Kleinunternehmer",
    "payment_terms": "", "iban": "", "bic": "", "expense_travel_amount": "0", "expense_lodging_amount": "0",
}


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch):
    monkeypatch.setenv("INVOICE_DRAFT_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))


def _make_match(client, event_date, status="confirmed"):
    artist_id, artist_email, _ = register_test_user(client, full_name="Invoice Issuer")
    contractor_id, contractor_email, _ = register_test_user(client, full_name="Invoice Contractor")
    listing = execute_returning(
        """
        INSERT INTO listings (author_id, listing_type, title, description, city, country, event_date)
        VALUES (:author_id, 'seeking_singer', 'P4 invoice test', 'A valid listing description.', 'München', 'DE', :event_date)
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


def test_request_creates_a_placeholder_only_once(client):
    match_id, artist_id, contractor_id = _make_match(client, date.today())

    assert request_invoice(match_id, contractor_id, artist_id, contractor_id, date.today()) == "created"
    assert request_invoice(match_id, contractor_id, artist_id, contractor_id, date.today()) == "already_open"

    draft = get_draft(match_id)
    assert draft["status"] == "awaiting_issuer"
    assert draft["issuer_user_id"] == artist_id


def test_request_outside_seven_day_window_is_rejected(client):
    match_id, artist_id, contractor_id = _make_match(client, date(2026, 1, 1))
    with pytest.raises(InvoiceDraftNotAllowed):
        request_invoice(match_id, contractor_id, artist_id, contractor_id, date(2026, 1, 1), today=date(2026, 2, 1))


def test_cancelled_match_status_still_lets_service_layer_be_asked_but_route_gates_it(client):
    # The service layer itself only checks the 7-day window — it's the
    # route's job to also check match.status != 'cancelled' (mirrors
    # can_evaluate()'s split in app/match_evaluations.py). Documented here
    # so a future change doesn't silently drop that route-level check.
    match_id, artist_id, contractor_id = _make_match(client, date.today(), status="cancelled")
    assert request_invoice(match_id, contractor_id, artist_id, contractor_id, date.today()) == "created"


def test_issuer_fills_form_and_contractor_can_preview(client):
    match_id, artist_id, contractor_id = _make_match(client, date.today())

    save_issuer_form(match_id, artist_id, contractor_id, VALID_FORM, date.today())

    draft = get_draft(match_id)
    assert draft["status"] == "awaiting_contractor"

    preview_for_contractor = get_preview(match_id, contractor_id)
    assert preview_for_contractor["number"] == "2026-0099"
    assert preview_for_contractor["net_amount"] == "120.00"

    # The issuer can re-open their own form to edit it.
    form = get_form_for_issuer(match_id, artist_id)
    assert form["issuer_name"] == "Ada Sängerin"


def test_only_the_issuer_can_fill_the_form(client):
    match_id, artist_id, contractor_id = _make_match(client, date.today())
    save_issuer_form(match_id, artist_id, contractor_id, VALID_FORM, date.today())

    with pytest.raises(InvoiceDraftNotAllowed):
        save_issuer_form(match_id, contractor_id, contractor_id, VALID_FORM, date.today())


def test_confirm_requires_the_contractor(client):
    match_id, artist_id, contractor_id = _make_match(client, date.today())
    save_issuer_form(match_id, artist_id, contractor_id, VALID_FORM, date.today())

    with pytest.raises(InvoiceDraftNotAllowed):
        confirm_and_send(
            match_id, artist_id, date.today(),
            issuer_email="issuer@example.com", issuer_name="Ada", issuer_lang="de",
            contractor_email="contractor@example.com", contractor_name="Chor", contractor_lang="de",
            production_title="P4 invoice test",
        )


def test_confirm_sends_pdf_and_deletes_the_draft_zero_storage(client):
    match_id, artist_id, contractor_id = _make_match(client, date.today())
    save_issuer_form(match_id, artist_id, contractor_id, VALID_FORM, date.today())

    confirm_and_send(
        match_id, contractor_id, date.today(),
        issuer_email="issuer@example.com", issuer_name="Ada", issuer_lang="de",
        contractor_email="contractor@example.com", contractor_name="Chor", contractor_lang="de",
        production_title="P4 invoice test",
    )

    assert get_draft(match_id) is None
    row = fetch_one(
        "SELECT count(*) AS n FROM invoice_match_drafts WHERE match_id = :m",
        {"m": match_id},
    )
    assert row["n"] == 0  # not just "closed" — the row itself is gone.

    match = fetch_one("SELECT invoice_sent_at FROM job_matches WHERE id = :id", {"id": match_id})
    assert match["invoice_sent_at"] is not None

    number = fetch_one(
        "SELECT last_number FROM invoice_number_sequences WHERE user_id = :id AND invoice_year = 2026",
        {"id": artist_id},
    )
    assert number["last_number"] == 99


def test_cancel_draft_removes_it_for_either_participant(client):
    match_id, artist_id, contractor_id = _make_match(client, date.today())
    save_issuer_form(match_id, artist_id, contractor_id, VALID_FORM, date.today())

    cancel_draft(match_id, contractor_id)

    assert get_draft(match_id) is None

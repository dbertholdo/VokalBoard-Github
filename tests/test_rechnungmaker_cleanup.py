"""Rechnungmaker cleanup (2026-09-27): server-side tax preset (the CSP-blocked
inline handler made every invoice DE standard VAT), translated form, header-safe
file name, stateless error echo, closed Matches, no-store pages."""
from datetime import date

import pytest
from cryptography.fernet import Fernet

from app.database import execute, fetch_one
from app.invoice_match_drafts import get_form_for_issuer, save_issuer_form
from app.invoice_tax_presets import parse_tax_preset
from app.routers import invoice_routes
from tests.test_invoice_match_drafts import VALID_FORM, _make_match
from tests.test_security import DEFAULT_PASSWORD, extract_csrf, login, register_test_user


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch):
    monkeypatch.setenv("INVOICE_DRAFT_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))


def _avulso(client, **over):
    token = extract_csrf(client.get("/rechnungmaker?tab=avulso").text)
    data = {"csrf_token": token, "number": "2026-7", "issue_date": "2026-09-27", "service_date": "2026-09-20",
            "issuer_name": "Ada Sängerin", "issuer_address": "Musterweg 1, München", "issuer_tax_id": "12/345/678",
            "recipient_name": "Chor Beispiel", "recipient_address": "Platz 2, Berlin", "service_description": "Solo",
            "net_amount": "100", "currency": "EUR", "tax_preset": "DE:kleinunternehmer"}
    data.update(over)
    return client.post("/rechnungen/pdf", data=data, follow_redirects=False)


def _verified_member(client):
    uid, _, _ = register_test_user(client)
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": uid})
    return uid


def test_parse_tax_preset():
    assert parse_tax_preset("CH:kleinunternehmer") == ("CH", "kleinunternehmer", "CH:kleinunternehmer")
    assert parse_tax_preset("XX:evil") == ("DE", "standard", "DE:standard")


def test_kleinunternehmer_choice_reaches_the_pdf(client, monkeypatch):
    _verified_member(client)
    seen = {}
    monkeypatch.setattr(invoice_routes, "render_invoice_pdf", lambda doc: seen.setdefault("doc", doc) and b"%PDF-1.4")
    r = _avulso(client)
    assert r.status_code == 200
    assert str(seen["doc"].tax_rate) in ("0", "0.00", "0.0")


def test_download_name_is_header_safe(client, monkeypatch):
    _verified_member(client)
    monkeypatch.setattr(invoice_routes, "render_invoice_pdf", lambda doc: b"%PDF-1.4")
    r = _avulso(client, number='Nr. 5/ü "x"')
    assert r.status_code == 200
    assert r.headers["content-disposition"] == 'attachment; filename="Rechnung-Nr.-5-x.pdf"'
    assert "no-store" in r.headers["cache-control"]


def test_invalid_form_comes_back_filled_in_and_translated(client):
    _verified_member(client)
    r = _avulso(client, net_amount="abc")
    assert r.status_code == 400
    assert 'value="Ada Sängerin"' in r.text and 'value="DE:kleinunternehmer" selected' in r.text
    assert "Seu nome" not in r.text and "onchange=" not in r.text


def test_closed_match_blocks_invoice_work_and_pages_are_not_cached(client):
    match_id, artist_id, contractor_id = _make_match(client, date.today(), status="cancelled")
    execute("UPDATE users SET email_verified = TRUE WHERE id IN (:a, :c)", {"a": artist_id, "c": contractor_id})
    token = extract_csrf(client.get("/rechnungmaker").text)
    r = client.post(f"/profile/matches/{match_id}/invoice/request", data={"csrf_token": token}, follow_redirects=False)
    assert "invoice_error=1" in r.headers["location"]
    assert fetch_one("SELECT 1 FROM invoice_match_drafts WHERE match_id = :m", {"m": match_id}) is None

    live_id, artist2, contractor2 = _make_match(client, date.today())
    execute("UPDATE users SET email_verified = TRUE WHERE id IN (:a, :c)", {"a": artist2, "c": contractor2})
    save_issuer_form(live_id, artist2, contractor2, {**VALID_FORM, "tax_preset": "AT:cultural"}, date.today())
    assert get_form_for_issuer(live_id, artist2)["tax_preset"] == "AT:cultural"
    client.cookies.clear()
    login(client, fetch_one("SELECT email FROM users WHERE id = :id", {"id": artist2})["email"], DEFAULT_PASSWORD)
    form_page = client.get(f"/profile/matches/{live_id}/invoice")
    assert "no-store" in form_page.headers["cache-control"]
    assert 'value="AT:cultural" selected' in form_page.text
    assert "no-store" in client.get(f"/profile/matches/{live_id}/invoice/preview").headers["cache-control"]

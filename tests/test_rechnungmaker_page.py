"""P4 Etapa 3 (18/09/2026): página única /rechnungmaker com 2 abas
(Match-Rechnungen / Gerador Avulso), badge de pendência ("ambos": pedido
novo + rascunho aguardando ação) e contador pessoal privado.
"""
from datetime import date

import pytest
from cryptography.fernet import Fernet

from app.database import execute
from app.invoice_match_drafts import count_pending_actions, list_invoice_matches_for_user, save_issuer_form

from tests.test_invoice_match_drafts import VALID_FORM, _make_match
from tests.test_security import register_test_user


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch):
    monkeypatch.setenv("INVOICE_DRAFT_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))


def test_pending_actions_counts_both_new_request_and_awaiting_action(client):
    match_id, artist_id, contractor_id = _make_match(client, date.today())

    # Nobody has anything pending yet.
    assert count_pending_actions(artist_id) == 0
    assert count_pending_actions(contractor_id) == 0

    # Contractor "pede" -> vira 'awaiting_issuer' — pro emissor (artist)
    # isso já é AO MESMO TEMPO "pedido novo" e "está na minha mão".
    from app.invoice_match_drafts import request_invoice
    request_invoice(match_id, contractor_id, artist_id, contractor_id, date.today())
    assert count_pending_actions(artist_id) == 1
    assert count_pending_actions(contractor_id) == 0

    # Issuer preenche -> vira 'awaiting_contractor' — agora é a vez do
    # contratante, não mais do emissor.
    save_issuer_form(match_id, artist_id, contractor_id, VALID_FORM, date.today())
    assert count_pending_actions(artist_id) == 0
    assert count_pending_actions(contractor_id) == 1


def test_list_invoice_matches_excludes_matches_with_nothing_to_show(client):
    # A far-past event with no draft: window has long closed, nothing to
    # request, nothing sent — this Match shouldn't clutter the list.
    match_id, artist_id, contractor_id = _make_match(client, date(2020, 1, 1))
    assert list_invoice_matches_for_user(artist_id, today=date(2026, 9, 18)) == []


def test_list_invoice_matches_includes_requestable_and_open_draft_matches(client):
    requestable_id, artist_id, contractor_id = _make_match(client, date.today())
    rows = list_invoice_matches_for_user(artist_id, today=date.today())
    assert len(rows) == 1
    assert rows[0]["match_id"] == requestable_id
    assert rows[0]["can_request_invoice"] is True
    assert rows[0]["draft_status"] is None
    assert rows[0]["is_issuer"] is True

    save_issuer_form(requestable_id, artist_id, contractor_id, VALID_FORM, date.today())
    rows = list_invoice_matches_for_user(artist_id, today=date.today())
    assert rows[0]["draft_status"] == "awaiting_contractor"
    assert rows[0]["can_request_invoice"] is False  # a draft already exists, no longer "requestable"


# --- Full HTTP route -------------------------------------------------------
# register_test_user() already leaves the client logged in (session
# cookie set by /register) — but /rechnungmaker requires a VERIFIED
# email (see invoice_routes.py:_member), so tests mark it verified
# directly, same pattern used throughout tests/test_security.py.

def test_rechnungmaker_route_renders_both_tabs_and_defaults_to_match(client):
    user_id, email, password = register_test_user(client)
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})

    default = client.get("/rechnungmaker", follow_redirects=False)
    assert default.status_code == 200
    assert "rechnungmaker_tab_match" not in default.text  # i18n key actually resolved, not leaked raw

    avulso = client.get("/rechnungmaker?tab=avulso", follow_redirects=False)
    assert avulso.status_code == 200
    assert 'action="/rechnungen/pdf"' in avulso.text
    # To-do do P4 (18/09/2026): país+tributação vira um único <select>,
    # não mais radios separados de status por baixo do país.
    # 2026-09-27: the select itself is submitted (the old inline-onchange copy into
    # hidden fields was blocked by the CSP) — no inline handlers on the page.
    assert 'name="tax_preset"' in avulso.text
    assert 'onchange=' not in avulso.text
    assert 'type="radio" name="tax_status"' not in avulso.text
    assert 'Deutschland — Kleinunternehmer' in avulso.text


def test_legacy_rechnungen_url_redirects_to_rechnungmaker(client):
    user_id, email, password = register_test_user(client)
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})

    r = client.get("/rechnungen", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/rechnungmaker?tab=avulso"


def test_rechnungmaker_anonymous_redirects_to_login(client):
    r = client.get("/rechnungmaker", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"

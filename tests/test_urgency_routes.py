"""P5 Etapa 2 (18/09/2026): rotas HTTP do Sistema de Urgência — o
checkbox na criação, o botão "marcar depois" e o filtro/ordenação do
/board. Ver app/routers/listings_routes.py."""
from datetime import date, timedelta

from app.database import execute
from tests.test_security import extract_csrf, login, register_test_user, job_vacancy_fields


def _base_listing_data(csrf_token, is_urgent=False):
    data = {
        "csrf_token": csrf_token,
        "listing_type": "seeking_singer",
        "title": "Sectest Urgent Route Listing",
        "description": "Test description.",
        "state": "Bayern",
        "city": "München",
        "country": "DE",
        "repertoire": "Requiem",
        "venue": "",
        "ensemble_type": "",
        **job_vacancy_fields(),
        # seeking_singer/seeking_conductor exigem event_date válido
        # (ver create_listing() -> _valid_event_date()).
        "event_date": (date.today() + timedelta(days=10)).isoformat(),
    }
    if is_urgent:
        data["is_urgent"] = "1"
    return data


def test_checkbox_at_creation_marks_listing_urgent(client):
    user_id, email, password = register_test_user(client, full_name="Urgent Checkbox Test")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    login(client, email, password)

    r = client.get("/listings/new")
    token = extract_csrf(r.text)
    resp = client.post("/listings/new", data=_base_listing_data(token, is_urgent=True), follow_redirects=False)
    assert resp.status_code == 303

    my_listings = client.get("/my-listings")
    assert "listing-card-urgent" in my_listings.text


def test_mark_urgent_button_on_an_existing_listing(client):
    user_id, email, password = register_test_user(client, full_name="Urgent Button Test")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    login(client, email, password)

    r = client.get("/listings/new")
    token = extract_csrf(r.text)
    client.post("/listings/new", data=_base_listing_data(token), follow_redirects=False)

    my_listings = client.get("/my-listings")
    assert "listing-card-urgent" not in my_listings.text

    import re
    listing_id_match = re.search(r'/listings/(\d+)/mark-urgent', my_listings.text)
    assert listing_id_match, "botão 'marcar como urgente' não apareceu na página"
    listing_id = listing_id_match.group(1)

    token2 = extract_csrf(my_listings.text)
    resp = client.post(f"/listings/{listing_id}/mark-urgent", data={"csrf_token": token2}, follow_redirects=False)
    assert resp.status_code == 303
    assert "urgent_marked=1" in resp.headers["location"]

    my_listings_after = client.get("/my-listings")
    assert "listing-card-urgent" in my_listings_after.text


def test_board_urgent_filter_shows_only_urgent_listings(client):
    user_id, email, password = register_test_user(client, full_name="Urgent Board Filter Test")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    login(client, email, password)

    r = client.get("/listings/new")
    token = extract_csrf(r.text)
    client.post("/listings/new", data=_base_listing_data(token, is_urgent=True), follow_redirects=False)

    board_urgent = client.get("/board?urgent=1")
    assert "Sectest Urgent Route Listing" in board_urgent.text
    assert "badge-urgent" in board_urgent.text

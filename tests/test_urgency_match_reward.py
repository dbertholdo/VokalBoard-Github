"""P5 Etapa 2 (18/09/2026): recompensa de conclusão — 0,50 Nota pra
quem publicou uma vaga urgente, quando o Match acontece pela
plataforma. Ver app/match_service.py (respond_invitation)."""
from datetime import date, timedelta
from decimal import Decimal

from app.database import execute, execute_returning, fetch_one
from app.match_service import create_invitation, respond_invitation
from app.notas_wallet import get_credit_balance
from app.urgency import URGENCY_MATCH_REWARD_NOTAS, mark_listing_urgent
from tests.test_security import register_test_user


def _make_vacancy(contractor_id: int, event_date=None):
    event_date = event_date or (date.today() + timedelta(days=10))
    listing = execute_returning(
        """
        INSERT INTO listings (author_id, listing_type, title, description, city, state, country, event_date)
        VALUES (:author_id, 'seeking_singer', 'Sectest Reward Listing', 'A valid description.', 'München', 'Bayern', 'DE', :event_date)
        RETURNING id
        """,
        {"author_id": contractor_id, "event_date": event_date},
    )
    voice_type_id = fetch_one("SELECT id FROM voice_types ORDER BY id LIMIT 1")["id"]
    vacancy = execute_returning(
        "INSERT INTO listing_vacancies (listing_id, voice_type_id) VALUES (:listing_id, :voice_type_id) RETURNING id",
        {"listing_id": listing["id"], "voice_type_id": voice_type_id},
    )
    return listing["id"], vacancy["id"]


def _clear(user_id: int):
    execute("DELETE FROM credit_ledger WHERE user_id = :id", {"id": user_id})
    execute("DELETE FROM urgency_weekly_usage WHERE user_id = :id", {"id": user_id})


def test_urgent_listing_match_credits_half_a_nota_to_the_publisher(client):
    contractor_id, _, _ = register_test_user(client, full_name="Reward Contractor")
    # Only verified accounts can invite (app/match_service.py, 2026-09-27).
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": contractor_id})
    artist_id, _, _ = register_test_user(client, full_name="Reward Artist")
    _clear(contractor_id)

    listing_id, vacancy_id = _make_vacancy(contractor_id)
    mark_listing_urgent(contractor_id, listing_id)

    invite = create_invitation(vacancy_id, artist_id, contractor_id)
    assert invite["ok"] is True
    result = respond_invitation(invite["id"], artist_id, "accept")
    assert result["ok"] is True

    assert get_credit_balance(contractor_id) == URGENCY_MATCH_REWARD_NOTAS


def test_non_urgent_listing_match_does_not_credit_reward(client):
    contractor_id, _, _ = register_test_user(client, full_name="No Reward Contractor")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": contractor_id})
    artist_id, _, _ = register_test_user(client, full_name="No Reward Artist")
    _clear(contractor_id)

    listing_id, vacancy_id = _make_vacancy(contractor_id)
    # nunca marcada como urgente

    invite = create_invitation(vacancy_id, artist_id, contractor_id)
    result = respond_invitation(invite["id"], artist_id, "accept")
    assert result["ok"] is True

    assert get_credit_balance(contractor_id) == Decimal("0")

"""Atomic state transitions for applications, invitations and Matches."""
from datetime import timedelta
from sqlalchemy import text
from app.database import engine


def invitation_expiry(event_date):
    """48h, shortened only when the event is less than six hours away."""
    with engine.connect() as conn:
        return conn.execute(text("SELECT LEAST(now() + interval '48 hours', (:event_date::date - interval '6 hours'))"), {"event_date": event_date}).scalar_one()


def accept_invitation(invitation_id: int, artist_id: int) -> int | None:
    """Accept once; fill a vacancy atomically and create exactly one Match."""
    with engine.begin() as conn:
        invite = conn.execute(text("SELECT * FROM job_invitations WHERE id=:id AND artist_user_id=:artist AND status='pending' AND expires_at > now() FOR UPDATE"), {"id": invitation_id, "artist": artist_id}).mappings().first()
        if not invite:
            return None
        vacancy = conn.execute(text("UPDATE listing_vacancies SET filled_slots=filled_slots+1 WHERE id=:id AND filled_slots < total_slots RETURNING listing_id"), {"id": invite["vacancy_id"]}).mappings().first()
        if not vacancy:
            return None
        conn.execute(text("UPDATE job_invitations SET status='accepted', responded_at=now() WHERE id=:id"), {"id": invitation_id})
        match_id = conn.execute(text("INSERT INTO job_matches (listing_id,vacancy_id,artist_user_id,contractor_user_id,invitation_id) SELECT :listing_id,:vacancy_id,artist_user_id,initiated_by_user_id,:invitation_id FROM job_invitations WHERE id=:invitation_id RETURNING id"), {"listing_id": vacancy["listing_id"], "vacancy_id": invite["vacancy_id"], "invitation_id": invitation_id}).scalar_one()
        conn.execute(text("UPDATE listings l SET is_active=FALSE WHERE l.id=:listing_id AND NOT EXISTS (SELECT 1 FROM listing_vacancies v WHERE v.listing_id=l.id AND v.filled_slots < v.total_slots)"), {"listing_id": vacancy["listing_id"]})
        return match_id

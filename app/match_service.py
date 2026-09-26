"""Atomic state transitions for applications, invitations and Matches.

P3.B: the same job_invitations row represents both directions of the
hiring flow, distinguished by who STARTED it:
  - a "convite" (invitation): initiated_by_user_id = the contractor
    (the listing's author). The ARTIST accepts/declines.
  - a "candidatura" (spontaneous application): initiated_by_user_id =
    artist_user_id itself. The CONTRACTOR accepts/declines.
Either way, whoever did NOT start it is the one who must respond —
see respond_invitation() below, the single entry point for both.
"""
from sqlalchemy import text
from app.database import engine
from app.notas_wallet import credit_in_tx
from app.urgency import URGENCY_MATCH_REWARD_NOTAS

MAX_PENDING_INVITATIONS_PER_ARTIST = 30


def invitation_expiry(event_date):
    """48h, shortened only when the event is less than six hours away."""
    with engine.connect() as conn:
        return conn.execute(text("SELECT LEAST(now() + interval '48 hours', (CAST(:event_date AS date) - interval '6 hours'))"), {"event_date": event_date}).scalar_one()


def create_invitation(vacancy_id: int, artist_user_id: int, initiated_by_user_id: int) -> dict:
    """
    Creates a job_invitations row — a convite when initiated_by_user_id
    is the contractor, a candidatura when it's the artist themselves.
    Returns {"ok": True, "id": ...} or {"ok": False, "reason": "..."}
    (reason is an i18n key, see app/routers/invitations_routes.py).
    """
    with engine.begin() as conn:
        vacancy = conn.execute(
            text(
                """
                SELECT lv.id, lv.total_slots, lv.filled_slots, l.id AS listing_id,
                       l.author_id, l.is_active, l.event_date, l.listing_type
                FROM listing_vacancies lv
                JOIN listings l ON l.id = lv.listing_id
                WHERE lv.id = :vacancy_id
                """
            ),
            {"vacancy_id": vacancy_id},
        ).mappings().first()
        # FIX (19/09/2026, Daniel: maestro também precisa de convite/
        # candidatura/Match) — was hardcoded to "seeking_singer" only;
        # now any job-type vacancy works, including a conductor's
        # single implicit one (voice_type_id NULL, see app/vacancies.py).
        if not vacancy or vacancy["listing_type"] not in ("seeking_singer", "seeking_conductor") or not vacancy["is_active"]:
            return {"ok": False, "reason": "invitation_error_vacancy_closed"}
        if vacancy["filled_slots"] >= vacancy["total_slots"]:
            return {"ok": False, "reason": "invitation_error_vacancy_full"}
        if artist_user_id == vacancy["author_id"]:
            return {"ok": False, "reason": "invitation_error_own_listing"}
        if initiated_by_user_id not in (artist_user_id, vacancy["author_id"]):
            # Only the artist themselves (candidatura) or the listing's
            # own author (convite) may ever start a row for this vacancy.
            return {"ok": False, "reason": "invitation_error_not_allowed"}

        existing = conn.execute(
            text("SELECT id FROM job_invitations WHERE vacancy_id=:vacancy_id AND artist_user_id=:artist_id AND status='pending'"),
            {"vacancy_id": vacancy_id, "artist_id": artist_user_id},
        ).first()
        if existing:
            return {"ok": False, "reason": "invitation_error_already_pending"}

        pending_count = conn.execute(
            text("SELECT count(*) FROM job_invitations WHERE artist_user_id=:artist_id AND status='pending'"),
            {"artist_id": artist_user_id},
        ).scalar_one()
        if pending_count >= MAX_PENDING_INVITATIONS_PER_ARTIST:
            return {"ok": False, "reason": "invitation_error_too_many_pending"}

        expires_at = conn.execute(
            text("SELECT LEAST(now() + interval '48 hours', (CAST(:event_date AS date) - interval '6 hours'))"),
            {"event_date": vacancy["event_date"]},
        ).scalar_one()

        invitation_id = conn.execute(
            text(
                """
                INSERT INTO job_invitations (vacancy_id, artist_user_id, initiated_by_user_id, expires_at)
                VALUES (:vacancy_id, :artist_id, :initiated_by, :expires_at)
                RETURNING id
                """
            ),
            {
                "vacancy_id": vacancy_id,
                "artist_id": artist_user_id,
                "initiated_by": initiated_by_user_id,
                "expires_at": expires_at,
            },
        ).scalar_one()
        return {"ok": True, "id": invitation_id, "listing_id": vacancy["listing_id"]}


def respond_invitation(invitation_id: int, acting_user_id: int, action: str) -> dict:
    """
    Accept or decline a pending invitation/candidatura. Only the
    counterparty (whoever did NOT initiate it) may respond — see the
    module docstring. Accepting fills a vacancy atomically (first to
    accept wins under concurrency) and creates exactly one Match;
    declining just closes the row.
    """
    if action not in ("accept", "decline"):
        raise ValueError("action must be 'accept' or 'decline'")

    with engine.begin() as conn:
        invite = conn.execute(
            text(
                """
                SELECT ji.*, lv.listing_id, l.author_id AS contractor_user_id, l.is_urgent
                FROM job_invitations ji
                JOIN listing_vacancies lv ON lv.id = ji.vacancy_id
                JOIN listings l ON l.id = lv.listing_id
                WHERE ji.id = :id AND ji.status = 'pending' AND ji.expires_at > now()
                FOR UPDATE OF ji
                """
            ),
            {"id": invitation_id},
        ).mappings().first()
        if not invite:
            return {"ok": False, "reason": "invitation_error_not_found"}

        # Whoever did NOT start this row is the one allowed to respond
        # to it — a candidatura (artist-initiated) is accepted/declined
        # by the contractor; a convite (contractor-initiated) is
        # accepted/declined by the artist.
        is_convite = invite["initiated_by_user_id"] == invite["contractor_user_id"]
        expected_responder_id = invite["artist_user_id"] if is_convite else invite["contractor_user_id"]
        if acting_user_id != expected_responder_id:
            return {"ok": False, "reason": "invitation_error_not_yours"}

        if action == "decline":
            conn.execute(
                text("UPDATE job_invitations SET status='declined', responded_at=now() WHERE id=:id"),
                {"id": invitation_id},
            )
            return {"ok": True, "match_id": None}

        vacancy = conn.execute(
            text("UPDATE listing_vacancies SET filled_slots=filled_slots+1 WHERE id=:id AND filled_slots < total_slots RETURNING listing_id, filled_slots, total_slots"),
            {"id": invite["vacancy_id"]},
        ).mappings().first()
        if not vacancy:
            # Someone else got there first — the vacancy filled up
            # between the check above and this UPDATE. Politely close
            # this invitation instead of leaving it dangling.
            conn.execute(
                text("UPDATE job_invitations SET status='declined', responded_at=now() WHERE id=:id"),
                {"id": invitation_id},
            )
            return {"ok": False, "reason": "invitation_error_vacancy_full"}

        conn.execute(
            text("UPDATE job_invitations SET status='accepted', responded_at=now() WHERE id=:id"),
            {"id": invitation_id},
        )
        match_id = conn.execute(
            text(
                """
                INSERT INTO job_matches (listing_id, vacancy_id, artist_user_id, contractor_user_id, invitation_id)
                VALUES (:listing_id, :vacancy_id, :artist_user_id, :contractor_user_id, :invitation_id)
                RETURNING id
                """
            ),
            {
                "listing_id": vacancy["listing_id"],
                "vacancy_id": invite["vacancy_id"],
                "artist_user_id": invite["artist_user_id"],
                "contractor_user_id": invite["contractor_user_id"],
                "invitation_id": invitation_id,
            },
        ).scalar_one()
        conn.execute(
            text("UPDATE listings l SET is_active=FALSE WHERE l.id=:listing_id AND NOT EXISTS (SELECT 1 FROM listing_vacancies v WHERE v.listing_id=l.id AND v.filled_slots < v.total_slots)"),
            {"listing_id": vacancy["listing_id"]},
        )

        # P5 Etapa 2 (18/09/2026): recompensa de conclusão de vaga
        # urgente — 0,50 Nota (metade do "preço cheio" de 1 Nota) pra
        # quem publicou, quando o Match acontece pela plataforma.
        # Fica NESTA transação (não numa chamada separada a
        # credit_notas() depois) de propósito: a recompensa só deve
        # existir SE o Match existir — as duas coisas sobem ou descem
        # juntas. idempotency_key pelo match_id garante que isso nunca
        # duplica, mesmo que respond_invitation() seja chamada de novo
        # por algum retry.
        if invite["is_urgent"]:
            # Notas v2: an earned lot (expires after 18 months), via the wallet.
            credit_in_tx(
                conn, invite["contractor_user_id"], URGENCY_MATCH_REWARD_NOTAS, "urgency_match_reward",
                reference_id=match_id, idempotency_key=f"urgency_match_reward:{match_id}",
            )

        # P3.D: a vacancy can have more than one slot (e.g. "3 Sopranos"),
        # so filling ONE slot doesn't mean the other pending invitations/
        # candidaturas for this same vacancy are stale — they're still
        # valid for the remaining slots. Only once EVERY slot is filled do
        # we close out whatever is still pending and tell those people the
        # vacancy is gone (vacancy_filled_email, wired up by the router).
        filled_other_ids = []
        if vacancy["filled_slots"] >= vacancy["total_slots"]:
            filled_other_ids = conn.execute(
                text(
                    """
                    UPDATE job_invitations
                    SET status='expired', responded_at=now()
                    WHERE vacancy_id=:vacancy_id AND status='pending' AND id <> :this_id
                    RETURNING id
                    """
                ),
                {"vacancy_id": invite["vacancy_id"], "this_id": invitation_id},
            ).scalars().all()

        return {"ok": True, "match_id": match_id, "filled_other_ids": list(filled_other_ids)}

-- P3.B — candidatura espontânea + convite pelo diretório both write to
-- job_invitations, differentiated by initiated_by_user_id: when it equals
-- artist_user_id, the ARTIST started it (a candidatura) and the
-- contractor (the listing's author) is the one who must accept/decline;
-- when it's someone else, that someone is the contractor inviting the
-- artist, who then accepts/declines. The original CHECK forbade the
-- self-initiated case entirely — drop it, app logic (app/match_service.py)
-- now owns this rule.
ALTER TABLE job_invitations DROP CONSTRAINT IF EXISTS job_invitations_check;

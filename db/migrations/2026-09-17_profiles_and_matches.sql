-- P2/P3 foundation: a singer can have more than one voice type and a listing
-- can contain several voice-specific vacancies. Existing single-voice listings
-- and profiles remain valid while the UI is migrated incrementally.

CREATE TABLE IF NOT EXISTS singer_profile_voice_types (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    voice_type_id BIGINT NOT NULL REFERENCES voice_types(id) ON DELETE RESTRICT,
    PRIMARY KEY (user_id, voice_type_id)
);

INSERT INTO singer_profile_voice_types (user_id, voice_type_id)
SELECT user_id, voice_type_id
FROM singer_profiles
WHERE voice_type_id IS NOT NULL
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS listing_vacancies (
    id BIGSERIAL PRIMARY KEY,
    listing_id BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    voice_type_id BIGINT NOT NULL REFERENCES voice_types(id) ON DELETE RESTRICT,
    fee VARCHAR(100),
    total_slots SMALLINT NOT NULL DEFAULT 1 CHECK (total_slots > 0),
    filled_slots SMALLINT NOT NULL DEFAULT 0 CHECK (filled_slots >= 0 AND filled_slots <= total_slots),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (listing_id, voice_type_id)
);

INSERT INTO listing_vacancies (listing_id, voice_type_id)
SELECT id, voice_type_id
FROM listings
WHERE listing_type = 'seeking_singer' AND voice_type_id IS NOT NULL
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS job_invitations (
    id BIGSERIAL PRIMARY KEY,
    vacancy_id BIGINT NOT NULL REFERENCES listing_vacancies(id) ON DELETE CASCADE,
    artist_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    initiated_by_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(16) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'declined', 'expired')),
    expires_at TIMESTAMPTZ NOT NULL,
    responded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (artist_user_id <> initiated_by_user_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_pending_job_invitation
ON job_invitations (vacancy_id, artist_user_id)
WHERE status = 'pending';

CREATE TABLE IF NOT EXISTS job_matches (
    id BIGSERIAL PRIMARY KEY,
    listing_id BIGINT NOT NULL REFERENCES listings(id) ON DELETE RESTRICT,
    vacancy_id BIGINT NOT NULL REFERENCES listing_vacancies(id) ON DELETE RESTRICT,
    artist_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    contractor_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    invitation_id BIGINT UNIQUE REFERENCES job_invitations(id) ON DELETE SET NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'completed', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    CHECK (artist_user_id <> contractor_user_id)
);

CREATE INDEX IF NOT EXISTS idx_job_invitations_artist_pending
ON job_invitations (artist_user_id, status, expires_at);
CREATE INDEX IF NOT EXISTS idx_job_matches_user
ON job_matches (artist_user_id, contractor_user_id, status);

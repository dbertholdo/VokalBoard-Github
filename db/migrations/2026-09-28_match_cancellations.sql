-- Cancel a confirmed Match (2026-09-28, HANDOFF 5b — Daniel's rules):
-- either side, until 7 days before the event, reason >= 50 characters;
-- admins review each cancellation and may warn; 3 warnings = 30 days
-- without new Matches. Idempotent, no $$ — apply with psql. Until applied
-- the cancel option simply doesn't appear (app/match_cancellation.py).

CREATE TABLE IF NOT EXISTS match_cancellations (
    id              BIGSERIAL PRIMARY KEY,
    match_id        BIGINT NOT NULL UNIQUE REFERENCES job_matches(id) ON DELETE CASCADE,
    cancelled_by    BIGINT REFERENCES users(id) ON DELETE SET NULL,
    other_user_id   BIGINT REFERENCES users(id) ON DELETE SET NULL,
    reason          TEXT NOT NULL CHECK (char_length(reason) >= 50),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at     TIMESTAMPTZ,
    reviewed_by     BIGINT REFERENCES users(id) ON DELETE SET NULL,
    outcome         VARCHAR(12) CHECK (outcome IN ('warned', 'dismissed'))
);
CREATE INDEX IF NOT EXISTS idx_match_cancellations_open ON match_cancellations (reviewed_at);

CREATE TABLE IF NOT EXISTS match_warnings (
    id               BIGSERIAL PRIMARY KEY,
    user_id          BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    cancellation_id  BIGINT REFERENCES match_cancellations(id) ON DELETE SET NULL,
    note             TEXT,
    issued_by        BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    counted_in_block BOOLEAN NOT NULL DEFAULT FALSE  -- TRUE once it helped trigger a 30-day block
);
CREATE INDEX IF NOT EXISTS idx_match_warnings_user ON match_warnings (user_id);

ALTER TABLE users ADD COLUMN IF NOT EXISTS matches_blocked_until TIMESTAMPTZ;

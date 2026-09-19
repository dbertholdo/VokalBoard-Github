-- P2 cluster (19/09/2026) — Profile Wizard + CV export + public-profile
-- solo/choir cards. Decided with Daniel via AskUserQuestion:
--   - Wizard: BOTH shown once automatically right after signup/first
--     login (if the profile is still incomplete) AND reachable anytime
--     on demand from the existing Atento mascot nudge. Not a replacement
--     of /profile, which keeps working exactly as before.
--   - Export: PDF CV only for now (the business-card/QR half of the
--     original spec item was not picked — left undone, see
--     AI_CHANGELOG.md).
--   - Solo/choir cards: a brand-new "works" table, separate from
--     listings.repertoire (a job-posting field, not a singer's own
--     portfolio) and from singer_audio_links (a bare untagged URL list).
--   - Directory Fach-filter: Daniel said to drop it from this cluster
--     entirely ("Delete this from the list.") — no schema change here.
--
-- Per AGENTS.md's standing migration freeze (18/09/2026): this file is
-- prepared, NOT applied to the Railway production database. Idempotent
-- (IF NOT EXISTS throughout) so it's safe whenever it does get applied.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS profile_wizard_seen_at TIMESTAMPTZ NULL;
-- Gates ONLY the one-time automatic redirect to /profile/wizard right
-- after signup (see app/routers/listings_routes.py's home()); the
-- wizard itself stays reachable manually at any time regardless of
-- this column. NULL = never auto-shown yet.

-- ------------------------------------------------------------
-- "Works" (repertoire items) a singer wants to showcase on their
-- public profile, split into solo vs. choir cards per the P2 spec.
-- Deliberately NOT reusing singer_audio_links (which has no title,
-- composer or solo/choir tag) or listings.repertoire (which describes
-- a job posting, not a person's own portfolio).
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS singer_works (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title        VARCHAR(150) NOT NULL,
    composer     VARCHAR(150),
    category     VARCHAR(10) NOT NULL CHECK (category IN ('solo', 'choir')),
    video_url    VARCHAR(500),
    audio_url    VARCHAR(500),
    sort_order   SMALLINT NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_singer_works_user ON singer_works(user_id);

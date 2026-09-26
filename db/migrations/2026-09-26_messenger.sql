-- ============================================================
-- Messenger (2026-09-26) — spec: docs/specs/MESSENGER.md (M1).
-- One conversation per pair of users; message requests; "had contact"
-- pairs; message reports; 60-day expiry per conversation (was ~30+60).
--
-- Apply ONLY with psql (dollar-quoted function — see docs/MIGRATIONS.md):
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/2026-09-26_messenger.sql
-- Safe to re-run: every step is guarded.
-- ============================================================
BEGIN;

CREATE TABLE IF NOT EXISTS conversations (
    id                BIGSERIAL PRIMARY KEY,
    user_low_id       BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_high_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- 'request' = first contact not yet accepted (lands in the recipient's
    -- Requests folder); 'active' = normal chat.
    status            VARCHAR(10) NOT NULL DEFAULT 'active' CHECK (status IN ('request', 'active')),
    requested_by      BIGINT REFERENCES users(id) ON DELETE CASCADE,
    declined_at       TIMESTAMPTZ,   -- recipient declined the request (sender is never told)
    low_hidden_at     TIMESTAMPTZ,   -- per-side "hide conversation"; cleared by any new message
    high_hidden_at    TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_activity_at  TIMESTAMPTZ NOT NULL DEFAULT now(),  -- 60-day expiry clock
    CHECK (user_low_id < user_high_id),
    UNIQUE (user_low_id, user_high_id)
);
CREATE INDEX IF NOT EXISTS idx_conversations_activity ON conversations(last_activity_at);
CREATE INDEX IF NOT EXISTS idx_conversations_high ON conversations(user_high_id);

-- "These two have had contact" — outlives deleted chats, so they never need
-- a request again. Erased with either account. Matches are checked live
-- against job_matches, not copied here.
CREATE TABLE IF NOT EXISTS contact_pairs (
    user_low_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_high_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    established_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    source          VARCHAR(10) NOT NULL CHECK (source IN ('accepted', 'legacy')),
    PRIMARY KEY (user_low_id, user_high_id),
    CHECK (user_low_id < user_high_id)
);

ALTER TABLE messages ADD COLUMN IF NOT EXISTS conversation_id BIGINT REFERENCES conversations(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, id);

-- Reports keep a snapshot of the text: the message itself may expire
-- (60 days) before moderation looks at it. Resolved reports are purged
-- 60 days after resolution by the retention worker.
CREATE TABLE IF NOT EXISTS message_reports (
    id                BIGSERIAL PRIMARY KEY,
    message_id        BIGINT REFERENCES messages(id) ON DELETE SET NULL,
    reporter_id       BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reported_user_id  BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason            VARCHAR(500) NOT NULL,
    body_snapshot     TEXT NOT NULL,
    status            VARCHAR(10) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'dismissed', 'removed')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at       TIMESTAMPTZ,
    resolved_by       BIGINT REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE (message_id, reporter_id)
);
CREATE INDEX IF NOT EXISTS idx_message_reports_open ON message_reports(created_at) WHERE status = 'open';

-- At most one "new messages" e-mail per recipient per day (M6).
ALTER TABLE users ADD COLUMN IF NOT EXISTS message_email_sent_at TIMESTAMPTZ;

-- Backfill: every still-visible message joins its pair's conversation.
-- Both sides have written → active + legacy contact pair; one-way → request.
-- Already-archived messages stay without a conversation and are purged by
-- the retention worker (they were hidden already).
INSERT INTO conversations (user_low_id, user_high_id, status, requested_by, created_at, last_activity_at)
SELECT lo, hi,
       CASE WHEN bool_or(sender_id = lo) AND bool_or(sender_id = hi) THEN 'active' ELSE 'request' END,
       CASE WHEN bool_or(sender_id = lo) AND bool_or(sender_id = hi) THEN NULL ELSE min(sender_id) END,
       min(created_at), max(created_at)
FROM (
    SELECT least(sender_id, recipient_id) AS lo, greatest(sender_id, recipient_id) AS hi, sender_id, created_at
    FROM messages WHERE archived_at IS NULL AND conversation_id IS NULL
) t
GROUP BY lo, hi
ON CONFLICT (user_low_id, user_high_id) DO NOTHING;

UPDATE messages m SET conversation_id = c.id
FROM conversations c
WHERE m.conversation_id IS NULL AND m.archived_at IS NULL
  AND c.user_low_id = least(m.sender_id, m.recipient_id)
  AND c.user_high_id = greatest(m.sender_id, m.recipient_id);

INSERT INTO contact_pairs (user_low_id, user_high_id, established_at, source)
SELECT user_low_id, user_high_id, created_at, 'legacy' FROM conversations WHERE status = 'active'
ON CONFLICT DO NOTHING;

-- Every inserted message belongs to its pair's conversation (created here
-- if the app didn't pass one — e.g. direct inserts), and an expired
-- conversation's old messages never come back (they're dropped first).
CREATE OR REPLACE FUNCTION message_activity() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    lo BIGINT := least(NEW.sender_id, NEW.recipient_id);
    hi BIGINT := greatest(NEW.sender_id, NEW.recipient_id);
BEGIN
    PERFORM pg_advisory_xact_lock((lo % 2147483647)::integer, (hi % 2147483647)::integer);
    IF NEW.conversation_id IS NULL THEN
        INSERT INTO conversations (user_low_id, user_high_id, status, created_at, last_activity_at)
        VALUES (lo, hi, 'active', NEW.created_at, NEW.created_at)
        ON CONFLICT (user_low_id, user_high_id) DO NOTHING;
        SELECT id INTO NEW.conversation_id FROM conversations WHERE user_low_id = lo AND user_high_id = hi;
    END IF;
    DELETE FROM messages
    WHERE conversation_id = NEW.conversation_id
      AND EXISTS (SELECT 1 FROM conversations c WHERE c.id = NEW.conversation_id
                  AND c.last_activity_at + interval '60 days' <= now());
    UPDATE conversations
    SET last_activity_at = GREATEST(last_activity_at, NEW.created_at), low_hidden_at = NULL, high_hidden_at = NULL
    WHERE id = NEW.conversation_id;
    NEW.activity_at := NEW.created_at;
    RETURN NEW;
END $$;

CREATE OR REPLACE VIEW visible_messages AS
 SELECT m.* FROM messages m JOIN conversations c ON c.id = m.conversation_id
 WHERE c.last_activity_at + interval '60 days' > now();

COMMIT;

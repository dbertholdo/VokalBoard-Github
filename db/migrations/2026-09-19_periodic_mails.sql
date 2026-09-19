-- Periodic mails (P0 backlog item: "define daily/weekly/monthly
-- reports") — Daniel's follow-up request (19/09/2026): a screen to
-- build, list, edit, pause and delete recurring admin emails. Each
-- mail's body is plain HTML, wrapped automatically by the existing
-- shared email layout (app/email_layout.py) — same envelope as every
-- other automatic email on the site, only the body is per-mail.
--
-- Recipients are fixed to the admin team (role_level >= 2) for this
-- delivery — see app/periodic_mails.py's module docstring for why
-- (deliberately NOT a general segmented-broadcast tool; that's the
-- "segmented email sending" item Daniel already deferred elsewhere,
-- blocked on a real Subscription system). recipient_scope is still a
-- column, not a hardcoded constant, so a second scope can be added
-- later without another migration.
CREATE TABLE IF NOT EXISTS periodic_mails (
    id                  BIGSERIAL PRIMARY KEY,
    name                VARCHAR(200) NOT NULL,
    subject             VARCHAR(300) NOT NULL,
    body_html           TEXT NOT NULL,
    frequency           VARCHAR(10) NOT NULL CHECK (frequency IN ('daily', 'weekly', 'monthly')),
    recipient_scope     VARCHAR(20) NOT NULL DEFAULT 'admins' CHECK (recipient_scope IN ('admins')),
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    last_sent_at        TIMESTAMPTZ,
    next_send_at        TIMESTAMPTZ NOT NULL,
    created_by_user_id  BIGINT REFERENCES users(id) ON DELETE SET NULL,
    updated_by_user_id  BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Worker query is "active mails due now" — partial index keeps it
-- cheap even once paused/old mails pile up.
CREATE INDEX IF NOT EXISTS idx_periodic_mails_due ON periodic_mails(next_send_at) WHERE is_active = TRUE;

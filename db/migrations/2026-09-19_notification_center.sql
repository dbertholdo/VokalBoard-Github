-- ============================================================
-- Central de Notificações (19/09/2026)
--
-- Designed together with Daniel via AskUserQuestion before coding —
-- see app/notification_center.py's module docstring and
-- AI_CHANGELOG.md for the full design conversation. A real list of
-- discrete, individually-readable events, additive on top of the
-- live pending-count nav badges already on the site (unread messages,
-- pending invitations/evaluations/invoice actions — app/render.py),
-- which are untouched by this migration.
--
-- Not destructive: only creates a new table + indexes. Safe to run
-- standalone or folded into a future consolidation alongside the
-- other pending migrations (see AGENTS.md's "migration freeze"
-- section — this is NOT applied to production yet, same as every
-- dated migration since 2026-09-15).
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS notifications (
    id            BIGSERIAL PRIMARY KEY,
    user_id       BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type          VARCHAR(40) NOT NULL,
    title_key     VARCHAR(80) NOT NULL,
    title_params  JSONB,
    link_url      VARCHAR(300),
    icon          VARCHAR(40) NOT NULL DEFAULT 'icon-bell',
    read_at       TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_created ON notifications(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_user_unread ON notifications(user_id) WHERE read_at IS NULL;

COMMIT;

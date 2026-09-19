-- P6 close-out (19/09/2026) — two of the three remaining P6 items,
-- scoped with Daniel via AskUserQuestion (the third, segmented email
-- sending, stays explicitly out of scope: it depends on a real
-- Subscription/payment gateway that doesn't exist in this codebase
-- yet — see PLANO_EXECUTIVO_ORGANIZADO.md and AI_CHANGELOG.md).
--
-- 1. Ad-hoc admin grant (God Mode only, /financeiro/conceder): an
--    Admin can credit/debit a specific user's Notas balance, or issue
--    a shop_catalog_items entry to them directly (bypassing
--    self-purchase), each with a mandatory free-text justification.
--    Reuses credit_ledger/app/notas_wallet.py for the actual
--    crediting/debiting — this new column just holds the admin's own
--    typed words, since `reason` itself stays a short machine label
--    ("admin_grant_credit" / "admin_grant_debit" / "redeem_<item_key>"
--    for a granted item), same shape as every other credit_ledger
--    reason in this codebase.
ALTER TABLE credit_ledger ADD COLUMN IF NOT EXISTS admin_note TEXT;

-- 2. "Fale conosco" (contact) + "Reportar erro" (bug report) — one
--    unified ticket inbox for both, distinguished by `type`, mirroring
--    the shape of listing_reports/moderation_actions (open ->
--    answered/resolved, resolved_by/resolved_at). A bug report
--    auto-captures page_url/page_name from the page the button was
--    clicked on (see app/templates/base.html); user_id is nullable
--    (SET NULL, never blocks account deletion) since a report can, in
--    principle, come off a page a logged-out visitor can still see.
--    `email` only matters for a logged-out submission (the contact
--    form itself requires login — see app/routers/support_routes.py)
--    so there's a way to reply.
CREATE TABLE IF NOT EXISTS support_tickets (
    id                   BIGSERIAL PRIMARY KEY,
    type                 VARCHAR(20) NOT NULL CHECK (type IN ('contact', 'bug_report')),
    user_id              BIGINT REFERENCES users(id) ON DELETE SET NULL,
    email                VARCHAR(255),
    subject              VARCHAR(200),
    description          TEXT NOT NULL CHECK (char_length(description) >= 10),
    page_url             TEXT,
    page_name            VARCHAR(200),
    status               VARCHAR(20) NOT NULL DEFAULT 'open'
                             CHECK (status IN ('open', 'answered', 'resolved')),
    admin_response       TEXT,
    resolved_by_user_id  BIGINT REFERENCES users(id) ON DELETE SET NULL,
    resolved_at          TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status);
CREATE INDEX IF NOT EXISTS idx_support_tickets_user ON support_tickets(user_id);

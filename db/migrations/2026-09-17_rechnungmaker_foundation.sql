-- Rechnungmaker: store only operational metadata. IBAN, BIC, tax ID,
-- residential address and invoice form contents must never be columns here.

CREATE TABLE IF NOT EXISTS invoice_number_sequences (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    invoice_year SMALLINT NOT NULL CHECK (invoice_year >= 2000),
    last_number INTEGER NOT NULL DEFAULT 0 CHECK (last_number >= 0),
    PRIMARY KEY (user_id, invoice_year)
);

-- Five free invoice generations per calendar month, per user. This resets
-- rather than carrying unused invoices forward.
CREATE TABLE IF NOT EXISTS invoice_monthly_usage (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    usage_month DATE NOT NULL CHECK (usage_month = date_trunc('month', usage_month)::date),
    free_used SMALLINT NOT NULL DEFAULT 0 CHECK (free_used BETWEEN 0 AND 5),
    PRIMARY KEY (user_id, usage_month)
);

-- Purchased credits are separate from the monthly allowance and never expire.
-- The future Notes purchase flow writes only delta/reason here, not financial
-- details from an invoice.
CREATE TABLE IF NOT EXISTS purchased_invoice_credits (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    delta SMALLINT NOT NULL CHECK (delta <> 0),
    reason VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_purchased_invoice_credits_user
ON purchased_invoice_credits (user_id, created_at DESC);

-- Match PDFs may exist privately for seven days. The table deliberately keeps
-- only a random filename, access relationship and expiry; no invoice content,
-- tax number, bank data or address is retained.
CREATE TABLE IF NOT EXISTS ephemeral_match_invoices (
    id BIGSERIAL PRIMARY KEY,
    match_id BIGINT NOT NULL REFERENCES job_matches(id) ON DELETE CASCADE,
    created_by_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    stored_filename VARCHAR(100) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ephemeral_match_invoices_expiry
ON ephemeral_match_invoices (expires_at);

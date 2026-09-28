-- Notas Store (2026-09-28, docs/specs/STORE.md). Idempotent, no $$ — apply
-- with psql. Until applied, /store shows only what the old catalogue had and
-- the new effects (frame, badges, pinning) are simply off (app/store.py).

-- Discounts per catalogue item ("−XX% off!" badge while active).
ALTER TABLE shop_catalog_items ADD COLUMN IF NOT EXISTS discount_percent SMALLINT
    CHECK (discount_percent IS NULL OR (discount_percent BETWEEN 1 AND 90));
ALTER TABLE shop_catalog_items ADD COLUMN IF NOT EXISTS discount_from TIMESTAMPTZ;   -- Daniel: start + end date
ALTER TABLE shop_catalog_items ADD COLUMN IF NOT EXISTS discount_until TIMESTAMPTZ;

-- Effects on the account.
ALTER TABLE users ADD COLUMN IF NOT EXISTS super_user_until TIMESTAMPTZ;   -- purple frame + label
ALTER TABLE users ADD COLUMN IF NOT EXISTS people_top_until TIMESTAMPTZ;   -- first in People search
ALTER TABLE users ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;        -- Verified badge (forever)
ALTER TABLE users ADD COLUMN IF NOT EXISTS supporter_since TIMESTAMPTZ;    -- Supporter badge (forever)

-- Featured listings: own table (listings are read through the visible_listings
-- view, which would not pick up a new listings column without being recreated).
CREATE TABLE IF NOT EXISTS featured_listings (
    listing_id     BIGINT PRIMARY KEY REFERENCES listings(id) ON DELETE CASCADE,
    featured_until TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_featured_listings_until ON featured_listings (featured_until);

-- Verified badge requests: a public proof link + note, reviewed by an admin.
-- Nothing else is stored (Zero-Storage). Rejected = the Notas are refunded.
CREATE TABLE IF NOT EXISTS verification_requests (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    proof_url    VARCHAR(500) NOT NULL,
    note         VARCHAR(1000),
    debit_id     BIGINT REFERENCES credit_ledger(id) ON DELETE SET NULL,
    status       VARCHAR(10) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at  TIMESTAMPTZ,
    reviewed_by  BIGINT REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_verification_requests_status ON verification_requests (status, created_at);

-- Products (Daniel's prices). Titles/descriptions come from app/i18n.py (NULL here).
INSERT INTO shop_catalog_items (item_key, cost, active, icon) VALUES
    ('super_user_1y', 5, TRUE, 'icon-crown'),
    ('featured_listing_30d', 2, TRUE, 'icon-star'),
    ('people_top_30d', 2, TRUE, 'icon-sparkle'),
    ('invoice_single', 0.50, TRUE, 'icon-scroll'),
    ('invoice_pack_5', 2, TRUE, 'icon-book'),
    ('verified_badge', 5, TRUE, 'icon-trophy'),
    ('supporter_badge', 5, TRUE, 'icon-gift'),
    ('urgent_listing', 1, TRUE, 'icon-tip'),
    ('subscription_1y', 15, TRUE, 'icon-card')
ON CONFLICT (item_key) DO NOTHING;

-- Super User replaces "Profile highlight 7 days" (switched off, not deleted;
-- running highlights keep running).
UPDATE shop_catalog_items SET active = FALSE, updated_at = now() WHERE item_key = 'profile_highlight_7d';

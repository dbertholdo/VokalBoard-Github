-- ============================================================
-- Notas v2 (2026-09-26) — purchased vs. earned credits, per-credit
-- expiry for earned Notas, lot usage. Spec: docs/specs/NOTAS_V2.md.
--
-- Apply ONLY with psql (dollar-quoted DO block — see docs/MIGRATIONS.md):
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/2026-09-26_notas_v2.sql
-- Safe to re-run: every step is guarded.
-- ============================================================
BEGIN;

-- category: set on every CREDIT (delta > 0). NULL on debits (a debit can
-- span both categories — credit_lot_usage records the exact split) and on
-- zero-delta rows (shop grants).
ALTER TABLE credit_ledger ADD COLUMN IF NOT EXISTS category VARCHAR(10);
-- expires_at: only on earned credits (created_at + 18 months).
ALTER TABLE credit_ledger ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

-- One-time backfill: purchases never existed before v2 (the buy page was a
-- stub), so every existing credit is EARNED. Its 18 months start at rollout,
-- not retroactively — nobody loses Notas on launch day.
UPDATE credit_ledger
SET category = 'earned', expires_at = now() + interval '18 months'
WHERE delta > 0 AND category IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'credit_ledger_category_valid') THEN
        ALTER TABLE credit_ledger ADD CONSTRAINT credit_ledger_category_valid
            CHECK (category IS NULL OR category IN ('purchased', 'earned'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'credit_ledger_credit_has_category') THEN
        ALTER TABLE credit_ledger ADD CONSTRAINT credit_ledger_credit_has_category
            CHECK (delta <= 0 OR category IS NOT NULL);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'credit_ledger_expiry_only_earned') THEN
        ALTER TABLE credit_ledger ADD CONSTRAINT credit_ledger_expiry_only_earned
            CHECK (expires_at IS NULL OR category = 'earned');
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_credit_ledger_earned_expiry
    ON credit_ledger (expires_at) WHERE category = 'earned';

-- Which credit "lots" each debit consumed. Needed for the spend order
-- (purchased first, then earned by expiry), for expiring only the unspent
-- remainder of an earned lot, and for category-correct refunds.
CREATE TABLE IF NOT EXISTS credit_lot_usage (
    id        BIGSERIAL PRIMARY KEY,
    debit_id  BIGINT NOT NULL REFERENCES credit_ledger(id) ON DELETE CASCADE,
    lot_id    BIGINT NOT NULL REFERENCES credit_ledger(id) ON DELETE CASCADE,
    amount    NUMERIC(10,2) NOT NULL CHECK (amount > 0)
);
CREATE INDEX IF NOT EXISTS idx_credit_lot_usage_lot ON credit_lot_usage(lot_id);
CREATE INDEX IF NOT EXISTS idx_credit_lot_usage_debit ON credit_lot_usage(debit_id);

-- Backfill: allocate every historical debit to that user's credits,
-- oldest first. A debit larger than all credits keeps an uncovered
-- remainder (a "debt"), which the app settles from the next credit.
DO $$
DECLARE
    d RECORD;
    lot RECORD;
    need NUMERIC(10,2);
    take NUMERIC(10,2);
BEGIN
    FOR d IN
        SELECT c.id, c.user_id, -c.delta AS amount
        FROM credit_ledger c
        WHERE c.delta < 0
          AND NOT EXISTS (SELECT 1 FROM credit_lot_usage u WHERE u.debit_id = c.id)
        ORDER BY c.created_at, c.id
    LOOP
        need := d.amount;
        FOR lot IN
            SELECT l.id,
                   l.delta - COALESCE((SELECT SUM(u.amount) FROM credit_lot_usage u WHERE u.lot_id = l.id), 0) AS remaining
            FROM credit_ledger l
            WHERE l.user_id = d.user_id AND l.delta > 0
            ORDER BY l.created_at, l.id
        LOOP
            EXIT WHEN need <= 0;
            CONTINUE WHEN lot.remaining <= 0;
            take := LEAST(need, lot.remaining);
            INSERT INTO credit_lot_usage (debit_id, lot_id, amount) VALUES (d.id, lot.id, take);
            need := need - take;
        END LOOP;
    END LOOP;
END $$;

COMMIT;

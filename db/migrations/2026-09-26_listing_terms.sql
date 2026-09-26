-- ============================================================
-- Match phase 2 / backlog #55 (2026-09-26) — one source for a listing's
-- voice type + fee (see app/listing_terms.py).
-- Job listings: listing_vacancies only (the copy on `listings` is cleared
-- and kept empty). Self-ads: their own `listings` columns.
--
-- Apply ONLY with psql (dollar-quoted block — see docs/MIGRATIONS.md):
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/2026-09-26_listing_terms.sql
-- Safe to re-run: every step is guarded.
-- ============================================================
BEGIN;

UPDATE listings
SET voice_type_id = NULL, fee_amount = NULL, fee_negotiable = FALSE
WHERE listing_type IN ('seeking_singer', 'seeking_conductor')
  AND (voice_type_id IS NOT NULL OR fee_amount IS NOT NULL OR fee_negotiable);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'listings_job_terms_live_in_vacancies') THEN
        ALTER TABLE listings ADD CONSTRAINT listings_job_terms_live_in_vacancies
            CHECK (listing_type NOT IN ('seeking_singer', 'seeking_conductor')
                   OR (voice_type_id IS NULL AND fee_amount IS NULL AND NOT fee_negotiable));
    END IF;
END $$;

CREATE OR REPLACE VIEW listing_terms AS
 SELECT lv.listing_id, lv.voice_type_id, lv.fee_amount, lv.fee_currency, lv.fee_negotiable
 FROM listing_vacancies lv
 JOIN listings l ON l.id = lv.listing_id AND l.listing_type IN ('seeking_singer', 'seeking_conductor')
 UNION ALL
 SELECT l.id, l.voice_type_id, l.fee_amount, l.fee_currency, l.fee_negotiable
 FROM listings l
 WHERE l.listing_type IN ('singer_available', 'conductor_available');

COMMIT;

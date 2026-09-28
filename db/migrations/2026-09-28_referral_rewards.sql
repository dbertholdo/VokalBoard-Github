-- Referral rewards v2 (2026-09-28, HANDOFF item 3): 1 Nota per successful
-- referral, paid only after real activity, with anti-fraud review.
-- Idempotent, no $$ blocks — apply with psql (never the Railway Query box).
-- The app tolerates this migration missing: until it runs, referrals keep
-- the old rule (1 Nota per 10 verified referrals).

ALTER TABLE users ADD COLUMN IF NOT EXISTS signup_ip_hash CHAR(64);

ALTER TABLE referral_events ADD COLUMN IF NOT EXISTS status VARCHAR(20);
ALTER TABLE referral_events ADD COLUMN IF NOT EXISTS flag_reason VARCHAR(40);
ALTER TABLE referral_events ADD COLUMN IF NOT EXISTS rewarded_at TIMESTAMPTZ;
ALTER TABLE referral_events ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;
ALTER TABLE referral_events ADD COLUMN IF NOT EXISTS reviewed_by BIGINT REFERENCES users(id) ON DELETE SET NULL;

-- Rows from the old rule were already paid in blocks of 10: never reward them again.
UPDATE referral_events SET status = 'legacy' WHERE status IS NULL;
ALTER TABLE referral_events ALTER COLUMN status SET DEFAULT 'pending';
ALTER TABLE referral_events ALTER COLUMN status SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_referral_events_status ON referral_events(status);
CREATE INDEX IF NOT EXISTS idx_referral_events_referred ON referral_events(referred_user_id);
CREATE INDEX IF NOT EXISTS idx_users_referrer_ip ON users(referred_by_user_id, signup_ip_hash);

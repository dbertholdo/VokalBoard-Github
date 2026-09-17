-- Phase 1: transactional e-mails need an account-level language preference.
-- Existing accounts intentionally get English as the documented fallback.
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(8) NOT NULL DEFAULT 'en';

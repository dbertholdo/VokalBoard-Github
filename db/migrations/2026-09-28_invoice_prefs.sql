-- Rechnungmaker v2 (2026-09-28): remember the last invoice country + invoice
-- language per account (not sensitive; address/tax ID/IBAN are never stored).
-- Idempotent, no $$ — apply with psql. Until applied, the form simply starts
-- from the profile country each time (app/invoice_form.py checks the columns).
ALTER TABLE users ADD COLUMN IF NOT EXISTS invoice_country VARCHAR(8);
ALTER TABLE users ADD COLUMN IF NOT EXISTS invoice_doc_lang VARCHAR(2);

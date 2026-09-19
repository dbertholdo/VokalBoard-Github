-- ============================================================
-- Unify voice-type/vaga entry into a single UI (19/09/2026)
--
-- Daniel: "Hoje temos duas formas de adicionar voz e eu quero que elas
-- se fundam em uma só... com duas formas de adicionar vagas, fica
-- confuso, inclusive para o código e db."
--
-- From now on, listing_vacancies is the ONLY place a seeking_singer/
-- seeking_conductor listing's voice type and fee are entered — the
-- standalone listings.voice_type_id/fee_amount/fee_currency/
-- fee_negotiable fields are still WRITTEN for these two listing_types
-- (kept in sync, derived from the vacancy rows — see
-- _derive_listing_fields_from_vacancies() in
-- app/routers/listings_routes.py) so every other query that still
-- reads those columns directly (home page matching, board filtering,
-- e-mail alerts, banner targeting, the "Buscar pessoas" directory)
-- keeps working unchanged. Also gives seeking_conductor listings
-- convite/candidatura/Match for the first time (previously hardcoded
-- to seeking_singer only in app/match_service.py) — a conductor
-- vacancy has voice_type_id = NULL, since conductors have no naipe.
--
-- Not destructive: relaxes one NOT NULL constraint and adds rows,
-- never removes or drops anything. Safe to run standalone or folded
-- into a future consolidation alongside the other pending migrations
-- (see AGENTS.md's "migration freeze" section — this is NOT applied
-- to production yet, same as every dated migration since 2026-09-15).
-- ============================================================

BEGIN;

-- 1) A conductor vacancy has no naipe.
ALTER TABLE listing_vacancies ALTER COLUMN voice_type_id DROP NOT NULL;

-- 2) Backfill: every currently-active seeking_singer/seeking_conductor
--    listing that has ZERO vacancy rows today gets exactly one,
--    mirroring its own (until-now standalone) voice_type_id/fee
--    columns — so every existing listing becomes invite-able
--    immediately, with nothing lost. total_slots=1 matches the
--    single-implicit-vacancy assumption the old single-field UI
--    always had.
INSERT INTO listing_vacancies (listing_id, voice_type_id, fee_amount, fee_currency, fee_negotiable, total_slots)
SELECT l.id, l.voice_type_id, l.fee_amount, l.fee_currency, l.fee_negotiable, 1
FROM listings l
WHERE l.listing_type IN ('seeking_singer', 'seeking_conductor')
  AND l.is_active = TRUE
  AND NOT EXISTS (SELECT 1 FROM listing_vacancies lv WHERE lv.listing_id = l.id);

COMMIT;

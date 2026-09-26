"""
Voice type + fee of a listing, from ONE source (backlog #55, 2026-09-26).

- Job listings (seeking_singer / seeking_conductor): the vacancy rows in
  `listing_vacancies` are the only truth. The old copy on `listings`
  (voice_type_id / fee_amount / fee_negotiable) is no longer written and
  is kept empty by a DB constraint.
- Self-ads (singer_available / conductor_available): no vacancies — the
  listing's own columns are the truth.

The DB view `listing_terms` (listing_id, voice_type_id, fee_amount,
fee_currency, fee_negotiable) merges both. Use:
- `TERMS_MATCH_ANY_VOICE_SQL`-style EXISTS checks for matching/filtering
  (a Soprano + Tenor listing matches sopranos AND tenors);
- `LISTING_SUMMARY_JOIN` for card display (one voice/fee per listing,
  same rules the old copy used: one vacancy → its values; several → the
  voice only if they all share it, no single fee).
"""

# Alias `ls`: ls.voice_type_id, ls.fee_amount, ls.fee_currency, ls.fee_negotiable.
LISTING_SUMMARY_JOIN = """
    LEFT JOIN LATERAL (
        SELECT CASE WHEN count(DISTINCT t.voice_type_id) = 1 THEN min(t.voice_type_id) END AS voice_type_id,
               CASE WHEN count(*) = 1 THEN min(t.fee_amount) END AS fee_amount,
               min(t.fee_currency) AS fee_currency,
               CASE WHEN count(*) = 1 THEN bool_or(t.fee_negotiable) ELSE FALSE END AS fee_negotiable
        FROM listing_terms t WHERE t.listing_id = l.id
    ) ls ON TRUE
"""

# Every voice type a listing is looking for / offers (NULLs dropped).
LISTING_VOICE_IDS_SQL = """
    ARRAY(SELECT t.voice_type_id FROM listing_terms t
          WHERE t.listing_id = l.id AND t.voice_type_id IS NOT NULL)
"""

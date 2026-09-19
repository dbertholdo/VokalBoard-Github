"""
Multiple job vacancies per listing, one row per voice type (P3.A) —
"um anúncio pai pode conter várias vagas por naipe... com cotas
individuais e cachês específicos" (CLAUDE.md).

Deliberately ADDITIVE, not a replacement: a "seeking_singer" listing can
still work exactly as before with just its own single
`listings.voice_type_id` / `listings.fee` (no vacancy rows at all) — that
path keeps every existing piece that reads those two columns directly
working unchanged (board matching, e-mail alerts in app/notifications.py,
banner targeting in app/banners.py, the "Buscar pessoas" directory).
Vacancies only come into play when the person filling out the listing
form adds one or more of them; in that case they're what drives
invitations/candidaturas/Matches (see app/match_service.py) for that
listing.
"""
from app.database import fetch_all, fetch_one, execute
from app.fees import parse_fee_amount, CURRENCIES, DEFAULT_CURRENCY

MAX_VACANCIES_PER_LISTING = 10


def get_vacancies(listing_id: int) -> list[dict]:
    return fetch_all(
        """
        SELECT lv.id, lv.voice_type_id, vt.name AS voice_type_name,
               lv.fee_amount, lv.fee_currency, lv.fee_negotiable,
               lv.total_slots, lv.filled_slots
        FROM listing_vacancies lv
        JOIN voice_types vt ON vt.id = lv.voice_type_id
        WHERE lv.listing_id = :listing_id
        ORDER BY vt.sort_order
        """,
        {"listing_id": listing_id},
    )


def parse_vacancies_form(
    voice_type_ids: list[str], fee_amounts: list[str], fee_currencies: list[str],
    fee_negotiables, slots: list[str],
) -> list[dict]:
    """
    Turns the parallel `vacancy_voice_type_id` / `vacancy_fee_amount` /
    `vacancy_fee_currency` / `vacancy_total_slots` repeated form fields
    (always one entry per row, even for a row the person left blank —
    a <select>/<input type=number> always submits something) into a
    clean list of dicts, ready for set_vacancies(). Rows with no voice
    type chosen are skipped (an unused extra row). A row with an
    invalid/missing slot count defaults to 1. Duplicate voice types are
    merged (the first valid row for that voice wins) since
    listing_vacancies has one row per (listing, voice_type). P3.E: an
    unparseable or "both set" fee silently falls back to "no fee yet"
    (None/False) rather than rejecting the whole form — the per-vacancy
    fee isn't validated as strictly required the way the top-level
    listing fee is (see _fee_valid in listings_routes.py), since a vaga
    row can be added/edited later.

    `fee_negotiables` is NOT a parallel list like the others: an
    unchecked checkbox submits nothing at all, so a plain
    form.getlist("vacancy_fee_negotiable") would silently lose its
    position and misalign every row after the first unchecked one.
    Instead the template names each row's checkbox
    "vacancy_fee_negotiable_{i}" and the caller passes a lookup —
    a dict-like/callable supporting `i in fee_negotiables` — built
    from the raw form (see listings_routes.py), so each row's checked
    state is read by its own index, independent of who else is checked.
    """
    valid_ids = {r["id"] for r in fetch_all("SELECT id FROM voice_types")}
    seen = set()
    result = []
    for i, raw_id in enumerate(voice_type_ids):
        try:
            vt_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if vt_id not in valid_ids or vt_id in seen:
            continue
        seen.add(vt_id)
        negotiable = bool(fee_negotiables(i)) if callable(fee_negotiables) else bool(i in fee_negotiables)
        try:
            amount = parse_fee_amount(fee_amounts[i]) if i < len(fee_amounts) else None
        except ValueError:
            amount = None
        if amount is not None and negotiable:
            # Both given — same "inconsistent" case the top-level fee
            # forbids outright; here we just drop the amount and keep
            # "a negociar", rather than failing the whole listing save.
            amount = None
        currency = fee_currencies[i].strip().upper() if i < len(fee_currencies) and fee_currencies[i] else DEFAULT_CURRENCY
        if currency not in CURRENCIES:
            currency = DEFAULT_CURRENCY
        try:
            total_slots = max(1, int(slots[i])) if i < len(slots) and slots[i] else 1
        except (TypeError, ValueError):
            total_slots = 1
        result.append({
            "voice_type_id": vt_id, "fee_amount": amount, "fee_currency": currency,
            "fee_negotiable": negotiable, "total_slots": total_slots,
        })
        if len(result) >= MAX_VACANCIES_PER_LISTING:
            break
    return result


def set_vacancies(listing_id: int, vacancies: list[dict]) -> None:
    """
    Replaces the listing's vacancies with `vacancies`. Existing rows for
    a voice type that's still present keep their `filled_slots` count
    (an edit shouldn't reset who already has the job) — only
    `total_slots`/`fee` update; rows for a voice type that's no longer
    present are deleted (cascades to job_invitations/keeps job_matches,
    since job_matches.vacancy_id has ON DELETE RESTRICT — see note
    below).
    """
    existing = {r["voice_type_id"]: r["id"] for r in fetch_all(
        "SELECT id, voice_type_id FROM listing_vacancies WHERE listing_id = :id", {"id": listing_id}
    )}
    incoming_voice_ids = {v["voice_type_id"] for v in vacancies}

    # Vacancies no longer in the list: only remove if nothing has
    # actually been filled/matched for them yet (job_matches.vacancy_id
    # has ON DELETE RESTRICT precisely to stop this from silently
    # destroying a confirmed Match's history).
    for voice_id, vacancy_id in existing.items():
        if voice_id not in incoming_voice_ids:
            has_match = fetch_one("SELECT 1 FROM job_matches WHERE vacancy_id = :id", {"id": vacancy_id})
            if has_match:
                continue
            execute("DELETE FROM job_invitations WHERE vacancy_id = :id", {"id": vacancy_id})
            execute("DELETE FROM listing_vacancies WHERE id = :id", {"id": vacancy_id})

    for v in vacancies:
        if v["voice_type_id"] in existing:
            # total_slots can never drop below what's already filled
            # (the table's own CHECK constraint would reject that update
            # anyway) — clamp instead of letting the edit fail outright.
            execute(
                """
                UPDATE listing_vacancies
                SET fee_amount = :fee_amount, fee_currency = :fee_currency, fee_negotiable = :fee_negotiable,
                    total_slots = GREATEST(:total_slots, filled_slots)
                WHERE id = :id
                """,
                {
                    "fee_amount": v["fee_amount"], "fee_currency": v["fee_currency"], "fee_negotiable": v["fee_negotiable"],
                    "total_slots": v["total_slots"], "id": existing[v["voice_type_id"]],
                },
            )
        else:
            execute(
                """
                INSERT INTO listing_vacancies (listing_id, voice_type_id, fee_amount, fee_currency, fee_negotiable, total_slots)
                VALUES (:listing_id, :voice_type_id, :fee_amount, :fee_currency, :fee_negotiable, :total_slots)
                """,
                {"listing_id": listing_id, **v},
            )

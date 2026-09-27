"""Listing service: validates the listing form and creates/updates a listing with
its vacancies in ONE transaction.

Moved out of app/routers/listings_routes.py on 2026-09-27 (CLAUDE.md §4). The
router only parses the request, calls these, and renders.
"""
from datetime import date

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database import fetch_one, transaction
from app.fees import CURRENCIES, DEFAULT_CURRENCY, fee_valid
from app.locations import COUNTRY_OPTIONS
from app.retention_rules import availability_valid
from app.vacancies import parse_vacancies_form, set_vacancies

LISTING_TYPE_KEYS = ["seeking_singer", "seeking_conductor", "singer_available", "conductor_available"]
JOB_TYPES = ("seeking_singer", "seeking_conductor")
ENSEMBLE_TYPE_KEYS = ["solo", "choir", "both"]
MAX_TITLE = 150
MAX_SHORT = 200   # repertoire, venue
MAX_CITY = 100
MAX_DESCRIPTION = 20000
MAX_URL = 500


class ListingFormError(Exception):
    """Invalid listing form; `key` is the i18n error key, `data` what to re-fill the form with."""

    def __init__(self, key: str, data: dict):
        super().__init__(key)
        self.key = key
        self.data = data


def _valid_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except (ValueError, TypeError):
        return False


def clean_listing_form(form, existing_type: str | None = None) -> dict:
    """Validates the /listings/new and /listings/{id}/edit form.
    `existing_type`: on edit the listing type is fixed (switching a job listing to a
    self-ad would orphan its vacancies/Matches). Raises ListingFormError."""
    g = lambda name, default="": (form.get(name) or default)  # noqa: E731
    listing_type = existing_type or g("listing_type")
    fee_negotiable = bool(g("fee_negotiable"))
    fee_currency = g("fee_currency", DEFAULT_CURRENCY)
    if fee_currency not in CURRENCIES:
        fee_currency = DEFAULT_CURRENCY
    sheet_music_available = bool(g("sheet_music_available"))
    sheet_music_url = g("sheet_music_url").strip()[:MAX_URL]
    country = g("country", "DE")

    data = {
        "listing_type": listing_type,
        "title": " ".join(g("title").split())[:MAX_TITLE],
        "description": g("description").strip()[:MAX_DESCRIPTION],
        "city": g("city").strip()[:MAX_CITY],
        "state": g("state").strip()[:MAX_CITY],
        "country": country if country in COUNTRY_OPTIONS else "DE",
        "voice_type_id": g("voice_type_id").strip(),
        "repertoire": g("repertoire").strip()[:MAX_SHORT],
        "venue": g("venue").strip()[:MAX_SHORT],
        "fee_amount": g("fee_amount"),
        "fee_currency": fee_currency,
        "fee_negotiable": fee_negotiable,
        "ensemble_type": g("ensemble_type") if g("ensemble_type") in ENSEMBLE_TYPE_KEYS else None,
        "event_date": g("event_date"),
        "available_from": g("available_from"),
        "available_until": g("available_until"),
        "travel_cost_covered": bool(g("travel_cost_covered")),
        "rehearsal_schedule_available": bool(g("rehearsal_schedule_available")),
        "sheet_music_available": sheet_music_available,
        # Zero-Storage: kept only when "available" is checked; http(s) only — this
        # becomes a link shown to the Match partner (no javascript:/data: URLs).
        "sheet_music_url": sheet_music_url if sheet_music_available and sheet_music_url.startswith(("http://", "https://")) else None,
        "is_urgent": bool(g("is_urgent")),
    }
    data["vacancies"] = parse_vacancies_form(
        form.getlist("vacancy_voice_type_id"), form.getlist("vacancy_fee_amount"),
        form.getlist("vacancy_fee_currency"), lambda i: form.get(f"vacancy_fee_negotiable_{i}"),
        form.getlist("vacancy_total_slots"), listing_type,
    ) if listing_type in JOB_TYPES else []

    def fail(key: str):
        raise ListingFormError(key, data)

    if listing_type not in LISTING_TYPE_KEYS:
        fail("error_required_fields")
    if not data["title"] or not data["description"]:
        fail("error_required_fields")
    if sheet_music_available and sheet_music_url and data["sheet_music_url"] is None:
        fail("error_required_fields")

    available = listing_type == "singer_available"
    if available:
        if not availability_valid(data["available_from"], data["available_until"]):
            fail("error_required_fields")
        data["event_date"] = ""
        if not data["state"] and not data["city"]:
            data["country"] = None
    else:
        if not data["state"]:
            fail("error_required_fields")
        if listing_type in JOB_TYPES:
            # Jobs need city, repertoire, a real vacancy and a valid event date (was a raw JSON 400).
            if not (data["city"] and data["repertoire"] and data["vacancies"]):
                fail("error_required_fields")
            if not _valid_date(data["event_date"]):
                fail("error_event_date_required")
        elif data["event_date"] and not _valid_date(data["event_date"]):
            fail("error_event_date_required")

    if listing_type in JOB_TYPES:
        # #55: job listings keep voice type and fee ONLY in listing_vacancies.
        data.update(db_voice_type_id=None, db_fee_amount=None, db_fee_negotiable=False)
    else:
        vt = data["voice_type_id"]
        if vt and (not vt.isdigit() or not fetch_one("SELECT 1 FROM voice_types WHERE id = :id", {"id": int(vt)})):
            fail("error_required_fields")
        fee_ok, amount = fee_valid(data["fee_amount"], fee_negotiable)
        if amount is not None and fee_negotiable:
            amount = None  # both given: keep "negotiable" (the DB forbids both at once — was a 500)
        data.update(db_voice_type_id=int(vt) if vt else None, db_fee_amount=amount, db_fee_negotiable=fee_negotiable)
    return data


def _row_params(data: dict) -> dict:
    available = data["listing_type"] == "singer_available"
    return {
        "listing_type": data["listing_type"], "title": data["title"], "description": data["description"],
        "city": data["city"] or None, "state": data["state"] or None, "country": data["country"],
        "voice_type_id": data["db_voice_type_id"], "repertoire": data["repertoire"] or None,
        "venue": data["venue"] or None, "fee_amount": data["db_fee_amount"], "fee_currency": data["fee_currency"],
        "fee_negotiable": data["db_fee_negotiable"], "ensemble_type": data["ensemble_type"],
        "event_date": data["event_date"] or None,
        "available_from": data["available_from"] if available else None,
        "available_until": data["available_until"] if available else None,
        "travel_cost_covered": data["travel_cost_covered"], "sheet_music_available": data["sheet_music_available"],
        "sheet_music_url": data["sheet_music_url"], "rehearsal_schedule_available": data["rehearsal_schedule_available"],
    }


def _availability_error(exc: IntegrityError, data: dict) -> ListingFormError | None:
    reason = getattr(getattr(exc.orig, "diag", None), "message_primary", "")
    return ListingFormError(reason, data) if reason in ("availability_limit", "availability_invalid") else None


def create_listing(author_id: int, data: dict) -> int:
    """Listing row + vacancies in one transaction. Raises ListingFormError for the
    DB-enforced availability rules (were a raw JSON 400)."""
    try:
        with transaction() as conn:
            listing_id = conn.execute(text(
                """
                INSERT INTO listings (author_id, listing_type, title, description, city, state, country, voice_type_id,
                    repertoire, venue, fee_amount, fee_currency, fee_negotiable, ensemble_type, event_date,
                    available_from, available_until, travel_cost_covered, sheet_music_available, sheet_music_url,
                    rehearsal_schedule_available)
                VALUES (:author_id, :listing_type, :title, :description, :city, :state, :country, :voice_type_id,
                    :repertoire, :venue, :fee_amount, :fee_currency, :fee_negotiable, :ensemble_type, :event_date,
                    :available_from, :available_until, :travel_cost_covered, :sheet_music_available, :sheet_music_url,
                    :rehearsal_schedule_available)
                RETURNING id
                """), {"author_id": author_id, **_row_params(data)}).scalar_one()
            if data["listing_type"] in JOB_TYPES:
                set_vacancies(listing_id, data["vacancies"], conn=conn)
    except IntegrityError as exc:
        err = _availability_error(exc, data)
        if err:
            raise err from exc
        raise
    return listing_id


def update_listing(listing_id: int, data: dict) -> None:
    try:
        with transaction() as conn:
            conn.execute(text(
                """
                UPDATE listings
                SET title = :title, description = :description, city = :city, state = :state, country = :country,
                    voice_type_id = :voice_type_id, repertoire = :repertoire, venue = :venue,
                    fee_amount = :fee_amount, fee_currency = :fee_currency, fee_negotiable = :fee_negotiable,
                    ensemble_type = :ensemble_type, event_date = :event_date,
                    available_from = :available_from, available_until = :available_until,
                    travel_cost_covered = :travel_cost_covered, sheet_music_available = :sheet_music_available,
                    sheet_music_url = :sheet_music_url, rehearsal_schedule_available = :rehearsal_schedule_available,
                    updated_at = now()
                WHERE id = :id
                """), {"id": listing_id, **_row_params(data)})
            if data["listing_type"] in JOB_TYPES:
                set_vacancies(listing_id, data["vacancies"], conn=conn)
    except IntegrityError as exc:
        err = _availability_error(exc, data)
        if err:
            raise err from exc
        raise


def form_values(data: dict) -> dict:
    """What the form template needs to re-fill itself after an error — including
    the vacancy rows and checkboxes (they used to reset to empty)."""
    values = {k: v for k, v in data.items() if k != "vacancies"}
    values["sheet_music_url"] = data.get("sheet_music_url") or ""
    return values

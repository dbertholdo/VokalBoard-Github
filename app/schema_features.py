"""Does the database already have these columns? (2026-09-28)

Code that ships before its migration is applied in production asks here
first. Positive answers are cached for good; missing columns are re-checked
at most once a minute, so applying the migration takes effect without a
restart."""
import time

from app.database import fetch_one

_cache: dict[tuple, tuple[bool, float]] = {}


def has_columns(table: str, *columns: str) -> bool:
    key = (table, columns)
    known = _cache.get(key)
    if known and (known[0] or time.monotonic() - known[1] < 60):
        return known[0]
    row = fetch_one(
        """SELECT count(*) AS n FROM information_schema.columns
           WHERE table_schema = current_schema() AND table_name = :table AND column_name = ANY(:cols)""",
        {"table": table, "cols": list(columns)},
    )
    ok = bool(row and row["n"] == len(columns))
    _cache[key] = (ok, time.monotonic())
    return ok

"""Pure rules: calendar periods are inclusive; archived content lasts 60 more days."""
from datetime import date, timedelta
from math import ceil


def availability_valid(start, end):
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
        return 0 <= (last-first).days <= 29
    except (TypeError, ValueError):
        return False


# Messenger (2026-09-26): a conversation is deleted 60 days after its last
# message; the "!" warning shows from day 50 (the last 10 days).
MESSAGE_RETENTION_DAYS = 60
MESSAGE_WARNING_DAYS = 10


def warning_days(activity, now):
    days = ceil(((activity + timedelta(days=MESSAGE_RETENTION_DAYS)) - now).total_seconds() / 86400)
    return days if 1 <= days <= MESSAGE_WARNING_DAYS else None

"""Pure rules: calendar periods are inclusive; archived content lasts 60 more days."""
from datetime import date, timedelta
from math import ceil


def availability_valid(start, end):
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
        return 0 <= (last-first).days <= 29
    except (TypeError, ValueError):
        return False


def warning_days(activity, now):
    days = ceil(((activity + timedelta(days=30))-now).total_seconds()/86400)
    return days if 1 <= days <= 7 else None

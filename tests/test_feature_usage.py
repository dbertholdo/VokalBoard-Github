"""P4 Etapa 3 (18/09/2026): contador genérico de uso de ferramentas do
site (Admin > "Ferramentas mais usadas"). Ver app/feature_usage.py.
"""
from datetime import date

from app.database import execute
from app.feature_usage import get_feature_usage_totals, record_feature_usage


def _clear(key: str):
    execute("DELETE FROM feature_usage_monthly WHERE feature_key = :k", {"k": key})


def test_record_feature_usage_increments_atomically(client):
    _clear("sectest_tool")
    record_feature_usage("sectest_tool", date(2026, 9, 1))
    record_feature_usage("sectest_tool", date(2026, 9, 15))
    record_feature_usage("sectest_tool", date(2026, 9, 30))

    totals = {f["key"]: f for f in get_feature_usage_totals()}
    assert totals["sectest_tool"]["total"] == 3


def test_totals_split_current_month_from_lifetime_total(client):
    _clear("sectest_tool2")
    record_feature_usage("sectest_tool2", date(2026, 1, 5))
    record_feature_usage("sectest_tool2", date.today())
    record_feature_usage("sectest_tool2", date.today())

    row = next(f for f in get_feature_usage_totals() if f["key"] == "sectest_tool2")
    assert row["total"] == 3
    assert row["this_month"] == 2  # January's use doesn't count as "this month".


def test_totals_ordered_busiest_first(client):
    _clear("sectest_busy")
    _clear("sectest_quiet")
    record_feature_usage("sectest_busy", date.today())
    record_feature_usage("sectest_busy", date.today())
    record_feature_usage("sectest_quiet", date.today())

    totals = [f["key"] for f in get_feature_usage_totals() if f["key"] in ("sectest_busy", "sectest_quiet")]
    assert totals.index("sectest_busy") < totals.index("sectest_quiet")


def test_unknown_feature_key_gets_a_readable_fallback_label(client):
    _clear("sectest_some_new_tool")
    record_feature_usage("sectest_some_new_tool")

    row = next(f for f in get_feature_usage_totals() if f["key"] == "sectest_some_new_tool")
    assert row["label"] == "Sectest Some New Tool"

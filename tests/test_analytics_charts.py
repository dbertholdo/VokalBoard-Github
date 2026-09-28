"""6d (2026-09-28): analytics charts get complete, short-labelled data."""
import json
import re

from app.database import execute
from tests.test_security import login, register_test_user


def _chart_data(html, title):
    block = html[html.index(title):]
    return json.loads(re.search(r"data-chart='([^']*)'", block).group(1).replace("&#34;", '"').replace("&quot;", '"'))


def test_charts_have_every_weekday_hour_and_day_with_short_labels(client):
    user_id, email, password = register_test_user(client, full_name="Charts Admin")
    execute("UPDATE users SET email_verified = TRUE, role_level = 2 WHERE id = :id", {"id": user_id})
    login(client, email, password)
    html = client.get("/admin/analytics").text
    assert 'class="analytics-grid analytics-stack"' in html
    weekdays = _chart_data(html, "Weekday (avg. per day)")
    assert [d["label"] for d in weekdays] == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    hours = _chart_data(html, "Hour of day")
    assert [d["label"] for d in hours] == [f"{h:02d}" for h in range(24)]
    days = _chart_data(html, "Day of month")
    assert [d["label"] for d in days] == [str(d) for d in range(1, 32)]

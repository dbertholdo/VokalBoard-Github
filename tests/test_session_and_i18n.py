import base64
import json
from datetime import datetime, timedelta, timezone

from itsdangerous import TimestampSigner
from app.i18n import SUPPORTED_LANGUAGES, translate


def test_new_requested_languages_are_available_with_safe_english_fallback():
    assert {"zh", "ko", "ro"}.issubset(SUPPORTED_LANGUAGES)
    assert translate("nav_login", "zh") == "Log in"
    assert translate("nav_login", "ko") == "Log in"
    assert translate("nav_login", "ro") == "Log in"


def _set_session(client, payload):
    """Create the same signed session cookie used by Starlette in development."""
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8"))
    signed = TimestampSigner("dev-secret-key-change-in-production").sign(encoded).decode("utf-8")
    client.cookies.set("session", signed, domain="testserver.local", path="/")


def _read_session(client):
    raw = client.cookies.get("session", domain="testserver.local", path="/")
    if not raw:
        return {}
    unsigned = TimestampSigner("dev-secret-key-change-in-production").unsign(raw)
    return json.loads(base64.b64decode(unsigned))


def test_inactive_authenticated_session_is_cleared(client):
    _set_session(client, {
        "user_id": 999999,
        "last_authenticated_activity_at": (
            datetime.now(timezone.utc) - timedelta(hours=24, seconds=1)
        ).isoformat(),
    })

    client.get("/")

    assert "user_id" not in _read_session(client)


def test_recent_authenticated_session_remains_active(client):
    _set_session(client, {
        "user_id": 999999,
        "last_authenticated_activity_at": datetime.now(timezone.utc).isoformat(),
    })

    client.get("/")

    assert _read_session(client)["user_id"] == 999999

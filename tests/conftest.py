"""
Shared configuration for the security tests (see tests/test_security.py).

These tests run against a real Postgres database (locally, the same
one from your dev .env; on GitHub Actions, a temporary Postgres
created just for this — see .github/workflows/security.yml), not a
"fake" database — so they test the application's real behavior
(session handling, CSRF, login lockout), not a simulation.

Every user created by the tests uses an email starting with
"sectest_", so it can be identified and deleted afterward without
any risk of touching real people's data.
"""
import pytest
from fastapi.testclient import TestClient

from app.database import execute
from app.main import app

TEST_EMAIL_PREFIX = "sectest_"


def _remove_test_match_rows():
    """Remove Match rows before test users.

    Matches intentionally use restrictive foreign keys in production so an
    accepted job cannot disappear accidentally.  Test cleanup must therefore
    remove only the rows owned by disposable ``sectest_`` accounts first.
    """
    execute(
        """
        DELETE FROM job_matches
        WHERE artist_user_id IN (SELECT id FROM users WHERE email LIKE :p)
           OR contractor_user_id IN (SELECT id FROM users WHERE email LIKE :p)
        """,
        {"p": f"{TEST_EMAIL_PREFIX}%"},
    )


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    """In-memory form limits (app/rate_limit.py) must not leak between tests."""
    from app.rate_limit import reset
    reset()
    yield


@pytest.fixture(autouse=True, scope="session")
def cleanup_test_data():
    # Also clean up BEFORE (not just after): if a previous run was
    # interrupted midway, a leftover registration_attempts/
    # login_lockouts row shouldn't make this run's tests start out
    # already "used up".
    # registration_attempts is just a temporary counter (never holds
    # real people's data) — safe to wipe entirely on every test run,
    # so an IP "used up" in a previous run never leaks into the next
    # one.
    execute("DELETE FROM login_lockouts WHERE email LIKE :p", {"p": f"{TEST_EMAIL_PREFIX}%"})
    execute("DELETE FROM registration_attempts")
    _remove_test_match_rows()
    execute("DELETE FROM users WHERE email LIKE :p", {"p": f"{TEST_EMAIL_PREFIX}%"})
    yield
    execute("DELETE FROM login_lockouts WHERE email LIKE :p", {"p": f"{TEST_EMAIL_PREFIX}%"})
    execute("DELETE FROM registration_attempts")
    _remove_test_match_rows()
    execute("DELETE FROM users WHERE email LIKE :p", {"p": f"{TEST_EMAIL_PREFIX}%"})

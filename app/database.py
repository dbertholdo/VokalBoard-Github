"""
Database access layer.

Deliberately, this project does NOT use a full ORM (like SQLAlchemy
ORM with model classes). Instead, we use SQLAlchemy only as a
connection engine and write SQL "by hand" with `text()`. The idea is
that you practice real SQL — SELECTs, JOINs, dynamic WHEREs, etc —
instead of letting an ORM generate everything for you.
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://vokalboard_user:vokalboard_pass@localhost:5432/vokalboard",
)

# pool_pre_ping avoids "connection closed" errors on deploy platforms
# that drop idle connections (common on Render/Railway's free tier).
engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def fetch_all(query: str, params: dict | None = None) -> list[dict]:
    """Executes a SELECT and returns a list of dicts (one per row)."""
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        return [dict(row._mapping) for row in result]


def fetch_one(query: str, params: dict | None = None) -> dict | None:
    """Executes a SELECT and returns the first row as a dict (or None)."""
    rows = fetch_all(query, params)
    return rows[0] if rows else None


def execute(query: str, params: dict | None = None) -> None:
    """Executes an INSERT/UPDATE/DELETE (no rows returned)."""
    with engine.begin() as conn:
        conn.execute(text(query), params or {})


def execute_returning(query: str, params: dict | None = None) -> dict | None:
    """Executes an INSERT/UPDATE ... RETURNING ... and returns the row."""
    with engine.begin() as conn:
        result = conn.execute(text(query), params or {})
        row = result.fetchone()
        return dict(row._mapping) if row else None

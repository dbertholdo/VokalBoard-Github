"""
Camada de acesso ao banco de dados.

De propósito, este projeto NÃO usa um ORM completo (tipo SQLAlchemy ORM
com classes de modelo). Em vez disso, usamos o SQLAlchemy só como motor
de conexão e escrevemos SQL "na mão" com `text()`. A ideia é que você
pratique SQL de verdade — SELECTs, JOINs, WHEREs dinâmicos, etc — em vez
de deixar um ORM gerar tudo por você.
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://maestro_user:maestro_pass@localhost:5432/maestro_cantor",
)

# pool_pre_ping evita erros de "conexão fechada" em plataformas de deploy
# que derrubam conexões ociosas (comum em Render/Railway free tier).
engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def fetch_all(query: str, params: dict | None = None) -> list[dict]:
    """Executa um SELECT e retorna uma lista de dicts (uma por linha)."""
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        return [dict(row._mapping) for row in result]


def fetch_one(query: str, params: dict | None = None) -> dict | None:
    """Executa um SELECT e retorna a primeira linha como dict (ou None)."""
    rows = fetch_all(query, params)
    return rows[0] if rows else None


def execute(query: str, params: dict | None = None) -> None:
    """Executa um INSERT/UPDATE/DELETE (sem retorno de linhas)."""
    with engine.begin() as conn:
        conn.execute(text(query), params or {})


def execute_returning(query: str, params: dict | None = None) -> dict | None:
    """Executa um INSERT/UPDATE ... RETURNING ... e retorna a linha."""
    with engine.begin() as conn:
        result = conn.execute(text(query), params or {})
        row = result.fetchone()
        return dict(row._mapping) if row else None

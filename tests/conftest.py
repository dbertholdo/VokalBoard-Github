"""
Configuração compartilhada dos testes de segurança (ver tests/test_security.py).

Esses testes rodam contra um banco Postgres de verdade (localmente, o
mesmo do seu .env de desenvolvimento; no GitHub Actions, um Postgres
temporário criado só pra isso — ver .github/workflows/security.yml),
não um banco "fake" — assim eles testam o comportamento real da
aplicação (sessão, CSRF, bloqueio de login), não uma simulação.

Todo usuário criado pelos testes usa um e-mail começando com
"sectest_", pra dar pra identificar e apagar no final sem risco de
mexer em dado de gente de verdade.
"""
import pytest
from fastapi.testclient import TestClient

from app.database import execute
from app.main import app

TEST_EMAIL_PREFIX = "sectest_"


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture(autouse=True, scope="session")
def cleanup_test_data():
    # Limpa ANTES também (não só depois): se uma execução anterior tiver
    # sido interrompida no meio, uma linha de registration_attempts/
    # login_lockouts velha não deveria fazer os testes desta execução
    # começarem já "gastos".
    # registration_attempts é só um contador temporário (nunca guarda
    # dado de gente de verdade) — seguro limpar por inteiro a cada
    # execução dos testes, pra um IP "gasto" numa execução anterior
    # nunca vazar pra próxima.
    execute("DELETE FROM login_lockouts WHERE email LIKE :p", {"p": f"{TEST_EMAIL_PREFIX}%"})
    execute("DELETE FROM registration_attempts")
    execute("DELETE FROM users WHERE email LIKE :p", {"p": f"{TEST_EMAIL_PREFIX}%"})
    yield
    execute("DELETE FROM login_lockouts WHERE email LIKE :p", {"p": f"{TEST_EMAIL_PREFIX}%"})
    execute("DELETE FROM registration_attempts")
    execute("DELETE FROM users WHERE email LIKE :p", {"p": f"{TEST_EMAIL_PREFIX}%"})

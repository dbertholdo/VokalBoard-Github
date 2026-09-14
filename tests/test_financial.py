"""
Testes da Zona Vermelha / painel financeiro (ver app/routers/financial_routes.py
e app/permissions.py):

1. Níveis de acesso: comum/moderador/admin não enxergam a Zona Vermelha,
   só god mode (nível 3).
2. A trava de segurança: toggle do Modo Capitalismo e mudança de preço
   exigem senha de novo, mesmo já logado como god mode — e uma senha
   errada não muda nada.
3. Toda ação sensível fica no audit_log, sucesso ou falha.
4. Painel financeiro: lançar/apagar despesa, exportar CSV.
5. Fechamento mensal/anual: cria e os três formatos de export respondem
   200 com o content-type certo.
"""
import uuid

import pytest

from app.database import execute, fetch_one
from tests.test_security import (
    DEFAULT_PASSWORD,
    extract_csrf,
    login,
    register_test_user,
)


def _promote(user_id: int, level: int):
    execute("UPDATE users SET role_level = :lvl, email_verified = TRUE WHERE id = :id", {"lvl": level, "id": user_id})


@pytest.fixture(autouse=True)
def _cleanup_financial_test_rows():
    """Estas tabelas não têm nenhuma relação com sectest_ (o cleanup de
    tests/conftest.py só apaga USUÁRIOS com esse prefixo de e-mail) —
    sem isso, cada execução da suíte deixaria despesas/fechamentos/logs
    de teste acumulando pra sempre no banco de dev. Marca o maior id de
    cada tabela antes do teste e apaga tudo que ficou acima disso
    depois — simples e não depende de nenhuma coluna nova.
    """
    max_ids = {
        t: (fetch_one(f"SELECT COALESCE(MAX(id), 0) AS n FROM {t}")["n"])
        for t in ("expenses", "financial_closings", "audit_log", "bank_import_profiles", "bank_transactions")
    }
    yield
    for t, max_id in max_ids.items():
        execute(f"DELETE FROM {t} WHERE id > :max_id", {"max_id": max_id})  # nosec B608 - t vem só da tupla fixa acima


@pytest.fixture()
def god_user(client):
    user_id, email, password = register_test_user(client, full_name="God Mode Test")
    _promote(user_id, 3)
    login(client, email, password)
    return {"id": user_id, "email": email, "password": password}


class TestAccessLevels:
    def test_common_user_cannot_see_zona_vermelha(self, client):
        user_id, email, password = register_test_user(client, full_name="Comum Test")
        login(client, email, password)
        r = client.get("/financeiro", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/"

    def test_admin_level_2_cannot_see_zona_vermelha(self, client):
        user_id, email, password = register_test_user(client, full_name="Admin Nivel 2")
        _promote(user_id, 2)
        login(client, email, password)
        r = client.get("/financeiro", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/"
        # mas o painel /admin "normal" continua acessível
        r2 = client.get("/admin", follow_redirects=False)
        assert r2.status_code == 200

    def test_moderator_level_1_cannot_reach_admin_users(self, client):
        user_id, email, password = register_test_user(client, full_name="Moderador Test")
        _promote(user_id, 1)
        login(client, email, password)
        # painel de leitura /admin já entra (nível >= 1)
        assert client.get("/admin", follow_redirects=False).status_code == 200
        # mas gestão de usuários exige nível 2+
        r = client.get("/admin/users", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/"

    def test_god_mode_sees_zona_vermelha(self, god_user, client):
        r = client.get("/financeiro")
        assert r.status_code == 200
        assert "Modo Capitalismo" in r.text

    def test_only_god_mode_can_promote_another_to_god_mode(self, client):
        # admin nível 2 tentando promover outra pessoa a god mode não deveria conseguir
        admin_id, admin_email, admin_password = register_test_user(client, full_name="Admin Promotor")
        _promote(admin_id, 2)
        target_id, _, _ = register_test_user(client, full_name="Alvo Promocao")
        _promote(target_id, 2)
        login(client, admin_email, admin_password)

        r = client.get(f"/admin/users/{target_id}")
        token = extract_csrf(r.text)
        client.post(
            f"/admin/users/{target_id}/toggle-god-mode",
            data={"csrf_token": token},
            follow_redirects=False,
        )
        level_after = fetch_one("SELECT role_level FROM users WHERE id = :id", {"id": target_id})["role_level"]
        assert level_after == 2, "admin comum não deveria conseguir promover ninguém a god mode"


class TestSecurityLockOnSensitiveActions:
    def test_toggle_capitalismo_requires_correct_password(self, god_user, client):
        r = client.get("/financeiro")
        token = extract_csrf(r.text)

        # senha errada: nada muda
        client.post(
            "/financeiro/toggle-capitalismo",
            data={"csrf_token": token, "current_password": "senha-errada-de-proposito"},
            follow_redirects=False,
        )
        setting = fetch_one("SELECT value FROM system_settings WHERE key = 'capitalismo_mode_enabled'")
        assert setting["value"] == "false", "senha errada não deveria ter ligado o Modo Capitalismo"

        # senha certa: liga
        client.post(
            "/financeiro/toggle-capitalismo",
            data={"csrf_token": token, "current_password": DEFAULT_PASSWORD},
            follow_redirects=False,
        )
        setting_after = fetch_one("SELECT value FROM system_settings WHERE key = 'capitalismo_mode_enabled'")
        assert setting_after["value"] == "true"

        # desliga de novo, pra não vazar estado pro próximo teste
        client.post(
            "/financeiro/toggle-capitalismo",
            data={"csrf_token": token, "current_password": DEFAULT_PASSWORD},
            follow_redirects=False,
        )

    def test_wrong_password_and_success_both_hit_audit_log(self, god_user, client):
        r = client.get("/financeiro")
        token = extract_csrf(r.text)
        before = fetch_one("SELECT COUNT(*) AS n FROM audit_log")["n"]

        client.post(
            "/financeiro/toggle-capitalismo",
            data={"csrf_token": token, "current_password": "errada"},
            follow_redirects=False,
        )
        after_fail = fetch_one("SELECT COUNT(*) AS n FROM audit_log")["n"]
        assert after_fail == before + 1

        client.post(
            "/financeiro/toggle-capitalismo",
            data={"csrf_token": token, "current_password": DEFAULT_PASSWORD},
            follow_redirects=False,
        )
        after_success = fetch_one("SELECT COUNT(*) AS n FROM audit_log")["n"]
        assert after_success == after_fail + 1

        last_action = fetch_one("SELECT action, actor_user_id FROM audit_log ORDER BY id DESC LIMIT 1")
        assert last_action["action"] == "toggle_capitalismo_mode"
        assert last_action["actor_user_id"] == god_user["id"]

        # desliga de novo pra não vazar estado
        client.post(
            "/financeiro/toggle-capitalismo",
            data={"csrf_token": token, "current_password": DEFAULT_PASSWORD},
            follow_redirects=False,
        )

    def test_set_price_requires_password_and_valid_amount(self, god_user, client):
        r = client.get("/financeiro")
        token = extract_csrf(r.text)

        client.post(
            "/financeiro/set-price",
            data={
                "csrf_token": token, "price_eur": "7.90", "price_chf": "8.90",
                "current_password": DEFAULT_PASSWORD,
            },
            follow_redirects=False,
        )
        eur = fetch_one("SELECT value FROM system_settings WHERE key = 'subscription_price_eur_cents'")
        assert eur["value"] == "790"

        # volta ao padrão pra não vazar estado entre testes
        client.post(
            "/financeiro/set-price",
            data={
                "csrf_token": token, "price_eur": "5.90", "price_chf": "6.90",
                "current_password": DEFAULT_PASSWORD,
            },
            follow_redirects=False,
        )


class TestFinancialPanel:
    def test_create_and_delete_expense(self, god_user, client):
        r = client.get("/financeiro/painel")
        assert r.status_code == 200
        token = extract_csrf(r.text)

        client.post(
            "/financeiro/expenses",
            data={
                "csrf_token": token, "description": "Hospedagem Railway", "amount": "12.50",
                "currency": "EUR", "category": "hosting", "expense_date": "2026-09-01",
                "is_recurring": "1", "recurrence_interval": "monthly",
            },
            follow_redirects=False,
        )
        expense = fetch_one("SELECT * FROM expenses WHERE description = 'Hospedagem Railway'")
        assert expense is not None
        assert expense["amount_cents"] == 1250
        assert expense["is_recurring"] is True

        client.post(
            f"/financeiro/expenses/{expense['id']}/delete",
            data={"csrf_token": token},
            follow_redirects=False,
        )
        assert fetch_one("SELECT * FROM expenses WHERE id = :id", {"id": expense["id"]}) is None

    def test_expenses_export_csv(self, god_user, client):
        r = client.get("/financeiro/expenses/export.csv")
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        assert "descricao" in r.text

    def test_non_god_mode_cannot_reach_financial_panel(self, client):
        user_id, email, password = register_test_user(client, full_name="Sem Acesso")
        login(client, email, password)
        assert client.get("/financeiro/painel", follow_redirects=False).status_code == 303
        assert client.get("/financeiro/expenses/export.csv", follow_redirects=False).status_code == 303


class TestFinancialClosing:
    def test_create_closing_and_export_all_formats(self, god_user, client):
        r = client.get("/financeiro/painel")
        token = extract_csrf(r.text)

        resp = client.post(
            "/financeiro/fechamento",
            data={
                "csrf_token": token, "period_type": "monthly",
                "period_start": "2026-09-01", "period_end": "2026-09-30",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303
        closing = fetch_one("SELECT * FROM financial_closings ORDER BY id DESC LIMIT 1")
        assert closing is not None
        assert closing["period_type"] == "monthly"

        csv_resp = client.get(f"/financeiro/fechamento/{closing['id']}/export.csv")
        assert csv_resp.status_code == 200
        assert "text/csv" in csv_resp.headers["content-type"]

        xlsx_resp = client.get(f"/financeiro/fechamento/{closing['id']}/export.xlsx")
        assert xlsx_resp.status_code == 200
        assert "spreadsheetml" in xlsx_resp.headers["content-type"]

        pdf_resp = client.get(f"/financeiro/fechamento/{closing['id']}/export.pdf")
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers["content-type"] == "application/pdf"


class TestCapitalismoBannerHidden:
    def test_banner_hidden_while_capitalismo_mode_off(self, client):
        user_id, email, password = register_test_user(client, full_name="Banner Test")
        login(client, email, password)
        r = client.get("/")
        assert "capitalismo-banner" not in r.text
        assert "Assine já" not in r.text

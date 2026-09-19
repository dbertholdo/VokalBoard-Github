"""P6 — fechar o loop de denúncias (18/09/2026): aceitar/rejeitar uma
denúncia em /admin (God Mode) e notificar quem denunciou por e-mail.
Pedido do Daniel: "resposta a denúncias e notificação ao usuário
quando denúncia for aceita". Ver app/moderation.py e
app/routers/admin_routes.py."""
from datetime import date, timedelta

from app.database import execute, fetch_one
from app.moderation import resolve_report, get_open_reports
from tests.test_security import extract_csrf, login, register_test_user


def _listing_data(csrf_token):
    return {
        "csrf_token": csrf_token,
        "listing_type": "seeking_singer",
        "title": "Sectest Report Moderation Listing",
        "description": "Test description.",
        "state": "Bayern",
        "city": "München",
        "country": "DE",
        "voice_type_id": "",
        "repertoire": "Requiem",
        "venue": "",
        "fee_amount": "100",
        "fee_currency": "EUR",
        "fee_negotiable": "",
        "ensemble_type": "",
        "event_date": (date.today() + timedelta(days=10)).isoformat(),
    }


def _make_reported_listing(client):
    """Creates an author + listing, then a separate reporter who files
    a report against it. Returns (listing_id, report_id, reporter_email,
    reporter_password)."""
    author_id, author_email, author_password = register_test_user(client, full_name="Report Mod Author")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": author_id})
    login(client, author_email, author_password)
    r = client.get("/listings/new")
    token = extract_csrf(r.text)
    client.post("/listings/new", data=_listing_data(token), follow_redirects=False)
    listing = fetch_one(
        "SELECT id FROM listings WHERE author_id = :id ORDER BY created_at DESC LIMIT 1", {"id": author_id}
    )

    reporter_id, reporter_email, reporter_password = register_test_user(client, full_name="Report Mod Reporter")
    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": reporter_id})
    login(client, reporter_email, reporter_password)
    page = client.get(f"/listings/{listing['id']}")
    token = extract_csrf(page.text)
    client.post(
        f"/listings/{listing['id']}/report",
        data={"csrf_token": token, "reason": "This listing looks like spam, please review it."},
        follow_redirects=False,
    )
    report = fetch_one(
        "SELECT id FROM listing_reports WHERE listing_id = :lid AND reporter_id = :rid",
        {"lid": listing["id"], "rid": reporter_id},
    )
    return listing["id"], report["id"], reporter_email, reporter_password


def _make_god_mode_admin(client):
    admin_id, admin_email, admin_password = register_test_user(client, full_name="Report Mod God Admin")
    execute("UPDATE users SET email_verified = TRUE, role_level = 3 WHERE id = :id", {"id": admin_id})
    login(client, admin_email, admin_password)
    return admin_id, admin_email, admin_password


# --- resolve_report() (module-level) ------------------------------------

def test_resolve_report_marks_status_and_resolver():
    admin_id, _, _ = _bootstrap_direct_admin()
    report_id, reporter_id = _bootstrap_direct_report()

    result = resolve_report(report_id, accepted=True, admin_id=admin_id)
    assert result is not None
    assert result["reporter_id"] == reporter_id

    row = fetch_one("SELECT status, resolved_by_user_id FROM listing_reports WHERE id = :id", {"id": report_id})
    assert row["status"] == "accepted"
    assert row["resolved_by_user_id"] == admin_id


def test_resolve_report_returns_none_when_already_resolved():
    admin_id, _, _ = _bootstrap_direct_admin()
    report_id, _ = _bootstrap_direct_report()

    first = resolve_report(report_id, accepted=False, admin_id=admin_id)
    assert first is not None
    second = resolve_report(report_id, accepted=True, admin_id=admin_id)
    assert second is None

    # The second (no-op) call didn't flip a rejected report to accepted.
    row = fetch_one("SELECT status FROM listing_reports WHERE id = :id", {"id": report_id})
    assert row["status"] == "rejected"


def test_get_open_reports_excludes_resolved():
    admin_id, _, _ = _bootstrap_direct_admin()
    report_id, _ = _bootstrap_direct_report()

    assert any(r["id"] == report_id for r in get_open_reports())
    resolve_report(report_id, accepted=True, admin_id=admin_id)
    assert not any(r["id"] == report_id for r in get_open_reports())


def _bootstrap_direct_admin():
    import uuid
    from app.database import execute_returning
    from app.auth import hash_password

    email = f"sectest_modadmin_{uuid.uuid4().hex[:10]}@example.com"
    row = execute_returning(
        """
        INSERT INTO users (full_name, email, password_hash, role, email_verified, role_level)
        VALUES (:name, :email, :hash, 'singer', TRUE, 3)
        RETURNING id
        """,
        {"name": "Direct Mod Admin", "email": email, "hash": hash_password("Sectest123!")},
    )
    return row["id"], email, "Sectest123!"


def _bootstrap_direct_report():
    import uuid
    from app.database import execute_returning
    from app.auth import hash_password

    def _make_user(name):
        email = f"sectest_modreport_{uuid.uuid4().hex[:10]}@example.com"
        row = execute_returning(
            """
            INSERT INTO users (full_name, email, password_hash, role, email_verified)
            VALUES (:name, :email, :hash, 'singer', TRUE)
            RETURNING id
            """,
            {"name": name, "email": email, "hash": hash_password("Sectest123!")},
        )
        return row["id"]

    author_id = _make_user("Direct Mod Author")
    reporter_id = _make_user("Direct Mod Reporter")
    listing = execute_returning(
        """
        INSERT INTO listings (author_id, listing_type, title, description, state, city, country, is_active)
        VALUES (:author_id, 'seeking_singer', 'Direct Mod Listing', 'desc', 'Bayern', 'München', 'DE', TRUE)
        RETURNING id
        """,
        {"author_id": author_id},
    )
    report = execute_returning(
        """
        INSERT INTO listing_reports (listing_id, reporter_id, reason)
        VALUES (:listing_id, :reporter_id, 'A long enough reason for the check constraint.')
        RETURNING id
        """,
        {"listing_id": listing["id"], "reporter_id": reporter_id},
    )
    return report["id"], reporter_id


# --- HTTP routes ----------------------------------------------------------

def test_admin_can_accept_a_report_and_reporter_is_notified(client, capsys):
    listing_id, report_id, reporter_email, _ = _make_reported_listing(client)
    admin_id, admin_email, admin_password = _make_god_mode_admin(client)

    page = client.get("/admin")
    token = extract_csrf(page.text)
    resp = client.post(f"/admin/reports/{report_id}/accept", data={"csrf_token": token}, follow_redirects=False)
    assert resp.status_code == 303

    row = fetch_one("SELECT status FROM listing_reports WHERE id = :id", {"id": report_id})
    assert row["status"] == "accepted"

    captured = capsys.readouterr()
    assert reporter_email in captured.out
    # Default account language is German (site default, see CLAUDE.md).
    assert any(
        word in captured.out.lower()
        for word in ("reviewed", "revisada", "examiné", "geprüft", "esaminata")
    )


def test_admin_can_reject_a_report(client):
    listing_id, report_id, reporter_email, _ = _make_reported_listing(client)
    admin_id, admin_email, admin_password = _make_god_mode_admin(client)

    page = client.get("/admin")
    token = extract_csrf(page.text)
    resp = client.post(f"/admin/reports/{report_id}/reject", data={"csrf_token": token}, follow_redirects=False)
    assert resp.status_code == 303

    row = fetch_one("SELECT status FROM listing_reports WHERE id = :id", {"id": report_id})
    assert row["status"] == "rejected"


def test_admin_level_2_cannot_resolve_reports(client):
    """Só God Mode (nível 3) pode triar denúncias — mesmo nível exigido
    pra VER o dashboard de reports (ver require_level(request,
    LEVEL_GOD) em admin_dashboard())."""
    listing_id, report_id, _, _ = _make_reported_listing(client)

    admin_id, admin_email, admin_password = register_test_user(client, full_name="Report Mod Level2 Admin")
    execute("UPDATE users SET email_verified = TRUE, role_level = 2 WHERE id = :id", {"id": admin_id})
    login(client, admin_email, admin_password)

    resp = client.post(
        f"/admin/reports/{report_id}/accept",
        data={"csrf_token": "irrelevant-because-redirect-happens-first"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"

    row = fetch_one("SELECT status FROM listing_reports WHERE id = :id", {"id": report_id})
    assert row["status"] == "open"

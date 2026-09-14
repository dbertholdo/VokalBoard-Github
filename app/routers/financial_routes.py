"""
Red Zone (/financeiro) — sensitive settings and data, visible only to
those with role_level == 3 (god mode, see app/permissions.py):

- Capitalism Mode: turns billing for the entire site on/off (while
  off — the default — no one sees a banner, a price, or anything
  related to payment anywhere on the site).
- Subscription price (EUR/CHF).
- Internal financial dashboard: expenses (with recurrence and
  receipts), manual bank statement upload, analytics by country,
  monthly/annual closing with export to Excel/CSV/PDF.

Every action that CHANGES something sensitive (turning Capitalism
Mode on/off, changing the price) requires password reauthentication
(step-up auth) on top of already being logged in as god mode, and is
recorded in audit_log — even a failed password attempt. See
app/permissions.py.
"""
import csv
import io
import os
import re
from datetime import date, datetime

from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse, FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import fetch_all, fetch_one, execute, execute_returning
from app.render import render
from app.csrf import verify_csrf
from app.permissions import require_level, reauthenticate, log_audit_action, LEVEL_GOD
from app.receipts import save_receipt, RECEIPT_DIR

router = APIRouter()

EXPENSE_CATEGORIES = ["hosting", "domain", "software", "marketing", "legal_accounting", "other"]


def _god(request: Request) -> dict | None:
    return require_level(request, LEVEL_GOD)


def _cents_to_amount(cents: int) -> float:
    return round(cents / 100, 2)


def _amount_to_cents(amount_str: str) -> int | None:
    try:
        return round(float(amount_str.replace(",", ".")) * 100)
    except (ValueError, AttributeError):
        return None


# ------------------------------------------------------------------
# Red Zone — main page (Capitalism Mode + price)
# ------------------------------------------------------------------

@router.get("/financeiro", response_class=HTMLResponse)
def zona_vermelha(request: Request):
    god = _god(request)
    if not god:
        return RedirectResponse(url="/", status_code=303)

    settings_rows = fetch_all("SELECT key, value FROM system_settings")
    settings = {r["key"]: r["value"] for r in settings_rows}
    capitalismo_enabled = (settings.get("capitalismo_mode_enabled") or "false").lower() == "true"

    recent_audit = fetch_all(
        """
        SELECT al.action, al.details, al.ip_address, al.created_at, u.full_name AS actor_name
        FROM audit_log al
        LEFT JOIN users u ON u.id = al.actor_user_id
        ORDER BY al.created_at DESC
        LIMIT 20
        """
    )

    context = {
        "user": god,
        "capitalismo_enabled": capitalismo_enabled,
        "price_eur": _cents_to_amount(int(settings.get("subscription_price_eur_cents") or 590)),
        "price_chf": _cents_to_amount(int(settings.get("subscription_price_chf_cents") or 690)),
        "recent_audit": recent_audit,
        "error": request.query_params.get("error"),
        "saved": request.query_params.get("saved"),
    }
    return render(request, "zona_vermelha.html", context)


@router.post("/financeiro/toggle-capitalismo")
def toggle_capitalismo(request: Request, current_password: str = Form(...), csrf_token: str = Form(...)):
    god = _god(request)
    if not god:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    if not reauthenticate(request, god, current_password):
        log_audit_action(request, god, "toggle_capitalismo_failed_auth", "incorrect password")
        return RedirectResponse(url="/financeiro?error=senha_incorreta", status_code=303)

    current = fetch_one("SELECT value FROM system_settings WHERE key = 'capitalismo_mode_enabled'")
    is_enabled = (current["value"] if current else "false").lower() == "true"
    new_value = "false" if is_enabled else "true"

    execute(
        """
        UPDATE system_settings SET value = :value, updated_at = now(), updated_by_user_id = :uid
        WHERE key = 'capitalismo_mode_enabled'
        """,
        {"value": new_value, "uid": god["id"]},
    )
    log_audit_action(
        request, god, "toggle_capitalismo_mode",
        f"{'enabled' if new_value == 'true' else 'disabled'} by {god['full_name']}",
    )
    return RedirectResponse(url="/financeiro?saved=1", status_code=303)


@router.post("/financeiro/set-price")
def set_price(
    request: Request,
    current_password: str = Form(...),
    price_eur: str = Form(...),
    price_chf: str = Form(...),
    csrf_token: str = Form(...),
):
    god = _god(request)
    if not god:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    if not reauthenticate(request, god, current_password):
        log_audit_action(request, god, "set_price_failed_auth", "incorrect password")
        return RedirectResponse(url="/financeiro?error=senha_incorreta", status_code=303)

    eur_cents = _amount_to_cents(price_eur)
    chf_cents = _amount_to_cents(price_chf)
    if eur_cents is None or chf_cents is None or eur_cents <= 0 or chf_cents <= 0:
        return RedirectResponse(url="/financeiro?error=preco_invalido", status_code=303)

    execute(
        "UPDATE system_settings SET value = :v, updated_at = now(), updated_by_user_id = :uid WHERE key = 'subscription_price_eur_cents'",
        {"v": str(eur_cents), "uid": god["id"]},
    )
    execute(
        "UPDATE system_settings SET value = :v, updated_at = now(), updated_by_user_id = :uid WHERE key = 'subscription_price_chf_cents'",
        {"v": str(chf_cents), "uid": god["id"]},
    )
    log_audit_action(
        request, god, "set_subscription_price",
        f"EUR {_cents_to_amount(eur_cents)} / CHF {_cents_to_amount(chf_cents)} by {god['full_name']}",
    )
    return RedirectResponse(url="/financeiro?saved=1", status_code=303)


# ------------------------------------------------------------------
# Financial dashboard — expenses
# ------------------------------------------------------------------

@router.get("/financeiro/painel", response_class=HTMLResponse)
def painel_financeiro(request: Request):
    god = _god(request)
    if not god:
        return RedirectResponse(url="/", status_code=303)

    expenses = fetch_all(
        "SELECT * FROM expenses ORDER BY expense_date DESC LIMIT 200"
    )
    total_expenses_cents = fetch_one("SELECT COALESCE(SUM(amount_cents), 0) AS n FROM expenses")["n"]
    recurring = fetch_all("SELECT * FROM expenses WHERE is_recurring = TRUE ORDER BY expense_date DESC")

    by_category = fetch_all(
        "SELECT category, SUM(amount_cents) AS total_cents FROM expenses GROUP BY category ORDER BY total_cents DESC"
    )
    by_month = fetch_all(
        """
        SELECT to_char(expense_date, 'YYYY-MM') AS month, SUM(amount_cents) AS total_cents
        FROM expenses GROUP BY month ORDER BY month
        """
    )

    country_adoption = fetch_all(
        """
        SELECT u.country, COUNT(DISTINCT u.id) AS total_users,
               COUNT(DISTINCT s.user_id) FILTER (WHERE s.is_active) AS paying_users
        FROM users u
        LEFT JOIN subscriptions s ON s.user_id = u.id AND s.is_active = TRUE
        WHERE u.deleted_at IS NULL
        GROUP BY u.country
        ORDER BY paying_users DESC, total_users DESC
        """
    )

    closings = fetch_all("SELECT * FROM financial_closings ORDER BY period_start DESC LIMIT 24")

    context = {
        "user": god,
        "expenses": expenses,
        "total_expenses": _cents_to_amount(total_expenses_cents),
        "recurring": recurring,
        "categories": EXPENSE_CATEGORIES,
        "by_category_json": [{"label": r["category"], "value": _cents_to_amount(r["total_cents"])} for r in by_category],
        "by_month_json": [{"label": r["month"], "value": _cents_to_amount(r["total_cents"])} for r in by_month],
        "country_adoption": country_adoption,
        "closings": closings,
        "saved": request.query_params.get("saved"),
    }
    return render(request, "financial_dashboard.html", context)


@router.post("/financeiro/expenses")
async def create_expense(
    request: Request,
    description: str = Form(...),
    amount: str = Form(...),
    currency: str = Form("EUR"),
    category: str = Form("other"),
    expense_date: str = Form(...),
    is_recurring: str = Form(""),
    recurrence_interval: str = Form(""),
    csrf_token: str = Form(...),
    receipt: UploadFile | None = File(None),
):
    god = _god(request)
    if not god:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    amount_cents = _amount_to_cents(amount)
    if amount_cents is None or amount_cents <= 0 or category not in EXPENSE_CATEGORIES:
        return RedirectResponse(url="/financeiro/painel?error=dados_invalidos", status_code=303)

    try:
        parsed_date = datetime.strptime(expense_date, "%Y-%m-%d").date()
    except ValueError:
        return RedirectResponse(url="/financeiro/painel?error=data_invalida", status_code=303)

    receipt_url = None
    if receipt is not None and receipt.filename:
        receipt_url = await save_receipt(receipt)

    recurring_flag = is_recurring == "1"
    interval = recurrence_interval if recurring_flag and recurrence_interval in ("monthly", "yearly") else None

    execute(
        """
        INSERT INTO expenses (description, amount_cents, currency, category, expense_date,
                               is_recurring, recurrence_interval, receipt_url, created_by_user_id)
        VALUES (:d, :a, :c, :cat, :date, :rec, :interval, :receipt, :uid)
        """,
        {
            "d": description.strip()[:200], "a": amount_cents, "c": currency, "cat": category,
            "date": parsed_date, "rec": recurring_flag, "interval": interval,
            "receipt": receipt_url, "uid": god["id"],
        },
    )
    return RedirectResponse(url="/financeiro/painel?saved=1", status_code=303)


@router.post("/financeiro/expenses/{expense_id}/delete")
def delete_expense(request: Request, expense_id: int, csrf_token: str = Form(...)):
    god = _god(request)
    if not god:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)
    execute("DELETE FROM expenses WHERE id = :id", {"id": expense_id})
    return RedirectResponse(url="/financeiro/painel", status_code=303)


@router.get("/financeiro/expenses/export.csv")
def export_expenses_csv(request: Request):
    god = _god(request)
    if not god:
        return RedirectResponse(url="/", status_code=303)

    expenses = fetch_all("SELECT * FROM expenses ORDER BY expense_date DESC")
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["date", "description", "category", "amount", "currency", "recurring", "receipt"])
    for e in expenses:
        writer.writerow([
            e["expense_date"], e["description"], e["category"],
            _cents_to_amount(e["amount_cents"]), e["currency"],
            "yes" if e["is_recurring"] else "no", e["receipt_url"] or "",
        ])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=expenses_vokalboard.csv"},
    )


_RECEIPT_FILENAME_RE = re.compile(r"^[A-Za-z0-9_-]+\.(pdf|jpg|png|webp)$")


@router.get("/financeiro/receipts/{filename}")
def serve_receipt(request: Request, filename: str):
    # Unlike /avatars/{filename} (public), a receipt is a sensitive
    # financial document — requires god mode to view, same lock as the
    # rest of the Red Zone.
    god = _god(request)
    if not god:
        raise StarletteHTTPException(status_code=404)
    if not _RECEIPT_FILENAME_RE.match(filename):
        raise StarletteHTTPException(status_code=404)
    path = os.path.join(RECEIPT_DIR, filename)
    if not os.path.isfile(path):
        raise StarletteHTTPException(status_code=404)
    return FileResponse(path)


# ------------------------------------------------------------------
# Manual bank statement upload
# ------------------------------------------------------------------

@router.get("/financeiro/extrato", response_class=HTMLResponse)
def import_statement_form(request: Request):
    god = _god(request)
    if not god:
        return RedirectResponse(url="/", status_code=303)
    profiles = fetch_all("SELECT * FROM bank_import_profiles ORDER BY name")
    transactions = fetch_all("SELECT * FROM bank_transactions ORDER BY transaction_date DESC LIMIT 100")
    return render(request, "financial_import.html", {
        "user": god, "profiles": profiles, "transactions": transactions,
        "error": request.query_params.get("error"),
        "saved": request.query_params.get("saved"),
    })


@router.post("/financeiro/extrato/perfil")
def create_import_profile(
    request: Request,
    name: str = Form(...),
    column_date: str = Form(...),
    column_amount: str = Form(...),
    column_description: str = Form(...),
    date_format: str = Form("%d/%m/%Y"),
    csrf_token: str = Form(...),
):
    """Creates (or updates) the column mapping for a bank — done just
    once per bank, then reused for every CSV import from that same
    bank (see the module docstring and the changelog)."""
    god = _god(request)
    if not god:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    import json
    mapping = json.dumps({"date": column_date, "amount": column_amount, "description": column_description})

    existing = fetch_one("SELECT id FROM bank_import_profiles WHERE name = :n", {"n": name})
    if existing:
        execute(
            "UPDATE bank_import_profiles SET column_mapping = :m, date_format = :df WHERE id = :id",
            {"m": mapping, "df": date_format, "id": existing["id"]},
        )
    else:
        execute(
            "INSERT INTO bank_import_profiles (name, column_mapping, date_format) VALUES (:n, :m, :df)",
            {"n": name, "m": mapping, "df": date_format},
        )
    return RedirectResponse(url="/financeiro/extrato?saved=1", status_code=303)


@router.post("/financeiro/extrato/importar")
async def import_statement(
    request: Request,
    profile_id: int = Form(...),
    csrf_token: str = Form(...),
    statement_file: UploadFile = File(...),
):
    """Imports a CSV using the column mapping saved in
    bank_import_profiles. OFX support is left for a future
    iteration (see changelog) — for now, CSV with a mapping covers
    any bank, you just configure the profile once.
    """
    god = _god(request)
    if not god:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    profile = fetch_one("SELECT * FROM bank_import_profiles WHERE id = :id", {"id": profile_id})
    if not profile:
        return RedirectResponse(url="/financeiro/extrato?error=perfil_nao_encontrado", status_code=303)

    import json
    mapping = json.loads(profile["column_mapping"]) if isinstance(profile["column_mapping"], str) else profile["column_mapping"]

    content = await statement_file.read()
    if len(content) > 5 * 1024 * 1024:
        return RedirectResponse(url="/financeiro/extrato?error=arquivo_grande", status_code=303)

    try:
        text_content = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text_content = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text_content))
    imported = 0
    skipped = 0
    for row in reader:
        raw_date = row.get(mapping.get("date", ""), "")
        raw_amount = row.get(mapping.get("amount", ""), "")
        raw_description = row.get(mapping.get("description", ""), "")
        try:
            parsed_date = datetime.strptime(raw_date.strip(), profile["date_format"]).date()
        except (ValueError, AttributeError):
            skipped += 1
            continue
        amount_cents = _amount_to_cents(raw_amount)
        if amount_cents is None:
            skipped += 1
            continue
        execute(
            """
            INSERT INTO bank_transactions (import_profile_id, transaction_date, amount_cents, description)
            VALUES (:pid, :date, :amount, :desc)
            """,
            {"pid": profile_id, "date": parsed_date, "amount": amount_cents, "desc": raw_description.strip()[:300]},
        )
        imported += 1

    return RedirectResponse(
        url=f"/financeiro/extrato?saved=1&imported={imported}&skipped={skipped}", status_code=303
    )


# ------------------------------------------------------------------
# Monthly/annual closing + export
# ------------------------------------------------------------------

@router.post("/financeiro/fechamento")
def create_closing(
    request: Request,
    period_type: str = Form(...),
    period_start: str = Form(...),
    period_end: str = Form(...),
    csrf_token: str = Form(...),
):
    god = _god(request)
    if not god:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    if period_type not in ("monthly", "annual"):
        return RedirectResponse(url="/financeiro/painel?error=periodo_invalido", status_code=303)

    try:
        start = datetime.strptime(period_start, "%Y-%m-%d").date()
        end = datetime.strptime(period_end, "%Y-%m-%d").date()
    except ValueError:
        return RedirectResponse(url="/financeiro/painel?error=data_invalida", status_code=303)

    expenses_in_period = fetch_all(
        "SELECT * FROM expenses WHERE expense_date BETWEEN :s AND :e ORDER BY expense_date",
        {"s": start, "e": end},
    )
    total_expenses_cents = sum(e["amount_cents"] for e in expenses_in_period)

    revenue_in_period = fetch_all(
        "SELECT * FROM subscriptions WHERE started_at::date BETWEEN :s AND :e",
        {"s": start, "e": end},
    )
    total_revenue_cents = sum(r["price_paid_cents"] for r in revenue_in_period)

    import json
    snapshot = {
        "expenses": [
            {"date": str(e["expense_date"]), "description": e["description"], "category": e["category"],
             "amount": _cents_to_amount(e["amount_cents"])}
            for e in expenses_in_period
        ],
        "revenue_count": len(revenue_in_period),
    }

    row = execute_returning(
        """
        INSERT INTO financial_closings (period_type, period_start, period_end, total_revenue_cents,
                                          total_expenses_cents, snapshot, closed_by_user_id)
        VALUES (:pt, :s, :e, :rev, :exp, :snap, :uid)
        RETURNING id
        """,
        {
            "pt": period_type, "s": start, "e": end, "rev": total_revenue_cents,
            "exp": total_expenses_cents, "snap": json.dumps(snapshot), "uid": god["id"],
        },
    )
    log_audit_action(request, god, "create_financial_closing", f"{period_type} {start} to {end}")
    return RedirectResponse(url=f"/financeiro/painel?saved=1&closing_id={row['id']}", status_code=303)


@router.get("/financeiro/fechamento/{closing_id}/export.csv")
def export_closing_csv(request: Request, closing_id: int):
    god = _god(request)
    if not god:
        return RedirectResponse(url="/", status_code=303)
    closing = fetch_one("SELECT * FROM financial_closings WHERE id = :id", {"id": closing_id})
    if not closing:
        raise StarletteHTTPException(status_code=404)

    import json
    snapshot = closing["snapshot"] if isinstance(closing["snapshot"], dict) else json.loads(closing["snapshot"])

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Closing", closing["period_type"], str(closing["period_start"]), "to", str(closing["period_end"])])
    writer.writerow(["Total revenue (cents)", closing["total_revenue_cents"]])
    writer.writerow(["Total expenses (cents)", closing["total_expenses_cents"]])
    writer.writerow([])
    writer.writerow(["date", "description", "category", "amount"])
    for e in snapshot.get("expenses", []):
        writer.writerow([e["date"], e["description"], e["category"], e["amount"]])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=closing_{closing['period_start']}.csv"},
    )


@router.get("/financeiro/fechamento/{closing_id}/export.xlsx")
def export_closing_xlsx(request: Request, closing_id: int):
    god = _god(request)
    if not god:
        return RedirectResponse(url="/", status_code=303)
    closing = fetch_one("SELECT * FROM financial_closings WHERE id = :id", {"id": closing_id})
    if not closing:
        raise StarletteHTTPException(status_code=404)

    import json
    from openpyxl import Workbook

    snapshot = closing["snapshot"] if isinstance(closing["snapshot"], dict) else json.loads(closing["snapshot"])

    wb = Workbook()
    ws = wb.active
    ws.title = "Closing"
    ws.append(["Closing", closing["period_type"], str(closing["period_start"]), "to", str(closing["period_end"])])
    ws.append(["Total revenue (EUR)", _cents_to_amount(closing["total_revenue_cents"])])
    ws.append(["Total expenses (EUR)", _cents_to_amount(closing["total_expenses_cents"])])
    ws.append([])
    ws.append(["Date", "Description", "Category", "Amount"])
    for e in snapshot.get("expenses", []):
        ws.append([e["date"], e["description"], e["category"], e["amount"]])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=closing_{closing['period_start']}.xlsx"},
    )


@router.get("/financeiro/fechamento/{closing_id}/export.pdf")
def export_closing_pdf(request: Request, closing_id: int):
    god = _god(request)
    if not god:
        return RedirectResponse(url="/", status_code=303)
    closing = fetch_one("SELECT * FROM financial_closings WHERE id = :id", {"id": closing_id})
    if not closing:
        raise StarletteHTTPException(status_code=404)

    import json
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as pdf_canvas

    snapshot = closing["snapshot"] if isinstance(closing["snapshot"], dict) else json.loads(closing["snapshot"])

    buffer = io.BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "VokalBoard — Financial closing")
    y -= 25
    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Period: {closing['period_type']} — {closing['period_start']} to {closing['period_end']}")
    y -= 20
    c.drawString(50, y, f"Total revenue: EUR {_cents_to_amount(closing['total_revenue_cents'])}")
    y -= 16
    c.drawString(50, y, f"Total expenses: EUR {_cents_to_amount(closing['total_expenses_cents'])}")
    y -= 30

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Expenses for the period:")
    y -= 18
    c.setFont("Helvetica", 9)
    for e in snapshot.get("expenses", []):
        if y < 60:
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 9)
        c.drawString(50, y, f"{e['date']}  ·  {e['description'][:60]}  ·  {e['category']}  ·  EUR {e['amount']}")
        y -= 14

    c.save()
    buffer.seek(0)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=fechamento_{closing['period_start']}.pdf"},
    )


# ------------------------------------------------------------------
# Subscription page (stub) — exists only so it doesn't 404 if the
# Capitalism Mode banner gets turned on before the payment processor
# is actually connected (country/Paddle still an open question).
# ------------------------------------------------------------------

@router.get("/assinar", response_class=HTMLResponse)
def assinar_stub(request: Request):
    from app.auth import get_current_user
    user = get_current_user(request)
    return render(request, "assinar_stub.html", {"user": user})

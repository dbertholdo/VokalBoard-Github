"""
"Fale conosco" (contact) + "Reportar erro" (bug report) — P6
close-out (19/09/2026). Daniel's request ("Make p6 done"), scoped via
AskUserQuestion: one unified ticket inbox for both (see
app/support_tickets.py), reached from two different entry points:

  - GET/POST /contato — a normal contact form, members-only (same
    "logged in" gate as most of the site; no anonymous submission
    here, unlike the bug report below).
  - POST /support/report-bug — the floating "Reportar erro" button
    that appears on every page (see app/templates/base.html). Works
    whether or not the person is logged in (a bug can happen on a
    page a logged-out visitor can see), and auto-captures page_url/
    page_name/user_id via hidden fields filled in by a small inline
    script — only the description is typed by the person.

Both land in the same Admin inbox (/admin/tickets, God Mode+ —
require_level LEVEL_ADMIN, same floor as the rest of day-to-day admin
work; punishing/banning stays LEVEL_GOD elsewhere, this is just
reading and replying to a message).
"""
from urllib.parse import urlparse

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.auth import get_current_user
from app.render import render
from app.csrf import verify_csrf
from app.permissions import require_level, log_audit_action, LEVEL_ADMIN
from app.email import send_email
from app.email_localization import ticket_response_email
from app.support_tickets import (
    create_ticket,
    get_tickets,
    respond_ticket,
    TICKET_STATUSES,
    TICKETS_PAGE_SIZE,
)

router = APIRouter()


def _safe_redirect_target(page_url: str) -> str:
    """The bug-report button posts back the page's own URL (the
    inline script in base.html reads window.location.href, so this
    arrives as an ABSOLUTE URL) so the person lands where they were,
    with a confirmation flag appended. `page_url` is client-supplied —
    nothing stops a direct POST from sending anything — so only the
    PATH (+ query string) is ever reused as a redirect target, never
    the scheme/host, so this endpoint can't be turned into an open
    redirect to another site."""
    try:
        parsed = urlparse(page_url)
    except ValueError:
        return "/"
    path = parsed.path or "/"
    if not path.startswith("/") or path.startswith("//"):
        return "/"
    return f"{path}?{parsed.query}" if parsed.query else path


MIN_DESCRIPTION_LENGTH = 10
MAX_DESCRIPTION_LENGTH = 4000
MAX_SUBJECT_LENGTH = 200
MAX_PAGE_URL_LENGTH = 500
MAX_PAGE_NAME_LENGTH = 200


# ------------------------------------------------------------------
# Fale conosco (contact)
# ------------------------------------------------------------------

@router.get("/contato", response_class=HTMLResponse)
def contato_form(request: Request, sent: str = ""):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login?next=/contato", status_code=303)
    return render(request, "contato.html", {"user": user, "sent": sent})


@router.post("/contato")
def contato_submit(
    request: Request,
    subject: str = Form(""),
    description: str = Form(...),
    csrf_token: str = Form(...),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login?next=/contato", status_code=303)
    verify_csrf(request, csrf_token)

    description = description.strip()
    if len(description) < MIN_DESCRIPTION_LENGTH:
        return RedirectResponse(url="/contato?error=descricao_curta", status_code=303)

    create_ticket(
        "contact",
        description[:MAX_DESCRIPTION_LENGTH],
        user_id=user["id"],
        subject=subject.strip()[:MAX_SUBJECT_LENGTH] or None,
    )
    return RedirectResponse(url="/contato?sent=1", status_code=303)


# ------------------------------------------------------------------
# Reportar erro (bug report) — the floating button on every page.
# ------------------------------------------------------------------

@router.post("/support/report-bug")
def report_bug(
    request: Request,
    description: str = Form(...),
    page_url: str = Form(""),
    page_name: str = Form(""),
    csrf_token: str = Form(""),
):
    verify_csrf(request, csrf_token)
    user = get_current_user(request)

    redirect_base = _safe_redirect_target(page_url)
    separator = "&" if "?" in redirect_base else "?"

    description = description.strip()
    if len(description) < MIN_DESCRIPTION_LENGTH:
        return RedirectResponse(url=f"{redirect_base}{separator}bug_report_error=1", status_code=303)

    # page_url stored in the ticket keeps the FULL original value
    # (including query string) for the Admin's context — only the
    # redirect target above is restricted to same-site.
    create_ticket(
        "bug_report",
        description[:MAX_DESCRIPTION_LENGTH],
        user_id=user["id"] if user else None,
        page_url=page_url.strip()[:MAX_PAGE_URL_LENGTH] or None,
        page_name=page_name.strip()[:MAX_PAGE_NAME_LENGTH] or None,
    )
    # Redirects back to the page the report was filed from (the
    # button lives on every page, there's no dedicated "thank you"
    # screen — a query param flag lets that same page show a small
    # confirmation, same "blank redirect param" idiom used everywhere
    # else in this app).
    return RedirectResponse(url=f"{redirect_base}{separator}bug_report_sent=1", status_code=303)


# ------------------------------------------------------------------
# Admin inbox
# ------------------------------------------------------------------

@router.get("/admin/tickets", response_class=HTMLResponse)
def admin_tickets(request: Request, status: str = "open", type: str = "", page: int = 1):
    admin = require_level(request, LEVEL_ADMIN)
    if not admin:
        return RedirectResponse(url="/", status_code=303)

    status = status if status in TICKET_STATUSES or status == "" else "open"
    page = max(page, 1)
    offset = (page - 1) * TICKETS_PAGE_SIZE

    tickets = get_tickets(status=status, ticket_type=type, limit=TICKETS_PAGE_SIZE, offset=offset)

    context = {
        "user": admin,
        "tickets": tickets,
        "status": status,
        "type": type,
        "page": page,
        "has_next": len(tickets) == TICKETS_PAGE_SIZE,
        "has_prev": page > 1,
        "responded": request.query_params.get("responded"),
    }
    return render(request, "admin_tickets.html", context)


@router.post("/admin/tickets/{ticket_id}/respond")
def admin_respond_ticket(
    request: Request,
    ticket_id: int,
    admin_response: str = Form(...),
    resolve: str = Form(""),
    csrf_token: str = Form(...),
):
    admin = require_level(request, LEVEL_ADMIN)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    admin_response = admin_response.strip()
    if len(admin_response) < 2:
        return RedirectResponse(url="/admin/tickets?error=resposta_vazia", status_code=303)

    ticket = respond_ticket(ticket_id, admin_response, admin["id"], mark_resolved=(resolve == "1"))
    if not ticket:
        return RedirectResponse(url="/admin/tickets", status_code=303)

    # Notify whoever can be reached: the account's own email if the
    # ticket has a user_id, else the email typed while logged out (a
    # bug report can have neither — nothing to send in that case, the
    # response still gets saved and shown in the inbox).
    recipient_email = ticket.get("user_email") or ticket.get("email")
    if recipient_email:
        recipient_name = ticket.get("user_name") or "there"
        subject, html = ticket_response_email(
            ticket.get("preferred_language"), recipient_name, admin_response, resolve == "1",
        )
        send_email(recipient_email, subject, html)

    log_audit_action(request, admin, "admin_respond_ticket", f"ticket_id={ticket_id} resolved={resolve == '1'}")
    return RedirectResponse(url="/admin/tickets?responded=1", status_code=303)

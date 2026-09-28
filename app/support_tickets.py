"""
Support tickets — "Fale conosco" (contact) + "Reportar erro" (bug
report), P6 close-out (19/09/2026). Daniel's request ("Make p6
done"), scoped via AskUserQuestion: one unified inbox for both,
distinguished by `type`, mirroring the shape already used for
moderation (see app/moderation.py) — open -> answered/resolved,
resolved_by/resolved_at.

Entry points:
  - "Fale conosco" (/contato, app/routers/support_routes.py):
    requires login, a free-form subject + description.
  - "Reportar erro" (a floating button on every page, see
    app/templates/base.html): auto-captures page_url/page_name/
    user_id (if logged in) via a small inline script, only the
    description is typed by the person.

Answering a ticket (Admin, /admin/tickets) always saves the response
text and marks the ticket, and — when the ticket has an email to
reach (the submitter's account email, or the one they typed while
logged out) — sends it, mirroring report_resolved_email() in
app/email_localization.py.
"""
import re

from sqlalchemy import text

from app.database import engine, fetch_all, fetch_one, execute, execute_returning

TICKET_TYPES = ("contact", "bug_report")
TICKET_STATUSES = ("open", "answered", "resolved")

TICKETS_PAGE_SIZE = 30


def create_ticket(
    ticket_type: str,
    description: str,
    user_id: int | None = None,
    email: str | None = None,
    subject: str | None = None,
    page_url: str | None = None,
    page_name: str | None = None,
) -> int:
    """Inserts a new ticket. Caller is responsible for validating
    `ticket_type` against TICKET_TYPES and `description`'s minimum
    length before calling (same split of responsibility as
    listing_reports' report_listing() route)."""
    row = execute_returning(
        """
        INSERT INTO support_tickets (type, user_id, email, subject, description, page_url, page_name)
        VALUES (:type, :uid, :email, :subject, :description, :page_url, :page_name)
        RETURNING id
        """,
        {
            "type": ticket_type, "uid": user_id, "email": email, "subject": subject,
            "description": description, "page_url": page_url, "page_name": page_name,
        },
    )
    return row["id"]


def get_tickets(status: str = "", ticket_type: str = "", limit: int = TICKETS_PAGE_SIZE, offset: int = 0) -> list[dict]:
    """Tickets for the Admin inbox, most recent first. `status`/
    `ticket_type` empty = no filter on that column (same "blank means
    unfiltered" convention used across the Red Zone's period
    filters)."""
    clause = ""
    params: dict = {"limit": limit, "offset": offset}
    if status in TICKET_STATUSES:
        clause += " AND st.status = :status"
        params["status"] = status
    if ticket_type in TICKET_TYPES:
        clause += " AND st.type = :ticket_type"
        params["ticket_type"] = ticket_type

    return fetch_all(
        f"""
        SELECT st.id, st.type, st.status, st.subject, st.description, st.page_url, st.page_name,
               st.email, st.admin_response, st.resolved_at, st.created_at,
               st.user_id, u.full_name AS user_name, u.email AS user_email, u.preferred_language,
               resolver.full_name AS resolved_by_name
        FROM support_tickets st
        LEFT JOIN users u ON u.id = st.user_id
        LEFT JOIN users resolver ON resolver.id = st.resolved_by_user_id
        WHERE TRUE {clause}
        ORDER BY (st.status = 'open') DESC, st.created_at DESC
        LIMIT :limit OFFSET :offset
        """,  # nosec B608 - clause is a fixed literal built only from the two branches above, values are always parameters
        params,
    )


def count_open_tickets() -> int:
    row = fetch_one("SELECT COUNT(*) AS n FROM support_tickets WHERE status = 'open'")
    return row["n"] if row else 0


def get_ticket(ticket_id: int) -> dict | None:
    return fetch_one(
        """
        SELECT st.*, u.full_name AS user_name, u.email AS user_email, u.preferred_language
        FROM support_tickets st
        LEFT JOIN users u ON u.id = st.user_id
        WHERE st.id = :id
        """,
        {"id": ticket_id},
    )


def respond_ticket(ticket_id: int, admin_response: str, admin_id: int, mark_resolved: bool) -> dict | None:
    """Saves the Admin's reply and moves the ticket to 'answered' (a
    reply without closing it) or 'resolved' (closing it). Returns the
    ticket row (with the fields needed to notify the submitter, if
    any) as it was BEFORE this update, or None if it doesn't exist —
    same "return what's needed to notify" pattern as
    moderation.resolve_report()."""
    ticket = get_ticket(ticket_id)
    if not ticket:
        return None

    new_status = "resolved" if mark_resolved else "answered"
    execute(
        """
        UPDATE support_tickets
        SET admin_response = :response, status = :status,
            resolved_by_user_id = :admin_id, resolved_at = now()
        WHERE id = :id
        """,
        {"response": admin_response.strip()[:2000], "status": new_status, "admin_id": admin_id, "id": ticket_id},
    )
    return ticket


# ---------------------------------------------------------------------------
# Spam (2026-09-28, HANDOFF 3c). Computed live, never stored: a ticket is
# "likely spam" when at least two signals agree. Admins confirm by deleting.
# ---------------------------------------------------------------------------

_SPAM_WORDS = re.compile(
    r"\b(seo|backlinks?|casino|crypto|bitcoin|forex|viagra|cialis|loan|guest ?posts?|link ?building"
    r"|rank(ing)? (your|on)|traffic to your|web ?design services|marketing services|lead generation"
    r"|whatsapp me|telegram me|dear (sir|webmaster))\b",
    re.IGNORECASE,
)
_LINK = re.compile(r"https?://|www\.", re.IGNORECASE)


def spam_signals(ticket: dict) -> list[str]:
    text = f"{ticket.get('subject') or ''} {ticket.get('description') or ''}"
    anonymous = not ticket.get("user_id")
    signals = []
    if len(_LINK.findall(text)) >= (1 if anonymous else 2):
        signals.append("links")
    if _SPAM_WORDS.search(text):
        signals.append("spam words")
    if anonymous:
        signals.append("anonymous")
    return signals


def likely_spam(ticket: dict) -> bool:
    return len(spam_signals(ticket)) >= 2


def get_likely_spam_tickets(limit: int = 500) -> list[dict]:
    return [t for t in get_tickets(limit=limit) if likely_spam(t)]


def delete_tickets(ticket_ids: list[int]) -> int:
    if not ticket_ids:
        return 0
    with engine.begin() as conn:
        return conn.execute(text("DELETE FROM support_tickets WHERE id = ANY(:ids)"), {"ids": list(ticket_ids)}).rowcount

"""
Periodic mails — P0 backlog item ("define daily/weekly/monthly
reports"), built as a follow-up request from Daniel (19/09/2026):
"Buttons to edit this Periodic Mails. This will change the body only
of the email template of the other sub menu. I need a way to build
other periodic mails. See the active ones. Edit, delete or pause
them."

"The other sub menu" is /admin/emails (app/email_layout.py) — the
shared layout (logo/accent/signature/footer) that already wraps every
automatic email on the site. Each periodic mail only edits its own
BODY (name, subject, HTML body, and how often it repeats); the
envelope around it is the one already governed by that other screen,
same as every other email sent by send_email() (app/email.py).

Recipients: fixed to the admin team (role_level >= 2) for this
delivery, confirmed with Daniel via AskUserQuestion. Deliberately NOT
a general segmented-broadcast tool — that's the "segmented email
sending" item Daniel already chose to skip during the P6 close-out
(2026-09-19 entry, AI_CHANGELOG.md), blocked on a real Subscription/
payment system that doesn't exist yet. `recipient_scope` is still a
real column (not a hardcoded constant) so a second scope (e.g. "all
verified users") can be added later without another migration — but
adding one is a product decision for Daniel to make explicitly, not
something to infer from this ticket.

Scheduling: `next_send_at` is computed in SQL (`now() + interval`),
not in Python — Postgres's interval arithmetic already handles
day/week/month math (including month-length differences) correctly,
so there's no need for a date library. The worker
(app/periodic_mail_worker.py) that actually sends these follows the
same advisory-lock/--once/--dry-run/loop shape as every other worker
in this app (see app/invitation_expiry_worker.py and friends) — lock
id 8305 (8301-8304 already taken, see urgent_listing_reminder_worker.py's
docstring for the running list).
"""
import re
from html import escape

from app.database import fetch_all, fetch_one, execute, execute_returning

FREQUENCIES = ("daily", "weekly", "monthly")
_FREQUENCY_INTERVAL_SQL = {
    "daily": "interval '1 day'",
    "weekly": "interval '7 days'",
    "monthly": "interval '1 month'",
}

NAME_MAX_LENGTH = 200
SUBJECT_MAX_LENGTH = 300
BODY_MAX_LENGTH = 20000  # same cap as the shared template's "Código" tab (app/email_layout.py)

# Same light precaution as the shared template's raw-HTML tab (see
# app/email_layout.py's module docstring for why <script> is the only
# thing stripped): this is admin-only input (role_level >= 2, same
# trust level as Adminer access), not run through the post-body
# sanitizer (app/richtext.py), which doesn't allow the markup an
# email body reasonably wants (inline style, etc.).
_SCRIPT_TAG_RE = re.compile(r"<\s*script\b[^>]*>.*?<\s*/\s*script\s*>", re.IGNORECASE | re.DOTALL)


def _clean_body_html(body_html: str) -> str:
    return _SCRIPT_TAG_RE.sub("", body_html).strip()


def list_periodic_mails() -> list[dict]:
    """Newest first, active before paused within that — matches the
    support-ticket inbox's own ordering idiom (open work first)."""
    return fetch_all(
        """
        SELECT pm.*, u.full_name AS created_by_name
        FROM periodic_mails pm
        LEFT JOIN users u ON u.id = pm.created_by_user_id
        ORDER BY pm.is_active DESC, pm.created_at DESC
        """
    )


def get_periodic_mail(mail_id: int) -> dict | None:
    return fetch_one("SELECT * FROM periodic_mails WHERE id = :id", {"id": mail_id})


def create_periodic_mail(name: str, subject: str, body_html: str, frequency: str, admin_id: int) -> int | None:
    """Returns the new row's id, or None if validation fails (caller
    turns that into a redirect with an error flag — see
    app/routers/admin_routes.py). First send happens at the next
    natural occurrence (now + one interval), not immediately — an
    Admin who just created a "weekly report" wouldn't expect one to
    go out the second they hit Save."""
    name = name.strip()[:NAME_MAX_LENGTH]
    subject = subject.strip()[:SUBJECT_MAX_LENGTH]
    body_html = _clean_body_html(body_html)[:BODY_MAX_LENGTH]
    if frequency not in FREQUENCIES or not name or not subject or not body_html:
        return None

    row = execute_returning(
        f"""
        INSERT INTO periodic_mails (name, subject, body_html, frequency, next_send_at, created_by_user_id, updated_by_user_id)
        VALUES (:name, :subject, :body_html, :frequency, now() + {_FREQUENCY_INTERVAL_SQL[frequency]}, :admin_id, :admin_id)
        RETURNING id
        """,  # nosec B608 - _FREQUENCY_INTERVAL_SQL[frequency] is one of 3 fixed literal
              # strings from the dict above (frequency is validated against FREQUENCIES
              # just above), never the raw request value; all real values are bound params.
        {"name": name, "subject": subject, "body_html": body_html, "frequency": frequency, "admin_id": admin_id},
    )
    return row["id"] if row else None


def update_periodic_mail(mail_id: int, name: str, subject: str, body_html: str, frequency: str, admin_id: int) -> bool:
    """Editing content (name/subject/body) never touches the
    schedule. Changing the FREQUENCY does reschedule next_send_at —
    from now, using the new interval — since the old countdown no
    longer means anything once the interval itself changed."""
    name = name.strip()[:NAME_MAX_LENGTH]
    subject = subject.strip()[:SUBJECT_MAX_LENGTH]
    body_html = _clean_body_html(body_html)[:BODY_MAX_LENGTH]
    if frequency not in FREQUENCIES or not name or not subject or not body_html:
        return False

    existing = get_periodic_mail(mail_id)
    if not existing:
        return False

    if existing["frequency"] == frequency:
        execute(
            """
            UPDATE periodic_mails
            SET name = :name, subject = :subject, body_html = :body_html,
                updated_at = now(), updated_by_user_id = :admin_id
            WHERE id = :id
            """,
            {"name": name, "subject": subject, "body_html": body_html, "admin_id": admin_id, "id": mail_id},
        )
    else:
        execute(
            f"""
            UPDATE periodic_mails
            SET name = :name, subject = :subject, body_html = :body_html, frequency = :frequency,
                next_send_at = now() + {_FREQUENCY_INTERVAL_SQL[frequency]},
                updated_at = now(), updated_by_user_id = :admin_id
            WHERE id = :id
            """,  # nosec B608 - same fixed-literal interval lookup as create_periodic_mail() above.
            {"name": name, "subject": subject, "body_html": body_html, "frequency": frequency, "admin_id": admin_id, "id": mail_id},
        )
    return True


def set_periodic_mail_active(mail_id: int, is_active: bool, admin_id: int) -> bool:
    """Pause/resume. Deliberately does NOT touch next_send_at either
    way: pausing just stops the worker from picking it up (it only
    ever looks at is_active = TRUE rows); resuming a mail whose
    next_send_at has already passed while paused means the worker
    sends it on its very next tick (a "catch up once, then back on
    schedule" behavior) rather than silently skipping the gap — the
    simplest rule that doesn't need a special case."""
    result = execute_returning(
        "UPDATE periodic_mails SET is_active = :is_active, updated_at = now(), updated_by_user_id = :admin_id WHERE id = :id RETURNING id",
        {"is_active": is_active, "admin_id": admin_id, "id": mail_id},
    )
    return result is not None


def delete_periodic_mail(mail_id: int) -> bool:
    result = execute_returning("DELETE FROM periodic_mails WHERE id = :id RETURNING id", {"id": mail_id})
    return result is not None


def render_body_preview(body_html: str) -> str:
    """Used only for the create/edit form's live-ish preview iframe —
    same idea as the shared-layout screen's preview (app/email_layout.py),
    just for this one mail's own body instead of the sample text."""
    from app.email_layout import render_email

    return render_email(body_html or "<p><em>(empty)</em></p>")

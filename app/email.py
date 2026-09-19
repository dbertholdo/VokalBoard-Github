"""
Email sending, with two "backends" swappable via environment variable:

- EMAIL_BACKEND=console (default): doesn't actually send anything,
  just prints the email content to the terminal/log. Perfect for
  developing and testing locally without needing real credentials —
  the verification/password-reset link shows up right in the server
  log.
- EMAIL_BACKEND=resend: actually sends via the Resend API
  (https://resend.com), which has a free tier for low volume. Set
  RESEND_API_KEY and EMAIL_FROM in .env when using it.

Switching email provider in the future (Postmark, SendGrid, etc.) is
just a matter of adding another `elif` here — the rest of the
application always calls the same `send_email()` function and doesn't
even know which backend is active.
"""
import base64
import os

import httpx

from app.email_layout import render_email

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "console")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "VokalBoard <onboarding@resend.dev>")


def send_email(to: str, subject: str, html: str, attachments: list[dict] | None = None) -> None:
    """attachments (optional): list of {"filename": str, "content": bytes}.
    Used by the Rechnungmaker (P4) to deliver the PDF by e-mail without ever
    storing it — the bytes only ever exist in memory, for this one call.

    `html` is only ever the BODY (paragraphs, links — whatever the
    caller built) — every call, from every one of the ~16 send sites
    across the app, is wrapped here with the shared layout (logo,
    accent color, signature, footer) editable at /admin/emails. This
    is deliberately the ONE place that does this wrapping — see
    app/email_layout.py — so changing the layout there changes every
    automatic email at once, without touching any of the callers.
    """
    html = render_email(html)
    if EMAIL_BACKEND == "resend" and not RESEND_API_KEY:
        # Bug found 19/09/2026: EMAIL_BACKEND=resend with no RESEND_API_KEY
        # silently fell through to the console backend below — nothing was
        # ever sent, and nothing in the log said why. This is exactly what
        # happened in production: confirmation/reset emails "worked" (no
        # error, no failed request) but never left the server. Now it's
        # loud instead of silent.
        print(
            "[email] WARNING: EMAIL_BACKEND=resend but RESEND_API_KEY is empty — "
            f"falling back to console (nothing sent) for the email to {to}. "
            "Set RESEND_API_KEY in the environment to actually send."
        )
    if EMAIL_BACKEND == "resend" and RESEND_API_KEY:
        try:
            payload = {"from": EMAIL_FROM, "to": [to], "subject": subject, "html": html}
            if attachments:
                payload["attachments"] = [
                    {"filename": a["filename"], "content": base64.b64encode(a["content"]).decode("ascii")}
                    for a in attachments
                ]
            response = httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json=payload,
                timeout=10,
            )
            # httpx only raises HTTPError on a network/connection problem —
            # an API rejection (invalid key, a test domain that only sends
            # to the account owner, etc.) comes back as a normal HTTP
            # response (4xx/5xx) that used to slip through here unnoticed,
            # leaving no trace in the log. Now this is visible.
            if response.status_code >= 400:
                print(f"[email] Resend rejected the send to {to} (HTTP {response.status_code}): {response.text}")
            else:
                print(f"[email] sent via Resend to {to} (HTTP {response.status_code})")
        except httpx.HTTPError as exc:
            # Don't fail the user's request because of an email-sending problem.
            print(f"[email] failed to send via Resend: {exc}")
    else:
        attachment_note = f"\nAttachments: {[a['filename'] for a in attachments]}" if attachments else ""
        print(
            "\n---- EMAIL (console backend — set EMAIL_BACKEND=resend to actually send) ----\n"
            f"To: {to}\nSubject: {subject}{attachment_note}\n\n{html}\n"
            "-------------------------------------------------------------------------------------\n"
        )

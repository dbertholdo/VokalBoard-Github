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
import os

import httpx

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "console")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "VokalBoard <onboarding@resend.dev>")


def send_email(to: str, subject: str, html: str) -> None:
    if EMAIL_BACKEND == "resend" and RESEND_API_KEY:
        try:
            response = httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={"from": EMAIL_FROM, "to": [to], "subject": subject, "html": html},
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
        print(
            "\n---- EMAIL (console backend — set EMAIL_BACKEND=resend to actually send) ----\n"
            f"To: {to}\nSubject: {subject}\n\n{html}\n"
            "-------------------------------------------------------------------------------------\n"
        )

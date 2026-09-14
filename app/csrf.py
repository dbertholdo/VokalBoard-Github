"""
CSRF (Cross-Site Request Forgery) protection — a manual, simple
implementation of the "synchronizer token" pattern, with no external
libraries, so you can see exactly how it works.

The idea, in short:
1. When someone loads a page with a form, we generate a random
   token and store it in their session (signed cookie).
2. The same token is embedded hidden in the form (<input type="hidden">).
3. When the form is submitted (POST), we compare the token that came
   with the form against the one stored in the session. We only let
   the action proceed if the two match.

Why this matters: a session cookie alone does NOT prove that it was
you who clicked the button — the browser sends cookies automatically
on any request to the domain, including one triggered by a malicious
site in another tab (e.g. a hidden <form> on another site that submits
a POST to "yourapp.com/listings/5/delete"). Since the CSRF token only
exists within your own page's HTML (the malicious site has no way to
read or guess this value), it acts as proof that the form really came
from your site.
"""
import secrets

from fastapi import Request, HTTPException

SESSION_KEY = "csrf_token"


def get_or_create_csrf_token(request: Request) -> str:
    token = request.session.get(SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[SESSION_KEY] = token
    return token


def verify_csrf(request: Request, submitted_token: str) -> None:
    """Raises a 400 error if the token doesn't match. Call this at the start of every POST."""
    expected = request.session.get(SESSION_KEY)
    if not expected or not submitted_token or not secrets.compare_digest(expected, submitted_token):
        raise HTTPException(status_code=400, detail="Invalid or missing CSRF token. Please reload the page and try again.")

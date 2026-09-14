"""
Two-layer anti-bot protection, following the same "pluggable backend"
pattern already used in app/email.py (console vs. Resend):

1. Honeypot (always active, ZERO configuration): an extra field in the
   form (see HONEYPOT_FIELD), hidden via CSS off-screen (not
   display:none — screen readers cope better with an "off-screen"
   field that still exists in the DOM but stays invisible to any real
   human). Simple bots fill in ALL fields of a form automatically, so
   if this field comes back filled in, it's almost certainly a bot.
   This alone already blocks most generic bots, with no need for any
   external key/service.

2. Cloudflare Turnstile (optional, needs your own keys): an "almost
   invisible" challenge (usually doesn't even require a click) that
   confirms the submitter is human, without Google reCAPTCHA's privacy
   issues (no cross-site tracking cookies). Only turns on if you
   configure TURNSTILE_SITE_KEY and TURNSTILE_SECRET_KEY in .env (see
   .env.example) — without that, the site stays protected by the
   honeypot alone, which is already a real barrier against the most
   common case (generic bots, not people specifically trying to abuse
   your site).

How to get Turnstile keys (free): create an account at
https://dash.cloudflare.com/ (no need to migrate your domain there,
Turnstile works independently) → Turnstile → Add site → copy the "Site
Key" (public, goes in the HTML) and the "Secret Key" (private, .env only).
"""
import os
import httpx

# Name of the trap field. Deliberately a "tempting" name for
# autofill/bots (it looks like a real field) — see the
# ".honeypot-field" CSS in style.css that hides it from humans.
HONEYPOT_FIELD = "website"

TURNSTILE_SITE_KEY = os.getenv("TURNSTILE_SITE_KEY", "")
TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY", "")
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def captcha_enabled() -> bool:
    """True only when both Turnstile keys are configured."""
    return bool(TURNSTILE_SITE_KEY and TURNSTILE_SECRET_KEY)


def is_bot(honeypot_value: str) -> bool:
    """Filled-in honeypot = almost certainly a bot. Always checked, with or without Turnstile."""
    return bool((honeypot_value or "").strip())


def verify_turnstile(token: str) -> bool:
    """
    Verifies the Turnstile widget token with Cloudflare.

    If Turnstile isn't configured (missing either key), it doesn't
    block anyone — the honeypot alone remains the protection in that
    case, so as not to block sign-up for someone just running the
    project locally without configuring anything extra.
    """
    if not captcha_enabled():
        return True
    if not token:
        return False
    try:
        resp = httpx.post(
            TURNSTILE_VERIFY_URL,
            data={"secret": TURNSTILE_SECRET_KEY, "response": token},
            timeout=5.0,
        )
        return bool(resp.json().get("success"))
    except Exception:
        # Cloudflare being down shouldn't block anyone's sign-up/password
        # reset — let it through (the honeypot is still active).
        return True

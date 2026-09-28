"""E-mail identity helpers for referral anti-fraud (2026-09-28).

`identity_email()` maps address variants that reach the same inbox to one
form, so "a.b+1@gmail.com" and "ab@googlemail.com" count as one person.
`is_disposable()` spots throwaway-inbox domains. Both are used only to
decide referral rewards; signups and logins keep the address as typed.
"""

_GMAIL_DOMAINS = {"gmail.com", "googlemail.com"}

# Well-known throwaway-inbox services. Not exhaustive — extend as abuse shows up.
DISPOSABLE_DOMAINS = frozenset({
    "10minutemail.com", "20minutemail.com", "33mail.com", "burnermail.io", "byom.de",
    "discard.email", "dispostable.com", "einrot.com", "emailfake.com", "emailondeck.com",
    "fakeinbox.com", "getnada.com", "grr.la", "guerrillamail.com", "guerrillamail.de",
    "guerrillamail.net", "guerrillamail.org", "guerrillamailblock.com", "inboxkitten.com",
    "mailcatch.com", "maildrop.cc", "mailinator.com", "mailnesia.com", "mailpoof.com",
    "minuteinbox.com", "mintemail.com", "moakt.com", "mohmal.com", "muellmail.com",
    "mytemp.email", "pokemail.net", "sharklasers.com", "spam4.me", "spambog.com",
    "spamgourmet.com", "temp-mail.io", "temp-mail.org", "tempinbox.com", "tempmail.com",
    "tempmailo.com", "tempr.email", "throwawaymail.com", "trashmail.com", "trashmail.de",
    "wegwerfemail.de", "wegwerfmail.de", "yopmail.com", "yopmail.fr", "1secmail.com",
    "1secmail.net",
})


def _split(email: str) -> tuple[str, str]:
    local, _, domain = (email or "").strip().lower().rpartition("@")
    return local, domain


def identity_email(email: str) -> str:
    """Lower-case; drops a "+tag" everywhere; Gmail also ignores dots and
    googlemail.com is gmail.com."""
    local, domain = _split(email)
    if not local:
        return (email or "").strip().lower()
    local = local.split("+", 1)[0]
    if domain in _GMAIL_DOMAINS:
        local, domain = local.replace(".", ""), "gmail.com"
    return f"{local}@{domain}"


def is_disposable(email: str) -> bool:
    domain = _split(email)[1]
    return any(domain == d or domain.endswith("." + d) for d in DISPOSABLE_DOMAINS)

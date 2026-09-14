"""
Determine the IP of whoever is making the request.

Behind a platform like Railway (or any reverse proxy),
`request.client.host` is the IP of the proxy ITSELF, not the real
person — the real IP comes in the `X-Forwarded-For` header, which the
proxy adds. Used only by the mass-signup throttle (see
app/register_throttle.py); it is NEVER stored permanently anywhere,
only compared against a temporary counter.
"""
from fastapi import Request


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        # The header may contain a list "client, proxy1, proxy2" —
        # the first item in the list is always closest to the browser.
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

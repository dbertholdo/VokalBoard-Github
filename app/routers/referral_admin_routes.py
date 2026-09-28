"""Admin review of referral rewards (2026-09-28, HANDOFF item 3).

Flagged referrals (e.g. several sign-ups from one IP) wait here. Approve
pays the Nota, Reject closes it unpaid, Reverse takes a paid Nota back.
Each action re-checks the admin's password and is written to audit_log
(CLAUDE.md §2.4). Rules live in app/referrals.py."""
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.csrf import verify_csrf
from app.permissions import LEVEL_ADMIN, log_audit_action, reauthenticate, require_level
from app.referrals import (
    REVIEW_STATUSES, admin_approve, admin_reject, admin_reverse, list_referral_events, rewards_v2_enabled,
)
from app.render import render

router = APIRouter()

_ACTIONS = {"approve": admin_approve, "reject": admin_reject, "reverse": admin_reverse}


@router.get("/admin/referrals", response_class=HTMLResponse)
def referral_review(request: Request, status: str = "flagged"):
    admin = require_level(request, LEVEL_ADMIN)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    status = status if status in REVIEW_STATUSES or status == "" else "flagged"
    return render(request, "admin_referrals.html", {
        "user": admin, "status": status, "statuses": REVIEW_STATUSES,
        "events": list_referral_events(status), "enabled": rewards_v2_enabled(),
        "done": request.query_params.get("done"), "failed": request.query_params.get("failed"),
    })


@router.post("/admin/referrals/{event_id}/{action}")
def referral_action(request: Request, event_id: int, action: str, csrf_token: str = Form(""),
                    current_password: str = Form(""), status: str = Form("flagged")):
    admin = require_level(request, LEVEL_ADMIN)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)
    back = f"/admin/referrals?status={status if status in REVIEW_STATUSES else ''}"
    handler = _ACTIONS.get(action)
    if not handler:
        return RedirectResponse(url=back + "&failed=1", status_code=303)
    if not reauthenticate(request, admin, current_password):
        log_audit_action(request, admin, f"referral_{action}_failed_auth", f"referral_event_id={event_id}")
        return RedirectResponse(url=back + "&failed=auth", status_code=303)
    if not handler(event_id, admin["id"]):
        return RedirectResponse(url=back + "&failed=1", status_code=303)
    log_audit_action(request, admin, f"referral_{action}", f"referral_event_id={event_id}")
    return RedirectResponse(url=back + f"&done={action}", status_code=303)

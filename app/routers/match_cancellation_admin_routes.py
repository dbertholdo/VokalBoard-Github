"""Admin review of Match cancellations (2026-09-28, HANDOFF 5b).

Each cancellation waits here with its reason. Warn = a warning for whoever
cancelled (3 warnings = 30 days without new Matches, rules in
app/match_cancellation.py); Dismiss = no action; Lift block = end a block
early (Daniel: "don't forget the option to unban"). Warn and Lift block
re-check the admin's password; every action is written to audit_log."""
from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.csrf import verify_csrf
from app.match_cancellation import (
    WARNINGS_PER_BLOCK, dismiss, feature_ready, lift_block, list_blocked_users, list_cancellations, warn,
)
from app.notifications import notify_match_warning
from app.permissions import LEVEL_ADMIN, log_audit_action, reauthenticate, require_level
from app.render import render

router = APIRouter()


@router.get("/admin/cancellations", response_class=HTMLResponse)
def cancellations_page(request: Request, show: str = "open"):
    admin = require_level(request, LEVEL_ADMIN)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    show = "all" if show == "all" else "open"
    return render(request, "admin_cancellations.html", {
        "user": admin, "show": show, "enabled": feature_ready(),
        "cancellations": list_cancellations(open_only=show == "open"),
        "blocked_users": list_blocked_users(), "warnings_per_block": WARNINGS_PER_BLOCK,
        "done": request.query_params.get("done"), "failed": request.query_params.get("failed"),
    })


def _password_ok(request: Request, admin: dict, password: str, action: str, detail: str) -> bool:
    if reauthenticate(request, admin, password):
        return True
    log_audit_action(request, admin, f"{action}_failed_auth", detail)
    return False


@router.post("/admin/cancellations/{cancellation_id}/warn")
def warn_cancellation(request: Request, background_tasks: BackgroundTasks, cancellation_id: int,
                      csrf_token: str = Form(""), current_password: str = Form(""), note: str = Form("")):
    admin = require_level(request, LEVEL_ADMIN)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)
    if not _password_ok(request, admin, current_password, "match_warning", f"cancellation_id={cancellation_id}"):
        return RedirectResponse(url="/admin/cancellations?failed=auth", status_code=303)
    result = warn(cancellation_id, admin["id"], note)
    if not result:
        return RedirectResponse(url="/admin/cancellations?failed=1", status_code=303)
    log_audit_action(request, admin, "match_warning",
                     f"cancellation_id={cancellation_id} user_id={result['user_id']} warnings={result['warnings']}"
                     + (f" blocked_until={result['blocked_until']:%Y-%m-%d}" if result["blocked_until"] else ""))
    background_tasks.add_task(notify_match_warning, str(request.base_url), result["user_id"],
                              result["towards_next_block"], result["blocked_until"])
    return RedirectResponse(url="/admin/cancellations?done=" + ("blocked" if result["blocked_until"] else "warned"), status_code=303)


@router.post("/admin/cancellations/{cancellation_id}/dismiss")
def dismiss_cancellation(request: Request, cancellation_id: int, csrf_token: str = Form("")):
    admin = require_level(request, LEVEL_ADMIN)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)
    if not dismiss(cancellation_id, admin["id"]):
        return RedirectResponse(url="/admin/cancellations?failed=1", status_code=303)
    log_audit_action(request, admin, "match_cancellation_dismissed", f"cancellation_id={cancellation_id}")
    return RedirectResponse(url="/admin/cancellations?done=dismissed", status_code=303)


@router.post("/admin/match-blocks/{user_id}/lift")
def lift_match_block(request: Request, user_id: int, csrf_token: str = Form(""), current_password: str = Form("")):
    admin = require_level(request, LEVEL_ADMIN)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)
    if not _password_ok(request, admin, current_password, "match_block_lifted", f"user_id={user_id}"):
        return RedirectResponse(url="/admin/cancellations?failed=auth", status_code=303)
    if not lift_block(user_id):
        return RedirectResponse(url="/admin/cancellations?failed=1", status_code=303)
    log_audit_action(request, admin, "match_block_lifted", f"user_id={user_id}")
    return RedirectResponse(url="/admin/cancellations?done=unblocked", status_code=303)

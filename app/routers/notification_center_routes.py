"""
Central de Notificações (19/09/2026, task #50) — see
app/notification_center.py for the service layer and its own module
docstring for the design agreed with Daniel. Kept as its own router
(CLAUDE.md "Fat Routers Proibidos") rather than folded into
messages_routes.py or listings_routes.py — this is its own concern,
not messaging or listing CRUD.
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse

from app.auth import get_current_user
from app.csrf import verify_csrf
from app.notification_center import mark_as_read, mark_all_as_read

router = APIRouter()


@router.get("/notifications/{notification_id}/open")
def open_notification(request: Request, notification_id: int):
    """Marks one notification read, then sends the viewer to whatever
    it points at — "opening" a notification is exactly those two
    steps (see mark_as_read()'s docstring)."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    link_url = mark_as_read(user["id"], notification_id)
    return RedirectResponse(url=link_url or "/", status_code=303)


@router.post("/notifications/mark-all-read")
def mark_all_read(request: Request, csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    mark_all_as_read(user["id"])
    referer = request.headers.get("referer") or "/"
    return RedirectResponse(url=referer, status_code=303)

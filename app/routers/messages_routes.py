"""
Messenger pages (docs/specs/MESSENGER.md). Thin by design — every rule
lives in app/messenger.py. Old URLs (/messages/sent, /messages/trash,
/messages/{id}) redirect into the conversation view so links in old
e-mails and notifications keep working.
"""
from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from fastapi.encoders import jsonable_encoder

from app import messenger
from app.auth import get_current_user
from app.badges import check_and_notify_new_badges
from app.csrf import verify_csrf
from app.database import fetch_one
from app.notifications import notify_new_message
from app.render import render

# Limits and rules live in app/messenger.py (re-exported for older imports).
from app.messenger import MAX_MESSAGE_LENGTH, MAX_MESSAGES_PER_HOUR, MAX_MESSAGES_PER_RECIPIENT_PER_HOUR  # noqa: F401

router = APIRouter()


def _page(request: Request, user: dict, folder: str, only_unread: bool, conversation: dict | None = None,
          listing_id: int | None = None, notice: str = ""):
    folder = folder if folder in ("inbox", "requests") else "inbox"
    context = {
        "user": user,
        "folder": folder,
        "only_unread": only_unread,
        "conversation": conversation,
        "notice": notice,
        "max_message_length": MAX_MESSAGE_LENGTH,
    }
    if conversation:
        conversation = dict(conversation)
        conversation["days_left"] = messenger.days_left(conversation["last_activity_at"])
        context["conversation"] = conversation
        other_id = conversation["user_high_id"] if conversation["user_low_id"] == user["id"] else conversation["user_low_id"]
        context.update({
            "thread": messenger.thread(user["id"], conversation["id"]),  # marks read first
            "other": fetch_one("SELECT id, full_name, avatar_url, deleted_at FROM users WHERE id = :id", {"id": other_id}),
            "is_request_for_me": conversation["status"] == "request" and conversation["requested_by"] != user["id"],
            "is_pending_mine": conversation["status"] == "request" and conversation["requested_by"] == user["id"],
            "compose_listing": fetch_one("SELECT id, title FROM visible_listings WHERE id = :id", {"id": listing_id}) if listing_id else None,
        })
    context["conversations"] = messenger.list_conversations(user["id"], folder, only_unread)
    context["counts"] = messenger.unread_counts(user["id"])
    return render(request, "messages.html", context)


def _require_user(request: Request):
    user = get_current_user(request)
    return user, (None if user else RedirectResponse(url="/login", status_code=303))


@router.get("/messages", response_class=HTMLResponse)
def inbox(request: Request, folder: str = "inbox", unread: str = ""):
    user, redirect = _require_user(request)
    if redirect:
        return redirect
    return _page(request, user, folder, unread == "1")


@router.get("/messages/c/{conversation_id}", response_class=HTMLResponse)
def conversation_page(request: Request, conversation_id: int, listing_id: int = 0, notice: str = ""):
    user, redirect = _require_user(request)
    if redirect:
        return redirect
    conversation = messenger.conversation_for(user["id"], conversation_id)
    if not conversation:
        return RedirectResponse(url="/messages", status_code=303)
    folder = "requests" if conversation["status"] == "request" and conversation["requested_by"] != user["id"] else "inbox"
    return _page(request, user, folder, False, conversation, listing_id or None, notice)


@router.get("/messages/new", response_class=HTMLResponse)
def compose_form(request: Request, to: int = 0, listing_id: int = 0):
    user, redirect = _require_user(request)
    if redirect:
        return redirect
    existing = messenger.conversation_between(user["id"], to) if to else None
    if existing:
        suffix = f"?listing_id={listing_id}" if listing_id else ""
        return RedirectResponse(url=f"/messages/c/{existing['id']}{suffix}", status_code=303)
    context = {
        "user": user,
        "recipient": fetch_one("SELECT id, full_name FROM users WHERE id = :id AND deleted_at IS NULL", {"id": to}) if to else None,
        "listing": fetch_one("SELECT id, title FROM visible_listings WHERE id = :id", {"id": listing_id}) if listing_id else None,
        "max_message_length": MAX_MESSAGE_LENGTH,
        "error": None,
    }
    return render(request, "message_compose.html", context)


@router.post("/messages/send")
def send_message(
    request: Request,
    background_tasks: BackgroundTasks,
    csrf_token: str = Form(""),
    recipient_id: int = Form(...),
    listing_id: str = Form(""),
    body: str = Form(...),
):
    verify_csrf(request, csrf_token)
    user, redirect = _require_user(request)
    if redirect:
        return redirect
    if not user["email_verified"]:
        return RedirectResponse(url="/?verify_required=1", status_code=303)

    status, conversation_id = messenger.send_message(
        user["id"], recipient_id, body, int(listing_id) if listing_id.isdigit() else None,
    )
    if status in ("rate_limited", "rate_limited_recipient"):
        context = {
            "user": user,
            "recipient": fetch_one("SELECT id, full_name FROM users WHERE id = :id", {"id": recipient_id}),
            "listing": fetch_one("SELECT id, title FROM visible_listings WHERE id = :id", {"id": int(listing_id)}) if listing_id.isdigit() else None,
            "max_message_length": MAX_MESSAGE_LENGTH,
            "error": "message_error_" + status,
        }
        return render(request, "message_compose.html", context, status_code=429)
    if status == "request_pending":
        return RedirectResponse(url=f"/messages/c/{conversation_id}?notice=request_pending", status_code=303)
    if status not in ("sent", "request_sent"):
        return RedirectResponse(url="/messages", status_code=303)
    _after_send(request, background_tasks, user, recipient_id)
    return RedirectResponse(url=f"/messages/c/{conversation_id}", status_code=303)


def _after_send(request: Request, background_tasks: BackgroundTasks, user: dict, recipient_id: int) -> None:
    """Side effects of a delivered message. No immediate bell notification:
    the Notification Center shows unread messages after 5 minutes
    (messenger.unread_messages_notification)."""
    recipient = fetch_one(
        "SELECT email, full_name, email_verified, notify_messages, preferred_language FROM users WHERE id = :id",
        {"id": recipient_id},
    )
    # At most one "new messages" e-mail per recipient per day (Daniel, 2026-09-26).
    if recipient["email_verified"] and recipient["notify_messages"] and messenger.claim_daily_email(recipient_id):
        background_tasks.add_task(
            notify_new_message, str(request.base_url), recipient["email"],
            recipient["full_name"], user["full_name"], recipient.get("preferred_language"),
        )
    background_tasks.add_task(check_and_notify_new_badges, user["id"], str(request.base_url))


def _conversation_action(request: Request, conversation_id: int, csrf_token: str, action, done_url: str):
    verify_csrf(request, csrf_token)
    user, redirect = _require_user(request)
    if redirect:
        return redirect
    action(user["id"], conversation_id)
    return RedirectResponse(url=done_url, status_code=303)


@router.post("/messages/c/{conversation_id}/accept")
def accept(request: Request, conversation_id: int, csrf_token: str = Form("")):
    return _conversation_action(request, conversation_id, csrf_token, messenger.accept_request, f"/messages/c/{conversation_id}")


@router.post("/messages/c/{conversation_id}/decline")
def decline(request: Request, conversation_id: int, csrf_token: str = Form("")):
    return _conversation_action(request, conversation_id, csrf_token, messenger.decline_request, "/messages?folder=requests")


@router.post("/messages/c/{conversation_id}/hide")
def hide(request: Request, conversation_id: int, csrf_token: str = Form("")):
    return _conversation_action(request, conversation_id, csrf_token, messenger.hide_conversation, "/messages")


@router.post("/messages/{message_id}/report")
def report(request: Request, message_id: int, csrf_token: str = Form(""), reason: str = Form("")):
    verify_csrf(request, csrf_token)
    user, redirect = _require_user(request)
    if redirect:
        return redirect
    result = messenger.report_message(user["id"], message_id, reason)
    row = fetch_one("SELECT conversation_id FROM visible_messages WHERE id = :id", {"id": message_id})
    target = f"/messages/c/{row['conversation_id']}" if row else "/messages"
    return RedirectResponse(url=f"{target}?notice=report_{result}", status_code=303)


# ---- Live updates (polled by app/static/js/messenger.js) -------------------

@router.get("/messages/unread-count")
def unread_count(request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "login"}, status_code=401)
    return JSONResponse(jsonable_encoder(messenger.poll_summary(user["id"])))


@router.get("/messages/c/{conversation_id}/since")
def conversation_since(request: Request, conversation_id: int, after: int = 0, peek: int = 0):
    """New messages after `after`. `peek=1` (minimized chat window) counts
    without marking anything as read."""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "login"}, status_code=401)
    if not messenger.conversation_for(user["id"], conversation_id):
        return JSONResponse({"error": "not_found"}, status_code=404)
    conversation = messenger.conversation_for(user["id"], conversation_id)
    other_id = conversation["user_high_id"] if conversation["user_low_id"] == user["id"] else conversation["user_low_id"]
    other = fetch_one("SELECT full_name FROM users WHERE id = :id", {"id": other_id})
    rows = messenger.thread(user["id"], conversation_id, after_id=after, mark_read=not peek)
    return JSONResponse({"other_name": other["full_name"] if other else "", "messages": [
        {"id": r["id"], "body": r["body"], "mine": r["mine"], "listing_title": r["listing_title"],
         "time": r["created_at"].strftime("%d.%m. %H:%M")}
        for r in rows
    ]})


@router.post("/messages/c/{conversation_id}/post")
def conversation_post(request: Request, background_tasks: BackgroundTasks, conversation_id: int,
                      csrf_token: str = Form(""), body: str = Form("")):
    """JSON send used by the desktop chat window (M5)."""
    verify_csrf(request, csrf_token)
    user = get_current_user(request)
    if not user:
        return JSONResponse({"status": "login"}, status_code=401)
    if not user["email_verified"]:
        return JSONResponse({"status": "verify_required"}, status_code=403)
    conversation = messenger.conversation_for(user["id"], conversation_id)
    if not conversation:
        return JSONResponse({"status": "not_found"}, status_code=404)
    other_id = conversation["user_high_id"] if conversation["user_low_id"] == user["id"] else conversation["user_low_id"]
    status, _ = messenger.send_message(user["id"], other_id, body)
    if status in ("sent", "request_sent"):
        _after_send(request, background_tasks, user, other_id)
    return JSONResponse({"status": status}, status_code=429 if status.startswith("rate_limited") else 200)


# ---- Old URLs (pre-Messenger folders / single messages) --------------------

@router.get("/messages/sent")
@router.get("/messages/trash")
def legacy_folders(request: Request):
    return RedirectResponse(url="/messages", status_code=303)


@router.get("/messages/{message_id}")
def legacy_message(request: Request, message_id: int):
    user, redirect = _require_user(request)
    if redirect:
        return redirect
    row = fetch_one(
        "SELECT conversation_id FROM visible_messages WHERE id = :id AND :u IN (sender_id, recipient_id)",
        {"id": message_id, "u": user["id"]},
    )
    return RedirectResponse(url=f"/messages/c/{row['conversation_id']}" if row else "/messages", status_code=303)

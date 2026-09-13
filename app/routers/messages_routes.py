from fastapi import APIRouter, Request, Form, BackgroundTasks
from fastapi.responses import RedirectResponse, HTMLResponse

from app.database import fetch_all, fetch_one, execute
from app.auth import get_current_user
from app.render import render
from app.csrf import verify_csrf
from app.notifications import notify_new_message
from app.badges import check_and_notify_new_badges

router = APIRouter()

MAX_MESSAGE_LENGTH = 2000


@router.get("/messages", response_class=HTMLResponse)
def inbox(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    messages = fetch_all(
        """
        SELECT m.id, m.body, m.created_at, m.read_at, m.listing_id,
               u.id AS other_id, u.full_name AS other_name,
               l.title AS listing_title
        FROM messages m
        JOIN users u ON u.id = m.sender_id
        LEFT JOIN listings l ON l.id = m.listing_id
        WHERE m.recipient_id = :id AND m.recipient_status = 'active'
        ORDER BY m.created_at DESC
        """,
        {"id": user["id"]},
    )
    return render(request, "messages.html", {"user": user, "messages": messages, "folder": "inbox"})


@router.get("/messages/sent", response_class=HTMLResponse)
def sent(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    messages = fetch_all(
        """
        SELECT m.id, m.body, m.created_at, m.read_at, m.listing_id,
               u.id AS other_id, u.full_name AS other_name,
               l.title AS listing_title
        FROM messages m
        JOIN users u ON u.id = m.recipient_id
        LEFT JOIN listings l ON l.id = m.listing_id
        WHERE m.sender_id = :id AND m.sender_status = 'active'
        ORDER BY m.created_at DESC
        """,
        {"id": user["id"]},
    )
    return render(request, "messages.html", {"user": user, "messages": messages, "folder": "sent"})


@router.get("/messages/trash", response_class=HTMLResponse)
def trash(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    messages = fetch_all(
        """
        SELECT m.id, m.body, m.created_at, m.read_at, m.listing_id, m.sender_id, m.recipient_id,
               CASE WHEN m.sender_id = :id THEN ru.full_name ELSE su.full_name END AS other_name,
               l.title AS listing_title
        FROM messages m
        JOIN users su ON su.id = m.sender_id
        JOIN users ru ON ru.id = m.recipient_id
        LEFT JOIN listings l ON l.id = m.listing_id
        WHERE (m.sender_id = :id AND m.sender_status = 'trashed')
           OR (m.recipient_id = :id AND m.recipient_status = 'trashed')
        ORDER BY m.created_at DESC
        """,
        {"id": user["id"]},
    )
    return render(request, "messages.html", {"user": user, "messages": messages, "folder": "trash"})


@router.get("/messages/new", response_class=HTMLResponse)
def compose_form(request: Request, to: int = 0, listing_id: int = 0):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    recipient = fetch_one("SELECT id, full_name FROM users WHERE id = :id", {"id": to}) if to else None
    listing = fetch_one("SELECT id, title FROM listings WHERE id = :id", {"id": listing_id}) if listing_id else None

    context = {
        "user": user,
        "recipient": recipient,
        "listing": listing,
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

    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    if not user["email_verified"]:
        return RedirectResponse(url="/?verify_required=1", status_code=303)

    body = body.strip()[:MAX_MESSAGE_LENGTH]
    if not body or recipient_id == user["id"]:
        return RedirectResponse(url="/messages", status_code=303)

    # Bloqueio impede mensagem nos dois sentidos: nem quem bloqueou nem
    # quem foi bloqueado consegue mandar mensagem pro outro lado.
    blocked = fetch_one(
        """
        SELECT 1 FROM blocked_users
        WHERE (blocker_id = :user_id AND blocked_id = :recipient_id)
           OR (blocker_id = :recipient_id AND blocked_id = :user_id)
        """,
        {"user_id": user["id"], "recipient_id": recipient_id},
    )
    if blocked:
        return RedirectResponse(url="/messages", status_code=303)

    recipient = fetch_one(
        "SELECT email, full_name, email_verified, notify_messages FROM users WHERE id = :id AND deleted_at IS NULL",
        {"id": recipient_id},
    )
    if not recipient:
        return RedirectResponse(url="/messages", status_code=303)

    execute(
        """
        INSERT INTO messages (sender_id, recipient_id, listing_id, body)
        VALUES (:sender_id, :recipient_id, :listing_id, :body)
        """,
        {
            "sender_id": user["id"],
            "recipient_id": recipient_id,
            "listing_id": int(listing_id) if listing_id else None,
            "body": body,
        },
    )

    # "Receber um e-mail toda vez que recebe uma mensagem" — em segundo
    # plano, pra não atrasar o redirecionamento de quem enviou. Só
    # dispara se a pessoa tiver e-mail verificado e o aviso ligado
    # (users.notify_messages, ver /profile).
    if recipient["email_verified"] and recipient["notify_messages"]:
        background_tasks.add_task(
            notify_new_message,
            str(request.base_url),
            recipient["email"],
            recipient["full_name"],
            user["full_name"],
        )

    # Badges que dependem de mensagens (contato, resposta rápida) —
    # checa pra quem ENVIOU (a ação foi dela).
    background_tasks.add_task(check_and_notify_new_badges, user["id"], str(request.base_url))

    return RedirectResponse(url="/messages/sent", status_code=303)


@router.get("/messages/{message_id}", response_class=HTMLResponse)
def message_detail(request: Request, message_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    message = fetch_one(
        """
        SELECT m.id, m.body, m.created_at, m.read_at, m.sender_id, m.recipient_id, m.listing_id,
               su.full_name AS sender_name, ru.full_name AS recipient_name,
               l.title AS listing_title
        FROM messages m
        JOIN users su ON su.id = m.sender_id
        JOIN users ru ON ru.id = m.recipient_id
        LEFT JOIN listings l ON l.id = m.listing_id
        WHERE m.id = :id
        """,
        {"id": message_id},
    )

    if not message or user["id"] not in (message["sender_id"], message["recipient_id"]):
        return RedirectResponse(url="/messages", status_code=303)

    if message["recipient_id"] == user["id"] and not message["read_at"]:
        execute("UPDATE messages SET read_at = now() WHERE id = :id", {"id": message_id})
        message["read_at"] = "now"

    other_id = message["recipient_id"] if message["sender_id"] == user["id"] else message["sender_id"]
    other_name = message["recipient_name"] if message["sender_id"] == user["id"] else message["sender_name"]

    context = {
        "user": user,
        "message": message,
        "other_id": other_id,
        "other_name": other_name,
    }
    return render(request, "message_detail.html", context)


@router.post("/messages/{message_id}/trash")
def trash_message(request: Request, message_id: int, csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)

    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    message = fetch_one("SELECT sender_id, recipient_id FROM messages WHERE id = :id", {"id": message_id})
    if message:
        if message["sender_id"] == user["id"]:
            execute("UPDATE messages SET sender_status = 'trashed' WHERE id = :id", {"id": message_id})
        elif message["recipient_id"] == user["id"]:
            execute("UPDATE messages SET recipient_status = 'trashed' WHERE id = :id", {"id": message_id})
    return RedirectResponse(url="/messages", status_code=303)


@router.post("/messages/{message_id}/restore")
def restore_message(request: Request, message_id: int, csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)

    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    message = fetch_one("SELECT sender_id, recipient_id FROM messages WHERE id = :id", {"id": message_id})
    if message:
        if message["sender_id"] == user["id"]:
            execute("UPDATE messages SET sender_status = 'active' WHERE id = :id", {"id": message_id})
        elif message["recipient_id"] == user["id"]:
            execute("UPDATE messages SET recipient_status = 'active' WHERE id = :id", {"id": message_id})
    return RedirectResponse(url="/messages/trash", status_code=303)


@router.post("/messages/trash/empty")
def empty_trash(request: Request, csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)

    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    # Simplificação didática: esvaziar a lixeira apaga a linha de vez,
    # o que remove a mensagem também do lado da outra pessoa (mesmo que
    # ela não tenha jogado a dela fora). Veja a nota em db/schema.sql.
    execute(
        """
        DELETE FROM messages
        WHERE (sender_id = :id AND sender_status = 'trashed')
           OR (recipient_id = :id AND recipient_status = 'trashed')
        """,
        {"id": user["id"]},
    )
    return RedirectResponse(url="/messages/trash", status_code=303)

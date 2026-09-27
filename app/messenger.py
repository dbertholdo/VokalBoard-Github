"""
Messenger rules (docs/specs/MESSENGER.md — Daniel, 2026-09-26).

- One conversation per pair of users (`conversations`, low/high id).
- Everyone can message everyone, but a first message from someone without
  prior contact becomes a REQUEST in the recipient's Requests folder; the
  sender may send only that one message until it's accepted. Replying
  counts as accepting. A declined request stays silent for the sender.
- No request needed when the pair has had contact before (`contact_pairs`,
  outlives deleted chats) or has a Match (`job_matches`). Blocking always wins.
- A conversation is deleted 60 days after its last message (DB trigger +
  retention worker); the "!" warning shows during the last 10 days.
- "Seen" is never exposed: `read_at` is only used for unread counts.

Routers stay thin; every rule lives here. List/thread queries are single
statements (no N+1).
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.database import engine, fetch_all, fetch_one
from app.retention_rules import warning_days

MAX_MESSAGE_LENGTH = 2000
MAX_MESSAGES_PER_HOUR = 20
MAX_MESSAGES_PER_RECIPIENT_PER_HOUR = 5
REPORT_REASON_MIN, REPORT_REASON_MAX = 3, 500
# Clock times are shown in the site's zone (DE/AT/CH all use CET/CEST);
# the database stores UTC, which used to be printed as-is (1–2 h off).
SITE_TZ = ZoneInfo("Europe/Berlin")


def local_time(dt, fmt: str = "%d.%m. %H:%M") -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(SITE_TZ).strftime(fmt)


def _pair(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def _side(conv: dict, user_id: int) -> str:
    return "low" if conv["user_low_id"] == user_id else "high"


def is_blocked(a: int, b: int) -> bool:
    return fetch_one(
        """SELECT 1 FROM blocked_users
           WHERE (blocker_id = :a AND blocked_id = :b) OR (blocker_id = :b AND blocked_id = :a)""",
        {"a": a, "b": b},
    ) is not None


def _has_contact(conn, a: int, b: int) -> bool:
    lo, hi = _pair(a, b)
    return conn.execute(
        text(
            """
            SELECT EXISTS (SELECT 1 FROM contact_pairs WHERE user_low_id = :lo AND user_high_id = :hi)
                OR EXISTS (SELECT 1 FROM job_matches
                           WHERE (artist_user_id = :lo AND contractor_user_id = :hi)
                              OR (artist_user_id = :hi AND contractor_user_id = :lo))
            """
        ),
        {"lo": lo, "hi": hi},
    ).scalar_one()


def _add_contact(conn, a: int, b: int, source: str = "accepted") -> None:
    lo, hi = _pair(a, b)
    conn.execute(
        text("INSERT INTO contact_pairs (user_low_id, user_high_id, source) VALUES (:lo, :hi, :s) ON CONFLICT DO NOTHING"),
        {"lo": lo, "hi": hi, "s": source},
    )


def _rate_limited(sender_id: int, recipient_id: int) -> str | None:
    counts = fetch_one(
        """
        SELECT count(*) AS total,
               count(*) FILTER (WHERE recipient_id = :r) AS to_recipient
        FROM visible_messages WHERE sender_id = :s AND created_at > now() - interval '1 hour'
        """,
        {"s": sender_id, "r": recipient_id},
    )
    if counts["total"] >= MAX_MESSAGES_PER_HOUR:
        return "rate_limited"
    if counts["to_recipient"] >= MAX_MESSAGES_PER_RECIPIENT_PER_HOUR:
        return "rate_limited_recipient"
    return None


def send_message(sender_id: int, recipient_id: int, body: str, listing_id: int | None = None) -> tuple[str, int | None]:
    """Returns (status, conversation_id). Status: 'sent', 'request_sent',
    'request_pending' (request already sent, not accepted yet — nothing
    stored), 'invalid', 'recipient_missing', 'blocked', 'rate_limited',
    'rate_limited_recipient'."""
    body = (body or "").strip()[:MAX_MESSAGE_LENGTH]
    if not body or sender_id == recipient_id:
        return "invalid", None
    if not fetch_one("SELECT 1 FROM users WHERE id = :id AND deleted_at IS NULL", {"id": recipient_id}):
        return "recipient_missing", None
    if is_blocked(sender_id, recipient_id):
        return "blocked", None
    limited = _rate_limited(sender_id, recipient_id)
    if limited:
        return limited, None
    if listing_id is not None and not fetch_one("SELECT 1 FROM visible_listings WHERE id = :id", {"id": listing_id}):
        listing_id = None  # stale/tampered reference: send the message without it (was an FK 500)
    lo, hi = _pair(sender_id, recipient_id)
    with engine.begin() as conn:
        # Same pair lock the message trigger takes — serializes two first
        # messages racing to create the conversation.
        conn.execute(text("SELECT pg_advisory_xact_lock(:a, :b)"),
                     {"a": lo % 2147483647, "b": hi % 2147483647})
        conv = conn.execute(
            text("SELECT * FROM conversations WHERE user_low_id = :lo AND user_high_id = :hi FOR UPDATE"),
            {"lo": lo, "hi": hi},
        ).mappings().first()
        contact = _has_contact(conn, sender_id, recipient_id)
        if conv is None:
            status = "active" if contact else "request"
            conv_id = conn.execute(
                text(
                    """INSERT INTO conversations (user_low_id, user_high_id, status, requested_by)
                       VALUES (:lo, :hi, :status, :by) RETURNING id"""
                ),
                {"lo": lo, "hi": hi, "status": status, "by": sender_id if status == "request" else None},
            ).scalar_one()
        else:
            conv_id, status = conv["id"], conv["status"]
            expired = conn.execute(
                text("SELECT :t + interval '60 days' <= now()"), {"t": conv["last_activity_at"]}
            ).scalar_one()
            if status == "request" and (contact or conv["requested_by"] != sender_id):
                # A Match/contact arrived meanwhile, or the recipient replies
                # (replying = accepting): the conversation becomes a chat.
                status = "active"
                conn.execute(text("UPDATE conversations SET status = 'active', declined_at = NULL WHERE id = :id"),
                             {"id": conv_id})
                _add_contact(conn, sender_id, recipient_id)
            elif status == "request" and not expired:
                already = conn.execute(
                    text("SELECT count(*) FROM messages WHERE conversation_id = :c AND sender_id = :s"),
                    {"c": conv_id, "s": sender_id},
                ).scalar_one()
                if already >= 1:
                    return "request_pending", conv_id
        conn.execute(
            text(
                """INSERT INTO messages (sender_id, recipient_id, listing_id, body, conversation_id)
                   VALUES (:s, :r, :l, :b, :c)"""
            ),
            {"s": sender_id, "r": recipient_id, "l": listing_id, "b": body, "c": conv_id},
        )
    return ("request_sent" if status == "request" else "sent"), conv_id


def conversation_for(user_id: int, conversation_id: int) -> dict | None:
    """The conversation if `user_id` is a participant and it hasn't expired."""
    return fetch_one(
        """SELECT * FROM conversations
           WHERE id = :id AND :u IN (user_low_id, user_high_id)
             AND last_activity_at + interval '60 days' > now()""",
        {"id": conversation_id, "u": user_id},
    )


def conversation_between(user_id: int, other_id: int) -> dict | None:
    """The live conversation between two users, if any (for "send message" links)."""
    lo, hi = _pair(user_id, other_id)
    return fetch_one(
        """SELECT * FROM conversations WHERE user_low_id = :lo AND user_high_id = :hi
             AND last_activity_at + interval '60 days' > now()
             AND EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id = conversations.id)""",
        {"lo": lo, "hi": hi},
    )


def accept_request(user_id: int, conversation_id: int) -> bool:
    conv = conversation_for(user_id, conversation_id)
    if not conv or conv["status"] != "request" or conv["requested_by"] == user_id:
        return False
    with engine.begin() as conn:
        conn.execute(text("UPDATE conversations SET status = 'active', declined_at = NULL WHERE id = :id"),
                     {"id": conversation_id})
        _add_contact(conn, conv["user_low_id"], conv["user_high_id"])
    return True


def decline_request(user_id: int, conversation_id: int) -> bool:
    conv = conversation_for(user_id, conversation_id)
    if not conv or conv["status"] != "request" or conv["requested_by"] == user_id:
        return False
    with engine.begin() as conn:
        conn.execute(text("UPDATE conversations SET declined_at = now() WHERE id = :id"), {"id": conversation_id})
    return True


def hide_conversation(user_id: int, conversation_id: int) -> bool:
    """Hides it from this user's list until the next message arrives."""
    conv = conversation_for(user_id, conversation_id)
    if not conv:
        return False
    column = f"{_side(conv, user_id)}_hidden_at"  # 'low_hidden_at' / 'high_hidden_at' only
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE conversations SET {column} = now() WHERE id = :id"),  # nosec B608 - fixed column names
                     {"id": conversation_id})
    return True


def report_message(user_id: int, message_id: int, reason: str) -> str:
    """'reported', 'already', 'invalid' or 'not_allowed'. Only the recipient
    of a message can report it; the text is snapshotted for moderation."""
    reason = (reason or "").strip()[:REPORT_REASON_MAX]
    if len(reason) < REPORT_REASON_MIN:
        return "invalid"
    message = fetch_one("SELECT id, sender_id, recipient_id, body FROM visible_messages WHERE id = :id", {"id": message_id})
    if not message or message["recipient_id"] != user_id:
        return "not_allowed"
    with engine.begin() as conn:
        inserted = conn.execute(
            text(
                """INSERT INTO message_reports (message_id, reporter_id, reported_user_id, reason, body_snapshot)
                   VALUES (:m, :r, :u, :reason, :body)
                   ON CONFLICT (message_id, reporter_id) DO NOTHING RETURNING id"""
            ),
            {"m": message_id, "r": user_id, "u": message["sender_id"], "reason": reason, "body": message["body"]},
        ).first()
    return "reported" if inserted else "already"


# ---------------------------------------------------------------------------
# Read side (single queries — no N+1)
# ---------------------------------------------------------------------------

_LIST_SQL = """
SELECT c.id, c.status, c.requested_by, c.declined_at, c.last_activity_at,
       o.id AS other_id, o.full_name AS other_name, o.avatar_url AS other_avatar,
       (o.deleted_at IS NOT NULL) AS other_deactivated,
       last.body AS last_body, last.sender_id AS last_sender_id, last.created_at AS last_created_at,
       COALESCE(unread.n, 0) AS unread
FROM conversations c
JOIN users o ON o.id = CASE WHEN c.user_low_id = :u THEN c.user_high_id ELSE c.user_low_id END
LEFT JOIN LATERAL (
    SELECT body, sender_id, created_at FROM messages m
    WHERE m.conversation_id = c.id ORDER BY m.id DESC LIMIT 1
) last ON TRUE
LEFT JOIN LATERAL (
    SELECT count(*) AS n FROM messages m
    WHERE m.conversation_id = c.id AND m.recipient_id = :u AND m.read_at IS NULL
) unread ON TRUE
WHERE :u IN (c.user_low_id, c.user_high_id)
  AND c.last_activity_at + interval '60 days' > now()
  AND last.created_at IS NOT NULL
  AND (CASE WHEN c.user_low_id = :u THEN c.low_hidden_at ELSE c.high_hidden_at END) IS NULL
  AND {folder}
  {unread_filter}
ORDER BY c.last_activity_at DESC
"""
_FOLDERS = {
    # My chats + my own pending requests (shown as "waiting for acceptance").
    "inbox": "(c.status = 'active' OR c.requested_by = :u)",
    # Requests others sent me that I haven't declined.
    "requests": "(c.status = 'request' AND c.requested_by <> :u AND c.declined_at IS NULL)",
}


def days_left(last_activity_at) -> int | None:
    """Days until deletion, only during the last 10 of 60 (the "!" warning)."""
    return warning_days(last_activity_at, datetime.now(timezone.utc))


def list_conversations(user_id: int, folder: str = "inbox", unread_only: bool = False) -> list[dict]:
    sql = _LIST_SQL.format(
        folder=_FOLDERS.get(folder, _FOLDERS["inbox"]),
        unread_filter="AND COALESCE(unread.n, 0) > 0" if unread_only else "",
    )
    rows = fetch_all(sql, {"u": user_id})  # nosec B608 - folder/filter are fixed literals
    now = datetime.now(timezone.utc)
    for row in rows:
        row["days_left"] = warning_days(row["last_activity_at"], now)
        row["pending_mine"] = row["status"] == "request" and row["requested_by"] == user_id
    return rows


def thread(user_id: int, conversation_id: int, after_id: int = 0, mark_read: bool = True) -> list[dict]:
    """Messages of a conversation (after `after_id`, for polling), oldest
    first; marks the ones addressed to `user_id` as read."""
    rows = fetch_all(
        """
        SELECT m.id, m.body, m.created_at, m.sender_id, (m.sender_id = :u) AS mine,
               m.listing_id, l.title AS listing_title
        FROM visible_messages m
        LEFT JOIN visible_listings l ON l.id = m.listing_id
        WHERE m.conversation_id = :c AND m.id > :after
        ORDER BY m.id
        """,
        {"u": user_id, "c": conversation_id, "after": after_id},
    )
    for r in rows:
        r["time"] = local_time(r["created_at"])
    if mark_read and any(not r["mine"] for r in rows):
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE messages SET read_at = now() WHERE conversation_id = :c AND recipient_id = :u AND read_at IS NULL"),
                {"c": conversation_id, "u": user_id},
            )
    return rows


def unread_counts(user_id: int) -> dict:
    """{'inbox': unread messages in chats, 'requests': pending requests with unread messages}."""
    row = fetch_one(
        """
        SELECT count(*) FILTER (WHERE c.status = 'active' OR c.requested_by = :u) AS inbox,
               count(DISTINCT c.id) FILTER (WHERE c.status = 'request' AND c.requested_by <> :u AND c.declined_at IS NULL) AS requests
        FROM messages m JOIN conversations c ON c.id = m.conversation_id
        WHERE m.recipient_id = :u AND m.read_at IS NULL
          AND c.last_activity_at + interval '60 days' > now()
          AND (CASE WHEN c.user_low_id = :u THEN c.low_hidden_at ELSE c.high_hidden_at END) IS NULL
        """,
        {"u": user_id},
    )
    return {"inbox": row["inbox"], "requests": row["requests"]}


# ---------------------------------------------------------------------------
# Live updates (M4): polling summary + the 5-minute Notification Center entry
# ---------------------------------------------------------------------------

_UNREAD_FOR_ME = """
    FROM messages m JOIN conversations c ON c.id = m.conversation_id
    JOIN users s ON s.id = m.sender_id
    WHERE m.recipient_id = :u AND m.read_at IS NULL
      AND c.last_activity_at + interval '60 days' > now()
      AND c.declined_at IS NULL
      AND (CASE WHEN c.user_low_id = :u THEN c.low_hidden_at ELSE c.high_hidden_at END) IS NULL
"""


def poll_summary(user_id: int) -> dict:
    """For the badge/bubble poll: counts + the newest unread message."""
    counts = unread_counts(user_id)
    latest = fetch_one(
        "SELECT m.id, m.conversation_id, left(m.body, 120) AS snippet, s.full_name AS sender_name" + _UNREAD_FOR_ME
        + " ORDER BY m.id DESC LIMIT 1",  # nosec B608 - fixed fragment
        {"u": user_id},
    )
    return {**counts, "total": counts["inbox"] + counts["requests"], "latest": dict(latest) if latest else None}


def unread_messages_notification(user_id: int) -> dict | None:
    """Synthetic Notification Center item (never stored), shaped like
    profile_incomplete_notification(): appears once a message has been
    unread for 5 minutes (Daniel, 2026-09-26), disappears when read."""
    row = fetch_one(
        "SELECT count(*) AS n, min(m.conversation_id) AS conversation_id" + _UNREAD_FOR_ME
        + " AND m.created_at <= now() - interval '5 minutes'",  # nosec B608 - fixed fragment
        {"u": user_id},
    )
    if not row or not row["n"]:
        return None
    link = f"/messages/c/{row['conversation_id']}" if row["n"] == 1 else "/messages"
    return {
        "id": None, "type": "new_message", "title_key": "notification_unread_messages",
        "title_params": {"n": row["n"]}, "link_url": link, "icon": "icon-mail",
        "read_at": None, "created_at": None, "synthetic": True,
    }


# ---------------------------------------------------------------------------
# M6: e-mail limit + moderation of reported messages
# ---------------------------------------------------------------------------

def claim_daily_email(recipient_id: int) -> bool:
    """At most one "new messages" e-mail per recipient per 24 h (Daniel,
    2026-09-26). Atomic: two messages arriving at once can't both win."""
    with engine.begin() as conn:
        return conn.execute(
            text(
                """UPDATE users SET message_email_sent_at = now()
                   WHERE id = :id AND (message_email_sent_at IS NULL
                                       OR message_email_sent_at <= now() - interval '24 hours')
                   RETURNING id"""
            ),
            {"id": recipient_id},
        ).first() is not None


def open_message_reports(limit: int = 50) -> list[dict]:
    return fetch_all(
        """
        SELECT r.id, r.reason, r.body_snapshot, r.created_at, r.message_id,
               rep.full_name AS reporter_name, u.id AS reported_user_id, u.full_name AS reported_name
        FROM message_reports r
        JOIN users rep ON rep.id = r.reporter_id
        JOIN users u ON u.id = r.reported_user_id
        WHERE r.status = 'open'
        ORDER BY r.created_at
        LIMIT :limit
        """,
        {"limit": limit},
    )


def resolve_message_report(report_id: int, admin_id: int, remove_message: bool) -> bool:
    """Dismiss, or remove the reported message (the report keeps its text
    snapshot until it's purged 60 days after resolution)."""
    with engine.begin() as conn:
        report = conn.execute(
            text("SELECT message_id FROM message_reports WHERE id = :id AND status = 'open' FOR UPDATE"),
            {"id": report_id},
        ).mappings().first()
        if not report:
            return False
        if remove_message and report["message_id"]:
            conn.execute(text("DELETE FROM messages WHERE id = :id"), {"id": report["message_id"]})
        conn.execute(
            text(
                """UPDATE message_reports SET status = :status, resolved_at = now(), resolved_by = :admin
                   WHERE id = :id"""
            ),
            {"status": "removed" if remove_message else "dismissed", "admin": admin_id, "id": report_id},
        )
    return True

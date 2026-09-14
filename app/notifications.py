"""
Matching-listing e-mail alerts.

When someone posts a "looking for a singer" or "looking for a
conductor" listing, we send an IMMEDIATE e-mail (not a daily digest —
that was considered before, but the person preferred the alert right
away) to whoever has a matching profile: singers with the right voice
type for 'seeking_singer', or conductors for 'seeking_conductor'.

It only makes sense to alert for these two types — 'singer_available'
and 'conductor_available' are the PERSON advertising themselves, not
an opening, so there's no "matching someone" to notify.

Each person can turn this off at any time in /profile
(users.notify_matches).

We run this as a FastAPI BackgroundTask (see create_listing in
listings_routes.py): the listing is published right away, without
waiting for all the e-mails to go out first — the sending happens
afterward, in the background, without delaying the response for
whoever posted.
"""
import html as html_module

from app.database import fetch_all
from app.email import send_email


def notify_matching_users(base_url: str, listing_id: int, listing_type: str, title: str,
                           city: str | None, author_id: int, voice_type_id: int | None) -> None:
    if listing_type == "seeking_singer":
        conditions = [
            "role = 'singer'",
            "email_verified = TRUE",
            "notify_matches = TRUE",
            "deleted_at IS NULL",
            "id != :author_id",
        ]
        params = {"author_id": author_id}
        if voice_type_id:
            conditions.append(
                "id IN (SELECT user_id FROM singer_profiles WHERE voice_type_id = :voice_type_id OR voice_type_id IS NULL)"
            )
            params["voice_type_id"] = voice_type_id
        # nosec B608 below: only joins FIXED WHERE fragments (defined above,
        # never coming from person input) — the actual values all go through
        # a parameter (:voice_type_id etc.) in `params`, never pasted into the string.
        recipients = fetch_all(
            f"SELECT email, full_name FROM users WHERE {' AND '.join(conditions)}", params  # nosec B608
        )
    elif listing_type == "seeking_conductor":
        recipients = fetch_all(
            """
            SELECT email, full_name FROM users
            WHERE role = 'conductor' AND email_verified = TRUE AND notify_matches = TRUE
                AND deleted_at IS NULL AND id != :author_id
            """,
            {"author_id": author_id},
        )
    else:
        return

    if not recipients:
        return

    listing_url = f"{base_url.rstrip('/')}/listings/{listing_id}"
    safe_title = html_module.escape(title)
    safe_city = html_module.escape(city) if city else None
    for recipient in recipients:
        safe_recipient_name = html_module.escape(recipient["full_name"])
        html = f"""
            <p>Hallo {safe_recipient_name},</p>
            <p>Es gibt eine neue Anzeige, die zu deinem Profil passen könnte:</p>
            <p><strong>{safe_title}</strong>{f' — {safe_city}' if safe_city else ''}</p>
            <p><a href="{listing_url}">{listing_url}</a></p>
            <p>Du erhältst diese Benachrichtigung, weil du passende Anzeigen abonniert hast.
            Das kannst du jederzeit in deinem Profil ausschalten.</p>
            <hr>
            <p>(EN) A new listing might match your profile: <strong>{safe_title}</strong>{f' — {safe_city}' if safe_city else ''}.
            <a href="{listing_url}">{listing_url}</a><br>
            You're getting this because match alerts are on for your account — you can turn them off anytime in your profile.</p>
        """
        send_email(recipient["email"], f"Neue passende Anzeige: {title} — VokalBoard", html)


def notify_new_message(base_url: str, recipient_email: str, recipient_name: str, sender_name: str) -> None:
    """
    E-mail letting someone know "you received a message" — different
    from the matching-listing alert above. Each person can turn this
    off at any time in /profile (users.notify_messages); the route
    that calls this function (send_message in messages_routes.py)
    already checks notify_messages and email_verified before calling.

    On purpose, the e-mail does NOT show the message content (it only
    tells you one arrived) — this way the person needs to log in to
    the site to read it, which helps the goal of bringing people back
    to the site.
    """
    inbox_url = f"{base_url.rstrip('/')}/messages"
    safe_recipient_name = html_module.escape(recipient_name)
    safe_sender_name = html_module.escape(sender_name)
    html = f"""
        <p>Hallo {safe_recipient_name},</p>
        <p><strong>{safe_sender_name}</strong> hat dir eine neue Nachricht auf VokalBoard geschickt.</p>
        <p><a href="{inbox_url}">{inbox_url}</a></p>
        <p>Du erhältst diese Benachrichtigung, weil Nachrichten-E-Mails für dein Konto aktiviert sind.
        Das kannst du jederzeit in deinem Profil ausschalten.</p>
        <hr>
        <p>(EN) <strong>{safe_sender_name}</strong> sent you a new message on VokalBoard.
        <a href="{inbox_url}">{inbox_url}</a><br>
        You're getting this because message e-mails are on for your account — you can turn them off anytime in your profile.</p>
    """
    send_email(recipient_email, f"Neue Nachricht von {sender_name} — VokalBoard", html)

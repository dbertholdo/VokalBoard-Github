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

from app.database import fetch_all, fetch_one
from app.email import send_email
from app.email_localization import (
    new_message_email,
    invitation_received_email,
    application_received_email,
    invitation_response_email,
    vacancy_filled_email,
)


def _matching_recipients(listing_type: str, author_id: int, voice_type_id: int | None) -> list[dict]:
    """Quem tem o perfil compatível com essa vaga e quer receber
    alerta — extraído de notify_matching_users() pra ser reaproveitado
    também pelo lembrete de 6h de vaga urgente (P5 Etapa 2,
    18/09/2026), sem duplicar a query de "quem é compatível"."""
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
                """(
                    EXISTS (
                        SELECT 1 FROM singer_profile_voice_types spvt
                        WHERE spvt.user_id = users.id AND spvt.voice_type_id = :voice_type_id
                    )
                    OR EXISTS (
                        SELECT 1 FROM singer_profiles sp
                        WHERE sp.user_id = users.id
                          AND (sp.voice_type_id = :voice_type_id OR sp.voice_type_id IS NULL)
                    )
                )"""
            )
            params["voice_type_id"] = voice_type_id
        # nosec B608 below: only joins FIXED WHERE fragments (defined above,
        # never coming from person input) — the actual values all go through
        # a parameter (:voice_type_id etc.) in `params`, never pasted into the string.
        return fetch_all(
            f"SELECT email, full_name FROM users WHERE {' AND '.join(conditions)}", params  # nosec B608
        )
    elif listing_type == "seeking_conductor":
        return fetch_all(
            """
            SELECT email, full_name FROM users
            WHERE role = 'conductor' AND email_verified = TRUE AND notify_matches = TRUE
                AND deleted_at IS NULL AND id != :author_id
            """,
            {"author_id": author_id},
        )
    return []


def notify_matching_users(base_url: str, listing_id: int, listing_type: str, title: str,
                           city: str | None, author_id: int, voice_type_id: int | None) -> None:
    recipients = _matching_recipients(listing_type, author_id, voice_type_id)
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


def notify_urgent_listing_reminder(base_url: str, listing_id: int, listing_type: str, title: str,
                                    city: str | None, author_id: int, voice_type_id: int | None) -> None:
    """
    P5 Etapa 2 (18/09/2026): lembrete extra, 6h depois de uma vaga ser
    marcada urgente, SE continuar sem Match — pros mesmos perfis
    compatíveis que já teriam recebido o alerta de "nova vaga" (mesma
    query de _matching_recipients(), reaproveitada). Chamado pelo
    app/urgent_listing_reminder_worker.py, nunca duas vezes pra mesma
    vaga (o worker marca urgent_reminder_sent_at depois de chamar
    isso, protegendo contra reenvio em duplicidade).

    Texto deliberadamente diferente do alerta original (senão pareceria
    spam de "vaga nova" repetida) — mesmo estilo bilíngue DE/EN inline
    já usado nesta função vizinha, em vez do padrão de 5 idiomas de
    app/email_localization.py (o alerta de match original também não
    usa esse padrão).
    """
    recipients = _matching_recipients(listing_type, author_id, voice_type_id)
    if not recipients:
        return

    listing_url = f"{base_url.rstrip('/')}/listings/{listing_id}"
    safe_title = html_module.escape(title)
    safe_city = html_module.escape(city) if city else None
    for recipient in recipients:
        safe_recipient_name = html_module.escape(recipient["full_name"])
        html = f"""
            <p>Hallo {safe_recipient_name},</p>
            <p>Diese dringende Anzeige ist seit 6 Stunden noch offen — falls du Interesse hast, jetzt ist ein guter Moment:</p>
            <p><strong>⚡ {safe_title}</strong>{f' — {safe_city}' if safe_city else ''}</p>
            <p><a href="{listing_url}">{listing_url}</a></p>
            <p>Du erhältst diese Benachrichtigung, weil du passende Anzeigen abonniert hast.
            Das kannst du jederzeit in deinem Profil ausschalten.</p>
            <hr>
            <p>(EN) This urgent listing has been open for 6 hours — if you're interested, now's a good moment:
            <strong>⚡ {safe_title}</strong>{f' — {safe_city}' if safe_city else ''}.
            <a href="{listing_url}">{listing_url}</a><br>
            You're getting this because match alerts are on for your account — you can turn them off anytime in your profile.</p>
        """
        send_email(recipient["email"], f"Immer noch dringend: {title} — VokalBoard", html)


def notify_new_message(base_url: str, recipient_email: str, recipient_name: str, sender_name: str, preferred_language: str | None = None) -> None:
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
    subject, html = new_message_email(preferred_language, recipient_name, sender_name, inbox_url)
    send_email(recipient_email, subject, html)


# --- P3.C: convites / candidaturas --------------------------------------
# Always sent (no opt-out column exists for these, unlike
# notify_matches/notify_messages above) — deliberately: these are
# time-sensitive (48h to respond) direct actions naming the person, not
# a generic broadcast, closer to a password-reset e-mail than a digest.

def notify_invitation_created(base_url: str, invitation_id: int) -> None:
    """Called right after create_invitation() succeeds — tells the
    RECEIVING side (whoever now owes a response) that something is
    waiting. Looks the row back up by id instead of taking every field
    as a param, since this always runs as a BackgroundTask after the
    HTTP response already went out."""
    row = fetch_one(
        """
        SELECT ji.artist_user_id, ji.initiated_by_user_id,
               l.title AS listing_title, l.author_id AS contractor_id,
               artist.email AS artist_email, artist.full_name AS artist_name, artist.preferred_language AS artist_lang,
               contractor.email AS contractor_email, contractor.full_name AS contractor_name, contractor.preferred_language AS contractor_lang
        FROM job_invitations ji
        JOIN listing_vacancies lv ON lv.id = ji.vacancy_id
        JOIN listings l ON l.id = lv.listing_id
        JOIN users artist ON artist.id = ji.artist_user_id
        JOIN users contractor ON contractor.id = l.author_id
        WHERE ji.id = :id
        """,
        {"id": invitation_id},
    )
    if not row:
        return
    url = f"{base_url.rstrip('/')}/invitations"
    is_candidatura = row["initiated_by_user_id"] == row["artist_user_id"]
    if is_candidatura:
        subject, html = application_received_email(row["contractor_lang"], row["contractor_name"], row["artist_name"], row["listing_title"], url)
        send_email(row["contractor_email"], subject, html)
    else:
        subject, html = invitation_received_email(row["artist_lang"], row["artist_name"], row["listing_title"], url)
        send_email(row["artist_email"], subject, html)


def notify_invitation_responded(base_url: str, invitation_id: int, accepted: bool) -> None:
    """Tells whoever INITIATED the row (the one who was waiting) that
    the other side responded. Called after respond_invitation()."""
    row = fetch_one(
        """
        SELECT ji.artist_user_id, ji.initiated_by_user_id,
               l.title AS listing_title,
               artist.full_name AS artist_name, artist.preferred_language AS artist_lang,
               contractor.email AS contractor_email, contractor.full_name AS contractor_name, contractor.preferred_language AS contractor_lang,
               initiator.email AS initiator_email, initiator.full_name AS initiator_name, initiator.preferred_language AS initiator_lang
        FROM job_invitations ji
        JOIN listing_vacancies lv ON lv.id = ji.vacancy_id
        JOIN listings l ON l.id = lv.listing_id
        JOIN users artist ON artist.id = ji.artist_user_id
        JOIN users contractor ON contractor.id = l.author_id
        JOIN users initiator ON initiator.id = ji.initiated_by_user_id
        WHERE ji.id = :id
        """,
        {"id": invitation_id},
    )
    if not row:
        return
    url = f"{base_url.rstrip('/')}/invitations"
    subject, html = invitation_response_email(row["initiator_lang"], row["initiator_name"], row["listing_title"], accepted, url)
    send_email(row["initiator_email"], subject, html)

def notify_vacancy_filled_elsewhere(base_url: str, invitation_id: int) -> None:
    """P3.D: tells an artist whose invitation/candidatura was still
    pending that the vacancy filled up (all slots taken) while they
    hadn't responded yet. Called by match_service.respond_invitation()'s
    filled_other_ids, ONLY once every slot on that vacancy is full — a
    multi-slot vacancy (e.g. "3 Sopranos") can have several people
    legitimately still pending after ONE slot fills, so this never fires
    on an ordinary single accept/decline, only when there's truly nothing
    left to respond to."""
    row = fetch_one(
        """
        SELECT ji.artist_user_id, l.title AS listing_title,
               artist.email AS artist_email, artist.full_name AS artist_name,
               artist.preferred_language AS artist_lang
        FROM job_invitations ji
        JOIN listing_vacancies lv ON lv.id = ji.vacancy_id
        JOIN listings l ON l.id = lv.listing_id
        JOIN users artist ON artist.id = ji.artist_user_id
        WHERE ji.id = :id
        """,
        {"id": invitation_id},
    )
    if not row:
        return
    subject, html = vacancy_filled_email(row["artist_lang"], row["artist_name"], row["listing_title"])
    send_email(row["artist_email"], subject, html)

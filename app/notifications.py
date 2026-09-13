"""
Alertas por e-mail de anúncio compatível.

Quando alguém publica um anúncio do tipo "procuro cantor(a)" ou
"procuro maestro(a)", mandamos um e-mail IMEDIATO (não um resumo
diário — isso foi cogitado antes, mas a pessoa preferiu o alerta na
hora) para quem tem o perfil compatível: cantores(as) do tipo de voz
certo pra 'seeking_singer', ou maestros(as) pra 'seeking_conductor'.

Só faz sentido alertar para esses dois tipos — 'singer_available' e
'conductor_available' são a PESSOA se anunciando, não uma vaga, então
não têm "alguém compatível" para avisar.

Cada pessoa pode desligar isso a qualquer momento em /profile
(users.notify_matches).

Rodamos isso como uma BackgroundTask do FastAPI (ver create_listing em
listings_routes.py): o anúncio é publicado na hora, sem esperar todos
os e-mails saírem primeiro — os envios acontecem depois, em segundo
plano, sem atrasar a resposta pra quem postou.
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
        recipients = fetch_all(
            f"SELECT email, full_name FROM users WHERE {' AND '.join(conditions)}", params
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
        send_email(recipient["email"], f"Neue passende Anzeige: {title} — Maestro & Cantor", html)


def notify_new_message(base_url: str, recipient_email: str, recipient_name: str, sender_name: str) -> None:
    """
    E-mail avisando "você recebeu uma mensagem" — diferente do alerta
    de anúncio compatível acima. Cada pessoa pode desligar isso a
    qualquer momento em /profile (users.notify_messages); a rota que
    chama essa função (send_message em messages_routes.py) já confere
    notify_messages e email_verified antes de chamar.

    De propósito, o e-mail NÃO mostra o conteúdo da mensagem (só avisa
    que uma chegou) — assim a pessoa precisa entrar no site pra ler,
    o que ajuda com o objetivo de trazer gente de volta ao site.
    """
    inbox_url = f"{base_url.rstrip('/')}/messages"
    safe_recipient_name = html_module.escape(recipient_name)
    safe_sender_name = html_module.escape(sender_name)
    html = f"""
        <p>Hallo {safe_recipient_name},</p>
        <p><strong>{safe_sender_name}</strong> hat dir eine neue Nachricht auf Maestro &amp; Cantor geschickt.</p>
        <p><a href="{inbox_url}">{inbox_url}</a></p>
        <p>Du erhältst diese Benachrichtigung, weil Nachrichten-E-Mails für dein Konto aktiviert sind.
        Das kannst du jederzeit in deinem Profil ausschalten.</p>
        <hr>
        <p>(EN) <strong>{safe_sender_name}</strong> sent you a new message on Maestro &amp; Cantor.
        <a href="{inbox_url}">{inbox_url}</a><br>
        You're getting this because message e-mails are on for your account — you can turn them off anytime in your profile.</p>
    """
    send_email(recipient_email, f"Nova mensagem de {sender_name} — Maestro & Cantor", html)

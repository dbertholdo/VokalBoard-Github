"""Small, explicit copy library for transactional e-mails.

E-mail language is an account preference, not a browser cookie: a message can
be read days later on a different device.  Unsupported or missing preferences
fall back to English deliberately.
"""
from html import escape

EMAIL_LANGUAGES = {"de", "en", "fr", "it", "pt"}


def email_language(preferred_language: str | None) -> str:
    return preferred_language if preferred_language in EMAIL_LANGUAGES else "en"


def verification_email(language: str | None, name: str, url: str, hours: int) -> tuple[str, str]:
    lang = email_language(language)
    safe_name, safe_url = escape(name), escape(url, quote=True)
    copy = {
        "de": ("Bestätige deine E-Mail-Adresse", "Hallo", "Bitte bestätige deine E-Mail-Adresse für VokalBoard.", "Dieser Link ist"),
        "en": ("Confirm your email address", "Hello", "Please confirm your VokalBoard email address.", "This link is valid for"),
        "fr": ("Confirmez votre adresse e-mail", "Bonjour", "Veuillez confirmer votre adresse e-mail VokalBoard.", "Ce lien est valable"),
        "it": ("Conferma il tuo indirizzo e-mail", "Ciao", "Conferma il tuo indirizzo e-mail VokalBoard.", "Questo link è valido per"),
        "pt": ("Confirme seu e-mail", "Olá", "Confirme seu endereço de e-mail do VokalBoard.", "Este link é válido por"),
    }[lang]
    return f"{copy[0]} — VokalBoard", f"<p>{copy[1]} {safe_name},</p><p>{copy[2]}</p><p><a href=\"{safe_url}\">{safe_url}</a></p><p>{copy[3]} {hours} hours.</p>"


def password_reset_email(language: str | None, name: str, url: str, hours: int) -> tuple[str, str]:
    lang = email_language(language)
    safe_name, safe_url = escape(name), escape(url, quote=True)
    copy = {
        "de": ("Passwort zurücksetzen", "Hallo", "Klicke auf den Link, um ein neues Passwort festzulegen."),
        "en": ("Reset your password", "Hello", "Use this link to set a new password."),
        "fr": ("Réinitialisez votre mot de passe", "Bonjour", "Utilisez ce lien pour définir un nouveau mot de passe."),
        "it": ("Reimposta la password", "Ciao", "Usa questo link per impostare una nuova password."),
        "pt": ("Redefina sua senha", "Olá", "Use este link para definir uma nova senha."),
    }[lang]
    return f"{copy[0]} — VokalBoard", f"<p>{copy[1]} {safe_name},</p><p>{copy[2]}</p><p><a href=\"{safe_url}\">{safe_url}</a></p><p>This link is valid for {hours} hours.</p>"


def new_message_email(language: str | None, recipient_name: str, sender_name: str, inbox_url: str) -> tuple[str, str]:
    lang = email_language(language)
    recipient, sender, url = escape(recipient_name), escape(sender_name), escape(inbox_url, quote=True)
    copy = {
        "de": ("Neue Nachricht von", "Hallo", "hat dir eine neue Nachricht auf VokalBoard geschickt."),
        "en": ("New message from", "Hello", "sent you a new message on VokalBoard."),
        "fr": ("Nouveau message de", "Bonjour", "vous a envoyé un nouveau message sur VokalBoard."),
        "it": ("Nuovo messaggio da", "Ciao", "ti ha inviato un nuovo messaggio su VokalBoard."),
        "pt": ("Nova mensagem de", "Olá", "enviou uma nova mensagem no VokalBoard."),
    }[lang]
    return f"{copy[0]} {sender_name} — VokalBoard", f"<p>{copy[1]} {recipient},</p><p><strong>{sender}</strong> {copy[2]}</p><p><a href=\"{url}\">{url}</a></p>"

from app.email_localization import email_language, new_message_email, password_reset_email, verification_email


def test_email_language_uses_account_preference_or_english_fallback():
    assert email_language("pt") == "pt"
    assert email_language("zh") == "en"
    assert email_language(None) == "en"


def test_transactional_emails_use_localized_copy_and_escape_user_input():
    subject, html = verification_email("pt", "Ana <script>", "https://example.test/?a=1&b=2", 48)
    assert subject == "Confirme seu e-mail — VokalBoard"
    assert "&lt;script&gt;" in html
    assert "&amp;" in html

    reset_subject, _ = password_reset_email("zz", "Ana", "https://example.test/reset", 2)
    message_subject, _ = new_message_email("fr", "Ana", "Béla", "https://example.test/messages")
    assert reset_subject == "Reset your password — VokalBoard"
    assert message_subject.startswith("Nouveau message de")


def test_spanish_emails_and_fixed_sentences():
    from app.email_localization import vacancy_filled_email
    assert email_language("es") == "es"
    subject, body = verification_email("es", "Ana", "https://example.test/v", 24)
    assert subject.startswith("Confirma tu dirección de correo") and "válido durante 24 horas" in body
    assert "Dieser Link ist 24 Stunden gültig." in verification_email("de", "Anna", "https://example.test/v", 24)[1]
    assert "Die Vakanz in" in vacancy_filled_email("de", "Anna", "Requiem")[1]
    assert "A vaga em" not in vacancy_filled_email("en", "Ann", "Requiem")[1]


def test_romanian_emails():
    assert email_language("ro") == "ro"
    subject, body = verification_email("ro", "Ana", "https://example.test/v", 24)
    assert subject.startswith("Confirmă-ți adresa de e-mail") and "valabil 24 ore" in body


def test_email_footer_follows_the_recipient_language(client):
    from app.database import execute
    from app.email_layout import render_email
    from tests.test_security import register_test_user
    uid, email, _ = register_test_user(client, full_name="Footer DE")
    execute("UPDATE users SET preferred_language = 'de' WHERE id = :id", {"id": uid})
    # Production still holds the old Portuguese seed: it must be treated as a default.
    execute("UPDATE system_settings SET value = 'Equipe VokalBoard' WHERE key = 'email_layout_signature'")
    html = render_email("<p>Body</p>", email)
    assert "Dein Team von VokalBoard.com" in html and "weil du ein Konto bei VokalBoard.com hast" in html
    assert "Você recebeu" not in html
    assert "From Team VokalBoard.com" in render_email("<p>Body</p>", "nobody@example.test")
    # A custom admin text is sent as-is.
    execute("UPDATE system_settings SET value = 'Liebe Grüße, Daniel' WHERE key = 'email_layout_signature'")
    assert "Liebe Grüße, Daniel" in render_email("<p>Body</p>", email)
    execute("UPDATE system_settings SET value = 'From Team VokalBoard.com' WHERE key = 'email_layout_signature'")

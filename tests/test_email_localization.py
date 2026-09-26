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

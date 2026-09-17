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

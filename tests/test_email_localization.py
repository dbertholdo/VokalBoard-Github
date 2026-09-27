from app.email_localization import email_language, new_message_email, password_reset_email, verification_email


def test_email_language_uses_account_preference_or_english_fallback():
    assert email_language("pt") == "pt"
    assert email_language("zh") == "zh"
    assert email_language("xx") == "en"
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


def test_chinese_and_korean_emails_put_the_name_first():
    subject, body = verification_email("zh", "张三", "https://example.test/v", 24)
    assert subject.startswith("确认你的邮箱地址") and body.startswith("<p>张三，你好！</p>") and "24 小时" in body
    subject, body = verification_email("ko", "김민지", "https://example.test/v", 24)
    assert subject.startswith("이메일 주소를 인증하세요") and body.startswith("<p>김민지 님, 안녕하세요!</p>")


def test_formerly_german_only_emails_follow_the_recipient_language():
    from app.email_localization import badge_unlocked_email, listing_match_alert_email, urgent_listing_reminder_email
    subject, body = listing_match_alert_email("en", "Ann", "Requiem <b>", "Köln", "https://example.test/l/1")
    assert subject == "New matching listing: Requiem <b> — VokalBoard"
    assert "Requiem &lt;b&gt;</strong> — Köln" in body and "Hallo" not in body and "(EN)" not in body
    assert urgent_listing_reminder_email("de", "Anna", "Messiah", None, "u")[0] == "Immer noch dringend: Messiah — VokalBoard"
    assert urgent_listing_reminder_email("ko", "김", "Messiah", None, "u")[0].startswith("아직 긴급해요")
    assert badge_unlocked_email("es", "Ana", "Embajador(a)", "u")[0] == "Nueva insignia desbloqueada — VokalBoard"


def test_badge_names_in_emails_are_localized():
    from app.badges import badge_label
    assert badge_label({"key": "listing"}, "fr") == "Première annonce"
    assert badge_label({"key": "anniversary", "years": 2}, "de") == "Jahrestag (2 Jahre)"
    assert badge_label({"key": "views", "threshold": 100}, "zh").endswith("(100+)")


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

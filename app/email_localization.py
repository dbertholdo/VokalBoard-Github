"""Small, explicit copy library for transactional e-mails.

E-mail language is an account preference, not a browser cookie: a message can
be read days later on a different device.  Unsupported or missing preferences
fall back to English deliberately.
"""
from html import escape

# es, ro, zh, ko (2026-09-26): added languages — e-mails too (docs/I18N.md phase 3).
EMAIL_LANGUAGES = {"de", "en", "fr", "it", "pt", "es", "ro", "zh", "ko", "tr"}

# "This link is valid for N hours." as one sentence per language (it used to
# end in English "hours" for everyone — "Dieser Link ist 24 hours.").
_VALID_FOR = {
    "de": "Dieser Link ist {hours} Stunden gültig.",
    "en": "This link is valid for {hours} hours.",
    "fr": "Ce lien est valable {hours} heures.",
    "it": "Questo link è valido per {hours} ore.",
    "pt": "Este link é válido por {hours} horas.",
    "es": "Este enlace es válido durante {hours} horas.",
    "ro": "Acest link este valabil {hours} ore.",
    "tr": "Bu bağlantı {hours} saat geçerlidir.",
    "zh": "此链接的有效期为 {hours} 小时。",
    "ko": "이 링크는 {hours}시간 동안 유효해요.",
}


def email_language(preferred_language: str | None) -> str:
    return preferred_language if preferred_language in EMAIL_LANGUAGES else "en"


def _hello(lang: str, word: str, name: str) -> str:
    """Greeting paragraph; zh/ko put the name first ("张三，你好！" / "김철수 님, 안녕하세요!")."""
    if lang == "zh":
        return f"<p>{name}，{word}！</p>"
    if lang == "ko":
        return f"<p>{name} 님, {word}!</p>"
    return f"<p>{word} {name},</p>"


_GREETING = {"de": "Hallo", "en": "Hello", "fr": "Bonjour", "it": "Ciao", "pt": "Olá", "es": "Hola", "ro": "Bună",
             "zh": "你好", "ko": "안녕하세요", "tr": "Merhaba"}
_STOP = {"zh": "。"}  # sentence end after a bold status word; "." elsewhere


def verification_email(language: str | None, name: str, url: str, hours: int) -> tuple[str, str]:
    lang = email_language(language)
    safe_name, safe_url = escape(name), escape(url, quote=True)
    copy = {
        "de": ("Bestätige deine E-Mail-Adresse", "Hallo", "Bitte bestätige deine E-Mail-Adresse für VokalBoard.", "Dieser Link ist"),
        "en": ("Confirm your email address", "Hello", "Please confirm your VokalBoard email address.", "This link is valid for"),
        "fr": ("Confirmez votre adresse e-mail", "Bonjour", "Veuillez confirmer votre adresse e-mail VokalBoard.", "Ce lien est valable"),
        "it": ("Conferma il tuo indirizzo e-mail", "Ciao", "Conferma il tuo indirizzo e-mail VokalBoard.", "Questo link è valido per"),
        "pt": ("Confirme seu e-mail", "Olá", "Confirme seu endereço de e-mail do VokalBoard.", "Este link é válido por"),
        "es": ("Confirma tu dirección de correo", "Hola", "Confirma tu dirección de correo de VokalBoard.", ""),
        "ro": ("Confirmă-ți adresa de e-mail", "Bună", "Confirmă-ți adresa de e-mail pentru VokalBoard.", ""),
        "tr": ("E-posta adresini onayla", "Merhaba", "Lütfen VokalBoard e-posta adresini onayla.", ""),
        "zh": ("确认你的邮箱地址", "你好", "请确认你在 VokalBoard 的邮箱地址。", ""),
        "ko": ("이메일 주소를 인증하세요", "안녕하세요", "VokalBoard 이메일 주소를 인증해 주세요.", ""),
    }[lang]
    return f"{copy[0]} — VokalBoard", f"{_hello(lang, copy[1], safe_name)}<p>{copy[2]}</p><p><a href=\"{safe_url}\">{safe_url}</a></p><p>{_VALID_FOR[lang].format(hours=hours)}</p>"


def password_reset_email(language: str | None, name: str, url: str, hours: int) -> tuple[str, str]:
    lang = email_language(language)
    safe_name, safe_url = escape(name), escape(url, quote=True)
    copy = {
        "de": ("Passwort zurücksetzen", "Hallo", "Klicke auf den Link, um ein neues Passwort festzulegen."),
        "en": ("Reset your password", "Hello", "Use this link to set a new password."),
        "fr": ("Réinitialisez votre mot de passe", "Bonjour", "Utilisez ce lien pour définir un nouveau mot de passe."),
        "it": ("Reimposta la password", "Ciao", "Usa questo link per impostare una nuova password."),
        "pt": ("Redefina sua senha", "Olá", "Use este link para definir uma nova senha."),
        "es": ("Restablece tu contraseña", "Hola", "Usa este enlace para establecer una contraseña nueva."),
        "ro": ("Resetează-ți parola", "Bună", "Folosește acest link pentru a seta o parolă nouă."),
        "tr": ("Şifreni sıfırla", "Merhaba", "Yeni bir şifre belirlemek için bu bağlantıyı kullan."),
        "zh": ("重置密码", "你好", "请使用此链接设置新密码。"),
        "ko": ("비밀번호 재설정", "안녕하세요", "이 링크로 새 비밀번호를 설정하세요."),
    }[lang]
    return f"{copy[0]} — VokalBoard", f"{_hello(lang, copy[1], safe_name)}<p>{copy[2]}</p><p><a href=\"{safe_url}\">{safe_url}</a></p><p>{_VALID_FOR[lang].format(hours=hours)}</p>"


def new_message_email(language: str | None, recipient_name: str, sender_name: str, inbox_url: str) -> tuple[str, str]:
    lang = email_language(language)
    recipient, sender, url = escape(recipient_name), escape(sender_name), escape(inbox_url, quote=True)
    copy = {
        "de": ("Neue Nachricht von", "Hallo", "hat dir eine neue Nachricht auf VokalBoard geschickt."),
        "en": ("New message from", "Hello", "sent you a new message on VokalBoard."),
        "fr": ("Nouveau message de", "Bonjour", "vous a envoyé un nouveau message sur VokalBoard."),
        "it": ("Nuovo messaggio da", "Ciao", "ti ha inviato un nuovo messaggio su VokalBoard."),
        "pt": ("Nova mensagem de", "Olá", "enviou uma nova mensagem no VokalBoard."),
        "es": ("Nuevo mensaje de", "Hola", "te envió un mensaje nuevo en VokalBoard."),
        "ro": ("Mesaj nou de la", "Bună", "ți-a trimis un mesaj nou pe VokalBoard."),
        "tr": ("Yeni mesaj:", "Merhaba", "sana VokalBoard'da yeni bir mesaj gönderdi."),
        "zh": ("新消息来自", "你好", "在 VokalBoard 上给你发了一条新消息。"),
        "ko": ("새 메시지:", "안녕하세요", "님이 VokalBoard에서 새 메시지를 보냈어요."),
    }[lang]
    return f"{copy[0]} {sender_name} — VokalBoard", f"{_hello(lang, copy[1], recipient)}<p><strong>{sender}</strong> {copy[2]}</p><p><a href=\"{url}\">{url}</a></p>"


# --- P3.C: convites / candidaturas ------------------------------------
def invitation_received_email(language: str | None, recipient_name: str, listing_title: str, url: str) -> tuple[str, str]:
    """A CONTRACTOR invited this singer to one of their vacancies."""
    lang = email_language(language)
    recipient, title, safe_url = escape(recipient_name), escape(listing_title), escape(url, quote=True)
    copy = {
        "de": ("Neue Einladung", "Hallo", "Du wurdest zu einer Vakanz eingeladen:", "Antworte innerhalb von 48 Stunden."),
        "en": ("New invitation", "Hello", "You've been invited to a vacancy:", "Respond within 48 hours."),
        "fr": ("Nouvelle invitation", "Bonjour", "Vous avez été invité(e) à un poste :", "Répondez dans les 48 heures."),
        "it": ("Nuovo invito", "Ciao", "Sei stato/a invitato/a a un posto:", "Rispondi entro 48 ore."),
        "pt": ("Novo convite", "Olá", "Você foi convidado(a) para uma vaga:", "Responda em até 48 horas."),
        "es": ("Nueva invitación", "Hola", "Te han invitado a una vacante:", "Responde en un plazo de 48 horas."),
        "ro": ("Invitație nouă", "Bună", "Ai fost invitat(ă) la un post:", "Răspunde în 48 de ore."),
        "tr": ("Yeni davet", "Merhaba", "Bir pozisyona davet edildin:", "48 saat içinde yanıt ver."),
        "zh": ("新邀请", "你好", "你被邀请参加一个职位：", "请在 48 小时内回复。"),
        "ko": ("새 초대", "안녕하세요", "포지션에 초대받았어요:", "48시간 안에 답해 주세요."),
    }[lang]
    return f"{copy[0]} — VokalBoard", f"{_hello(lang, copy[1], recipient)}<p>{copy[2]} <strong>{title}</strong></p><p><a href=\"{safe_url}\">{safe_url}</a></p><p>{copy[3]}</p>"


def application_received_email(language: str | None, recipient_name: str, artist_name: str, listing_title: str, url: str) -> tuple[str, str]:
    """An ARTIST applied on their own to one of this contractor's vacancies."""
    lang = email_language(language)
    recipient, artist, title, safe_url = escape(recipient_name), escape(artist_name), escape(listing_title), escape(url, quote=True)
    copy = {
        "de": ("Neue Bewerbung", "Hallo", "hat sich auf eine Vakanz in", "beworben."),
        "en": ("New application", "Hello", "applied to a vacancy in", "."),
        "fr": ("Nouvelle candidature", "Bonjour", "a postulé à un poste dans", "."),
        "it": ("Nuova candidatura", "Ciao", "si è candidato/a a un posto in", "."),
        "pt": ("Nova candidatura", "Olá", "se candidatou a uma vaga em", "."),
        "es": ("Nueva candidatura", "Hola", "se postuló a una vacante en", "."),
        "ro": ("Candidatură nouă", "Bună", "a aplicat la un post din", "."),
        "tr": ("Yeni başvuru", "Merhaba", "şu ilandaki bir pozisyona başvurdu:", "."),
        "zh": ("新申请", "你好", "申请了", " 中的职位。"),
        "ko": ("새 지원", "안녕하세요", "님이", "의 포지션에 지원했어요."),
    }[lang]
    return f"{copy[0]} — VokalBoard", f"{_hello(lang, copy[1], recipient)}<p><strong>{artist}</strong> {copy[2]} <strong>{title}</strong>{copy[3]}</p><p><a href=\"{safe_url}\">{safe_url}</a></p>"


def invitation_response_email(language: str | None, recipient_name: str, listing_title: str, accepted: bool, url: str) -> tuple[str, str]:
    """Tells whoever INITIATED a row (contractor for a convite, artist for
    a candidatura) that the other side responded."""
    lang = email_language(language)
    recipient, title, safe_url = escape(recipient_name), escape(listing_title), escape(url, quote=True)
    status_word = {
        "de": "angenommen" if accepted else "abgelehnt",
        "en": "accepted" if accepted else "declined",
        "fr": "acceptée" if accepted else "refusée",
        "it": "accettata" if accepted else "rifiutata",
        "pt": "aceita" if accepted else "recusada",
        "es": "aceptada" if accepted else "rechazada",
        "ro": "acceptată" if accepted else "refuzată",
        "tr": "kabul edildi" if accepted else "reddedildi",
        "zh": "接受" if accepted else "拒绝",
        "ko": "수락되었어요" if accepted else "거절되었어요",
    }[lang]
    copy = {
        "de": ("Antwort erhalten", "Hallo", "Deine Anfrage für", "wurde"),
        "en": ("Response received", "Hello", "Your request for", "was"),
        "fr": ("Réponse reçue", "Bonjour", "Votre demande pour", "a été"),
        "it": ("Risposta ricevuta", "Ciao", "La tua richiesta per", "è stata"),
        "pt": ("Resposta recebida", "Olá", "Sua solicitação para", "foi"),
        "es": ("Respuesta recibida", "Hola", "Tu solicitud para", "fue"),
        "ro": ("Răspuns primit", "Bună", "Cererea ta pentru", "a fost"),
        "tr": ("Yanıt geldi", "Merhaba", "Şu talebin:", "durumu:"),
        "zh": ("已收到回复", "你好", "你对", "的申请已被"),
        "ko": ("답변이 왔어요", "안녕하세요", "요청하신", "건이"),
    }[lang]
    return f"{copy[0]} — VokalBoard", f"{_hello(lang, copy[1], recipient)}<p>{copy[2]} <strong>{title}</strong> {copy[3]} <strong>{status_word}</strong>{_STOP.get(lang, ".")}</p><p><a href=\"{safe_url}\">{safe_url}</a></p>"


def vacancy_filled_email(language: str | None, recipient_name: str, listing_title: str) -> tuple[str, str]:
    """Tells an artist whose invitation/candidatura was still pending
    that the vacancy got filled by someone else — see P3.D's "convite
    express" (several people invited to the same vacancy, first to
    accept wins) for why this matters."""
    lang = email_language(language)
    recipient, title = escape(recipient_name), escape(listing_title)
    copy = {
        "de": ("Vakanz bereits vergeben", "Hallo", "wurde inzwischen von jemand anderem besetzt. Danke für dein Interesse!"),
        "en": ("Vacancy already filled", "Hello", "has since been filled by someone else. Thanks for your interest!"),
        "fr": ("Poste déjà pourvu", "Bonjour", "a depuis été pourvu par quelqu'un d'autre. Merci de votre intérêt !"),
        "it": ("Posto già assegnato", "Ciao", "è stato nel frattempo assegnato a qualcun altro. Grazie per l'interesse!"),
        "pt": ("Vaga já preenchida", "Olá", "já foi preenchida por outra pessoa. Obrigado pelo interesse!"),
        "es": ("Vacante ya cubierta", "Hola", "ya fue cubierta por otra persona. ¡Gracias por tu interés!"),
        "ro": ("Post deja ocupat", "Bună", "a fost între timp ocupat de altcineva. Mulțumim pentru interes!"),
        "tr": ("Pozisyon zaten doldu", "Merhaba", "pozisyonu bu arada başka biriyle dolduruldu. İlgin için teşekkürler!"),
        "zh": ("职位已满", "你好", "职位已由他人获得。感谢你的关注！"),
        "ko": ("포지션 마감", "안녕하세요", "포지션은 이미 다른 분으로 채워졌어요. 관심 가져 주셔서 감사해요!"),
    }[lang]
    prefix = {"de": "Die Vakanz in", "en": "The vacancy in", "fr": "Le poste dans", "it": "Il posto in",
              "pt": "A vaga em", "es": "La vacante en", "ro": "Postul din",
              "zh": "你关注的", "ko": "지원하신", "tr": "Başvurduğun"}[lang]
    return f"{copy[0]} — VokalBoard", f"{_hello(lang, copy[1], recipient)}<p>{prefix} <strong>{title}</strong> {copy[2]}</p>"


def match_evaluation_reminder_email(language: str | None, recipient_name: str, counterpart_first_name: str, url: str) -> tuple[str, str]:
    """P3.F: lembrete pra avaliar o outro lado do Match, dentro da janela
    de 14 dias — texto-base pedido no documento-fonte ("Wie war deine
    Erfahrung? Bewerte {Primeiro nome}!"), traduzido nas línguas do site.
    A avaliação em si é secreta (ver app/match_evaluations.py) — o
    e-mail só convida a avaliar, não revela nada sobre avaliações já
    recebidas."""
    lang = email_language(language)
    recipient = escape(recipient_name)
    counterpart = escape(counterpart_first_name)
    safe_url = escape(url, quote=True)
    copy = {
        "de": ("Wie war deine Erfahrung?", "Hallo", f"Wie war deine Erfahrung? Bewerte {counterpart}!", "Bewerten"),
        "en": ("How was your experience?", "Hello", f"How was your experience? Rate {counterpart}!", "Rate now"),
        "fr": ("Comment s'est passée votre expérience ?", "Bonjour", f"Comment s'est passée votre expérience ? Évaluez {counterpart} !", "Évaluer"),
        "it": ("Com'è andata la tua esperienza?", "Ciao", f"Com'è andata la tua esperienza? Valuta {counterpart}!", "Valuta ora"),
        "pt": ("Como foi sua experiência?", "Olá", f"Como foi sua experiência? Avalie {counterpart}!", "Avaliar agora"),
        "es": ("¿Qué tal fue tu experiencia?", "Hola", f"¿Qué tal fue tu experiencia? ¡Valora a {counterpart}!", "Valorar ahora"),
        "ro": ("Cum a fost experiența ta?", "Bună", f"Cum a fost experiența ta? Evaluează-l/o pe {counterpart}!", "Evaluează acum"),
        "tr": ("Deneyimin nasıldı?", "Merhaba", f"Deneyimin nasıldı? {counterpart} kişisini değerlendir!", "Şimdi değerlendir"),
        "zh": ("合作体验如何？", "你好", f"这次合作体验如何？给 {counterpart} 评个分吧！", "立即评价"),
        "ko": ("함께한 경험은 어땠나요?", "안녕하세요", f"함께한 경험은 어땠나요? {counterpart} 님을 평가해 주세요!", "지금 평가하기"),
    }[lang]
    return (
        f"{copy[0]} — VokalBoard",
        f"{_hello(lang, copy[1], recipient)}<p>{copy[2]}</p><p><a href=\"{safe_url}\">{copy[3]}</a></p>",
    )


def match_invoice_requested_email(language: str | None, recipient_name: str, counterpart_first_name: str, production_title: str, url: str) -> tuple[str, str]:
    """P4: a outra parte pediu pra emitir/revisar a Rechnung deste Match.
    Nunca menciona valores/dados — só avisa que há uma ação pendente
    (ver app/invoice_match_drafts.py, sigilo dos dados fiscais/bancários
    é garantido por criptografia, nunca por e-mail)."""
    lang = email_language(language)
    recipient, counterpart, title = escape(recipient_name), escape(counterpart_first_name), escape(production_title)
    safe_url = escape(url, quote=True)
    copy = {
        "de": ("Rechnung angefordert", "Hallo", f"{counterpart} hat eine Rechnung für „{title}" + "“ angefordert.", "Öffnen"),
        "en": ("Invoice requested", "Hello", f"{counterpart} requested an invoice for “{title}”.", "Open"),
        "fr": ("Facture demandée", "Bonjour", f"{counterpart} a demandé une facture pour « {title} ».", "Ouvrir"),
        "it": ("Fattura richiesta", "Ciao", f"{counterpart} ha richiesto una fattura per “{title}”.", "Apri"),
        "pt": ("Fatura solicitada", "Olá", f"{counterpart} pediu uma fatura para “{title}”.", "Abrir"),
        "es": ("Factura solicitada", "Hola", f"{counterpart} solicitó una factura para “{title}”.", "Abrir"),
        "ro": ("Factură solicitată", "Bună", f"{counterpart} a solicitat o factură pentru „{title}”.", "Deschide"),
        "tr": ("Fatura talep edildi", "Merhaba", f"{counterpart}, “{title}” için fatura talep etti.", "Aç"),
        "zh": ("发票请求", "你好", f"{counterpart} 请求为“{title}”开具发票。", "打开"),
        "ko": ("인보이스 요청", "안녕하세요", f"{counterpart} 님이 “{title}”의 인보이스를 요청했어요.", "열기"),
    }[lang]
    return (
        f"{copy[0]} — VokalBoard",
        f"{_hello(lang, copy[1], recipient)}<p>{copy[2]}</p><p><a href=\"{safe_url}\">{copy[3]}</a></p>",
    )


def match_invoice_ready_for_review_email(language: str | None, recipient_name: str, counterpart_first_name: str, production_title: str, url: str) -> tuple[str, str]:
    """P4: o emissor preencheu a Rechnung do Match — a outra parte
    (contratante) precisa revisar e confirmar antes do PDF ser gerado e
    enviado por e-mail às duas partes."""
    lang = email_language(language)
    recipient, counterpart, title = escape(recipient_name), escape(counterpart_first_name), escape(production_title)
    safe_url = escape(url, quote=True)
    copy = {
        "de": ("Rechnung bereit zur Prüfung", "Hallo", f"{counterpart} hat eine Rechnung für „{title}" + "“ erstellt — bitte prüfe und bestätige sie.", "Prüfen"),
        "en": ("Invoice ready for review", "Hello", f"{counterpart} prepared an invoice for “{title}” — please review and confirm it.", "Review"),
        "fr": ("Facture prête à être vérifiée", "Bonjour", f"{counterpart} a préparé une facture pour « {title} » — merci de la vérifier et de la confirmer.", "Vérifier"),
        "it": ("Fattura pronta per la revisione", "Ciao", f"{counterpart} ha preparato una fattura per “{title}” — controllala e confermala.", "Rivedi"),
        "pt": ("Fatura pronta para revisão", "Olá", f"{counterpart} preparou uma fatura para “{title}” — revise e confirme.", "Revisar"),
        "es": ("Factura lista para revisar", "Hola", f"{counterpart} preparó una factura para “{title}”: revísala y confírmala.", "Revisar"),
        "ro": ("Factură gata de verificare", "Bună", f"{counterpart} a pregătit o factură pentru „{title}” — verific-o și confirm-o.", "Verifică"),
        "tr": ("Fatura incelemeye hazır", "Merhaba", f"{counterpart}, “{title}” için bir fatura hazırladı — lütfen incele ve onayla.", "İncele"),
        "zh": ("发票待审核", "你好", f"{counterpart} 已为“{title}”准备好发票，请审核并确认。", "审核"),
        "ko": ("인보이스 검토 요청", "안녕하세요", f"{counterpart} 님이 “{title}”의 인보이스를 작성했어요. 검토하고 확인해 주세요.", "검토하기"),
    }[lang]
    return (
        f"{copy[0]} — VokalBoard",
        f"{_hello(lang, copy[1], recipient)}<p>{copy[2]}</p><p><a href=\"{safe_url}\">{copy[3]}</a></p>",
    )


def match_invoice_confirmed_email(language: str | None, recipient_name: str, production_title: str) -> tuple[str, str]:
    """P4: PDF final anexado a este e-mail para as duas partes — o
    VokalBoard não guarda cópia nenhuma (Zero-Storage, ver CLAUDE.md
    Seção 2)."""
    lang = email_language(language)
    recipient, title = escape(recipient_name), escape(production_title)
    copy = {
        "de": ("Deine Rechnung ist da", "Hallo", f"Im Anhang findest du die Rechnung für „{title}" + "“. VokalBoard speichert keine Kopie."),
        "en": ("Your invoice is ready", "Hello", f"Attached is the invoice for “{title}”. VokalBoard keeps no copy."),
        "fr": ("Votre facture est prête", "Bonjour", f"Vous trouverez en pièce jointe la facture pour « {title} ». VokalBoard n'en conserve aucune copie."),
        "it": ("La tua fattura è pronta", "Ciao", f"In allegato la fattura per “{title}”. VokalBoard non conserva alcuna copia."),
        "pt": ("Sua fatura está pronta", "Olá", f"Em anexo está a fatura de “{title}”. O VokalBoard não guarda nenhuma cópia."),
        "es": ("Tu factura está lista", "Hola", f"Adjunta encontrarás la factura de “{title}”. VokalBoard no guarda ninguna copia."),
        "ro": ("Factura ta este gata", "Bună", f"Găsești atașată factura pentru „{title}”. VokalBoard nu păstrează nicio copie."),
        "tr": ("Faturan hazır", "Merhaba", f"“{title}” faturası ektedir. VokalBoard hiçbir kopya saklamaz."),
        "zh": ("你的发票已开好", "你好", f"附件是“{title}”的发票。VokalBoard 不保留任何副本。"),
        "ko": ("인보이스가 준비되었어요", "안녕하세요", f"“{title}”의 인보이스를 첨부했어요. VokalBoard는 어떤 사본도 보관하지 않아요."),
    }[lang]
    return (
        f"{copy[0]} — VokalBoard",
        f"{_hello(lang, copy[1], recipient)}<p>{copy[2]}</p>",
    )


def match_invoice_expired_email(language: str | None, recipient_name: str, production_title: str, url: str) -> tuple[str, str]:
    """P4 Etapa 2: o rascunho de Rechnung do Match passou dos 7 dias sem
    confirmação e foi apagado (Zero-Storage — nada fica retido). Enviado
    às DUAS partes, nunca menciona quem "travou" o processo — o motivo
    real (esqueceram, desistiram, etc.) não é rastreado nem exposto."""
    lang = email_language(language)
    recipient, title = escape(recipient_name), escape(production_title)
    safe_url = escape(url, quote=True)
    copy = {
        "de": ("Rechnung-Entwurf abgelaufen", "Hallo", f"Der Rechnungsentwurf für „{title}" + "“ wurde nicht innerhalb von 7 Tagen bestätigt und wurde automatisch gelöscht. Du kannst bei Bedarf erneut eine Rechnung anfordern.", "Erneut anfordern"),
        "en": ("Invoice draft expired", "Hello", f"The invoice draft for “{title}” wasn't confirmed within 7 days and was automatically deleted. You can request a new one if it's still needed.", "Request again"),
        "fr": ("Brouillon de facture expiré", "Bonjour", f"Le brouillon de facture pour « {title} » n'a pas été confirmé dans les 7 jours et a été supprimé automatiquement. Vous pouvez en redemander une si besoin.", "Redemander"),
        "it": ("Bozza di fattura scaduta", "Ciao", f"La bozza di fattura per “{title}” non è stata confermata entro 7 giorni ed è stata eliminata automaticamente. Puoi richiederne una nuova se serve ancora.", "Richiedi di nuovo"),
        "pt": ("Rascunho de fatura expirado", "Olá", f"O rascunho de fatura de “{title}” não foi confirmado em 7 dias e foi apagado automaticamente. Você pode pedir uma nova, se ainda for necessário.", "Pedir de novo"),
        "es": ("Borrador de factura caducado", "Hola", f"El borrador de factura de “{title}” no se confirmó en 7 días y se eliminó automáticamente. Puedes solicitar una nueva si todavía la necesitas.", "Solicitar de nuevo"),
        "ro": ("Ciorna facturii a expirat", "Bună", f"Ciorna facturii pentru „{title}” nu a fost confirmată în 7 zile și a fost ștearsă automat. Poți solicita una nouă dacă mai este nevoie.", "Solicită din nou"),
        "tr": ("Fatura taslağının süresi doldu", "Merhaba", f"“{title}” için fatura taslağı 7 gün içinde onaylanmadığı için otomatik olarak silindi. Hâlâ gerekiyorsa yenisini talep edebilirsin.", "Tekrar talep et"),
        "zh": ("发票草稿已过期", "你好", f"“{title}”的发票草稿在 7 天内未被确认，已自动删除。如仍需要，可以重新申请。", "重新申请"),
        "ko": ("인보이스 초안 만료", "안녕하세요", f"“{title}”의 인보이스 초안이 7일 안에 확인되지 않아 자동으로 삭제되었어요. 아직 필요하다면 다시 요청할 수 있어요.", "다시 요청하기"),
    }[lang]
    return (
        f"{copy[0]} — VokalBoard",
        f"{_hello(lang, copy[1], recipient)}<p>{copy[2]}</p><p><a href=\"{safe_url}\">{copy[3]}</a></p>",
    )


def report_resolved_email(language: str | None, recipient_name: str, listing_title: str, accepted: bool) -> tuple[str, str]:
    """P6 (18/09/2026): "resposta a denúncias e notificação ao usuário
    quando denúncia for aceita" — avisa quem DENUNCIOU o que o Admin
    decidiu (ver app/moderation.py, `resolve_report()`). Nunca menciona
    a identidade de quem publicou o anúncio nem detalhes da decisão
    interna — só confirma que foi revisado."""
    lang = email_language(language)
    recipient, title = escape(recipient_name), escape(listing_title)
    if accepted:
        body = {
            "de": f"deine Meldung zu „{title}" + "“ wurde geprüft und Maßnahmen wurden ergriffen. Danke, dass du geholfen hast, VokalBoard sicher zu halten.",
            "en": f"your report about “{title}” has been reviewed and action was taken. Thanks for helping keep VokalBoard safe.",
            "fr": f"votre signalement concernant « {title} » a été examiné et des mesures ont été prises. Merci de nous aider à garder VokalBoard sûr.",
            "it": f"la tua segnalazione su “{title}” è stata esaminata e sono state prese delle misure. Grazie per aiutarci a mantenere sicuro VokalBoard.",
            "pt": f"sua denúncia sobre “{title}” foi analisada e uma ação foi tomada. Obrigado por ajudar a manter o VokalBoard seguro.",
            "es": f"tu denuncia sobre “{title}” ha sido revisada y se han tomado medidas. Gracias por ayudar a mantener VokalBoard seguro.",
            "ro": f"raportul tău despre „{title}” a fost analizat și s-au luat măsuri. Mulțumim că ajuți la menținerea siguranței pe VokalBoard.",
            "tr": f"“{title}” hakkındaki bildirimin incelendi ve gerekli işlem yapıldı. VokalBoard'u güvenli tutmaya yardım ettiğin için teşekkürler.",
            "zh": f"你对“{title}”的举报已审核，我们已采取措施。感谢你帮助维护 VokalBoard 的安全。",
            "ko": f"“{title}”에 대한 신고를 검토하고 조치를 취했어요. VokalBoard를 안전하게 지켜 주셔서 감사해요.",
        }[lang]
    else:
        body = {
            "de": f"deine Meldung zu „{title}" + "“ wurde geprüft. Wir haben keinen Verstoß gegen unsere Richtlinien festgestellt.",
            "en": f"your report about “{title}” has been reviewed. We didn't find a violation of our guidelines.",
            "fr": f"votre signalement concernant « {title} » a été examiné. Nous n'avons constaté aucune infraction à nos règles.",
            "it": f"la tua segnalazione su “{title}” è stata esaminata. Non abbiamo riscontrato una violazione delle nostre regole.",
            "pt": f"sua denúncia sobre “{title}” foi analisada. Não encontramos uma violação das nossas regras nesse caso.",
            "es": f"tu denuncia sobre “{title}” ha sido revisada. No encontramos ninguna infracción de nuestras normas.",
            "ro": f"raportul tău despre „{title}” a fost analizat. Nu am găsit o încălcare a regulilor noastre.",
            "tr": f"“{title}” hakkındaki bildirimin incelendi. Kurallarımızın ihlal edildiğini tespit etmedik.",
            "zh": f"你对“{title}”的举报已审核。我们没有发现违反规则的情况。",
            "ko": f"“{title}”에 대한 신고를 검토했어요. 규칙 위반은 발견되지 않았어요.",
        }[lang]
    subject = {
        "de": "Deine Meldung wurde geprüft",
        "en": "Your report has been reviewed",
        "fr": "Votre signalement a été examiné",
        "it": "La tua segnalazione è stata esaminata",
        "pt": "Sua denúncia foi analisada",
        "es": "Tu denuncia ha sido revisada",
        "ro": "Raportul tău a fost analizat",
        "tr": "Bildirimin incelendi",
        "zh": "你的举报已审核",
        "ko": "신고가 검토되었어요",
    }[lang]
    greeting = _GREETING[lang]
    return f"{subject} — VokalBoard", f"{_hello(lang, greeting, recipient)}<p>{body}</p>"


def moderation_punishment_email(language: str | None, recipient_name: str, listing_title: str, punishment: str) -> tuple[str, str]:
    """P6 (18/09/2026): "no botão de denúncia precisamos definir
    alguma forma de warning/punição/banimento" — avisa o AUTOR do
    anúncio denunciado (não quem denunciou — ver
    report_resolved_email() acima) sobre a decisão tomada ao aceitar a
    denúncia. `punishment` é um de "warning"/"suspend"/"ban" (ver
    app/moderation.py, PUNISHMENT_TYPES)."""
    lang = email_language(language)
    recipient, title = escape(recipient_name), escape(listing_title)
    bodies = {
        "de": {
            "warning": f"wir haben eine Meldung zu „{title}" + "“ geprüft und eine Verwarnung ausgesprochen. Bitte stelle sicher, dass zukünftige Inhalte unseren Richtlinien entsprechen.",
            "suspend": f"nach Prüfung einer Meldung zu „{title}" + "“ wurde dein Konto vorübergehend deaktiviert. Du kannst es reaktivieren, indem du dich erneut einloggst.",
            "ban": "nach Prüfung einer Meldung wurde dein Konto dauerhaft gesperrt. Diese Entscheidung ist endgültig.",
        },
        "en": {
            "warning": f"we reviewed a report about “{title}” and issued a warning. Please make sure future content follows our guidelines.",
            "suspend": f"after reviewing a report about “{title}”, your account has been temporarily suspended. You can reactivate it by logging in again.",
            "ban": "after reviewing a report, your account has been permanently banned. This decision is final.",
        },
        "fr": {
            "warning": f"nous avons examiné un signalement concernant « {title} » et émis un avertissement. Merci de veiller à ce que vos futurs contenus respectent nos règles.",
            "suspend": f"après examen d'un signalement concernant « {title} », votre compte a été temporairement suspendu. Vous pouvez le réactiver en vous reconnectant.",
            "ban": "après examen d'un signalement, votre compte a été banni définitivement. Cette décision est finale.",
        },
        "it": {
            "warning": f"abbiamo esaminato una segnalazione su “{title}” e abbiamo emesso un avvertimento. Assicurati che i contenuti futuri rispettino le nostre regole.",
            "suspend": f"dopo aver esaminato una segnalazione su “{title}”, il tuo account è stato temporaneamente sospeso. Puoi riattivarlo effettuando di nuovo l'accesso.",
            "ban": "dopo aver esaminato una segnalazione, il tuo account è stato bannato definitivamente. Questa decisione è definitiva.",
        },
        "pt": {
            "warning": f"analisamos uma denúncia sobre “{title}” e emitimos um aviso. Por favor, garanta que os próximos conteúdos sigam nossas regras.",
            "suspend": f"após analisar uma denúncia sobre “{title}”, sua conta foi temporariamente suspensa. Você pode reativá-la fazendo login novamente.",
            "ban": "após analisar uma denúncia, sua conta foi banida permanentemente. Essa decisão é definitiva.",
        },
        "es": {
            "warning": f"revisamos una denuncia sobre “{title}” y emitimos una advertencia. Asegúrate de que tus próximos contenidos cumplan nuestras normas.",
            "suspend": f"tras revisar una denuncia sobre “{title}”, tu cuenta ha sido suspendida temporalmente. Puedes reactivarla iniciando sesión de nuevo.",
            "ban": "tras revisar una denuncia, tu cuenta ha sido bloqueada de forma permanente. Esta decisión es definitiva.",
        },
        "ro": {
            "warning": f"am analizat un raport despre „{title}” și am emis un avertisment. Asigură-te că viitoarele conținuturi respectă regulile noastre.",
            "suspend": f"după analizarea unui raport despre „{title}”, contul tău a fost suspendat temporar. Îl poți reactiva autentificându-te din nou.",
            "ban": "după analizarea unui raport, contul tău a fost blocat definitiv. Această decizie este finală.",
        },
        "tr": {
            "warning": f"“{title}” hakkındaki bir bildirimi inceledik ve sana bir uyarı verdik. Lütfen bundan sonraki içeriklerin kurallarımıza uymasına dikkat et.",
            "suspend": f"“{title}” hakkındaki bir bildirimi inceledikten sonra hesabın geçici olarak askıya alındı. Tekrar giriş yaparak yeniden etkinleştirebilirsin.",
            "ban": "Bir bildirimi inceledikten sonra hesabın kalıcı olarak yasaklandı. Bu karar kesindir.",
        },
        "zh": {
            "warning": f"我们审核了关于“{title}”的举报，并对你发出警告。请确保今后发布的内容遵守我们的规则。",
            "suspend": f"在审核关于“{title}”的举报后，你的账户已被暂时停用。重新登录即可恢复。",
            "ban": "在审核举报后，你的账户已被永久封禁。此决定为最终决定。",
        },
        "ko": {
            "warning": f"“{title}”에 대한 신고를 검토하고 경고를 드렸어요. 앞으로 올리는 내용이 규칙을 지키도록 해 주세요.",
            "suspend": f"“{title}”에 대한 신고를 검토한 결과, 계정이 일시 정지되었어요. 다시 로그인하면 재활성화할 수 있어요.",
            "ban": "신고를 검토한 결과, 계정이 영구 정지되었어요. 이 결정은 최종이에요.",
        },
    }
    subjects = {
        "de": {"warning": "Verwarnung erhalten", "suspend": "Konto vorübergehend deaktiviert", "ban": "Konto dauerhaft gesperrt"},
        "en": {"warning": "You've received a warning", "suspend": "Your account has been suspended", "ban": "Your account has been banned"},
        "fr": {"warning": "Vous avez reçu un avertissement", "suspend": "Votre compte a été suspendu", "ban": "Votre compte a été banni"},
        "it": {"warning": "Hai ricevuto un avvertimento", "suspend": "Il tuo account è stato sospeso", "ban": "Il tuo account è stato bannato"},
        "pt": {"warning": "Você recebeu um aviso", "suspend": "Sua conta foi suspensa", "ban": "Sua conta foi banida"},
        "es": {"warning": "Has recibido una advertencia", "suspend": "Tu cuenta ha sido suspendida", "ban": "Tu cuenta ha sido bloqueada"},
        "ro": {"warning": "Ai primit un avertisment", "suspend": "Contul tău a fost suspendat", "ban": "Contul tău a fost blocat"},
        "tr": {"warning": "Bir uyarı aldın", "suspend": "Hesabın askıya alındı", "ban": "Hesabın yasaklandı"},
        "zh": {"warning": "你收到了一次警告", "suspend": "你的账户已被停用", "ban": "你的账户已被封禁"},
        "ko": {"warning": "경고를 받았어요", "suspend": "계정이 정지되었어요", "ban": "계정이 영구 정지되었어요"},
    }
    greeting = _GREETING[lang]
    subject = subjects[lang][punishment]
    body = bodies[lang][punishment]
    return f"{subject} — VokalBoard", f"{_hello(lang, greeting, recipient)}<p>{body}</p>"


def ticket_response_email(language: str | None, recipient_name: str, admin_response: str, resolved: bool) -> tuple[str, str]:
    """P6 close-out (19/09/2026): notifies whoever opened a "Fale
    conosco"/"Reportar erro" ticket (see app/support_tickets.py) that
    an Admin replied. `resolved` only changes the closing line — the
    Admin's own response text is shown verbatim (escaped) either way."""
    lang = email_language(language)
    recipient = escape(recipient_name)
    response = escape(admin_response)
    closing = {
        "de": "Dieses Ticket ist jetzt als erledigt markiert." if resolved else "Wir bleiben dran, falls es noch etwas zu klären gibt.",
        "en": "This ticket is now marked as resolved." if resolved else "We'll keep it open in case there's anything left to clarify.",
        "fr": "Ce ticket est maintenant marqué comme résolu." if resolved else "Nous le laissons ouvert au cas où il resterait quelque chose à clarifier.",
        "it": "Questo ticket è ora contrassegnato come risolto." if resolved else "Lo lasciamo aperto nel caso ci sia ancora qualcosa da chiarire.",
        "pt": "Esse ticket agora está marcado como resolvido." if resolved else "Deixamos ele em aberto, caso ainda falte esclarecer algo.",
        "es": "Este ticket ya está marcado como resuelto." if resolved else "Lo dejamos abierto por si queda algo por aclarar.",
        "ro": "Acest tichet este acum marcat ca rezolvat." if resolved else "Îl lăsăm deschis în caz că mai este ceva de clarificat.",
        "tr": "Bu destek talebi artık çözüldü olarak işaretlendi." if resolved else "Netleştirilecek bir şey kalırsa diye açık tutuyoruz.",
        "zh": "此工单现已标记为已解决。" if resolved else "如还有需要澄清的地方，我们会保持工单开放。",
        "ko": "이 문의는 해결됨으로 표시되었어요." if resolved else "더 확인할 내용이 있을 수 있어 문의를 열어 둘게요.",
    }[lang]
    intro = {
        "de": "wir haben auf dein Ticket geantwortet:",
        "en": "we replied to your ticket:",
        "fr": "nous avons répondu à votre ticket :",
        "it": "abbiamo risposto al tuo ticket:",
        "pt": "respondemos seu ticket:",
        "es": "respondimos a tu ticket:",
        "ro": "am răspuns la tichetul tău:",
        "tr": "destek talebini yanıtladık:",
        "zh": "我们已回复你的工单：",
        "ko": "문의에 답변했어요:",
    }[lang]
    subject = {
        "de": "Antwort auf dein Ticket",
        "en": "Reply to your ticket",
        "fr": "Réponse à votre ticket",
        "it": "Risposta al tuo ticket",
        "pt": "Resposta ao seu ticket",
        "es": "Respuesta a tu ticket",
        "ro": "Răspuns la tichetul tău",
        "tr": "Destek talebine yanıt",
        "zh": "你的工单有新回复",
        "ko": "문의에 대한 답변",
    }[lang]
    greeting = _GREETING[lang]
    return (
        f"{subject} — VokalBoard",
        f"{_hello(lang, greeting, recipient)}<p>{intro}</p><p>{response}</p><p>{closing}</p>",
    )


def notas_expiring_email(language: str | None, recipient_name: str, amount: str, date: str, url: str) -> tuple[str, str]:
    """Notas v2 (N3): earned Notas expire 18 months after they were
    credited; this warns 30 days ahead. Purchased Notas never expire."""
    lang = email_language(language)
    recipient = escape(recipient_name)
    safe_url = escape(url, quote=True)
    amount, date = escape(amount), escape(date)
    copy = {
        "de": ("Deine Notas laufen bald ab", "Hallo", f"{amount} deiner verdienten Notas laufen am {date} ab. Nutze sie vorher — gekaufte Notas laufen nie ab.", "Zu meinen Notas"),
        "en": ("Your Notas expire soon", "Hello", f"{amount} of your earned Notas expire on {date}. Use them before then — purchased Notas never expire.", "Go to my Notas"),
        "fr": ("Vos Notas expirent bientôt", "Bonjour", f"{amount} de vos Notas gagnées expirent le {date}. Utilisez-les avant — les Notas achetées n'expirent jamais.", "Voir mes Notas"),
        "it": ("Le tue Notas scadono presto", "Ciao", f"{amount} delle tue Notas guadagnate scadono il {date}. Usale prima — le Notas acquistate non scadono mai.", "Vai alle mie Notas"),
        "pt": ("Suas Notas vão expirar em breve", "Olá", f"{amount} das suas Notas ganhas expiram em {date}. Use-as antes disso — Notas compradas nunca expiram.", "Ver minhas Notas"),
        "es": ("Tus Notas caducan pronto", "Hola", f"{amount} de tus Notas ganadas caducan el {date}. Úsalas antes: las Notas compradas nunca caducan.", "Ver mis Notas"),
        "ro": ("Notas tale expiră în curând", "Bună", f"{amount} dintre Notas câștigate expiră pe {date}. Folosește-le înainte — Notas cumpărate nu expiră niciodată.", "Vezi Notas mele"),
        "tr": ("Notas'ın yakında sona eriyor", "Merhaba", f"Kazandığın Notas'tan {amount} tanesi {date} tarihinde sona eriyor. Ondan önce kullan — satın alınan Notas'ın süresi hiç dolmaz.", "Notas'ıma git"),
        "zh": ("你的 Notas 即将过期", "你好", f"你获得的 Notas 中有 {amount} 个将于 {date} 过期。请在此之前使用——购买的 Notas 永不过期。", "查看我的 Notas"),
        "ko": ("Notas가 곧 만료돼요", "안녕하세요", f"적립된 Notas {amount}개가 {date}에 만료돼요. 그 전에 사용하세요 — 구매한 Notas는 만료되지 않아요.", "내 Notas 보기"),
    }[lang]
    return (
        f"{copy[0]} — VokalBoard",
        f"{_hello(lang, copy[1], recipient)}<p>{copy[2]}</p><p><a href=\"{safe_url}\">{copy[3]}</a></p>",
    )


def _listing_line(title: str, city: str | None) -> str:
    return f"<strong>{escape(title)}</strong>" + (f" — {escape(city)}" if city else "")


_ALERT_OPT_OUT = {
    "de": "Du erhältst diese Benachrichtigung, weil du passende Anzeigen abonniert hast. Das kannst du jederzeit in deinem Profil ausschalten.",
    "en": "You're getting this because match alerts are on for your account — you can turn them off anytime in your profile.",
    "fr": "Vous recevez ce message parce que les alertes d'annonces correspondantes sont activées — vous pouvez les désactiver à tout moment dans votre profil.",
    "it": "Ricevi questo messaggio perché hai attivato gli avvisi per gli annunci compatibili — puoi disattivarli in qualsiasi momento dal tuo profilo.",
    "pt": "Você recebe este aviso porque os alertas de anúncios compatíveis estão ativados — dá para desligá-los a qualquer momento no seu perfil.",
    "es": "Recibes este aviso porque tienes activadas las alertas de anuncios compatibles; puedes desactivarlas cuando quieras en tu perfil.",
    "ro": "Primești acest mesaj pentru că ai activate alertele pentru anunțuri potrivite — le poți dezactiva oricând din profil.",
    "tr": "Hesabında uygun ilan bildirimleri açık olduğu için bu e-postayı alıyorsun — istediğin zaman profilinden kapatabilirsin.",
    "zh": "你收到这封邮件，是因为你开启了匹配信息提醒——可以随时在个人资料中关闭。",
    "ko": "맞는 공고 알림을 켜 두셔서 이 메일을 받았어요 — 프로필에서 언제든 끌 수 있어요.",
}


def listing_match_alert_email(language: str | None, recipient_name: str, listing_title: str, city: str | None, url: str) -> tuple[str, str]:
    """A new listing matches this user's profile (app/notifications.py)."""
    lang = email_language(language)
    safe_url = escape(url, quote=True)
    copy = {
        "de": ("Neue passende Anzeige", "Es gibt eine neue Anzeige, die zu deinem Profil passen könnte:"),
        "en": ("New matching listing", "A new listing might match your profile:"),
        "fr": ("Nouvelle annonce pour vous", "Une nouvelle annonce pourrait correspondre à votre profil :"),
        "it": ("Nuovo annuncio per te", "C'è un nuovo annuncio che potrebbe fare al caso tuo:"),
        "pt": ("Novo anúncio compatível", "Há um novo anúncio que pode combinar com o seu perfil:"),
        "es": ("Nuevo anuncio compatible", "Hay un anuncio nuevo que podría encajar con tu perfil:"),
        "ro": ("Anunț nou potrivit", "Există un anunț nou care s-ar putea potrivi profilului tău:"),
        "tr": ("Sana uygun yeni ilan", "Profiline uyabilecek yeni bir ilan var:"),
        "zh": ("新的匹配信息", "有一条新信息可能适合你的个人资料："),
        "ko": ("맞는 새 공고", "내 프로필에 맞을 수 있는 새 공고가 올라왔어요:"),
    }[lang]
    return (
        f"{copy[0]}: {listing_title} — VokalBoard",
        f"{_hello(lang, _GREETING[lang], escape(recipient_name))}<p>{copy[1]}</p><p>{_listing_line(listing_title, city)}</p>"
        f"<p><a href=\"{safe_url}\">{safe_url}</a></p><p>{_ALERT_OPT_OUT[lang]}</p>",
    )


def urgent_listing_reminder_email(language: str | None, recipient_name: str, listing_title: str, city: str | None, url: str) -> tuple[str, str]:
    """Sent once, 6 h after a listing was marked urgent and still has no Match
    (app/urgent_listing_reminder_worker.py) — worded differently from the alert above."""
    lang = email_language(language)
    safe_url = escape(url, quote=True)
    copy = {
        "de": ("Immer noch dringend", "Diese dringende Anzeige ist seit 6 Stunden noch offen — falls du Interesse hast, jetzt ist ein guter Moment:"),
        "en": ("Still urgent", "This urgent listing has been open for 6 hours — if you're interested, now's a good moment:"),
        "fr": ("Toujours urgent", "Cette annonce urgente est ouverte depuis 6 heures — si elle vous intéresse, c'est le bon moment :"),
        "it": ("Ancora urgente", "Questo annuncio urgente è aperto da 6 ore — se ti interessa, è il momento giusto:"),
        "pt": ("Ainda urgente", "Este anúncio urgente está aberto há 6 horas — se tiver interesse, agora é um bom momento:"),
        "es": ("Sigue siendo urgente", "Este anuncio urgente lleva 6 horas abierto; si te interesa, ahora es un buen momento:"),
        "ro": ("Încă urgent", "Acest anunț urgent este deschis de 6 ore — dacă te interesează, acum e momentul potrivit:"),
        "tr": ("Hâlâ acil", "Bu acil ilan 6 saattir açık — ilgileniyorsan şimdi tam zamanı:"),
        "zh": ("仍然紧急", "这条紧急信息已开放 6 小时——如果你感兴趣，现在正是好时机："),
        "ko": ("아직 긴급해요", "이 긴급 공고가 6시간째 열려 있어요 — 관심 있다면 지금이 좋은 때예요:"),
    }[lang]
    return (
        f"{copy[0]}: {listing_title} — VokalBoard",
        f"{_hello(lang, _GREETING[lang], escape(recipient_name))}<p>{copy[1]}</p><p>⚡ {_listing_line(listing_title, city)}</p>"
        f"<p><a href=\"{safe_url}\">{safe_url}</a></p><p>{_ALERT_OPT_OUT[lang]}</p>",
    )


def badge_unlocked_email(language: str | None, recipient_name: str, badge_name: str, url: str) -> tuple[str, str]:
    """A new badge/tier was unlocked (app/badges.py); `badge_name` is already localized."""
    lang = email_language(language)
    safe_url = escape(url, quote=True)
    copy = {
        "de": ("Neue Auszeichnung freigeschaltet", "Du hast eine neue Auszeichnung freigeschaltet:"),
        "en": ("New badge unlocked", "You've unlocked a new badge:"),
        "fr": ("Nouvelle distinction débloquée", "Vous avez débloqué une nouvelle distinction :"),
        "it": ("Nuovo distintivo sbloccato", "Hai sbloccato un nuovo distintivo:"),
        "pt": ("Nova conquista desbloqueada", "Você desbloqueou uma nova conquista:"),
        "es": ("Nueva insignia desbloqueada", "Has desbloqueado una insignia nueva:"),
        "ro": ("Insignă nouă deblocată", "Ai deblocat o insignă nouă:"),
        "tr": ("Yeni rozet açıldı", "Yeni bir rozet açtın:"),
        "zh": ("解锁了新徽章", "你解锁了一枚新徽章："),
        "ko": ("새 배지를 획득했어요", "새 배지를 획득했어요:"),
    }[lang]
    return (
        f"{copy[0]} — VokalBoard",
        f"{_hello(lang, _GREETING[lang], escape(recipient_name))}<p>{copy[1]} <strong>{escape(badge_name)}</strong></p>"
        f"<p><a href=\"{safe_url}\">{safe_url}</a></p>",
    )


def match_cancelled_email(language: str | None, recipient_name: str, canceller_name: str, title: str,
                          reason: str, url: str) -> tuple[str, str]:
    """5b (2026-09-28): the other side of a cancelled Match — who, which job, and the reason given."""
    lang = email_language(language)
    copy = {
        "de": ("Match abgesagt", "hat den Match abgesagt für", "Begründung:", "Die Stelle ist wieder offen. Details:"),
        "en": ("Match cancelled", "cancelled the Match for", "Reason given:", "The vacancy is open again. Details:"),
        "fr": ("Match annulé", "a annulé le Match pour", "Motif :", "Le poste est de nouveau ouvert. Détails :"),
        "it": ("Match annullato", "ha annullato il Match per", "Motivo:", "Il posto è di nuovo disponibile. Dettagli:"),
        "pt": ("Match cancelado", "cancelou o Match de", "Motivo informado:", "A vaga está aberta de novo. Detalhes:"),
        "es": ("Match cancelado", "canceló el Match de", "Motivo:", "La vacante vuelve a estar abierta. Detalles:"),
        "ro": ("Match anulat", "a anulat Match-ul pentru", "Motivul:", "Postul este din nou disponibil. Detalii:"),
        "tr": ("Match iptal edildi", "şu ilanın Match'ini iptal etti:", "Belirtilen gerekçe:", "Pozisyon yeniden açık. Ayrıntılar:"),
        "zh": ("匹配已取消", "取消了以下职位的匹配：", "给出的理由：", "该职位已重新开放。详情："),
        "ko": ("매치 취소", "님이 다음 공고의 매치를 취소했습니다:", "사유:", "포지션이 다시 열렸습니다. 자세히 보기:"),
    }[lang]
    safe_url = escape(url, quote=True)
    who, job = escape(canceller_name), escape(title or "")
    return (
        f"{copy[0]} — VokalBoard",
        f"{_hello(lang, _GREETING[lang], escape(recipient_name))}<p><strong>{who}</strong> {copy[1]} <strong>{job}</strong>{_STOP.get(lang, '.')}</p>"
        f"<p>{copy[2]}<br><em>{escape(reason)}</em></p><p>{copy[3]} <a href=\"{safe_url}\">{safe_url}</a></p>",
    )


def match_warning_email(language: str | None, recipient_name: str, warnings_towards_block: int,
                        blocked_until: str | None, url: str) -> tuple[str, str]:
    """5b: a warning after a Match cancellation; the 3rd one blocks new Matches for 30 days."""
    lang = email_language(language)
    copy = {
        "de": ("Verwarnung wegen einer Match-Absage", "Nach Prüfung deiner Match-Absage hast du eine Verwarnung erhalten.",
               "Verwarnungen: {n} von 3. Bei 3 Verwarnungen kannst du 30 Tage lang keine neuen Matches eingehen.",
               "Du hast 3 Verwarnungen erreicht: Bis {date} kannst du keine neuen Matches eingehen (bewerben, einladen, annehmen)."),
        "en": ("Warning for a Match cancellation", "After reviewing your Match cancellation, we have issued a warning.",
               "Warnings: {n} of 3. At 3 warnings you can't start new Matches for 30 days.",
               "You have reached 3 warnings: until {date} you can't start new Matches (apply, invite or accept)."),
        "fr": ("Avertissement pour l'annulation d'un Match", "Après examen de votre annulation, vous avez reçu un avertissement.",
               "Avertissements : {n} sur 3. À 3 avertissements, vous ne pourrez plus conclure de Match pendant 30 jours.",
               "Vous avez atteint 3 avertissements : jusqu'au {date}, vous ne pouvez plus conclure de nouveau Match (postuler, inviter, accepter)."),
        "it": ("Avviso per l'annullamento di un Match", "Dopo aver esaminato il tuo annullamento, hai ricevuto un avviso.",
               "Avvisi: {n} su 3. Con 3 avvisi non potrai avviare nuovi Match per 30 giorni.",
               "Hai raggiunto 3 avvisi: fino al {date} non puoi avviare nuovi Match (candidarti, invitare, accettare)."),
        "pt": ("Advertência por cancelar um Match", "Depois de analisarmos o seu cancelamento, você recebeu uma advertência.",
               "Advertências: {n} de 3. Com 3 advertências você fica 30 dias sem poder fazer novos Matches.",
               "Você chegou a 3 advertências: até {date} não pode fazer novos Matches (se candidatar, convidar ou aceitar)."),
        "es": ("Aviso por cancelar un Match", "Tras revisar tu cancelación, has recibido un aviso.",
               "Avisos: {n} de 3. Con 3 avisos no podrás hacer nuevos Matches durante 30 días.",
               "Has llegado a 3 avisos: hasta el {date} no puedes hacer nuevos Matches (postularte, invitar ni aceptar)."),
        "ro": ("Avertisment pentru anularea unui Match", "După analizarea anulării tale, ai primit un avertisment.",
               "Avertismente: {n} din 3. La 3 avertismente nu poți face Match-uri noi timp de 30 de zile.",
               "Ai ajuns la 3 avertismente: până la {date} nu poți face Match-uri noi (să aplici, să inviți sau să accepți)."),
        "tr": ("Match iptali için uyarı", "Match iptalini inceledikten sonra sana bir uyarı verdik.",
               "Uyarılar: 3'te {n}. 3 uyarıda 30 gün boyunca yeni Match yapamazsın.",
               "3 uyarıya ulaştın: {date} tarihine kadar yeni Match yapamazsın (başvuru, davet ya da kabul)."),
        "zh": ("取消匹配的警告", "经审核你的取消记录后，你收到了一次警告。",
               "警告次数：{n}/3。累计 3 次警告将在 30 天内无法建立新的匹配。",
               "你已累计 3 次警告：在 {date} 之前无法建立新的匹配（申请、邀请或接受）。"),
        "ko": ("매치 취소 경고", "매치 취소 건을 검토한 결과 경고가 부여되었습니다.",
               "경고: 3회 중 {n}회. 경고 3회가 되면 30일 동안 새 매치를 할 수 없습니다.",
               "경고 3회에 도달했습니다. {date}까지 새 매치(지원, 초대, 수락)를 할 수 없습니다."),
    }[lang]
    status = copy[3].replace("{date}", escape(blocked_until)) if blocked_until else copy[2].replace("{n}", str(warnings_towards_block))
    safe_url = escape(url, quote=True)
    return (
        f"{copy[0]} — VokalBoard",
        f"{_hello(lang, _GREETING[lang], escape(recipient_name))}<p>{copy[1]}</p><p>{status}</p>"
        f"<p><a href=\"{safe_url}\">{safe_url}</a></p>",
    )

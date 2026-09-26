"""Small, explicit copy library for transactional e-mails.

E-mail language is an account preference, not a browser cookie: a message can
be read days later on a different device.  Unsupported or missing preferences
fall back to English deliberately.
"""
from html import escape

# es (2026-09-26): added language — e-mails too (docs/I18N.md phase 3).
EMAIL_LANGUAGES = {"de", "en", "fr", "it", "pt", "es"}

# "This link is valid for N hours." as one sentence per language (it used to
# end in English "hours" for everyone — "Dieser Link ist 24 hours.").
_VALID_FOR = {
    "de": "Dieser Link ist {hours} Stunden gültig.",
    "en": "This link is valid for {hours} hours.",
    "fr": "Ce lien est valable {hours} heures.",
    "it": "Questo link è valido per {hours} ore.",
    "pt": "Este link é válido por {hours} horas.",
    "es": "Este enlace es válido durante {hours} horas.",
}


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
        "es": ("Confirma tu dirección de correo", "Hola", "Confirma tu dirección de correo de VokalBoard.", ""),
    }[lang]
    return f"{copy[0]} — VokalBoard", f"<p>{copy[1]} {safe_name},</p><p>{copy[2]}</p><p><a href=\"{safe_url}\">{safe_url}</a></p><p>{_VALID_FOR[lang].format(hours=hours)}</p>"


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
    }[lang]
    return f"{copy[0]} — VokalBoard", f"<p>{copy[1]} {safe_name},</p><p>{copy[2]}</p><p><a href=\"{safe_url}\">{safe_url}</a></p><p>{_VALID_FOR[lang].format(hours=hours)}</p>"


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
    }[lang]
    return f"{copy[0]} {sender_name} — VokalBoard", f"<p>{copy[1]} {recipient},</p><p><strong>{sender}</strong> {copy[2]}</p><p><a href=\"{url}\">{url}</a></p>"


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
    }[lang]
    return f"{copy[0]} — VokalBoard", f"<p>{copy[1]} {recipient},</p><p>{copy[2]} <strong>{title}</strong></p><p><a href=\"{safe_url}\">{safe_url}</a></p><p>{copy[3]}</p>"


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
    }[lang]
    return f"{copy[0]} — VokalBoard", f"<p>{copy[1]} {recipient},</p><p><strong>{artist}</strong> {copy[2]} <strong>{title}</strong>{copy[3]}</p><p><a href=\"{safe_url}\">{safe_url}</a></p>"


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
    }[lang]
    copy = {
        "de": ("Antwort erhalten", "Hallo", "Deine Anfrage für", "wurde"),
        "en": ("Response received", "Hello", "Your request for", "was"),
        "fr": ("Réponse reçue", "Bonjour", "Votre demande pour", "a été"),
        "it": ("Risposta ricevuta", "Ciao", "La tua richiesta per", "è stata"),
        "pt": ("Resposta recebida", "Olá", "Sua solicitação para", "foi"),
        "es": ("Respuesta recibida", "Hola", "Tu solicitud para", "fue"),
    }[lang]
    return f"{copy[0]} — VokalBoard", f"<p>{copy[1]} {recipient},</p><p>{copy[2]} <strong>{title}</strong> {copy[3]} <strong>{status_word}</strong>.</p><p><a href=\"{safe_url}\">{safe_url}</a></p>"


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
    }[lang]
    prefix = {"de": "Die Vakanz in", "en": "The vacancy in", "fr": "Le poste dans", "it": "Il posto in",
              "pt": "A vaga em", "es": "La vacante en"}[lang]
    return f"{copy[0]} — VokalBoard", f"<p>{copy[1]} {recipient},</p><p>{prefix} <strong>{title}</strong> {copy[2]}</p>"


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
    }[lang]
    return (
        f"{copy[0]} — VokalBoard",
        f"<p>{copy[1]} {recipient},</p><p>{copy[2]}</p><p><a href=\"{safe_url}\">{copy[3]}</a></p>",
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
        "pt": ("Rechnung solicitada", "Olá", f"{counterpart} pediu uma Rechnung para “{title}”.", "Abrir"),
        "es": ("Factura solicitada", "Hola", f"{counterpart} solicitó una factura para “{title}”.", "Abrir"),
    }[lang]
    return (
        f"{copy[0]} — VokalBoard",
        f"<p>{copy[1]} {recipient},</p><p>{copy[2]}</p><p><a href=\"{safe_url}\">{copy[3]}</a></p>",
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
        "pt": ("Rechnung pronta para revisão", "Olá", f"{counterpart} preparou uma Rechnung para “{title}” — revise e confirme.", "Revisar"),
        "es": ("Factura lista para revisar", "Hola", f"{counterpart} preparó una factura para “{title}”: revísala y confírmala.", "Revisar"),
    }[lang]
    return (
        f"{copy[0]} — VokalBoard",
        f"<p>{copy[1]} {recipient},</p><p>{copy[2]}</p><p><a href=\"{safe_url}\">{copy[3]}</a></p>",
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
        "pt": ("Sua Rechnung está pronta", "Olá", f"Em anexo está a Rechnung de “{title}”. O VokalBoard não guarda nenhuma cópia."),
        "es": ("Tu factura está lista", "Hola", f"Adjunta encontrarás la factura de “{title}”. VokalBoard no guarda ninguna copia."),
    }[lang]
    return (
        f"{copy[0]} — VokalBoard",
        f"<p>{copy[1]} {recipient},</p><p>{copy[2]}</p>",
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
        "pt": ("Rascunho de Rechnung expirado", "Olá", f"O rascunho de Rechnung de “{title}” não foi confirmado em 7 dias e foi apagado automaticamente. Você pode pedir uma nova, se ainda for necessário.", "Pedir de novo"),
        "es": ("Borrador de factura caducado", "Hola", f"El borrador de factura de “{title}” no se confirmó en 7 días y se eliminó automáticamente. Puedes solicitar una nueva si todavía la necesitas.", "Solicitar de nuevo"),
    }[lang]
    return (
        f"{copy[0]} — VokalBoard",
        f"<p>{copy[1]} {recipient},</p><p>{copy[2]}</p><p><a href=\"{safe_url}\">{copy[3]}</a></p>",
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
        }[lang]
    else:
        body = {
            "de": f"deine Meldung zu „{title}" + "“ wurde geprüft. Wir haben keinen Verstoß gegen unsere Richtlinien festgestellt.",
            "en": f"your report about “{title}” has been reviewed. We didn't find a violation of our guidelines.",
            "fr": f"votre signalement concernant « {title} » a été examiné. Nous n'avons constaté aucune infraction à nos règles.",
            "it": f"la tua segnalazione su “{title}” è stata esaminata. Non abbiamo riscontrato una violazione delle nostre regole.",
            "pt": f"sua denúncia sobre “{title}” foi analisada. Não encontramos uma violação das nossas regras nesse caso.",
            "es": f"tu denuncia sobre “{title}” ha sido revisada. No encontramos ninguna infracción de nuestras normas.",
        }[lang]
    subject = {
        "de": "Deine Meldung wurde geprüft",
        "en": "Your report has been reviewed",
        "fr": "Votre signalement a été examiné",
        "it": "La tua segnalazione è stata esaminata",
        "pt": "Sua denúncia foi analisada",
        "es": "Tu denuncia ha sido revisada",
    }[lang]
    greeting = {"de": "Hallo", "en": "Hello", "fr": "Bonjour", "it": "Ciao", "pt": "Olá", "es": "Hola"}[lang]
    return f"{subject} — VokalBoard", f"<p>{greeting} {recipient},</p><p>{body}</p>"


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
    }
    subjects = {
        "de": {"warning": "Verwarnung erhalten", "suspend": "Konto vorübergehend deaktiviert", "ban": "Konto dauerhaft gesperrt"},
        "en": {"warning": "You've received a warning", "suspend": "Your account has been suspended", "ban": "Your account has been banned"},
        "fr": {"warning": "Vous avez reçu un avertissement", "suspend": "Votre compte a été suspendu", "ban": "Votre compte a été banni"},
        "it": {"warning": "Hai ricevuto un avvertimento", "suspend": "Il tuo account è stato sospeso", "ban": "Il tuo account è stato bannato"},
        "pt": {"warning": "Você recebeu um aviso", "suspend": "Sua conta foi suspensa", "ban": "Sua conta foi banida"},
        "es": {"warning": "Has recibido una advertencia", "suspend": "Tu cuenta ha sido suspendida", "ban": "Tu cuenta ha sido bloqueada"},
    }
    greeting = {"de": "Hallo", "en": "Hello", "fr": "Bonjour", "it": "Ciao", "pt": "Olá", "es": "Hola"}[lang]
    subject = subjects[lang][punishment]
    body = bodies[lang][punishment]
    return f"{subject} — VokalBoard", f"<p>{greeting} {recipient},</p><p>{body}</p>"


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
    }[lang]
    intro = {
        "de": "wir haben auf dein Ticket geantwortet:",
        "en": "we replied to your ticket:",
        "fr": "nous avons répondu à votre ticket :",
        "it": "abbiamo risposto al tuo ticket:",
        "pt": "respondemos seu ticket:",
        "es": "respondimos a tu ticket:",
    }[lang]
    subject = {
        "de": "Antwort auf dein Ticket",
        "en": "Reply to your ticket",
        "fr": "Réponse à votre ticket",
        "it": "Risposta al tuo ticket",
        "pt": "Resposta ao seu ticket",
        "es": "Respuesta a tu ticket",
    }[lang]
    greeting = {"de": "Hallo", "en": "Hello", "fr": "Bonjour", "it": "Ciao", "pt": "Olá", "es": "Hola"}[lang]
    return (
        f"{subject} — VokalBoard",
        f"<p>{greeting} {recipient},</p><p>{intro}</p><p>{response}</p><p>{closing}</p>",
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
    }[lang]
    return (
        f"{copy[0]} — VokalBoard",
        f"<p>{copy[1]} {recipient},</p><p>{copy[2]}</p><p><a href=\"{safe_url}\">{copy[3]}</a></p>",
    )

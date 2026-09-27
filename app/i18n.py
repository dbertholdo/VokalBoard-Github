"""
Simple internationalization (i18n), with no external dependencies.

Each UI string has a key (e.g. "nav_login"), and each key has a
translation in German ("de"), English ("en"), French ("fr"), Italian
("it") and Brazilian Portuguese ("pt"). The default language is
German, since the site's main audience is in Germany.

How it works in practice:
- `LanguageMiddleware` (in app/main.py) decides the request's language
  (querystring ?lang=.. > cookie > default "de") and stores it in
  `request.state.lang`.
- `app/render.py` injects a `t(key)` function into every template's
  context, which simply looks up this dictionary.

Languages added after the core five (zh, ko, ro, ...) are NOT edited
here: they live in app/locales/<lang>.json (see docs/I18N.md).

Language is a UI-only choice, independent from currency (EUR/CHF are
picked by country, not by language) — see app/financial_settings.py.
"""

# Core five (complete, inline below) + languages added later, which live in
# app/locales/<lang>.json and cover the PUBLIC site only (admin stays English).
# Roadmap for the added ones: docs/I18N.md.
SUPPORTED_LANGUAGES = ["de", "en", "fr", "it", "pt", "es", "zh", "ko", "ro"]
DEFAULT_LANGUAGE = "de"

# Flag + native label for each supported language, used by the
# dropdown switcher in base.html (kept here so there's one place to
# add a language, instead of duplicating this list in the template).
LANGUAGE_META = {
    "de": {"flag": "🇩🇪", "label": "DE"},
    "en": {"flag": "🇬🇧", "label": "EN"},
    "fr": {"flag": "🇫🇷", "label": "FR"},
    "it": {"flag": "🇮🇹", "label": "IT"},
    "pt": {"flag": "🇧🇷", "label": "PT"},
    "es": {"flag": "🇪🇸", "label": "ES"},
    "zh": {"flag": "🇨🇳", "label": "中文"},
    "ko": {"flag": "🇰🇷", "label": "한국어"},
    "ro": {"flag": "🇷🇴", "label": "RO"},
}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "availability_period": {"en": "Availability period", "pt": "Período de disponibilidade", "de": "Verfügbarkeitszeitraum", "fr": "Période de disponibilité", "it": "Periodo di disponibilità"},
    "availability_from": {"en": "From", "pt": "De", "de": "Von", "fr": "Du", "it": "Dal"},
    "availability_until": {"en": "Until", "pt": "Até", "de": "Bis", "fr": "Au", "it": "Al"},
    "availability_help": {"en": "Up to 30 days including both dates. Maximum two active periods.", "pt": "Até 30 dias contando as duas datas. Máximo de dois períodos ativos.", "de": "Bis zu 30 Tage einschließlich beider Daten. Höchstens zwei aktive Zeiträume.", "fr": "Jusqu’à 30 jours, dates incluses. Deux périodes actives au maximum.", "it": "Fino a 30 giorni, date incluse. Massimo due periodi attivi."},
    "listing_location_scope": {"en": "Location", "pt": "Localidade", "de": "Ort", "fr": "Localité", "it": "Località"},
    "availability_location_help": {"en": "For singer availability, leave state and city empty if you have no location restriction.", "pt": "Na disponibilidade de cantor, deixe estado e cidade em branco se não houver restrição de localidade.", "de": "Bei Verfügbarkeit Bundesland und Stadt leer lassen, wenn es keine örtliche Einschränkung gibt.", "fr": "Pour une disponibilité, laissez région et ville vides sans restriction de lieu.", "it": "Per la disponibilità, lascia regione e città vuote se non ci sono restrizioni di luogo."},
    # FIX (19/09/2026, translation audit for task #49): these two keys
    # had only en/pt — de/fr/it were silently falling back to English
    # via translate()'s fallback chain (see app/i18n.py's translate()),
    # which matters more than most since German is DEFAULT_LANGUAGE.
    "availability_limit": {
        "en": "You already have two active availability periods.",
        "pt": "Você já tem dois períodos de disponibilidade ativos.",
        "de": "Sie haben bereits zwei aktive Verfügbarkeitszeiträume.",
        "fr": "Vous avez déjà deux périodes de disponibilité actives.",
        "it": "Hai già due periodi di disponibilità attivi.",
    },
    "availability_invalid": {
        "en": "Choose a valid period of at most 30 days, including both dates.",
        "pt": "Escolha um período válido de até 30 dias, contando as duas datas.",
        "de": "Wählen Sie einen gültigen Zeitraum von höchstens 30 Tagen, beide Daten eingeschlossen.",
        "fr": "Choisissez une période valide d'au plus 30 jours, dates incluses.",
        "it": "Scegli un periodo valido di massimo 30 giorni, date incluse.",
    },
    "message_retention_warning": {"de": "In {days} Tagen wird dieser Chat wegen Inaktivität gelöscht.", "en": "In {days} days this chat will be deleted for inactivity.", "fr": "Dans {days} jours, ce chat sera supprimé pour inactivité.", "it": "Tra {days} giorni questa chat verrà eliminata per inattività.", "pt": "Em {days} dias este chat será apagado por inatividade."},
    "nav_view_my_profile": {"de": "Mein Profil ansehen", "en": "View My Profile", "fr": "Voir mon profil", "it": "Visualizza il mio profilo", "pt": "Ver meu perfil"},
    "nav_edit_profile": {"de": "Profil bearbeiten", "en": "Edit Profile", "fr": "Modifier le profil", "it": "Modifica profilo", "pt": "Editar perfil"},
    "nav_match_history": {"de": "Match-Verlauf", "en": "Match History", "fr": "Historique des Matches", "it": "Cronologia dei Match", "pt": "Histórico de Matches"},
    "nav_profile_download": {"de": "Lebenslauf/Digital Pass herunterladen", "en": "Download CV/Digital Pass", "fr": "Télécharger CV/Digital Pass", "it": "Scarica CV/Digital Pass", "pt": "Baixar CV/Digital Pass"},
    # Digital Pass (19/09/2026, task #51): its own menu entry + stub
    # page now (see app/templates/digital_pass_stub.html), replacing
    # the disabled placeholder line above used to be the only mention
    # of it — kept "Digital Pass" untranslated, same term Daniel used
    # himself and the one already embedded in nav_profile_download above.
    "nav_digital_pass": {"de": "Digital Pass", "en": "Digital Pass", "fr": "Digital Pass", "it": "Digital Pass", "pt": "Digital Pass"},
    "digital_pass_intro": {
        "de": "Dein Lebenslauf und deine Visitenkarte, in einem Ort.",
        "en": "Your CV and your business card, in one place.",
        "fr": "Votre CV et votre carte de visite, au même endroit.",
        "it": "Il tuo CV e il tuo biglietto da visita, in un unico posto.",
        "pt": "Seu currículo e seu cartão de visita, em um só lugar.",
    },
    "digital_pass_cv_tab": {"de": "Lebenslauf", "en": "CV", "fr": "CV", "it": "CV", "pt": "Currículo"},
    "digital_pass_cv_body": {
        "de": "Dein Lebenslauf als PDF, mit Foto und QR-Code zu deinem Profil.",
        "en": "Your CV as a PDF, with your photo and a QR code to your profile.",
        "fr": "Votre CV en PDF, avec votre photo et un QR code vers votre profil.",
        "it": "Il tuo CV in PDF, con la tua foto e un QR code al tuo profilo.",
        "pt": "Seu currículo em PDF, com sua foto e um QR Code pro seu perfil.",
    },
    "digital_pass_cv_download_button": {"de": "Lebenslauf als PDF herunterladen", "en": "Download CV as PDF", "fr": "Télécharger le CV en PDF", "it": "Scarica il CV in PDF", "pt": "Baixar currículo em PDF"},
    "digital_pass_card_tab": {"de": "Visitenkarte", "en": "Business card", "fr": "Carte de visite", "it": "Biglietto da visita", "pt": "Cartão de visita"},
    "digital_pass_card_body": {
        "de": "Erstelle eine digitale Visitenkarte auf Basis deines Lebenslaufs — zum Teilen bei Vorsingen und Konzerten.",
        "en": "Generate a digital business card based on your CV — handy to share at auditions and concerts.",
        "fr": "Générez une carte de visite numérique basée sur votre CV — pratique à partager lors d'auditions et de concerts.",
        "it": "Genera un biglietto da visita digitale basato sul tuo CV — comodo da condividere ad audizioni e concerti.",
        "pt": "Gere um cartão de visita digital baseado no seu currículo — prático pra compartilhar em audições e concertos.",
    },
    "feature_coming_soon": {"de": "Demnächst", "en": "Coming soon", "fr": "Bientôt", "it": "Prossimamente", "pt": "Em breve"},
    "match_history_privacy": {"de": "Nur für die beteiligten Personen und Administratoren sichtbar.", "en": "Visible only to the participants and administrators.", "fr": "Visible uniquement par les participants et les administrateurs.", "it": "Visibile solo ai partecipanti e agli amministratori.", "pt": "Visível somente aos participantes e administradores."},
    "match_history_empty": {"de": "Noch keine Matches.", "en": "No Matches yet.", "fr": "Aucun Match pour le moment.", "it": "Nessun Match ancora.", "pt": "Nenhum Match ainda."},
    "match_status_confirmed": {"de": "Bestätigt", "en": "Confirmed", "fr": "Confirmé", "it": "Confermato", "pt": "Confirmado"},
    "match_status_completed": {"de": "Abgeschlossen", "en": "Completed", "fr": "Terminé", "it": "Completato", "pt": "Concluído"},
    "match_status_cancelled": {"de": "Abgesagt", "en": "Cancelled", "fr": "Annulé", "it": "Annullato", "pt": "Cancelado"},
    "match_event_date": {"de": "Veranstaltungsdatum", "en": "Event date", "fr": "Date de l’événement", "it": "Data dell’evento", "pt": "Data do evento"},
    "match_fee": {"de": "Honorar", "en": "Fee", "fr": "Cachet", "it": "Compenso", "pt": "Cachê"},
    # FIX (19/09/2026, translation audit for task #49): referenced by
    # listing_form.html's currency <select> (a screen-reader-only
    # label) but never actually defined — translate()'s fallback for a
    # missing key returns the raw key string itself, so this was
    # rendering the literal text "listing_form_fee_currency_label" to
    # screen readers in every language.
    "listing_form_fee_currency_label": {
        "de": "Währung", "en": "Currency", "fr": "Devise",
        "it": "Valuta", "pt": "Moeda",
    },
    "match_contact_revealed_help": {"de": "Kontaktdaten wurden freigegeben, weil dieses Match bestätigt ist.", "en": "Contact details were revealed because this Match is confirmed.", "fr": "Les coordonnées ont été révélées car ce Match est confirmé.", "it": "I contatti sono stati rivelati perché questo Match è confermato.", "pt": "O contato foi liberado porque este Match está confirmado."},
    "eval_section_title": {"de": "Bewertung (privat)", "en": "Evaluation (private)", "fr": "Évaluation (privée)", "it": "Valutazione (privata)", "pt": "Avaliação (privada)"},
    "eval_privacy_help": {"de": "Deine Bewertung ist geheim — niemand sieht, wer wie bewertet hat, auch nicht die bewertete Person.", "en": "Your evaluation is secret — nobody sees who rated what, not even the person being rated.", "fr": "Votre évaluation est secrète — personne ne voit qui a évalué quoi, pas même la personne évaluée.", "it": "La tua valutazione è segreta — nessuno vede chi ha valutato cosa, nemmeno la persona valutata.", "pt": "Sua avaliação é secreta — ninguém vê quem avaliou o quê, nem a pessoa avaliada."},
    "eval_window_help": {"de": "Verfügbar für 14 Tage nach der Veranstaltung.", "en": "Available for 14 days after the event.", "fr": "Disponible pendant 14 jours après l’événement.", "it": "Disponibile per 14 giorni dopo l’evento.", "pt": "Disponível por 14 dias após o evento."},
    "eval_already_submitted": {"de": "Du hast diese Bewertung bereits abgegeben. Du kannst sie aktualisieren.", "en": "You already submitted this evaluation. You can update it.", "fr": "Vous avez déjà soumis cette évaluation. Vous pouvez la mettre à jour.", "it": "Hai già inviato questa valutazione. Puoi aggiornarla.", "pt": "Você já enviou essa avaliação. Pode atualizá-la."},
    "eval_submit": {"de": "Bewertung speichern", "en": "Save evaluation", "fr": "Enregistrer l’évaluation", "it": "Salva valutazione", "pt": "Salvar avaliação"},
    "eval_success": {"de": "Bewertung gespeichert. Danke!", "en": "Evaluation saved. Thank you!", "fr": "Évaluation enregistrée. Merci !", "it": "Valutazione salvata. Grazie!", "pt": "Avaliação salva. Obrigado!"},
    "eval_error": {"de": "Diese Bewertung kann gerade nicht abgegeben werden (Zeitfenster abgelaufen oder Match storniert).", "en": "This evaluation can't be submitted right now (window expired or Match cancelled).", "fr": "Cette évaluation ne peut pas être soumise maintenant (délai expiré ou Match annulé).", "it": "Questa valutazione non può essere inviata ora (finestra scaduta o Match annullato).", "pt": "Essa avaliação não pode ser enviada agora (janela expirada ou Match cancelado)."},
    "eval_category_punctuality": {"de": "Pünktlichkeit", "en": "Punctuality", "fr": "Ponctualité", "it": "Puntualità", "pt": "Pontualidade"},
    "eval_category_preparation": {"de": "Vorbereitung", "en": "Preparation", "fr": "Préparation", "it": "Preparazione", "pt": "Preparação"},
    "eval_category_musicality": {"de": "Musikalität", "en": "Musicality", "fr": "Musicalité", "it": "Musicalità", "pt": "Musicalidade"},
    "eval_category_communication": {"de": "Professionelle Kommunikation", "en": "Professional communication", "fr": "Communication professionnelle", "it": "Comunicazione professionale", "pt": "Comunicação profissional"},
    "eval_category_collaboration": {"de": "Angenehme Zusammenarbeit", "en": "Pleasant collaboration", "fr": "Collaboration agréable", "it": "Collaborazione piacevole", "pt": "Colaboração agradável"},
    "eval_quality_section_title": {"de": "Qualitätsabzeichen (privat)", "en": "Quality badges (private)", "fr": "Badges de qualité (privés)", "it": "Badge di qualità (privati)", "pt": "Selos de qualidade (privados)"},
    "eval_quality_section_help": {"de": "Nur für dich (und Admins) sichtbar — basiert auf Bewertungen, die du von anderen erhalten hast. Kann mit der Zeit steigen oder sinken.", "en": "Visible only to you (and Admins) — based on evaluations you've received from others. Can go up or down over time.", "fr": "Visible uniquement par vous (et les administrateurs) — basé sur les évaluations reçues des autres. Peut monter ou descendre au fil du temps.", "it": "Visibile solo a te (e agli Admin) — basato sulle valutazioni ricevute dagli altri. Può salire o scendere nel tempo.", "pt": "Visível só pra você (e Admins) — baseado nas avaliações que você recebeu de outras pessoas. Pode subir ou descer com o tempo."},
    "eval_quality_not_enough": {"de": "Noch nicht genug Bewertungen", "en": "Not enough evaluations yet", "fr": "Pas encore assez d’évaluations", "it": "Non ci sono ancora abbastanza valutazioni", "pt": "Ainda não há avaliações suficientes"},
    "eval_tier_bronze": {"de": "Bronze", "en": "Bronze", "fr": "Bronze", "it": "Bronzo", "pt": "Bronze"},
    "eval_tier_silver": {"de": "Silber", "en": "Silver", "fr": "Argent", "it": "Argento", "pt": "Prata"},
    "eval_tier_gold": {"de": "Gold", "en": "Gold", "fr": "Or", "it": "Oro", "pt": "Ouro"},
    "eval_tier_platinum": {"de": "Platin", "en": "Platinum", "fr": "Platine", "it": "Platino", "pt": "Platina"},
    "invoice_requested_ok": {"de": "Anfrage gesendet.", "en": "Request sent.", "fr": "Demande envoyée.", "it": "Richiesta inviata.", "pt": "Pedido enviado."},
    "invoice_sent_ok": {"de": "Rechnung per E-Mail gesendet.", "en": "Invoice sent by e-mail.", "fr": "Facture envoyée par e-mail.", "it": "Fattura inviata via e-mail.", "pt": "Rechnung enviada por e-mail."},
    "invoice_cancelled_ok": {"de": "Rechnungsanfrage storniert.", "en": "Invoice request cancelled.", "fr": "Demande de facture annulée.", "it": "Richiesta di fattura annullata.", "pt": "Pedido de Rechnung cancelado."},
    "invoice_error": {"de": "Diese Aktion ist gerade nicht möglich (Zeitfenster abgelaufen oder Match storniert).", "en": "This action isn't available right now (window expired or Match cancelled).", "fr": "Cette action n'est pas disponible actuellement (délai expiré ou Match annulé).", "it": "Questa azione non è disponibile ora (finestra scaduta o Match annullato).", "pt": "Essa ação não está disponível agora (janela expirada ou Match cancelado)."},
    # Rechnungmaker form UI (2026-09-27; the invoice document itself stays German).
    "inv_number": {"de": "Rechnungsnummer", "en": "Invoice number", "fr": "Numéro de facture", "it": "Numero fattura", "pt": "Número da fatura"},
    "inv_issue_date": {"de": "Rechnungsdatum", "en": "Invoice date", "fr": "Date de facture", "it": "Data fattura", "pt": "Data da fatura"},
    "inv_service_date": {"de": "Leistungsdatum", "en": "Date of performance", "fr": "Date de la prestation", "it": "Data della prestazione", "pt": "Data do serviço"},
    "inv_issuer_name": {"de": "Dein Name", "en": "Your name", "fr": "Votre nom", "it": "Il tuo nome", "pt": "Seu nome"},
    "inv_issuer_address": {"de": "Deine Adresse", "en": "Your address", "fr": "Votre adresse", "it": "Il tuo indirizzo", "pt": "Seu endereço"},
    "inv_issuer_tax_id": {"de": "Steuernummer / USt-IdNr.", "en": "Tax number / VAT ID", "fr": "Numéro fiscal / n° TVA", "it": "Codice fiscale / partita IVA", "pt": "Número fiscal / ID de IVA"},
    "inv_recipient_name": {"de": "Rechnungsempfänger", "en": "Bill to", "fr": "Destinataire", "it": "Destinatario", "pt": "Destinatário"},
    "inv_recipient_address": {"de": "Adresse des Empfängers", "en": "Recipient's address", "fr": "Adresse du destinataire", "it": "Indirizzo del destinatario", "pt": "Endereço do destinatário"},
    "inv_service": {"de": "Leistung", "en": "Service", "fr": "Prestation", "it": "Prestazione", "pt": "Serviço"},
    "inv_net_amount": {"de": "Nettobetrag", "en": "Net amount", "fr": "Montant net", "it": "Importo netto", "pt": "Valor líquido"},
    "inv_currency": {"de": "Währung", "en": "Currency", "fr": "Devise", "it": "Valuta", "pt": "Moeda"},
    "inv_tax_preset": {"de": "Land und Besteuerung (USt/MWST)", "en": "Country and tax (VAT)", "fr": "Pays et fiscalité (TVA)", "it": "Paese e fiscalità (IVA)", "pt": "País e tributação (IVA)"},
    "inv_tax_rate_override": {"de": "Steuersatz in % (nur bei „Regelbesteuerung“/„Anderes“)", "en": "Tax rate in % (only for “standard” / “other”)", "fr": "Taux en % (seulement « standard » / « autre »)", "it": "Aliquota in % (solo «standard» / «altro»)", "pt": "Alíquota em % (só “padrão” / “outro”)"},
    "inv_tax_rate_placeholder": {"de": "z. B. 19", "en": "e.g. 19", "fr": "ex. 19", "it": "es. 19", "pt": "ex.: 19"},
    "inv_tax_custom_text": {"de": "Steuerhinweis / freier Text („Anderes“)", "en": "Tax note / free text (“other”)", "fr": "Mention fiscale / texte libre (« autre »)", "it": "Nota fiscale / testo libero («altro»)", "pt": "Observação fiscal / texto livre (“outro”)"},
    "inv_tax_custom_placeholder": {"de": "z. B. die Steuerregel deines Landes", "en": "e.g. your country's tax rule", "fr": "ex. la règle fiscale de votre pays", "it": "es. la regola fiscale del tuo paese", "pt": "ex.: a regra do seu país"},
    "inv_travel": {"de": "Fahrkosten (optional)", "en": "Travel costs (optional)", "fr": "Frais de déplacement (facultatif)", "it": "Spese di viaggio (facoltative)", "pt": "Deslocamento (opcional)"},
    "inv_lodging": {"de": "Übernachtungskosten (optional)", "en": "Accommodation (optional)", "fr": "Hébergement (facultatif)", "it": "Alloggio (facoltativo)", "pt": "Hospedagem (opcional)"},
    "inv_payment_terms": {"de": "Zahlungsbedingungen", "en": "Payment terms", "fr": "Conditions de paiement", "it": "Condizioni di pagamento", "pt": "Condições de pagamento"},
    "inv_generate_pdf": {"de": "PDF erstellen", "en": "Create PDF", "fr": "Créer le PDF", "it": "Crea PDF", "pt": "Gerar PDF"},
    "inv_save_for_review": {"de": "Speichern und zur Prüfung senden", "en": "Save and send for review", "fr": "Enregistrer et envoyer pour vérification", "it": "Salva e invia per la revisione", "pt": "Salvar e enviar para revisão"},
    "inv_form_error": {"de": "Bitte prüfe die Pflichtfelder und Beträge.", "en": "Please check the required fields and amounts.", "fr": "Veuillez vérifier les champs obligatoires et les montants.", "it": "Controlla i campi obbligatori e gli importi.", "pt": "Confira os campos obrigatórios e os valores."},
    "inv_no_credit": {"de": "Dein Rechnungskontingent für diesen Monat ist aufgebraucht.", "en": "You've used up this month's invoice allowance.", "fr": "Vous avez épuisé votre quota de factures ce mois-ci.", "it": "Hai esaurito le fatture disponibili per questo mese.", "pt": "Você já usou todas as faturas disponíveis deste mês."},
    "inv_preview_title": {"de": "Rechnungsvorschau", "en": "Invoice preview", "fr": "Aperçu de la facture", "it": "Anteprima della fattura", "pt": "Prévia da fatura"},
    "inv_confirm_send": {"de": "Bestätigen und per E-Mail senden", "en": "Confirm and send by e-mail", "fr": "Confirmer et envoyer par e-mail", "it": "Conferma e invia via e-mail", "pt": "Confirmar e enviar por e-mail"},
    "inv_waiting_for": {"de": "Wartet darauf, dass {name} prüft und bestätigt.", "en": "Waiting for {name} to review and confirm.", "fr": "En attente de la vérification et de la confirmation de {name}.", "it": "In attesa che {name} controlli e confermi.", "pt": "Aguardando {name} revisar e confirmar."},
    "inv_cancel_request": {"de": "Anfrage abbrechen", "en": "Cancel this request", "fr": "Annuler cette demande", "it": "Annulla questa richiesta", "pt": "Cancelar este pedido"},
    "inv_tax_de_klein": {"de": "Deutschland — Kleinunternehmer (§19 UStG, keine USt)", "en": "Germany — small business (§19 UStG, no VAT)", "fr": "Allemagne — petite entreprise (§19 UStG, sans TVA)", "it": "Germania — piccola impresa (§19 UStG, senza IVA)", "pt": "Alemanha — pequeno empresário (§19 UStG, sem IVA)"},
    "inv_tax_de_cultural": {"de": "Deutschland — Kulturbefreiung (§4 Nr. 20 UStG, keine USt)", "en": "Germany — cultural exemption (§4 No. 20 UStG, no VAT)", "fr": "Allemagne — exonération culturelle (§4 n° 20 UStG, sans TVA)", "it": "Germania — esenzione culturale (§4 n. 20 UStG, senza IVA)", "pt": "Alemanha — isenção cultural (§4 nº 20 UStG, sem IVA)"},
    "inv_tax_de_standard": {"de": "Deutschland — Regelbesteuerung", "en": "Germany — standard VAT", "fr": "Allemagne — TVA standard", "it": "Germania — IVA ordinaria", "pt": "Alemanha — tributação padrão"},
    "inv_tax_at_klein": {"de": "Österreich — Kleinunternehmerregelung (keine USt)", "en": "Austria — small business (no VAT)", "fr": "Autriche — petite entreprise (sans TVA)", "it": "Austria — piccola impresa (senza IVA)", "pt": "Áustria — pequeno empresário (sem IVA)"},
    "inv_tax_at_cultural": {"de": "Österreich — Kulturbefreiung (keine USt)", "en": "Austria — cultural exemption (no VAT)", "fr": "Autriche — exonération culturelle (sans TVA)", "it": "Austria — esenzione culturale (senza IVA)", "pt": "Áustria — isenção cultural (sem IVA)"},
    "inv_tax_at_standard": {"de": "Österreich — Regelbesteuerung", "en": "Austria — standard VAT", "fr": "Autriche — TVA standard", "it": "Austria — IVA ordinaria", "pt": "Áustria — tributação padrão"},
    "inv_tax_ch_exempt": {"de": "Schweiz — von der MWST befreit", "en": "Switzerland — exempt from VAT (MWST)", "fr": "Suisse — exonéré de TVA", "it": "Svizzera — esente IVA", "pt": "Suíça — isento de IVA (MWST)"},
    "inv_tax_ch_cultural": {"de": "Schweiz — Kulturbefreiung (keine MWST)", "en": "Switzerland — cultural exemption (no VAT)", "fr": "Suisse — exonération culturelle (sans TVA)", "it": "Svizzera — esenzione culturale (senza IVA)", "pt": "Suíça — isenção cultural (sem IVA)"},
    "inv_tax_ch_standard": {"de": "Schweiz — Regelbesteuerung (MWST)", "en": "Switzerland — standard VAT (MWST)", "fr": "Suisse — TVA standard", "it": "Svizzera — IVA ordinaria", "pt": "Suíça — tributação padrão (MWST)"},
    "inv_tax_other": {"de": "Anderes Land (außerhalb DE/AT/CH — unten eingeben)", "en": "Other country (outside DE/AT/CH — type it below)", "fr": "Autre pays (hors DE/AT/CH — à saisir ci-dessous)", "it": "Altro paese (fuori DE/AT/CH — scrivilo sotto)", "pt": "Outro país (fora DE/AT/CH — digite abaixo)"},
    "invoice_already_sent": {"de": "Rechnung für diesen Match wurde bereits gesendet.", "en": "An invoice for this Match has already been sent.", "fr": "Une facture pour ce Match a déjà été envoyée.", "it": "Per questo Match è già stata inviata una fattura.", "pt": "A Rechnung deste Match já foi enviada."},
    "invoice_view_draft": {"de": "Rechnungsentwurf ansehen", "en": "View invoice draft", "fr": "Voir le brouillon de facture", "it": "Vedi bozza della fattura", "pt": "Ver rascunho da Rechnung"},
    "invoice_fill_now": {"de": "Jetzt ausfüllen", "en": "Fill in now", "fr": "Remplir maintenant", "it": "Compila ora", "pt": "Preencher agora"},
    "invoice_generate": {"de": "Rechnung erstellen", "en": "Generate invoice", "fr": "Générer la facture", "it": "Genera fattura", "pt": "Gerar Rechnung"},
    "invoice_request": {"de": "Rechnung anfordern", "en": "Request invoice", "fr": "Demander une facture", "it": "Richiedi fattura", "pt": "Solicitar Rechnung"},
    "nav_rechnungmaker": {"de": "Rechnungmaker", "en": "Rechnungmaker", "fr": "Rechnungmaker", "it": "Rechnungmaker", "pt": "Rechnungmaker"},
    "rechnungmaker_tab_match": {"de": "Match-Rechnungen", "en": "Match invoices", "fr": "Factures de Match", "it": "Fatture da Match", "pt": "Rechnungen de Match"},
    "rechnungmaker_tab_avulso": {"de": "Freier Rechnungsgenerator", "en": "Standalone generator", "fr": "Générateur libre", "it": "Generatore libero", "pt": "Gerador Avulso"},
    "rechnungmaker_match_empty": {"de": "Gerade nichts zu tun — keine Rechnung offen oder anfragbar.", "en": "Nothing to do right now — no invoice open or requestable.", "fr": "Rien à faire pour le moment — aucune facture ouverte ou à demander.", "it": "Niente da fare al momento — nessuna fattura aperta o richiedibile.", "pt": "Nada pendente por enquanto — nenhuma Rechnung aberta ou disponível pra pedir."},
    "rechnungmaker_avulso_help": {"de": "Freier Generator: deine Daten bleiben nur bei dieser Erstellung und im heruntergeladenen PDF.", "en": "Standalone generator: your data stays only in this generation and in the downloaded PDF.", "fr": "Générateur libre : vos données restent uniquement dans cette génération et dans le PDF téléchargé.", "it": "Generatore libero: i tuoi dati restano solo in questa generazione e nel PDF scaricato.", "pt": "Gerador avulso: seus dados ficam apenas nesta geração e no PDF baixado."},
    # Rechnungmaker live-preview pane (19/09/2026) — label above the
    # WYSIWYG mock of the PDF (see app/templates/_invoice_preview.html).
    "invoice_preview_label": {"de": "Live-Vorschau", "en": "Live preview", "fr": "Aperçu en direct", "it": "Anteprima dal vivo", "pt": "Prévia em tempo real"},
    "rechnungmaker_avulso_form_error": {"de": "Bitte Pflichtfelder und dein Rechnungskontingent prüfen.", "en": "Please check the required fields and your invoice allowance.", "fr": "Vérifiez les champs obligatoires et votre quota de factures.", "it": "Controlla i campi obbligatori e il tuo credito fatture.", "pt": "Confira os campos obrigatórios e seus créditos de Rechnung."},
    "rechnungmaker_personal_counter_title": {"de": "Deine ausgestellten Rechnungen", "en": "Your issued invoices", "fr": "Vos factures émises", "it": "Le tue fatture emesse", "pt": "Suas Rechnungen emitidas"},
    "rechnungmaker_personal_counter_help": {"de": "Nur für dich sichtbar — Freier Generator + Match-Rechnungen zusammen.", "en": "Visible only to you — standalone generator + Match invoices combined.", "fr": "Visible uniquement par vous — générateur libre + factures de Match cumulés.", "it": "Visibile solo a te — generatore libero + fatture da Match insieme.", "pt": "Visível só pra você — Gerador Avulso e Match-Rechnungen somados."},
    "invoice_status_draft_open": {"de": "Rechnungsentwurf offen.", "en": "Invoice draft open.", "fr": "Brouillon de facture ouvert.", "it": "Bozza di fattura aperta.", "pt": "Rascunho de Rechnung em aberto."},
    "invoice_status_available": {"de": "Rechnung kann angefordert werden.", "en": "Invoice can be requested.", "fr": "Facture disponible sur demande.", "it": "Fattura disponibile su richiesta.", "pt": "Rechnung disponível pra pedir."},
    "invoice_go_to_rechnungmaker": {"de": "Zum Rechnungmaker", "en": "Go to Rechnungmaker", "fr": "Aller au Rechnungmaker", "it": "Vai al Rechnungmaker", "pt": "Ir para o Rechnungmaker"},
    "listing_form_details_section": {"de": "Musikalische Angaben", "en": "Musical details", "fr": "Détails musicaux", "it": "Dettagli musicali", "pt": "Detalhes musicais"},
    "listing_form_job_required_help": {
        "de": "Bei der Suche nach Gesang oder Dirigat ist das Werk Pflichtfeld (*). Stimmlage und Honorar werden unten in der Liste der offenen Stellen angegeben (mindestens eine Stelle erforderlich). Der Veranstaltungsort ist optional.",
        "en": "When seeking a singer or conductor, work/piece is required (*). Voice type and fee are filled in the vacancy list below (at least one vacancy required). Venue is optional.",
        "fr": "Pour rechercher un chanteur ou un chef, l'œuvre est obligatoire (*). La tessiture et le cachet sont renseignés dans la liste des postes vacants ci-dessous (au moins un poste requis). Le lieu est facultatif.",
        "it": "Per cercare un cantante o direttore, l'opera è obbligatoria (*). Tessitura e compenso si inseriscono nell'elenco dei posti vacanti qui sotto (almeno un posto richiesto). La sede è facoltativa.",
        "pt": "Ao procurar cantor ou maestro, obra é obrigatória (*). Tipo de voz e cachê são preenchidos na lista de vagas abaixo (pelo menos uma vaga obrigatória). O local de apresentação é opcional.",
    },
    "profile_preferences_card": {"de": "Benachrichtigungen", "en": "Notifications", "fr": "Notifications", "it": "Notifiche", "pt": "Notificações"},
    "profile_visibility_card": {"de": "Sichtbarkeit und Profil-Link", "en": "Visibility and profile link", "fr": "Visibilité et lien du profil", "it": "Visibilità e link del profilo", "pt": "Visibilidade e link do perfil"},
    "profile_professional_card": {"de": "Musikalisches Profil", "en": "Musical profile", "fr": "Profil musical", "it": "Profilo musicale", "pt": "Perfil musical"},
    "profile_email_language": {"de": "E-Mail-Sprache", "en": "Email language", "fr": "Langue des e-mails", "it": "Lingua delle email", "pt": "Idioma dos e-mails"},
    "profile_email_language_help": {"de": "System-E-Mails verwenden diese Sprache, andernfalls Englisch.", "en": "System emails use this language, or English if a translation is unavailable.", "fr": "Les e-mails système utilisent cette langue, ou l’anglais si la traduction est indisponible.", "it": "Le email di sistema usano questa lingua, oppure l’inglese se la traduzione non è disponibile.", "pt": "Os e-mails do sistema usam este idioma, ou inglês quando não houver tradução."},
    "profile_account_controls": {"de": "Kontoverwaltung", "en": "Account controls", "fr": "Gestion du compte", "it": "Gestione dell’account", "pt": "Gestão da conta"},
    "profile_account_private_help": {"de": "Private Kontoverwaltung, nicht Teil des öffentlichen Profils.", "en": "Private account controls, separate from your public profile.", "fr": "Gestion privée du compte, séparée du profil public.", "it": "Gestione privata dell’account, separata dal profilo pubblico.", "pt": "Controles privados da conta, separados do seu perfil público."},
    # --- navigation / layout -------------------------------------------------
    "site_tagline": {"de": "Dein Weg zu dem perfekten Auftritt!", "en": "Your path to the perfect performance!", "fr": "Votre chemin vers la prestation parfaite !", "it": "La tua strada verso la performance perfetta!", "pt": "Seu caminho para a apresentação perfeita!"},
    "nav_home": {"de": "Start", "en": "Home", "fr": "Accueil", "it": "Home", "pt": "Início"},
    "nav_my_listings": {"de": "Meine Anzeigen", "en": "My listings", "fr": "Mes annonces", "it": "I miei annunci", "pt": "Meus anúncios"},
    "nav_favorites": {"de": "Favoriten", "en": "Favorites", "fr": "Favoris", "it": "Preferiti", "pt": "Favoritos"},
    "nav_notas": {"de": "Notas", "en": "Notas", "fr": "Notas", "it": "Notas", "pt": "Notas"},
    "nav_hall_da_fama": {"de": "Ruhmeshalle", "en": "Hall of Fame", "fr": "Temple de la renommée", "it": "Bacheca della fama", "pt": "Hall da Fama"},
    "nav_board": {"de": "Jobs", "en": "Jobs", "fr": "Annonces", "it": "Annunci", "pt": "Vagas"},
    # Sub-items of the "Jobs" side-nav group (19/09/2026, task #51 menu
    # reorg — see AI_CHANGELOG.md for Daniel's own sketch). "Search for
    # a Job" links to the same /board as nav_board above (deliberately
    # worded differently from the group's own header so it doesn't read
    # like a duplicate).
    "nav_search_for_job": {"de": "Job suchen", "en": "Search for a job", "fr": "Rechercher une annonce", "it": "Cerca un annuncio", "pt": "Buscar vaga"},
    "nav_post_job": {"de": "Anzeige aufgeben", "en": "Post a job", "fr": "Publier une annonce", "it": "Pubblica un annuncio", "pt": "Publicar vaga"},
    "nav_menu_toggle": {"de": "Menü", "en": "Menu", "fr": "Menu", "it": "Menu", "pt": "Menu"},
    "nav_profile": {"de": "Mein Profil", "en": "My profile", "fr": "Mon profil", "it": "Il mio profilo", "pt": "Meu perfil"},
    "nav_login": {"de": "Anmelden", "en": "Log in", "fr": "Connexion", "it": "Accedi", "pt": "Entrar"},
    "nav_register": {"de": "Registrieren", "en": "Sign up", "fr": "S'inscrire", "it": "Registrati", "pt": "Cadastrar"},
    "nav_logout": {"de": "Abmelden", "en": "Log out", "fr": "Déconnexion", "it": "Esci", "pt": "Sair"},
    "role_singer": {"de": "Sänger(in)", "en": "Singer", "fr": "Chanteur(euse)", "it": "Cantante", "pt": "Cantor(a)"},
    "role_conductor": {"de": "Dirigent(in)", "en": "Conductor", "fr": "Chef(fe) de chœur", "it": "Direttore/Direttrice", "pt": "Regente"},
    "footer_text": {
        "de": "Lernprojekt — verbindet Sänger(innen) und Dirigent(innen) in Deutschland.",
        "en": "Learning project — connecting singers and conductors in Germany.",
        "fr": "Projet pédagogique — met en relation chanteurs et chefs de chœur en Allemagne.",
        "it": "Progetto didattico — mette in contatto cantanti e direttori in Germania.",
        "pt": "Projeto de estudo — conecta cantores e regentes na Alemanha.",
    },

    # --- home (boas-vindas + matches) ----------------------------------------
    "home_title": {"de": "Schwarzes Brett", "en": "Bulletin board", "fr": "Petites annonces", "it": "Bacheca", "pt": "Mural de avisos"},
    "home_welcome": {"de": "Willkommen, {name}", "en": "Welcome, {name}", "fr": "Bienvenue, {name}", "it": "Benvenuto/a, {name}", "pt": "Bem-vindo(a), {name}"},
    "posts_feed_title": {"de": "Neuigkeiten", "en": "Announcements", "fr": "Actualités", "it": "Novità", "pt": "Novidades"},
    "post_read_more": {"de": "Weiterlesen", "en": "Read more", "fr": "Lire la suite", "it": "Continua a leggere", "pt": "Ler mais"},
    "post_unpublished_notice": {
        "de": "Entwurf / nicht veröffentlicht — nur für Admins sichtbar",
        "en": "Draft / unpublished — visible to admins only",
        "fr": "Brouillon / non publié — visible uniquement par les admins",
        "it": "Bozza / non pubblicato — visibile solo agli admin",
        "pt": "Rascunho / não publicado — visível só para administradores",
    },
    "home_matches_title": {"de": "Das könnte zu dir passen", "en": "Matches for your profile", "fr": "Cela pourrait vous correspondre", "it": "Potrebbe fare al caso tuo", "pt": "Isso pode combinar com você"},
    "home_matches_subtitle": {
        "de": "Bis zu 5 Anzeigen, ausgewählt nach deiner Stimmlage/Rolle und Stadt.",
        "en": "Up to 5 listings, picked to match your voice type/role and city.",
        "fr": "Jusqu'à 5 annonces, sélectionnées selon votre tessiture/rôle et votre ville.",
        "it": "Fino a 5 annunci, scelti in base alla tua tessitura/ruolo e città.",
        "pt": "Até 5 anúncios, escolhidos de acordo com sua voz/papel e cidade.",
    },
    "home_highlights_title": {
        "de": "Highlights der Woche",
        "en": "Highlights of the week",
        "fr": "À la une cette semaine",
        "it": "In evidenza questa settimana",
        "pt": "Destaques da semana",
    },
    "home_highlights_subtitle": {
        "de": "Aktive Mitglieder der Community — teils hervorgehobene Profile, teils die meistbesuchten dieser Woche.",
        "en": "Active members of the community — a mix of featured profiles and this week's most-visited.",
        "fr": "Membres actifs de la communauté — un mélange de profils en vedette et des plus visités cette semaine.",
        "it": "Membri attivi della community — un mix di profili in evidenza e i più visitati questa settimana.",
        "pt": "Membros ativos da comunidade — uma mistura de perfis em destaque e os mais visitados da semana.",
    },
    "home_matches_empty": {
        "de": "Gerade nichts Passendes — wirf einen Blick auf die ganze Jobbörse.",
        "en": "Nothing matching right now — take a look at the full board.",
        "fr": "Rien de correspondant pour l'instant — jetez un œil à toutes les annonces.",
        "it": "Al momento nessun annuncio corrispondente — dai un'occhiata alla bacheca completa.",
        "pt": "Nada compatível no momento — dê uma olhada em todos os anúncios.",
    },
    "home_anon_title": {
        "de": "Sänger(innen) und Dirigent(innen) finden sich hier",
        "en": "Where singers and conductors find each other",
        "fr": "Là où chanteurs et chefs de chœur se rencontrent",
        "it": "Dove cantanti e direttori si incontrano",
        "pt": "Onde cantores e regentes se encontram",
    },
    "home_anon_subtitle": {
        "de": "Ein Schwarzes Brett für Gesuche und Angebote in Deutschland, Österreich und der Schweiz.",
        "en": "A bulletin board for job postings and availability across Germany, Austria, and Switzerland.",
        "fr": "Des petites annonces pour offres et recherches en Allemagne, en Autriche et en Suisse.",
        "it": "Una bacheca di annunci per offerte e disponibilità in Germania, Austria e Svizzera.",
        "pt": "Um mural de avisos para vagas e disponibilidade na Alemanha, Áustria e Suíça.",
    },
    "home_teaser_title": {"de": "Neueste Anzeigen", "en": "Latest listings", "fr": "Dernières annonces", "it": "Ultimi annunci", "pt": "Últimos anúncios"},
    "home_cta_register": {"de": "Kostenlos registrieren", "en": "Sign up for free", "fr": "Inscription gratuite", "it": "Registrati gratis", "pt": "Cadastre-se grátis"},
    "home_cta_login": {"de": "Anmelden", "en": "Log in", "fr": "Connexion", "it": "Accedi", "pt": "Entrar"},
    "home_cta_browse": {"de": "Alle Anzeigen ansehen", "en": "View all listings", "fr": "Voir toutes les annonces", "it": "Vedi tutti gli annunci", "pt": "Ver todos os anúncios"},

    # --- /board (quadro de avisos completo, com filtros) ---------------------
    "board_title": {"de": "Jobbörse", "en": "Jobs / Browse", "fr": "Annonces / Parcourir", "it": "Annunci / Sfoglia", "pt": "Vagas / Buscar"},
    "board_subtitle": {
        "de": "Das vollständige Schwarze Brett — durchsuchen und filtern.",
        "en": "The full bulletin board — search and filter.",
        "fr": "Toutes les petites annonces — recherchez et filtrez.",
        "it": "La bacheca completa — cerca e filtra.",
        "pt": "O mural completo — busque e filtre.",
    },
    "filter_search_placeholder": {"de": "Suche eingeben...", "en": "Type your search here...", "fr": "Tapez votre recherche...", "it": "Digita la tua ricerca...", "pt": "Digite sua busca..."},
    "filter_city_placeholder": {"de": "Stadt", "en": "City", "fr": "Ville", "it": "Città", "pt": "Cidade"},
    "filter_all_countries": {"de": "Alle Länder", "en": "All countries", "fr": "Tous les pays", "it": "Tutti i paesi", "pt": "Todos os países"},
    "filter_country_de": {"de": "Deutschland", "en": "Germany", "fr": "Allemagne", "it": "Germania", "pt": "Alemanha"},
    "filter_country_at": {"de": "Österreich", "en": "Austria", "fr": "Autriche", "it": "Austria", "pt": "Áustria"},
    "filter_country_ch": {"de": "Schweiz", "en": "Switzerland", "fr": "Suisse", "it": "Svizzera", "pt": "Suíça"},
    "filter_country_other": {"de": "Andere", "en": "Other", "fr": "Autre", "it": "Altro", "pt": "Outro"},
    "filter_all_types": {"de": "Alle Anzeigentypen", "en": "All listing types", "fr": "Tous les types d'annonces", "it": "Tutti i tipi di annuncio", "pt": "Todos os tipos de anúncio"},
    "filter_all_voice_types": {"de": "Alle Stimmlagen", "en": "All voice types", "fr": "Toutes les tessitures", "it": "Tutte le tessiture", "pt": "Todos os tipos de voz"},
    "filter_hashtag_placeholder": {"de": "Komponist (Hashtag)", "en": "Composer (hashtag)", "fr": "Compositeur (hashtag)", "it": "Compositore (hashtag)", "pt": "Compositor (hashtag)"},
    "filter_button": {"de": "Filtern", "en": "Filter", "fr": "Filtrer", "it": "Filtra", "pt": "Filtrar"},
    "filter_clear": {"de": "Filter zurücksetzen", "en": "Clear filters", "fr": "Réinitialiser les filtres", "it": "Cancella filtri", "pt": "Limpar filtros"},
    "empty_state": {
        "de": "Keine Anzeigen mit diesen Filtern gefunden.",
        "en": "No listings found with these filters.",
        "fr": "Aucune annonce trouvée avec ces filtres.",
        "it": "Nessun annuncio trovato con questi filtri.",
        "pt": "Nenhum anúncio encontrado com esses filtros.",
    },
    "by_author": {"de": "von", "en": "by", "fr": "par", "it": "di", "pt": "por"},

    "listing_type_seeking_singer": {"de": "Dirigent(in) sucht Sänger(in)", "en": "Conductor seeking singer", "fr": "Chef(fe) de chœur cherche chanteur(euse)", "it": "Direttore cerca cantante", "pt": "Regente procura cantor(a)"},
    "listing_type_seeking_conductor": {"de": "Sänger(in) sucht Dirigent(in)", "en": "Singer seeking conductor", "fr": "Chanteur(euse) cherche chef(fe) de chœur", "it": "Cantante cerca direttore", "pt": "Cantor(a) procura regente"},
    "listing_type_singer_available": {"de": "Sänger(in) verfügbar", "en": "Singer available", "fr": "Chanteur(euse) disponible", "it": "Cantante disponibile", "pt": "Cantor(a) disponível"},
    "listing_type_conductor_available": {"de": "Dirigent(in) verfügbar", "en": "Conductor available", "fr": "Chef(fe) de chœur disponible", "it": "Direttore disponibile", "pt": "Regente disponível"},

    # --- listing detail ---------------------------------------------------
    "listing_not_found": {"de": "Anzeige nicht gefunden.", "en": "Listing not found.", "fr": "Annonce introuvable.", "it": "Annuncio non trovato.", "pt": "Anúncio não encontrado."},
    "back_to_board": {"de": "Zurück zum Schwarzen Brett", "en": "Back to the board", "fr": "Retour aux annonces", "it": "Torna alla bacheca", "pt": "Voltar ao mural"},
    "contact_title": {"de": "Kontakt", "en": "Contact", "fr": "Contact", "it": "Contatto", "pt": "Contato"},
    "view_profile": {"de": "Profil ansehen", "en": "View profile", "fr": "Voir le profil", "it": "Vedi profilo", "pt": "Ver perfil"},
    "delete_button": {"de": "Anzeige löschen", "en": "Delete listing", "fr": "Supprimer l'annonce", "it": "Elimina annuncio", "pt": "Excluir anúncio"},
    "delete_confirm": {"de": "Diese Anzeige wirklich löschen?", "en": "Really delete this listing?", "fr": "Vraiment supprimer cette annonce ?", "it": "Eliminare davvero questo annuncio?", "pt": "Excluir mesmo este anúncio?"},
    "edit_button": {"de": "Bearbeiten", "en": "Edit", "fr": "Modifier", "it": "Modifica", "pt": "Editar"},
    "voice_type_all": {"de": "Alle Stimmlagen", "en": "All voice types", "fr": "Toutes les tessitures", "it": "Tutte le tessiture", "pt": "Todos os tipos de voz"},

    # --- listing form -------------------------------------------------
    "listing_form_title": {"de": "Anzeige aufgeben", "en": "Post a listing", "fr": "Publier une annonce", "it": "Pubblica un annuncio", "pt": "Publicar anúncio"},
    "listing_form_required_section": {"de": "Pflichtangaben", "en": "Required information", "fr": "Informations obligatoires", "it": "Informazioni obbligatorie", "pt": "Informações obrigatórias"},
    "listing_form_optional_section": {"de": "Optionale Details", "en": "Optional details", "fr": "Détails facultatifs", "it": "Dettagli facoltativi", "pt": "Detalhes opcionais"},
    "listing_form_edit_title": {"de": "Anzeige bearbeiten", "en": "Edit listing", "fr": "Modifier l'annonce", "it": "Modifica annuncio", "pt": "Editar anúncio"},
    "listing_form_type_label": {"de": "Anzeigentyp", "en": "Listing type", "fr": "Type d'annonce", "it": "Tipo di annuncio", "pt": "Tipo de anúncio"},
    "listing_form_title_label": {"de": "Titel", "en": "Title", "fr": "Titre", "it": "Titolo", "pt": "Título"},
    "listing_form_description_label": {"de": "Beschreibung", "en": "Description", "fr": "Description", "it": "Descrizione", "pt": "Descrição"},
    "listing_form_city_label": {"de": "Stadt*", "en": "City*", "fr": "Ville*", "it": "Città*", "pt": "Cidade*"},
    "listing_form_voice_type_label": {"de": "Stimmlage (falls zutreffend)", "en": "Voice type (if applicable)", "fr": "Tessiture (le cas échéant)", "it": "Tessitura (se applicabile)", "pt": "Tipo de voz (se aplicável)"},

    # --- P3.A: logistics checkboxes + vacancies per voice type --------
    # FIX (19/09/2026): this field only shows for singer_available/
    # conductor_available now (a seeking_singer/seeking_conductor
    # listing enters voice type through the vacancy list only, see
    # listing_form_vacancies_help below) — reworded away from the old
    # "for multiple vacancies, use the list below" text, which no
    # longer applies to this field at all.
    "listing_form_voice_type_help": {
        "de": "Wird zum Filtern im Verzeichnis und auf der Pinnwand verwendet.",
        "en": "Used for filtering in the directory and on the board.",
        "fr": "Utilisé pour le filtrage dans l'annuaire et sur le tableau.",
        "it": "Usato per il filtro nella directory e in bacheca.",
        "pt": "Usado para filtrar no diretório e no mural.",
    },
    "listing_form_travel_cost_label": {"de": "Fahrkosten werden übernommen", "en": "Travel costs are covered", "fr": "Frais de déplacement pris en charge", "it": "Spese di viaggio coperte", "pt": "Custos de deslocamento cobertos"},
    "listing_form_rehearsal_schedule_label": {"de": "Probenplan vorhanden", "en": "Rehearsal schedule available", "fr": "Calendrier des répétitions disponible", "it": "Calendario delle prove disponibile", "pt": "Cronograma de ensaios disponível"},
    "listing_form_sheet_music_label": {"de": "Partitur vorhanden", "en": "Sheet music available", "fr": "Partition disponible", "it": "Spartito disponibile", "pt": "Partitura disponível"},
    "listing_form_sheet_music_url_label": {"de": "Link zur Partitur", "en": "Sheet music link", "fr": "Lien vers la partition", "it": "Link allo spartito", "pt": "Link da partitura"},
    "listing_form_sheet_music_url_help": {
        "de": "Wird erst nach einem bestätigten Match sichtbar (Zero-Storage: nur der Link wird gespeichert, keine Datei).",
        "en": "Only shown after a confirmed Match (Zero-Storage: only the link is stored, no file).",
        "fr": "Visible uniquement après un Match confirmé (Zero-Storage : seul le lien est stocké, aucun fichier).",
        "it": "Visibile solo dopo un Match confermato (Zero-Storage: viene salvato solo il link, nessun file).",
        "pt": "Só é exibido após um Match confirmado (Zero-Storage: apenas o link é salvo, nenhum arquivo).",
    },
    "listing_form_vacancies_section": {"de": "Offene Stellen", "en": "Vacancies", "fr": "Postes vacants", "it": "Posti vacanti", "pt": "Vagas"},
    "listing_form_vacancies_help": {
        "de": "Fügen Sie mindestens eine Stelle hinzu. Bei der Suche nach Gesang wählen Sie die gesuchte Stimmlage; bei der Suche nach Dirigat genügen Anzahl der Plätze und Honorar.",
        "en": "Add at least one vacancy. For a singer listing, choose the voice type you're seeking; for a conductor listing, just the number of slots and fee.",
        "fr": "Ajoutez au moins un poste. Pour une annonce de chanteur, choisissez la tessiture recherchée ; pour une annonce de chef, le nombre de places et le cachet suffisent.",
        "it": "Aggiungi almeno un posto. Per un annuncio da cantante, scegli la tessitura richiesta; per uno da direttore, bastano il numero di posti e il compenso.",
        "pt": "Adicione pelo menos uma vaga. Para anúncio de cantor, escolha o tipo de voz buscado; para anúncio de maestro, só o número de vagas e o cachê.",
    },
    "listing_form_vacancy_slots_placeholder": {"de": "Plätze", "en": "Slots", "fr": "Places", "it": "Posti", "pt": "Vagas"},
    # a11y (26/09/2026): visible labels for each vacancy-row control.
    "listing_form_vacancy_voice_label": {"de": "Stimmlage", "en": "Voice type", "fr": "Tessiture", "it": "Registro vocale", "pt": "Naipe"},
    "listing_form_vacancy_fee_label": {"de": "Honorar", "en": "Fee", "fr": "Cachet", "it": "Compenso", "pt": "Cachê"},
    # 26/09/2026: public strings that were hardcoded (Portuguese/English) in templates.
    "invoice_match_encrypted_help": {"de": "Match-Rechnung: Die Daten bleiben verschlüsselt, bis {name} bestätigt. Nichts wird im Klartext gespeichert.", "en": "Match invoice: the data stays encrypted until {name} confirms. Nothing is stored in plain text.", "fr": "Facture Match : les données restent chiffrées jusqu'à la confirmation de {name}. Rien n'est stocké en clair.", "it": "Fattura Match: i dati restano crittografati finché {name} non conferma. Nulla viene salvato in chiaro.", "pt": "Match-Rechnung: os dados ficam criptografados até {name} confirmar. Nada fica salvo em texto aberto."},
    "invoice_match_confirm_failed": {"de": "Bestätigung nicht möglich — der Entwurf ist möglicherweise abgelaufen.", "en": "Couldn't confirm — the draft may have expired.", "fr": "Confirmation impossible — le brouillon a peut-être expiré.", "it": "Impossibile confermare — la bozza potrebbe essere scaduta.", "pt": "Não foi possível confirmar — o rascunho pode ter expirado."},
    "invoice_match_after_confirm_help": {"de": "Nach der Bestätigung wird das PDF erstellt und per E-Mail an beide Seiten geschickt — VokalBoard speichert keine Kopie, auch nicht diesen Entwurf.", "en": "After confirming, the PDF is generated and e-mailed to both parties — VokalBoard keeps no copy, not even this draft.", "fr": "Après confirmation, le PDF est généré et envoyé par e-mail aux deux parties — VokalBoard n'en garde aucune copie, pas même ce brouillon.", "it": "Dopo la conferma, il PDF viene generato e inviato via e-mail a entrambe le parti — VokalBoard non ne conserva alcuna copia, nemmeno di questa bozza.", "pt": "Depois de confirmar, o PDF é gerado e enviado por e-mail para as duas partes — o VokalBoard não guarda nenhuma cópia, nem este rascunho."},
    "listing_contact_after_match_help": {"de": "Direkte Kontaktdaten werden nach einem bestätigten Match freigegeben.", "en": "Direct contact details are shared after a confirmed Match.", "fr": "Les coordonnées directes sont partagées après un Match confirmé.", "it": "I contatti diretti vengono condivisi dopo un Match confermato.", "pt": "Os contatos diretos são compartilhados após um Match confirmado."},
    "listing_form_vacancy_filled_label": {"de": "besetzt", "en": "filled", "fr": "pourvu(s)", "it": "occupati", "pt": "preenchidas"},
    # Task #52: soft client-side confirm before publishing without a fee
    # amount or "negotiable" set anywhere on the listing — fee stays
    # fully optional (can be added later), this is only a nudge, since
    # listings with a visible fee get more applications. Fires for the
    # top-level fee (self-ad listings) OR every vacancy row (job
    # listings) — see listing-form.js.
    "listing_form_fee_warning_confirm": {
        "de": "Sie haben kein Honorar angegeben und \"Verhandelbar\" nicht angekreuzt. Anzeigen mit sichtbarem Honorar erhalten mehr Bewerbungen. Trotzdem veröffentlichen?",
        "en": "You haven't entered a fee or checked \"Negotiable\". Listings with a visible fee get more applications. Publish anyway?",
        "fr": "Vous n'avez pas indiqué de cachet ni coché \"Négociable\". Les annonces avec un cachet visible reçoivent plus de candidatures. Publier quand même ?",
        "it": "Non hai indicato un compenso né spuntato \"Trattabile\". Gli annunci con compenso visibile ricevono più candidature. Pubblicare comunque?",
        "pt": "Você não preencheu o cachê nem marcou \"A negociar\". Anúncios com cachê visível recebem mais candidaturas. Publicar mesmo assim?",
    },
    "listing_form_add_vacancy": {"de": "Weitere Stimmlage hinzufügen", "en": "Add another voice type", "fr": "Ajouter une autre tessiture", "it": "Aggiungi un'altra tessitura", "pt": "Adicionar outro tipo de voz"},
    # FIX (19/09/2026, task #54, Daniel: "permitir remover vaga/naipe já
    # adicionado, não só adicionar") — replaces the old "leave the field
    # empty and save again" workaround with a real X button per row (see
    # .vacancy-remove-btn in listing_form.html/listing-form.js). The
    # help text now explains the button instead of the workaround.
    "listing_form_vacancies_remove_help": {
        "de": "Klicken Sie auf das X einer Zeile, um sie zu entfernen. Zeilen mit bereits bestätigten Matches können nicht entfernt werden.",
        "en": "Click the X on a row to remove it. Rows with an already-confirmed match can't be removed.",
        "fr": "Cliquez sur le X d'une ligne pour la supprimer. Les lignes avec un match déjà confirmé ne peuvent pas être supprimées.",
        "it": "Clicca sulla X di una riga per rimuoverla. Le righe con un match già confermato non possono essere rimosse.",
        "pt": "Clique no X de uma linha para removê-la. Linhas com Match já confirmado não podem ser removidas.",
    },
    "listing_form_remove_vacancy": {
        "de": "Diese Stelle entfernen", "en": "Remove this vacancy",
        "fr": "Supprimer ce poste", "it": "Rimuovi questo posto",
        "pt": "Remover esta vaga",
    },
    "listing_form_remove_vacancy_locked": {
        "de": "Kann nicht entfernt werden — hat bereits ein bestätigtes Match.",
        "en": "Can't be removed — already has a confirmed match.",
        "fr": "Impossible à supprimer — a déjà un match confirmé.",
        "it": "Non può essere rimossa — ha già un match confermato.",
        "pt": "Não pode ser removida — já tem um Match confirmado.",
    },
    "listing_form_repertoire_label": {"de": "Repertoire", "en": "Repertoire", "fr": "Répertoire", "it": "Repertorio", "pt": "Repertório"},
    "listing_form_work_label": {"de": "Werk*", "en": "Work/Piece*", "fr": "Œuvre*", "it": "Opera*", "pt": "Obra*"},
    "listing_form_repertoire_placeholder": {"de": "z.B. Mozart, Requiem", "en": "e.g. Mozart, Requiem", "fr": "ex. Mozart, Requiem", "it": "es. Mozart, Requiem", "pt": "ex.: Mozart, Requiem"},
    "listing_form_venue_label": {"de": "Ort (Kirche, Saal, ...)", "en": "Venue (church, hall, ...)", "fr": "Lieu (église, salle, ...)", "it": "Luogo (chiesa, sala, ...)", "pt": "Local (igreja, sala, ...)"},
    "listing_form_fee_label": {"de": "Honorar*", "en": "Fee*", "fr": "Cachet*", "it": "Compenso*", "pt": "Cachê*"},
    "listing_form_fee_placeholder": {
        "de": "z.B. 250€ oder \"nach Vereinbarung\"",
        "en": "e.g. €250 or \"negotiable\"",
        "fr": "ex. 250€ ou « à négocier »",
        "it": "es. 250€ o \"da concordare\"",
        "pt": "ex.: 250€ ou \"a combinar\"",
    },
    "listing_form_event_date_label": {"de": "Termin (optional)", "en": "Event date (optional)", "fr": "Date (facultatif)", "it": "Data (facoltativo)", "pt": "Data (opcional)"},
    "listing_form_country_label": {"de": "Land", "en": "Country", "fr": "Pays", "it": "Paese", "pt": "País"},
    "listing_form_submit": {"de": "Veröffentlichen", "en": "Publish", "fr": "Publier", "it": "Pubblica", "pt": "Publicar"},
    "listing_form_update_submit": {"de": "Aktualisieren", "en": "Update", "fr": "Mettre à jour", "it": "Aggiorna", "pt": "Atualizar"},
    "error_event_date_required": {"de": "Bitte gib ein gültiges Veranstaltungsdatum an.", "en": "Please enter a valid event date.", "fr": "Veuillez indiquer une date d'événement valide.", "it": "Inserisci una data valida per l'evento.", "pt": "Informe uma data válida para o evento."},
    "error_required_fields": {
        "de": "Bitte füllen Sie Werk und Stadt aus und fügen Sie mindestens eine offene Stelle hinzu.",
        "en": "Please fill in work and city, and add at least one vacancy below.",
        "fr": "Veuillez renseigner l'œuvre et la ville, et ajouter au moins un poste vacant.",
        "it": "Compila opera e città, e aggiungi almeno un posto vacante.",
        "pt": "Preencha obra e cidade, e adicione pelo menos uma vaga.",
    },
    "error_listing_rate_limited": {
        "de": "Zu viele Anzeigen in kurzer Zeit — bitte warten Sie ein paar Minuten und versuchen Sie es erneut.",
        "en": "Too many listings in a short time — please wait a few minutes and try again.",
        "fr": "Trop d'annonces en peu de temps — veuillez patienter quelques minutes et réessayer.",
        "it": "Troppi annunci in poco tempo — attendi qualche minuto e riprova.",
        "pt": "Muitos anúncios em pouco tempo — aguarde alguns minutos e tente novamente.",
    },
    "error_phone_required_for_listing": {
        "de": "Um eine Anzeige zu veröffentlichen, hinterlegen Sie zuerst eine Telefonnummer in Ihrem Profil.",
        "en": "To publish a listing, add a phone number to your profile first.",
        "fr": "Pour publier une annonce, ajoutez d'abord un numéro de téléphone à votre profil.",
        "it": "Per pubblicare un annuncio, aggiungi prima un numero di telefono al tuo profilo.",
        "pt": "Para publicar um anúncio, cadastre antes um telefone no seu perfil.",
    },

    # --- login -----------------------------------------------------------------
    "login_title": {"de": "Anmelden", "en": "Log in", "fr": "Connexion", "it": "Accedi", "pt": "Entrar"},
    "login_email_label": {"de": "E-Mail", "en": "Email", "fr": "E-mail", "it": "Email", "pt": "E-mail"},
    "login_password_label": {"de": "Passwort", "en": "Password", "fr": "Mot de passe", "it": "Password", "pt": "Senha"},
    "login_submit": {"de": "Anmelden", "en": "Log in", "fr": "Connexion", "it": "Accedi", "pt": "Entrar"},
    "login_no_account": {"de": "Noch kein Konto?", "en": "Don't have an account yet?", "fr": "Pas encore de compte ?", "it": "Non hai ancora un account?", "pt": "Ainda não tem conta?"},
    "og_site_description": {
        "de": "Das Schwarze Brett für Sänger(innen) und Dirigent(innen) in Deutschland, Österreich und der Schweiz.",
        "en": "The bulletin board connecting singers and conductors in Germany, Austria and Switzerland.",
        "fr": "Les petites annonces qui relient chanteurs et chefs de chœur en Allemagne, en Autriche et en Suisse.",
        "it": "La bacheca che mette in contatto cantanti e direttori in Germania, Austria e Svizzera.",
        "pt": "O mural que conecta cantores e regentes na Alemanha, Áustria e Suíça.",
    },
    # P3.D "convite express": teaser shown when a vaga's link is shared
    # outside the site (WhatsApp/Telegram/etc preview card) — prefix and
    # suffix wrap the listing's own repertoire/city, which the template
    # concatenates (see listing_detail.html; t() has no .format() support).
    # Deliberately does NOT reveal fee, exact date or the rest of the
    # listing — only Obra/Compositor (repertoire) and Cidade (city).
    "og_listing_teaser_prefix": {
        "de": "Schau dir diese Gelegenheit an:",
        "en": "Check out this opportunity:",
        "fr": "Regarde cette opportunité :",
        "it": "Guarda questa opportunità:",
        "pt": "Veja essa oportunidade:",
    },
    "og_listing_teaser_suffix": {
        "de": "Hab an dich gedacht!",
        "en": "Saw this and thought of you!",
        "fr": "Je l'ai vue et j'ai pensé à toi !",
        "it": "L'ho vista e ho pensato a te!",
        "pt": "Vi e pensei em você!",
    },
    "og_listing_teaser_description": {
        "de": "Alle Details (Honorar, Datum und mehr) auf VokalBoard.",
        "en": "Full details (fee, date and more) on VokalBoard.",
        "fr": "Tous les détails (cachet, date et plus) sur VokalBoard.",
        "it": "Tutti i dettagli (compenso, data e altro) su VokalBoard.",
        "pt": "Todos os detalhes (cachê, data e mais) no VokalBoard.",
    },
    # P3.D follow-up (2026-09-18): shown on the vaga page itself under
    # the trimmed meta line, for an anonymous visitor — same idea as
    # the two keys above, but for the actual page, not just the share
    # preview card.
    "listing_anon_teaser_hint": {
        "de": "Honorar, Datum und weitere Details sind nach der Anmeldung sichtbar.",
        "en": "Fee, date and more details become visible after you register.",
        "fr": "Cachet, date et autres détails visibles après inscription.",
        "it": "Compenso, data e altri dettagli visibili dopo la registrazione.",
        "pt": "Cachê, data e outros detalhes ficam visíveis depois de criar conta.",
    },
    "fee_negotiable_label": {
        "de": "Verhandelbar",
        "en": "Negotiable",
        "fr": "À négocier",
        "it": "Da negoziare",
        "pt": "A negociar",
    },
    # Listing flyer PDF (19/09/2026) — caption under the QR Code, see
    # app/listing_pdf.py / GET /listings/{id}/flyer.pdf.
    "listing_flyer_scan_caption": {
        "de": "QR-Code scannen für Details und Bewerbung",
        "en": "Scan the QR Code for details and to apply",
        "fr": "Scannez le QR Code pour les détails et pour postuler",
        "it": "Scansiona il QR Code per i dettagli e per candidarti",
        "pt": "Escaneie o QR Code para ver detalhes e se candidatar",
    },
    "listing_flyer_download_button": {
        "de": "Anzeige herunterladen (QR-Code)",
        "en": "Download flyer (QR Code)",
        "fr": "Télécharger l'affiche (QR Code)",
        "it": "Scarica il volantino (QR Code)",
        "pt": "Baixar anúncio (QR Code)",
    },
    "fee_negotiable_checkbox": {
        "de": "Honorar verhandelbar (kein Betrag)",
        "en": "Fee negotiable (no amount)",
        "fr": "Cachet à négocier (pas de montant)",
        "it": "Compenso da negoziare (nessun importo)",
        "pt": "Cachê a negociar (sem valor)",
    },
    "fee_amount_or_negotiable_required": {
        "de": "Bitte gib entweder einen Honorarbetrag ein oder markiere \"Verhandelbar\".",
        "en": "Please either enter a fee amount or check \"Negotiable\".",
        "fr": "Indique un montant ou coche « À négocier ».",
        "it": "Inserisci un importo o seleziona \"Da negoziare\".",
        "pt": "Informe um valor de cachê ou marque \"A negociar\".",
    },
    "login_error": {"de": "E-Mail oder Passwort falsch.", "en": "Incorrect email or password.", "fr": "E-mail ou mot de passe incorrect.", "it": "Email o password errati.", "pt": "E-mail ou senha incorretos."},
    "login_error_banned": {
        "de": "Dieses Konto wurde dauerhaft gesperrt.",
        "en": "This account has been permanently banned.",
        "fr": "Ce compte a été banni définitivement.",
        "it": "Questo account è stato bannato definitivamente.",
        "pt": "Esta conta foi banida permanentemente.",
    },
    "login_error_locked": {
        "de": "Zu viele fehlgeschlagene Versuche. Bitte versuche es in {minutes} Minute(n) erneut.",
        "en": "Too many failed attempts. Please try again in {minutes} minute(s).",
        "fr": "Trop de tentatives échouées. Réessayez dans {minutes} minute(s).",
        "it": "Troppi tentativi falliti. Riprova tra {minutes} minuto/i.",
        "pt": "Muitas tentativas malsucedidas. Tente novamente em {minutes} minuto(s).",
    },

    # --- registro ----------------------------------------------------------------
    "register_title": {"de": "Konto erstellen", "en": "Create an account", "fr": "Créer un compte", "it": "Crea un account", "pt": "Criar conta"},
    "register_category_label": {"de": "Ich bin", "en": "I am", "fr": "Je suis", "it": "Sono", "pt": "Eu sou"},
    "register_category_soprano": {"de": "Sopran", "en": "Soprano", "fr": "Soprano", "it": "Soprano", "pt": "Soprano"},
    "register_category_alto": {"de": "Alt", "en": "Alto", "fr": "Alto", "it": "Contralto", "pt": "Contralto"},
    "register_category_tenor": {"de": "Tenor", "en": "Tenor", "fr": "Ténor", "it": "Tenore", "pt": "Tenor"},
    "register_category_baixo": {"de": "Bass", "en": "Bass", "fr": "Basse", "it": "Basso", "pt": "Baixo"},
    "register_category_conductor": {"de": "Dirigent(in)", "en": "Conductor", "fr": "Chef(fe) de chœur", "it": "Direttore/Direttrice", "pt": "Regente"},
    "register_fullname_label": {"de": "Vollständiger Name", "en": "Full name", "fr": "Nom complet", "it": "Nome completo", "pt": "Nome completo"},
    "register_email_label": {"de": "E-Mail", "en": "Email", "fr": "E-mail", "it": "Email", "pt": "E-mail"},
    "register_password_label": {"de": "Passwort", "en": "Password", "fr": "Mot de passe", "it": "Password", "pt": "Senha"},
    "register_phone_label": {"de": "Telefon (optional)", "en": "Phone (optional)", "fr": "Téléphone (facultatif)", "it": "Telefono (facoltativo)", "pt": "Telefone (opcional)"},
    "register_bio_label": {
        "de": "Kurzbiografie (bis zu 1000 Zeichen)",
        "en": "Short biography (up to 1000 characters)",
        "fr": "Courte biographie (jusqu'à 1000 caractères)",
        "it": "Breve biografia (fino a 1000 caratteri)",
        "pt": "Biografia curta (até 1000 caracteres)",
    },
    "register_hashtags_label": {"de": "Komponisten-Hashtags (bis zu 10)", "en": "Composer hashtags (up to 10)", "fr": "Hashtags de compositeurs (jusqu'à 10)", "it": "Hashtag di compositori (fino a 10)", "pt": "Hashtags de compositores (até 10)"},
    "register_hashtags_help": {
        "de": "Komponisten, die Sie bereits gesungen haben, getrennt durch Kommas, z.B. Mozart, Verdi, Puccini",
        "en": "Composers you've already sung, separated by commas, e.g. Mozart, Verdi, Puccini",
        "fr": "Compositeurs que vous avez déjà chantés, séparés par des virgules, ex. Mozart, Verdi, Puccini",
        "it": "Compositori che hai già cantato, separati da virgole, es. Mozart, Verdi, Puccini",
        "pt": "Compositores que você já cantou, separados por vírgula, ex.: Mozart, Verdi, Puccini",
    },
    "register_ensemble_label": {"de": "Chor/Orchester, den Sie vertreten (optional)", "en": "Choir/orchestra you represent (optional)", "fr": "Chœur/orchestre que vous représentez (facultatif)", "it": "Coro/orchestra che rappresenti (facoltativo)", "pt": "Coral/orquestra que você representa (opcional)"},
    "register_submit": {"de": "Konto erstellen", "en": "Create account", "fr": "Créer le compte", "it": "Crea account", "pt": "Criar conta"},
    "register_have_account": {"de": "Schon ein Konto?", "en": "Already have an account?", "fr": "Déjà un compte ?", "it": "Hai già un account?", "pt": "Já tem uma conta?"},
    "register_error_duplicate": {"de": "Es gibt bereits ein Konto mit dieser E-Mail.", "en": "An account with this email already exists.", "fr": "Un compte avec cet e-mail existe déjà.", "it": "Esiste già un account con questa email.", "pt": "Já existe uma conta com este e-mail."},
    "register_error_invalid_category": {"de": "Bitte wählen Sie eine gültige Kategorie.", "en": "Please choose a valid category.", "fr": "Veuillez choisir une catégorie valide.", "it": "Scegli una categoria valida.", "pt": "Escolha uma categoria válida."},
    "register_error_invalid_country": {"de": "Bitte wählen Sie ein gültiges Land.", "en": "Please choose a valid country.", "fr": "Veuillez choisir un pays valide.", "it": "Scegli un paese valido.", "pt": "Escolha um país válido."},
    "register_error_missing_location": {"de": "Bitte geben Sie Bundesland/Kanton und Stadt an.", "en": "Please provide your state/canton and city.", "fr": "Veuillez indiquer votre région/canton et votre ville.", "it": "Indica regione/cantone e città.", "pt": "Informe seu estado/cantão e cidade."},
    "register_error_invalid_email": {"de": "Bitte gib eine gültige E-Mail-Adresse ein.", "en": "Please enter a valid email address.", "fr": "Veuillez saisir une adresse e-mail valide.", "it": "Inserisci un indirizzo e-mail valido.", "pt": "Informe um endereço de e-mail válido."},
    "register_error_invalid_name": {"de": "Bitte gib deinen Namen ein (höchstens 150 Zeichen).", "en": "Please enter your name (up to 150 characters).", "fr": "Veuillez saisir votre nom (150 caractères maximum).", "it": "Inserisci il tuo nome (massimo 150 caratteri).", "pt": "Informe seu nome (até 150 caracteres)."},
    "register_error_too_many_tags": {
        "de": "Maximal 10 Komponisten-Hashtags erlaubt.",
        "en": "A maximum of 10 composer hashtags is allowed.",
        "fr": "Un maximum de 10 hashtags de compositeurs est autorisé.",
        "it": "Sono ammessi al massimo 10 hashtag di compositori.",
        "pt": "É permitido no máximo 10 hashtags de compositores.",
    },
    "register_error_rate_limited": {
        "de": "Zu viele neue Konten von dieser Internetverbindung in kurzer Zeit. Bitte versuchen Sie es in etwas später erneut.",
        "en": "Too many new accounts from this network in a short time. Please try again a bit later.",
        "fr": "Trop de nouveaux comptes créés depuis cette connexion en peu de temps. Réessayez un peu plus tard.",
        "it": "Troppi nuovi account creati da questa rete in poco tempo. Riprova più tardi.",
        "pt": "Muitas contas novas criadas por esta conexão em pouco tempo. Tente novamente mais tarde.",
    },
    "password_rules_hint": {
        "de": "Mindestens 6 Zeichen, mit 1 Buchstaben, 1 Zahl und 1 Sonderzeichen (z. B. ! @ # $ % & *).",
        "en": "At least 6 characters, with 1 letter, 1 number and 1 special character (e.g. ! @ # $ % & *).",
        "fr": "Au moins 6 caractères, avec 1 lettre, 1 chiffre et 1 caractère spécial (ex. ! @ # $ % & *).",
        "it": "Almeno 6 caratteri, con 1 lettera, 1 numero e 1 carattere speciale (es. ! @ # $ % & *).",
        "pt": "No mínimo 6 caracteres, com 1 letra, 1 número e 1 caractere especial (ex.: ! @ # $ % & *).",
    },
    "password_error_length": {"de": "Das Passwort braucht mindestens 6 Zeichen.", "en": "The password must be at least 6 characters long.", "fr": "Le mot de passe doit comporter au moins 6 caractères.", "it": "La password deve avere almeno 6 caratteri.", "pt": "A senha precisa ter no mínimo 6 caracteres."},
    "password_error_letter": {"de": "Das Passwort braucht mindestens 1 Buchstaben.", "en": "The password must contain at least 1 letter.", "fr": "Le mot de passe doit contenir au moins 1 lettre.", "it": "La password deve contenere almeno 1 lettera.", "pt": "A senha precisa ter pelo menos 1 letra."},
    "password_error_digit": {"de": "Das Passwort braucht mindestens 1 Zahl.", "en": "The password must contain at least 1 number.", "fr": "Le mot de passe doit contenir au moins 1 chiffre.", "it": "La password deve contenere almeno 1 numero.", "pt": "A senha precisa ter pelo menos 1 número."},
    "password_error_special": {
        "de": "Das Passwort braucht mindestens 1 Sonderzeichen (z. B. ! @ # $ % & *).",
        "en": "The password must contain at least 1 special character (e.g. ! @ # $ % & *).",
        "fr": "Le mot de passe doit contenir au moins 1 caractère spécial (ex. ! @ # $ % & *).",
        "it": "La password deve contenere almeno 1 carattere speciale (es. ! @ # $ % & *).",
        "pt": "A senha precisa ter pelo menos 1 caractere especial (ex.: ! @ # $ % & *).",
    },

    # --- my listings -------------------------------------------------------------
    "my_listings_title": {"de": "Meine Anzeigen", "en": "My listings", "fr": "Mes annonces", "it": "I miei annunci", "pt": "Meus anúncios"},
    "my_listings_empty": {"de": "Sie haben noch keine Anzeige veröffentlicht.", "en": "You haven't posted any listings yet.", "fr": "Vous n'avez encore publié aucune annonce.", "it": "Non hai ancora pubblicato annunci.", "pt": "Você ainda não publicou nenhum anúncio."},
    "my_listings_publish_first": {"de": "Erste Anzeige veröffentlichen", "en": "Publish your first listing", "fr": "Publier votre première annonce", "it": "Pubblica il tuo primo annuncio", "pt": "Publicar seu primeiro anúncio"},
    "inactive_label": {"de": "inaktiv", "en": "inactive", "fr": "inactive", "it": "inattivo", "pt": "inativo"},
    "listing_candidates_link": {"de": "Bewerbungen", "en": "Candidates", "fr": "Candidatures", "it": "Candidature", "pt": "Candidaturas"},

    # --- P3.B: candidaturas, convites, aceitar/recusar ---------------------
    "invitation_apply_button": {"de": "Bewerben", "en": "Apply", "fr": "Postuler", "it": "Candidati", "pt": "Candidatar-se"},
    "invitation_applied_success": {"de": "Bewerbung gesendet!", "en": "Application sent!", "fr": "Candidature envoyée !", "it": "Candidatura inviata!", "pt": "Candidatura enviada!"},
    "invitation_status_pending": {"de": "Ausstehend", "en": "Pending", "fr": "En attente", "it": "In attesa", "pt": "Pendente"},
    "invitation_status_accepted": {"de": "Angenommen", "en": "Accepted", "fr": "Acceptée", "it": "Accettata", "pt": "Aceita"},
    "invitation_status_declined": {"de": "Abgelehnt", "en": "Declined", "fr": "Refusée", "it": "Rifiutata", "pt": "Recusada"},
    "invitation_status_expired": {"de": "Abgelaufen", "en": "Expired", "fr": "Expirée", "it": "Scaduta", "pt": "Expirada"},
    "invitation_invite_button": {"de": "Zu einer Vakanz einladen", "en": "Invite to a vacancy", "fr": "Inviter à un poste", "it": "Invita a un posto", "pt": "Convidar para uma vaga"},
    "invitation_choose_vacancy_label": {"de": "Anzeige und Vakanz auswählen", "en": "Choose a listing and vacancy", "fr": "Choisir une annonce et un poste", "it": "Scegli un annuncio e un posto", "pt": "Escolha o anúncio e a vaga"},
    "invitation_invite_confirm": {"de": "Einladung senden", "en": "Send invitation", "fr": "Envoyer l'invitation", "it": "Invia l'invito", "pt": "Enviar convite"},
    "invitation_invited_success": {"de": "Einladung gesendet!", "en": "Invitation sent!", "fr": "Invitation envoyée !", "it": "Invito inviato!", "pt": "Convite enviado!"},
    "invitation_accept_button": {"de": "Annehmen", "en": "Accept", "fr": "Accepter", "it": "Accetta", "pt": "Aceitar"},
    "invitation_decline_button": {"de": "Ablehnen", "en": "Decline", "fr": "Refuser", "it": "Rifiuta", "pt": "Recusar"},
    "invitation_responded_accepted": {"de": "Angenommen — es wurde ein Match erstellt!", "en": "Accepted — a Match was created!", "fr": "Acceptée — un Match a été créé !", "it": "Accettata — è stato creato un Match!", "pt": "Aceita — um Match foi criado!"},
    "invitation_responded_declined": {"de": "Abgelehnt.", "en": "Declined.", "fr": "Refusée.", "it": "Rifiutata.", "pt": "Recusada."},
    "invitation_from_label": {"de": "von", "en": "from", "fr": "de", "it": "da", "pt": "de"},
    "invitation_applied_for_label": {"de": "hat sich beworben für", "en": "applied for", "fr": "a postulé pour", "it": "si è candidato/a per", "pt": "se candidatou para"},
    "invitation_invited_to_label": {"de": "eingeladen zu", "en": "invited to", "fr": "invité(e) à", "it": "invitato/a a", "pt": "convidado(a) para"},
    "invitation_error_vacancy_closed": {"de": "Diese Vakanz ist nicht mehr verfügbar.", "en": "This vacancy is no longer available.", "fr": "Ce poste n'est plus disponible.", "it": "Questo posto non è più disponibile.", "pt": "Essa vaga não está mais disponível."},
    "invitation_error_vacancy_full": {"de": "Diese Vakanz ist bereits vollständig besetzt.", "en": "This vacancy is already fully filled.", "fr": "Ce poste est déjà entièrement pourvu.", "it": "Questo posto è già completamente occupato.", "pt": "Essa vaga já foi totalmente preenchida."},
    "invitation_error_own_listing": {"de": "Sie können sich nicht auf Ihre eigene Anzeige bewerben.", "en": "You can't apply to your own listing.", "fr": "Vous ne pouvez pas postuler à votre propre annonce.", "it": "Non puoi candidarti al tuo stesso annuncio.", "pt": "Você não pode se candidatar ao seu próprio anúncio."},
    "invitation_error_not_allowed": {"de": "Diese Aktion ist nicht erlaubt.", "en": "This action isn't allowed.", "fr": "Cette action n'est pas autorisée.", "it": "Questa azione non è consentita.", "pt": "Essa ação não é permitida."},
    "invitation_error_already_pending": {"de": "Sie haben sich bereits für diese Vakanz beworben oder wurden bereits eingeladen.", "en": "You've already applied to (or been invited to) this vacancy.", "fr": "Vous avez déjà postulé à ce poste (ou avez déjà été invité(e)).", "it": "Ti sei già candidato/a (o sei già stato/a invitato/a) a questo posto.", "pt": "Você já se candidatou (ou já foi convidado) para essa vaga."},
    "invitation_error_too_many_pending": {"de": "Sie haben zu viele ausstehende Bewerbungen/Einladungen. Bitte warten Sie, bis einige beantwortet wurden.", "en": "You have too many pending applications/invitations. Please wait until some are answered.", "fr": "Vous avez trop de candidatures/invitations en attente. Veuillez attendre que certaines soient répondues.", "it": "Hai troppe candidature/inviti in sospeso. Attendi che alcuni vengano gestiti.", "pt": "Você tem candidaturas/convites pendentes demais. Aguarde até que alguns sejam respondidos."},
    "invitation_error_not_found": {"de": "Diese Einladung existiert nicht mehr oder ist abgelaufen.", "en": "This invitation no longer exists or has expired.", "fr": "Cette invitation n'existe plus ou a expiré.", "it": "Questo invito non esiste più o è scaduto.", "pt": "Esse convite não existe mais ou expirou."},
    "invitation_error_not_yours": {"de": "Sie sind nicht berechtigt, auf diese Einladung zu antworten.", "en": "You're not allowed to respond to this invitation.", "fr": "Vous n'êtes pas autorisé(e) à répondre à cette invitation.", "it": "Non sei autorizzato/a a rispondere a questo invito.", "pt": "Você não tem permissão para responder a esse convite."},
    "invitations_none": {"de": "Nichts hier.", "en": "Nothing here.", "fr": "Rien ici.", "it": "Niente qui.", "pt": "Nada por aqui."},
    "invitations_received_title": {"de": "Erhaltene Einladungen", "en": "Invitations received", "fr": "Invitations reçues", "it": "Inviti ricevuti", "pt": "Convites recebidos"},
    "invitations_applications_received_title": {"de": "Erhaltene Bewerbungen", "en": "Applications received", "fr": "Candidatures reçues", "it": "Candidature ricevute", "pt": "Candidaturas recebidas"},
    "invitations_applications_sent_title": {"de": "Gesendete Bewerbungen", "en": "Applications sent", "fr": "Candidatures envoyées", "it": "Candidature inviate", "pt": "Candidaturas enviadas"},
    "invitations_sent_title": {"de": "Gesendete Einladungen", "en": "Invitations sent", "fr": "Invitations envoyées", "it": "Inviti inviati", "pt": "Convites enviados"},
    "listing_candidates_title": {"de": "Bewerbungen & Einladungen", "en": "Candidates & invitations", "fr": "Candidatures et invitations", "it": "Candidature e inviti", "pt": "Candidaturas e convites"},
    "listing_candidates_applications_title": {"de": "Bewerbungen", "en": "Applications", "fr": "Candidatures", "it": "Candidature", "pt": "Candidaturas"},
    "listing_candidates_applications_help": {"de": "Personen, die sich selbst auf eine Vakanz dieser Anzeige beworben haben.", "en": "People who applied on their own to a vacancy on this listing.", "fr": "Personnes qui ont postulé d'elles-mêmes à un poste de cette annonce.", "it": "Persone che si sono candidate autonomamente a un posto di questo annuncio.", "pt": "Pessoas que se candidataram por conta própria a uma vaga deste anúncio."},
    "listing_candidates_invites_title": {"de": "Gesendete Einladungen", "en": "Invitations sent", "fr": "Invitations envoyées", "it": "Inviti inviati", "pt": "Convites enviados"},
    "listing_candidates_invites_help": {"de": "Personen, die Sie direkt zu einer Vakanz dieser Anzeige eingeladen haben.", "en": "People you invited directly to a vacancy on this listing.", "fr": "Personnes que vous avez invitées directement à un poste de cette annonce.", "it": "Persone che hai invitato direttamente a un posto di questo annuncio.", "pt": "Pessoas que você convidou diretamente para uma vaga deste anúncio."},

    # --- profile (own / public) -------------------------------------------------
    "profile_title": {"de": "Mein Profil", "en": "My profile", "fr": "Mon profil", "it": "Il mio profilo", "pt": "Meu perfil"},
    "profile_phone_card": {"de": "Telefon", "en": "Phone", "fr": "Téléphone", "it": "Telefono", "pt": "Telefone"},
    "profile_phone_help": {"de": "Wird nie öffentlich angezeigt, außer du erlaubst es unten — bei einem bestätigten Match wird die Nummer aber immer geteilt.", "en": "Never shown publicly unless you allow it below — it's always shared with a confirmed Match, regardless of that setting.", "fr": "Jamais affiché publiquement sauf si vous l'autorisez ci-dessous — il est toujours partagé avec un Match confirmé, quel que soit ce réglage.", "it": "Non viene mai mostrato pubblicamente a meno che tu non lo consenta qui sotto — viene comunque sempre condiviso con un Match confermato.", "pt": "Nunca aparece publicamente a menos que você permita abaixo — mas é sempre compartilhado com um Match confirmado, independente dessa escolha."},
    "profile_phone_label": {"de": "Telefonnummer", "en": "Phone number", "fr": "Numéro de téléphone", "it": "Numero di telefono", "pt": "Número de telefone"},
    "profile_phone_visibility_label": {"de": "Telefonnummer auf meinem öffentlichen Profil anzeigen", "en": "Show my phone number on my public profile", "fr": "Afficher mon numéro de téléphone sur mon profil public", "it": "Mostra il mio numero di telefono sul mio profilo pubblico", "pt": "Mostrar meu telefone no meu perfil público"},
    "profile_phone_visibility_help": {"de": "Optional — unabhängig davon siehst du die Nummer deines Gegenübers immer, sobald ein Match bestätigt ist.", "en": "Optional — separately, you'll always see your counterpart's number once a Match is confirmed.", "fr": "Facultatif — indépendamment, vous verrez toujours le numéro de votre interlocuteur dès qu'un Match est confirmé.", "it": "Facoltativo — a parte questo, vedrai sempre il numero della controparte non appena un Match è confermato.", "pt": "Opcional — separadamente, você sempre verá o telefone da outra pessoa assim que um Match for confirmado."},
    "profile_voice_type_label": {"de": "Stimmlage", "en": "Voice type", "fr": "Tessiture", "it": "Tessitura", "pt": "Tipo de voz"},
    "profile_extra_voice_types_label": {"de": "Weitere Stimmlagen", "en": "Additional voice types", "fr": "Autres tessitures", "it": "Altre tessiture", "pt": "Outras tessituras"},
    "profile_extra_voice_types_help": {"de": "Wähle alle weiteren Stimmlagen, die du auch singst (zusätzlich zur Hauptstimmlage oben).", "en": "Select any other voice types you also sing (in addition to the primary voice type above).", "fr": "Sélectionnez les autres tessitures que vous chantez également (en plus de la tessiture principale ci-dessus).", "it": "Seleziona le altre tessiture che canti anche tu (oltre alla tessitura principale sopra).", "pt": "Selecione outras tessituras que você também canta (além da tessitura principal acima)."},
    "profile_spoken_languages_card": {"de": "Gesprochene Sprachen", "en": "Spoken languages", "fr": "Langues parlées", "it": "Lingue parlate", "pt": "Idiomas falados"},
    "profile_spoken_languages_help": {"de": "Wähle bis zu 4 Sprachen, die du sprichst.", "en": "Select up to 4 languages you speak.", "fr": "Sélectionnez jusqu'à 4 langues que vous parlez.", "it": "Seleziona fino a 4 lingue che parli.", "pt": "Selecione até 4 idiomas que você fala."},
    "profile_spoken_languages_remove_help": {"de": "Um eine Sprache zu entfernen, setze das jeweilige Feld zurück auf \"—\".", "en": "To remove a language, set that field back to \"—\".", "fr": "Pour supprimer une langue, remettez ce champ sur « — ».", "it": "Per rimuovere una lingua, riporta quel campo su \"—\".", "pt": "Para remover um idioma, deixe o campo de volta em \"—\"."},
    "spoken_language_none": {"de": "—", "en": "—", "fr": "—", "it": "—", "pt": "—"},
    "spoken_language_other": {"de": "Andere", "en": "Other", "fr": "Autre", "it": "Altra", "pt": "Outra"},
    "spoken_language_other_placeholder": {"de": "Sprache eingeben", "en": "Type a language", "fr": "Saisir une langue", "it": "Inserisci una lingua", "pt": "Digite um idioma"},
    "profile_bio_label": {"de": "Biografie", "en": "Biography", "fr": "Biographie", "it": "Biografia", "pt": "Biografia"},
    "profile_hashtags_label": {"de": "Komponisten", "en": "Composers", "fr": "Compositeurs", "it": "Compositori", "pt": "Compositores"},
    "profile_ensemble_label": {"de": "Chor/Orchester", "en": "Choir/orchestra", "fr": "Chœur/orchestre", "it": "Coro/orchestra", "pt": "Coral/orquestra"},
    "profile_save": {"de": "Speichern", "en": "Save", "fr": "Enregistrer", "it": "Salva", "pt": "Salvar"},
    "profile_saved": {"de": "Profil aktualisiert.", "en": "Profile updated.", "fr": "Profil mis à jour.", "it": "Profilo aggiornato.", "pt": "Perfil atualizado."},
    "public_profile_active_listings": {"de": "Aktive Anzeigen", "en": "Active listings", "fr": "Annonces actives", "it": "Annunci attivi", "pt": "Anúncios ativos"},
    "public_profile_none": {"de": "Keine aktiven Anzeigen.", "en": "No active listings.", "fr": "Aucune annonce active.", "it": "Nessun annuncio attivo.", "pt": "Nenhum anúncio ativo."},
    "no_bio": {"de": "Noch keine Biografie.", "en": "No biography yet.", "fr": "Pas encore de biographie.", "it": "Nessuna biografia ancora.", "pt": "Ainda sem biografia."},

    # --- audiobeispiele (links) ------------------------------------------------
    "audio_links_label": {"de": "Audiobeispiele (Links, bis zu 3)", "en": "Audio samples (links, up to 3)", "fr": "Extraits audio (liens, jusqu'à 3)", "it": "Esempi audio (link, fino a 3)", "pt": "Amostras de áudio (links, até 3)"},
    "audio_links_help": {
        "de": "Link zu YouTube, SoundCloud o.Ä. — einer pro Zeile oder durch Komma getrennt.",
        "en": "Link to YouTube, SoundCloud, etc. — one per line or comma-separated.",
        "fr": "Lien vers YouTube, SoundCloud, etc. — un par ligne ou séparés par des virgules.",
        "it": "Link a YouTube, SoundCloud, ecc. — uno per riga o separati da virgola.",
        "pt": "Link para YouTube, SoundCloud etc. — um por linha ou separados por vírgula.",
    },
    "audio_links_title": {"de": "Hörbeispiele", "en": "Listen", "fr": "Écouter", "it": "Ascolta", "pt": "Ouvir"},
    "audio_link_play": {"de": "▶ Anhören", "en": "▶ Listen", "fr": "▶ Écouter", "it": "▶ Ascolta", "pt": "▶ Ouvir"},

    # --- e-mail verification --------------------------------------------------
    "verify_banner_text": {
        "de": "Bitte bestätige deine E-Mail-Adresse, um Anzeigen zu veröffentlichen und Nachrichten zu senden.",
        "en": "Please verify your email address to post listings and send messages.",
        "fr": "Veuillez vérifier votre adresse e-mail pour publier des annonces et envoyer des messages.",
        "it": "Verifica il tuo indirizzo email per pubblicare annunci e inviare messaggi.",
        "pt": "Confirme seu e-mail para publicar anúncios e enviar mensagens.",
    },
    "verify_banner_resend": {"de": "E-Mail erneut senden", "en": "Resend email", "fr": "Renvoyer l'e-mail", "it": "Invia di nuovo l'email", "pt": "Reenviar e-mail"},
    "verify_success_title": {"de": "E-Mail bestätigt", "en": "Email verified", "fr": "E-mail vérifié", "it": "Email verificata", "pt": "E-mail confirmado"},
    "verify_success_message": {
        "de": "Deine E-Mail-Adresse wurde bestätigt. Du kannst jetzt Anzeigen veröffentlichen und Nachrichten senden.",
        "en": "Your email address has been verified. You can now post listings and send messages.",
        "fr": "Votre adresse e-mail a été vérifiée. Vous pouvez désormais publier des annonces et envoyer des messages.",
        "it": "Il tuo indirizzo email è stato verificato. Ora puoi pubblicare annunci e inviare messaggi.",
        "pt": "Seu e-mail foi confirmado. Agora você pode publicar anúncios e enviar mensagens.",
    },
    "verify_invalid_title": {"de": "Link ungültig", "en": "Invalid link", "fr": "Lien invalide", "it": "Link non valido", "pt": "Link inválido"},
    "verify_invalid_message": {
        "de": "Dieser Bestätigungslink ist ungültig oder abgelaufen.",
        "en": "This verification link is invalid or has expired.",
        "fr": "Ce lien de vérification est invalide ou a expiré.",
        "it": "Questo link di verifica non è valido o è scaduto.",
        "pt": "Este link de confirmação é inválido ou expirou.",
    },
    "verify_required_banner": {
        "de": "Bitte bestätige zuerst deine E-Mail-Adresse, bevor du das machst.",
        "en": "Please verify your email address before doing that.",
        "fr": "Veuillez d'abord vérifier votre adresse e-mail avant de faire cela.",
        "it": "Verifica prima il tuo indirizzo email prima di farlo.",
        "pt": "Confirme seu e-mail antes de fazer isso.",
    },

    # --- esqueci/redefinir senha --------------------------------------------------
    "forgot_password_title": {"de": "Passwort vergessen?", "en": "Forgot password?", "fr": "Mot de passe oublié ?", "it": "Password dimenticata?", "pt": "Esqueceu a senha?"},
    "forgot_password_email_label": {"de": "E-Mail", "en": "Email", "fr": "E-mail", "it": "Email", "pt": "E-mail"},
    "forgot_password_submit": {"de": "Link zum Zurücksetzen senden", "en": "Send reset link", "fr": "Envoyer le lien de réinitialisation", "it": "Invia link di reimpostazione", "pt": "Enviar link de redefinição"},
    "forgot_password_sent_title": {"de": "E-Mail unterwegs", "en": "Email on its way", "fr": "E-mail envoyé", "it": "Email in arrivo", "pt": "E-mail a caminho"},
    "forgot_password_sent_message": {
        "de": "Falls diese E-Mail-Adresse registriert ist, haben wir einen Link zum Zurücksetzen des Passworts gesendet.",
        "en": "If this email address is registered, we've sent a password reset link.",
        "fr": "Si cette adresse e-mail est enregistrée, nous avons envoyé un lien de réinitialisation du mot de passe.",
        "it": "Se questo indirizzo email è registrato, abbiamo inviato un link per reimpostare la password.",
        "pt": "Se este e-mail estiver cadastrado, enviamos um link para redefinir a senha.",
    },
    "reset_password_title": {"de": "Neues Passwort festlegen", "en": "Set a new password", "fr": "Définir un nouveau mot de passe", "it": "Imposta una nuova password", "pt": "Definir nova senha"},
    "reset_password_new_password_label": {"de": "Neues Passwort", "en": "New password", "fr": "Nouveau mot de passe", "it": "Nuova password", "pt": "Nova senha"},
    "reset_password_submit": {"de": "Passwort speichern", "en": "Save password", "fr": "Enregistrer le mot de passe", "it": "Salva password", "pt": "Salvar senha"},
    "reset_password_success_title": {"de": "Passwort geändert", "en": "Password changed", "fr": "Mot de passe modifié", "it": "Password modificata", "pt": "Senha alterada"},
    "reset_password_success_message": {
        "de": "Dein Passwort wurde geändert. Du kannst dich jetzt anmelden.",
        "en": "Your password has been changed. You can now log in.",
        "fr": "Votre mot de passe a été modifié. Vous pouvez maintenant vous connecter.",
        "it": "La tua password è stata modificata. Ora puoi accedere.",
        "pt": "Sua senha foi alterada. Agora você pode entrar.",
    },
    "reset_password_invalid_title": {"de": "Link ungültig", "en": "Invalid link", "fr": "Lien invalide", "it": "Link non valido", "pt": "Link inválido"},
    "reset_password_invalid_message": {
        "de": "Dieser Link ist ungültig oder abgelaufen. Fordere einen neuen an.",
        "en": "This link is invalid or has expired. Please request a new one.",
        "fr": "Ce lien est invalide ou a expiré. Demandez-en un nouveau.",
        "it": "Questo link non è valido o è scaduto. Richiedine uno nuovo.",
        "pt": "Este link é inválido ou expirou. Solicite um novo.",
    },
    "login_forgot_password_link": {"de": "Passwort vergessen?", "en": "Forgot password?", "fr": "Mot de passe oublié ?", "it": "Password dimenticata?", "pt": "Esqueceu a senha?"},
    "back_to_login": {"de": "Zurück zum Login", "en": "Back to login", "fr": "Retour à la connexion", "it": "Torna al login", "pt": "Voltar ao login"},

    # --- error pages (404 / generic error / 500) -------------------------
    "error_404_title": {"de": "Seite nicht gefunden", "en": "Page not found", "fr": "Page introuvable", "it": "Pagina non trovata", "pt": "Página não encontrada"},
    "error_404_message": {
        "de": "Diese Seite existiert nicht (mehr), oder der Link ist falsch.",
        "en": "This page doesn't exist (anymore), or the link is wrong.",
        "fr": "Cette page n'existe pas (plus), ou le lien est incorrect.",
        "it": "Questa pagina non esiste (più), oppure il link è sbagliato.",
        "pt": "Esta página não existe (mais), ou o link está errado.",
    },
    "error_generic_title": {"de": "Etwas ist schiefgelaufen", "en": "Something went wrong", "fr": "Une erreur s'est produite", "it": "Qualcosa è andato storto", "pt": "Algo deu errado"},
    "error_generic_message": {
        "de": "Die Anfrage konnte nicht bearbeitet werden (Fehler {status}).",
        "en": "The request couldn't be processed (error {status}).",
        "fr": "La demande n'a pas pu être traitée (erreur {status}).",
        "it": "Non è stato possibile elaborare la richiesta (errore {status}).",
        "pt": "Não foi possível processar a solicitação (erro {status}).",
    },
    "error_500_title": {"de": "Etwas ist schiefgelaufen", "en": "Something went wrong", "fr": "Une erreur s'est produite", "it": "Qualcosa è andato storto", "pt": "Algo deu errado"},
    "error_500_message": {
        "de": "Ein unerwarteter Fehler ist aufgetreten. Wir wurden benachrichtigt — bitte versuchen Sie es später erneut.",
        "en": "An unexpected error occurred. We've been notified — please try again later.",
        "fr": "Une erreur inattendue s'est produite. Nous avons été notifiés — veuillez réessayer plus tard.",
        "it": "Si è verificato un errore imprevisto. Siamo stati avvisati — riprova più tardi.",
        "pt": "Ocorreu um erro inesperado. Já fomos notificados — tente novamente mais tarde.",
    },
    "error_back_home": {"de": "Zurück zur Startseite", "en": "Back to the homepage", "fr": "Retour à l'accueil", "it": "Torna alla home", "pt": "Voltar à página inicial"},

    # --- indicador de data (bolinha colorida) --------------------------------------
    "event_status_upcoming": {"de": "Termin in der Zukunft", "en": "Upcoming event", "fr": "Événement à venir", "it": "Evento futuro", "pt": "Evento futuro"},
    "event_status_soon": {"de": "Termin diese Woche", "en": "Happening this week", "fr": "Cette semaine", "it": "Questa settimana", "pt": "Nesta semana"},
    "event_status_past": {"de": "Termin bereits vorbei", "en": "Event already passed", "fr": "Événement déjà passé", "it": "Evento già passato", "pt": "Evento já ocorreu"},

    # --- mensagens internas -------------------------------------------------------
    "nav_messages": {"de": "Nachrichten", "en": "Messages", "fr": "Messages", "it": "Messaggi", "pt": "Mensagens"},
    # /invitations tab filter (19/09/2026, task #51 menu reorg) — the
    # side-nav's "Matches" group links straight into one of these two
    # via ?tab=, and the same toggle appears at the top of the page
    # itself so it's not a dead-end once you're there.
    "invitations_tab_all": {"de": "Alle", "en": "All", "fr": "Tous", "it": "Tutti", "pt": "Todos"},
    "invitations_tab_pending": {"de": "Ausstehend", "en": "Pending", "fr": "En attente", "it": "In sospeso", "pt": "Pendentes"},
    "invitations_tab_history": {"de": "Verlauf", "en": "History", "fr": "Historique", "it": "Cronologia", "pt": "Histórico"},
    # Renamed (19/09/2026, task #51 menu reorg — Daniel's own sketch
    # labels this "Matches (Job Invitations)"): kept as the international
    # loanword "Match(es)", same convention already used everywhere else
    # on the site (nav_match_history, mascot_reminder_evaluation, etc.)
    # rather than translating it per language.
    "nav_invitations": {"de": "Matches", "en": "Matches", "fr": "Matches", "it": "Match", "pt": "Matches"},
    # Messenger (2026-09-26, docs/specs/MESSENGER.md).
    "messenger_title": {"de": "Nachrichten", "en": "Messages", "fr": "Messages", "it": "Messaggi", "pt": "Mensagens"},
    "messenger_tab_requests": {"de": "Anfragen", "en": "Requests", "fr": "Demandes", "it": "Richieste", "pt": "Solicitações"},
    "messenger_filter_all": {"de": "Alle", "en": "All", "fr": "Toutes", "it": "Tutte", "pt": "Todas"},
    "messenger_filter_unread": {"de": "Ungelesen", "en": "Unread", "fr": "Non lues", "it": "Non lette", "pt": "Não lidas"},
    "messenger_empty_inbox": {"de": "Noch keine Unterhaltungen.", "en": "No conversations yet.", "fr": "Aucune conversation pour l'instant.", "it": "Ancora nessuna conversazione.", "pt": "Nenhuma conversa ainda."},
    "messenger_empty_requests": {"de": "Keine offenen Anfragen.", "en": "No pending requests.", "fr": "Aucune demande en attente.", "it": "Nessuna richiesta in sospeso.", "pt": "Nenhuma solicitação pendente."},
    "messenger_select_conversation": {"de": "Wähle links eine Unterhaltung aus.", "en": "Pick a conversation on the left.", "fr": "Choisissez une conversation à gauche.", "it": "Scegli una conversazione a sinistra.", "pt": "Escolha uma conversa à esquerda."},
    "messenger_request_banner": {"de": "{name} möchte dir schreiben. Wenn du annimmst, landet der Chat in deinem Posteingang.", "en": "{name} wants to message you. If you accept, the chat moves to your inbox.", "fr": "{name} souhaite vous écrire. Si vous acceptez, le chat passe dans votre boîte de réception.", "it": "{name} vuole scriverti. Se accetti, la chat passa nella tua posta in arrivo.", "pt": "{name} quer falar com você. Se aceitar, o chat vai para sua caixa de entrada."},
    "messenger_accept": {"de": "Annehmen", "en": "Accept", "fr": "Accepter", "it": "Accetta", "pt": "Aceitar"},
    "messenger_decline": {"de": "Ablehnen", "en": "Decline", "fr": "Refuser", "it": "Rifiuta", "pt": "Recusar"},
    "messenger_pending_mine": {"de": "Deine Anfrage wartet darauf, dass {name} sie annimmt. Bis dahin kannst du keine weitere Nachricht senden.", "en": "Your request is waiting for {name} to accept it. Until then you can't send another message.", "fr": "Votre demande attend que {name} l'accepte. D'ici là, vous ne pouvez pas envoyer d'autre message.", "it": "La tua richiesta attende che {name} la accetti. Fino ad allora non puoi inviare altri messaggi.", "pt": "Sua solicitação aguarda {name} aceitar. Até lá você não pode enviar outra mensagem."},
    "messenger_request_label": {"de": "Anfrage", "en": "Request", "fr": "Demande", "it": "Richiesta", "pt": "Solicitação"},
    "messenger_pending_label": {"de": "wartet", "en": "waiting", "fr": "en attente", "it": "in attesa", "pt": "aguardando"},
    "messenger_hide": {"de": "Ausblenden", "en": "Hide", "fr": "Masquer", "it": "Nascondi", "pt": "Ocultar"},
    "messenger_block": {"de": "Blockieren", "en": "Block", "fr": "Bloquer", "it": "Blocca", "pt": "Bloquear"},
    "messenger_report": {"de": "Melden", "en": "Report", "fr": "Signaler", "it": "Segnala", "pt": "Denunciar"},
    "messenger_report_reason_label": {"de": "Was ist das Problem?", "en": "What's the problem?", "fr": "Quel est le problème ?", "it": "Qual è il problema?", "pt": "Qual é o problema?"},
    "messenger_report_submit": {"de": "Meldung senden", "en": "Send report", "fr": "Envoyer le signalement", "it": "Invia segnalazione", "pt": "Enviar denúncia"},
    "messenger_notice_report_reported": {"de": "Danke — die Nachricht wurde an die Moderation gemeldet.", "en": "Thanks — the message was reported to moderation.", "fr": "Merci — le message a été signalé à la modération.", "it": "Grazie — il messaggio è stato segnalato alla moderazione.", "pt": "Obrigado — a mensagem foi denunciada à moderação."},
    "messenger_notice_report_already": {"de": "Du hast diese Nachricht bereits gemeldet.", "en": "You already reported this message.", "fr": "Vous avez déjà signalé ce message.", "it": "Hai già segnalato questo messaggio.", "pt": "Você já denunciou esta mensagem."},
    "messenger_notice_report_invalid": {"de": "Bitte beschreibe kurz das Problem.", "en": "Please describe the problem briefly.", "fr": "Veuillez décrire brièvement le problème.", "it": "Descrivi brevemente il problema.", "pt": "Descreva o problema brevemente."},
    "messenger_notice_report_not_allowed": {"de": "Diese Nachricht kann nicht gemeldet werden.", "en": "This message can't be reported.", "fr": "Ce message ne peut pas être signalé.", "it": "Questo messaggio non può essere segnalato.", "pt": "Esta mensagem não pode ser denunciada."},
    "messenger_notice_request_pending": {"de": "Deine Anfrage wurde noch nicht angenommen — die Nachricht wurde nicht gesendet.", "en": "Your request hasn't been accepted yet — the message wasn't sent.", "fr": "Votre demande n'a pas encore été acceptée — le message n'a pas été envoyé.", "it": "La tua richiesta non è ancora stata accettata — il messaggio non è stato inviato.", "pt": "Sua solicitação ainda não foi aceita — a mensagem não foi enviada."},
    "messenger_composer_placeholder": {"de": "Nachricht schreiben…", "en": "Write a message…", "fr": "Écrire un message…", "it": "Scrivi un messaggio…", "pt": "Escreva uma mensagem…"},
    "messenger_deactivated_user": {"de": "Deaktiviertes Konto", "en": "Deactivated account", "fr": "Compte désactivé", "it": "Account disattivato", "pt": "Conta desativada"},
    "messenger_back": {"de": "Alle Unterhaltungen", "en": "All conversations", "fr": "Toutes les conversations", "it": "Tutte le conversazioni", "pt": "Todas as conversas"},
    "messenger_you": {"de": "Du", "en": "You", "fr": "Vous", "it": "Tu", "pt": "Você"},
    "messenger_minimize": {"de": "Minimieren", "en": "Minimize", "fr": "Réduire", "it": "Riduci", "pt": "Minimizar"},
    "messenger_close": {"de": "Schließen", "en": "Close", "fr": "Fermer", "it": "Chiudi", "pt": "Fechar"},
    "messenger_open_full": {"de": "Vollständigen Chat öffnen", "en": "Open full chat", "fr": "Ouvrir le chat complet", "it": "Apri la chat completa", "pt": "Abrir chat completo"},
    "messenger_new_message_from": {"de": "Neue Nachricht von {name}", "en": "New message from {name}", "fr": "Nouveau message de {name}", "it": "Nuovo messaggio da {name}", "pt": "Nova mensagem de {name}"},
    "messenger_window_error": {"de": "Nicht gesendet — öffne den vollständigen Chat.", "en": "Not sent — open the full chat.", "fr": "Non envoyé — ouvrez le chat complet.", "it": "Non inviato — apri la chat completa.", "pt": "Não enviada — abra o chat completo."},
    "messages_inbox_title": {"de": "Posteingang", "en": "Inbox", "fr": "Boîte de réception", "it": "Posta in arrivo", "pt": "Caixa de entrada"},
    "messages_sent_title": {"de": "Gesendet", "en": "Sent", "fr": "Envoyés", "it": "Inviati", "pt": "Enviadas"},
    "messages_trash_title": {"de": "Papierkorb", "en": "Trash", "fr": "Corbeille", "it": "Cestino", "pt": "Lixeira"},
    "messages_tab_inbox": {"de": "Posteingang", "en": "Inbox", "fr": "Boîte de réception", "it": "Posta in arrivo", "pt": "Caixa de entrada"},
    "messages_tab_sent": {"de": "Gesendet", "en": "Sent", "fr": "Envoyés", "it": "Inviati", "pt": "Enviadas"},
    "messages_tab_trash": {"de": "Papierkorb", "en": "Trash", "fr": "Corbeille", "it": "Cestino", "pt": "Lixeira"},
    "messages_empty_inbox": {"de": "Kein Posteingang bisher.", "en": "No messages yet.", "fr": "Aucun message pour l'instant.", "it": "Nessun messaggio finora.", "pt": "Nenhuma mensagem ainda."},
    "messages_empty_sent": {"de": "Noch nichts gesendet.", "en": "Nothing sent yet.", "fr": "Rien d'envoyé pour l'instant.", "it": "Ancora nulla di inviato.", "pt": "Nada enviado ainda."},
    "messages_empty_trash": {"de": "Papierkorb ist leer.", "en": "Trash is empty.", "fr": "La corbeille est vide.", "it": "Il cestino è vuoto.", "pt": "A lixeira está vazia."},
    "message_from": {"de": "von", "en": "from", "fr": "de", "it": "da", "pt": "de"},
    "message_to": {"de": "an", "en": "to", "fr": "à", "it": "a", "pt": "para"},
    "message_about_listing": {"de": "zu Anzeige", "en": "about listing", "fr": "à propos de l'annonce", "it": "riguardo all'annuncio", "pt": "sobre o anúncio"},
    "message_unread": {"de": "ungelesen", "en": "unread", "fr": "non lu", "it": "non letto", "pt": "não lida"},
    "message_trash_button": {"de": "In den Papierkorb", "en": "Move to trash", "fr": "Déplacer vers la corbeille", "it": "Sposta nel cestino", "pt": "Mover para a lixeira"},
    "message_restore_button": {"de": "Wiederherstellen", "en": "Restore", "fr": "Restaurer", "it": "Ripristina", "pt": "Restaurar"},
    "message_empty_trash_button": {"de": "Papierkorb leeren", "en": "Empty trash", "fr": "Vider la corbeille", "it": "Svuota cestino", "pt": "Esvaziar lixeira"},
    "message_empty_trash_confirm": {
        "de": "Papierkorb wirklich leeren? Das löscht die Nachrichten endgültig (auch für die andere Person).",
        "en": "Really empty the trash? This permanently deletes the messages (for the other person too).",
        "fr": "Vraiment vider la corbeille ? Cela supprime définitivement les messages (aussi pour l'autre personne).",
        "it": "Svuotare davvero il cestino? Questo elimina definitivamente i messaggi (anche per l'altra persona).",
        "pt": "Esvaziar mesmo a lixeira? Isso exclui as mensagens permanentemente (também para a outra pessoa).",
    },
    "message_compose_title": {"de": "Neue Nachricht", "en": "New message", "fr": "Nouveau message", "it": "Nuovo messaggio", "pt": "Nova mensagem"},
    "message_error_rate_limited": {
        "de": "Sie haben in der letzten Stunde schon viele Nachrichten verschickt. Bitte versuchen Sie es später erneut.",
        "en": "You've sent a lot of messages in the last hour. Please try again a bit later.",
        "fr": "Vous avez déjà envoyé beaucoup de messages au cours de la dernière heure. Réessayez un peu plus tard.",
        "it": "Hai già inviato molti messaggi nell'ultima ora. Riprova più tardi.",
        "pt": "Você já enviou muitas mensagens na última hora. Tente novamente mais tarde.",
    },
    "message_error_rate_limited_recipient": {
        "de": "Sie haben dieser Person in der letzten Stunde schon mehrmals geschrieben. Warten Sie kurz auf eine Antwort, bevor Sie erneut schreiben.",
        "en": "You've already written to this person several times in the last hour. Give them a bit of time to reply before writing again.",
        "fr": "Vous avez déjà écrit plusieurs fois à cette personne au cours de la dernière heure. Laissez-lui un peu de temps pour répondre avant d'écrire à nouveau.",
        "it": "Hai già scritto più volte a questa persona nell'ultima ora. Dai un po' di tempo per rispondere prima di scrivere di nuovo.",
        "pt": "Você já escreveu para esta pessoa várias vezes na última hora. Dê um tempo para ela responder antes de escrever de novo.",
    },
    "message_to_label": {"de": "An", "en": "To", "fr": "À", "it": "A", "pt": "Para"},
    "message_body_label": {"de": "Nachricht", "en": "Message", "fr": "Message", "it": "Messaggio", "pt": "Mensagem"},
    "message_send": {"de": "Senden", "en": "Send", "fr": "Envoyer", "it": "Invia", "pt": "Enviar"},
    "message_reply": {"de": "Antworten", "en": "Reply", "fr": "Répondre", "it": "Rispondi", "pt": "Responder"},
    "message_send_here": {"de": "Nachricht senden", "en": "Send a message", "fr": "Envoyer un message", "it": "Invia un messaggio", "pt": "Enviar mensagem"},

    # --- freemium: content locked without login ----------------------------------
    "locked_listing_title": {"de": "Details nur für Mitglieder", "en": "Details for members only", "fr": "Détails réservés aux membres", "it": "Dettagli solo per membri", "pt": "Detalhes só para membros"},
    "locked_listing_text": {
        "de": "Registriere dich kostenlos, um die vollständige Beschreibung und die Kontaktdaten zu sehen.",
        "en": "Sign up for free to see the full description and contact details.",
        "fr": "Inscrivez-vous gratuitement pour voir la description complète et les coordonnées.",
        "it": "Registrati gratis per vedere la descrizione completa e i contatti.",
        "pt": "Cadastre-se grátis para ver a descrição completa e os contatos.",
    },
    "locked_listing_unverified_title": {"de": "E-Mail-Bestätigung nötig", "en": "Email verification needed", "fr": "Vérification de l'e-mail nécessaire", "it": "Verifica email necessaria", "pt": "Confirmação de e-mail necessária"},
    "locked_listing_unverified_text": {
        "de": "Bitte bestätige zuerst deine E-Mail-Adresse, um die vollständige Beschreibung und die Kontaktdaten zu sehen.",
        "en": "Please verify your email address first to see the full description and contact details.",
        "fr": "Veuillez d'abord vérifier votre adresse e-mail pour voir la description complète et les coordonnées.",
        "it": "Verifica prima il tuo indirizzo email per vedere la descrizione completa e i contatti.",
        "pt": "Confirme seu e-mail primeiro para ver a descrição completa e os contatos.",
    },
    "locked_profile_title": {"de": "Profil nur für Mitglieder", "en": "Profile for members only", "fr": "Profil réservé aux membres", "it": "Profilo solo per membri", "pt": "Perfil só para membros"},
    "locked_profile_text": {
        "de": "Registriere dich kostenlos, um Biografie, Hörbeispiele und Anzeigen zu sehen.",
        "en": "Sign up for free to see the biography, audio samples, and listings.",
        "fr": "Inscrivez-vous gratuitement pour voir la biographie, les extraits audio et les annonces.",
        "it": "Registrati gratis per vedere biografia, esempi audio e annunci.",
        "pt": "Cadastre-se grátis para ver biografia, amostras de áudio e anúncios.",
    },

    # --- "Post Job" (my listings + new listing button) ------------------
    "my_listings_new_button": {"de": "+ Neue Anzeige", "en": "+ New listing", "fr": "+ Nouvelle annonce", "it": "+ Nuovo annuncio", "pt": "+ Novo anúncio"},

    # --- cascading location (Country > State) + type (solo/choir) ---------
    "listing_form_state_label": {"de": "Bundesland / Kanton", "en": "State / Province", "fr": "Région / Canton", "it": "Regione / Cantone", "pt": "Estado / Cantão"},
    "listing_form_state_other_placeholder": {"de": "Bundesland/Region eingeben", "en": "Enter state/region", "fr": "Saisir la région", "it": "Inserisci regione", "pt": "Digite o estado/região"},
    "listing_form_city_other_placeholder": {"de": "Stadt eingeben", "en": "Enter city", "fr": "Saisir la ville", "it": "Inserisci città", "pt": "Digite a cidade"},
    "listing_form_city_not_listed": {"de": "Meine Stadt ist nicht dabei", "en": "My city isn't listed", "fr": "Ma ville n'est pas listée", "it": "La mia città non è in elenco", "pt": "Minha cidade não está na lista"},
    "listing_form_city_choose_from_list": {"de": "Aus Liste wählen", "en": "Choose from list", "fr": "Choisir dans la liste", "it": "Scegli dalla lista", "pt": "Escolher da lista"},
    "listing_form_ensemble_type_label": {"de": "Solo, Chor oder beides?", "en": "Solo, choir, or both?", "fr": "Solo, chœur, ou les deux ?", "it": "Solo, coro o entrambi?", "pt": "Solo, coral ou ambos?"},
    "ensemble_type_solo": {"de": "Solo", "en": "Solo", "fr": "Solo", "it": "Solo", "pt": "Solo"},
    "ensemble_type_choir": {"de": "Chor", "en": "Choir", "fr": "Chœur", "it": "Coro", "pt": "Coral"},
    "ensemble_type_both": {"de": "Beides", "en": "Both", "fr": "Les deux", "it": "Entrambi", "pt": "Ambos"},
    "filter_all_states": {"de": "Alle Bundesländer", "en": "All states", "fr": "Toutes les régions", "it": "Tutte le regioni", "pt": "Todos os estados"},
    "filter_all_cities": {"de": "Alle Städte", "en": "All cities", "fr": "Toutes les villes", "it": "Tutte le città", "pt": "Todas as cidades"},
    "filter_all_ensemble_types": {"de": "Solo/Chor: alle", "en": "Solo/Choir: all", "fr": "Solo/Chœur : tous", "it": "Solo/Coro: tutti", "pt": "Solo/Coral: todos"},
    "filter_show_past": {"de": "Vergangene Termine anzeigen", "en": "Show past events", "fr": "Afficher les événements passés", "it": "Mostra eventi passati", "pt": "Mostrar eventos passados"},
    # --- P5 Etapa 2 (18/09/2026): Sistema de Urgência ---------------------------
    "filter_urgent_only": {"de": "Nur dringende Anzeigen", "en": "Urgent listings only", "fr": "Annonces urgentes uniquement", "it": "Solo annunci urgenti", "pt": "Só vagas urgentes"},
    "urgent_badge": {"de": "Dringend", "en": "Urgent", "fr": "Urgent", "it": "Urgente", "pt": "Urgente"},
    "listing_form_urgent_label": {"de": "Als dringend markieren", "en": "Mark as urgent", "fr": "Marquer comme urgent", "it": "Segna come urgente", "pt": "Marcar como urgente"},
    "listing_form_urgent_help": {
        "de": "Erscheint hervorgehoben im dringenden Bereich. Nutzt dein wöchentliches Gratis-Token, oder kostet Notas, falls schon verbraucht.",
        "en": "Shows up highlighted in the urgent board. Uses your weekly free token, or costs Notas if already used.",
        "fr": "Apparaît en évidence dans le tableau des annonces urgentes. Utilise votre jeton gratuit hebdomadaire, ou coûte des Notas s'il est déjà utilisé.",
        "it": "Appare in evidenza nella bacheca degli annunci urgenti. Usa il tuo token gratuito settimanale, o costa Notas se già usato.",
        "pt": "Aparece destacada no quadro de vagas urgentes. Usa seu token grátis da semana, ou custa Notas se já tiver sido usado.",
    },
    "mark_urgent_button_free": {"de": "Als dringend markieren (kostenlos)", "en": "Mark as urgent (free)", "fr": "Marquer comme urgent (gratuit)", "it": "Segna come urgente (gratis)", "pt": "Marcar como urgente (grátis)"},
    "mark_urgent_button_paid": {
        "de": "Als dringend markieren ({cost} Notas)", "en": "Mark as urgent ({cost} Notas)",
        "fr": "Marquer comme urgent ({cost} Notas)", "it": "Segna come urgente ({cost} Notas)", "pt": "Marcar como urgente ({cost} Notas)",
    },
    "urgent_marked_success": {"de": "Als dringend markiert!", "en": "Marked as urgent!", "fr": "Marqué comme urgent !", "it": "Segnato come urgente!", "pt": "Marcada como urgente!"},
    # Confirmation before spending Notas to mark a listing urgent
    # (19/09/2026, same fix as notas_redeem_confirm) — only shown for
    # the PAID path; the free-token path costs nothing, so there's
    # nothing to confirm there.
    "mark_urgent_confirm_paid": {
        "de": "Als dringend markieren für {cost} Notas? Dies wird sofort von deinem Guthaben abgezogen.",
        "en": "Mark as urgent for {cost} Notas? This will be deducted from your balance right away.",
        "fr": "Marquer comme urgent pour {cost} Notas ? Ce montant sera déduit immédiatement de votre solde.",
        "it": "Segnare come urgente per {cost} Notas? Verrà detratto subito dal tuo saldo.",
        "pt": "Marcar como urgente por {cost} Notas? Isso será descontado do seu saldo imediatamente.",
    },
    "urgent_error_insufficient_balance": {
        "de": "Kein Gratis-Token diese Woche und nicht genug Notas, um Dringlichkeit zu kaufen.",
        "en": "No free token this week and not enough Notas to buy urgency.",
        "fr": "Aucun jeton gratuit cette semaine et pas assez de Notas pour acheter l'urgence.",
        "it": "Nessun token gratuito questa settimana e Notas insufficienti per acquistare l'urgenza.",
        "pt": "Sem token grátis essa semana e sem Notas suficientes pra comprar urgência.",
    },
    "urgent_error_not_eligible": {
        "de": "Diese Anzeige kann nicht als dringend markiert werden.",
        "en": "This listing can't be marked as urgent.",
        "fr": "Cette annonce ne peut pas être marquée comme urgente.",
        "it": "Questo annuncio non può essere segnato come urgente.",
        "pt": "Essa vaga não pode ser marcada como urgente.",
    },
    "notas_reason_urgency_purchase": {"de": "Dringlichkeit gekauft", "en": "Urgency purchased", "fr": "Urgence achetée", "it": "Urgenza acquistata", "pt": "Urgência comprada"},
    "notas_reason_urgency_match_reward": {
        "de": "Prämie: dringende Vagabesetzung", "en": "Reward: urgent listing filled",
        "fr": "Récompense : annonce urgente pourvue", "it": "Ricompensa: annuncio urgente coperto", "pt": "Recompensa: vaga urgente preenchida",
    },
    "filter_period_from_label": {"de": "Zeitraum von", "en": "Period from", "fr": "Période à partir de", "it": "Periodo da", "pt": "Período de"},
    "filter_period_to_label": {"de": "bis", "en": "to", "fr": "à", "it": "a", "pt": "até"},
    "board_results_label": {"de": "Ergebnisse", "en": "results", "fr": "résultats", "it": "risultati", "pt": "resultados"},

    # --- pagination -----------------------------------------------------------
    "pagination_prev": {"de": "Zurück", "en": "Previous", "fr": "Précédent", "it": "Precedente", "pt": "Anterior"},
    "pagination_next": {"de": "Weiter", "en": "Next", "fr": "Suivant", "it": "Successivo", "pt": "Próximo"},
    "pagination_error": {"de": "Ergebnisse konnten nicht geladen werden.", "en": "Could not load results.", "fr": "Impossible de charger les résultats.", "it": "Impossibile caricare i risultati.", "pt": "Não foi possível carregar os resultados."},
    "pagination_retry": {"de": "Erneut versuchen", "en": "Try again", "fr": "Réessayer", "it": "Riprova", "pt": "Tentar novamente"},
    "pagination_page": {"de": "Seite", "en": "Page", "fr": "Page", "it": "Pagina", "pt": "Página"},

    # --- "message already sent" -------------------------------------------------
    "already_messaged_text": {
        "de": "Du hast zu dieser Anzeige bereits eine Nachricht gesendet.",
        "en": "You've already sent a message about this listing.",
        "fr": "Vous avez déjà envoyé un message à propos de cette annonce.",
        "it": "Hai già inviato un messaggio per questo annuncio.",
        "pt": "Você já enviou uma mensagem sobre este anúncio.",
    },

    # --- redes sociais no perfil -----------------------------------------------
    "social_links_title": {"de": "Soziale Netzwerke", "en": "Social links", "fr": "Réseaux sociaux", "it": "Social network", "pt": "Redes sociais"},
    "social_links_help": {
        "de": "Optional. Wird auf deinem öffentlichen Profil nur als Schaltfläche angezeigt (nicht als voller Link).",
        "en": "Optional. Shown on your public profile only as a button (not the full link).",
        "fr": "Facultatif. Affiché sur votre profil public uniquement sous forme de bouton (pas le lien complet).",
        "it": "Facoltativo. Mostrato sul tuo profilo pubblico solo come pulsante (non il link completo).",
        "pt": "Opcional. Aparece no seu perfil público apenas como um botão (não o link completo).",
    },
    "social_platform_website": {"de": "Website", "en": "Website", "fr": "Site web", "it": "Sito web", "pt": "Site"},
    "social_platform_facebook": {"de": "Facebook", "en": "Facebook", "fr": "Facebook", "it": "Facebook", "pt": "Facebook"},
    "social_platform_instagram": {"de": "Instagram", "en": "Instagram", "fr": "Instagram", "it": "Instagram", "pt": "Instagram"},
    "social_platform_twitter": {"de": "Twitter", "en": "Twitter", "fr": "Twitter", "it": "Twitter", "pt": "Twitter"},
    "social_platform_whatsapp": {"de": "WhatsApp", "en": "WhatsApp", "fr": "WhatsApp", "it": "WhatsApp", "pt": "WhatsApp"},

    # --- star rating (private, only whoever received it sees it) ------------------
    "rating_widget_title": {"de": "Bewertung abgeben", "en": "Leave a rating", "fr": "Laisser une note", "it": "Lascia una valutazione", "pt": "Deixar uma avaliação"},
    "rating_widget_help": {
        "de": "Deine Bewertung ist nur für diese Person sichtbar — niemand sonst kann sie sehen.",
        "en": "Your rating is only visible to this person — no one else can see it.",
        "fr": "Votre note n'est visible que par cette personne — personne d'autre ne peut la voir.",
        "it": "La tua valutazione è visibile solo a questa persona — nessun altro può vederla.",
        "pt": "Sua avaliação só é visível para esta pessoa — mais ninguém pode vê-la.",
    },
    "rating_saved": {"de": "Bewertung gespeichert.", "en": "Rating saved.", "fr": "Note enregistrée.", "it": "Valutazione salvata.", "pt": "Avaliação salva."},
    "rating_stars_label": {"de": "Sterne (0–5)", "en": "Stars (0–5)", "fr": "Étoiles (0–5)", "it": "Stelle (0–5)", "pt": "Estrelas (0–5)"},
    "rating_comment_label": {"de": "Kommentar (optional)", "en": "Comment (optional)", "fr": "Commentaire (facultatif)", "it": "Commento (facoltativo)", "pt": "Comentário (opcional)"},
    "rating_submit": {"de": "Bewertung senden", "en": "Submit rating", "fr": "Envoyer la note", "it": "Invia valutazione", "pt": "Enviar avaliação"},
    "my_ratings_title": {"de": "Meine Bewertungen", "en": "My ratings", "fr": "Mes évaluations", "it": "Le mie valutazioni", "pt": "Minhas avaliações"},
    "my_ratings_help": {
        "de": "Nur du siehst diese Bewertungen — sie sind privat.",
        "en": "Only you can see these ratings — they're private.",
        "fr": "Vous seul(e) voyez ces évaluations — elles sont privées.",
        "it": "Solo tu vedi queste valutazioni — sono private.",
        "pt": "Só você vê essas avaliações — elas são privadas.",
    },
    "my_ratings_count_label": {"de": "Bewertungen", "en": "ratings", "fr": "évaluations", "it": "valutazioni", "pt": "avaliações"},
    "my_ratings_none": {"de": "Noch keine Bewertungen erhalten.", "en": "No ratings received yet.", "fr": "Aucune évaluation reçue pour l'instant.", "it": "Nessuna valutazione ricevuta finora.", "pt": "Nenhuma avaliação recebida ainda."},

    # --- account: password, deletion and reactivation ------------------------------------
    "account_section_title": {"de": "Konto", "en": "Account", "fr": "Compte", "it": "Account", "pt": "Conta"},
    "change_password_title": {"de": "Passwort ändern", "en": "Change password", "fr": "Changer le mot de passe", "it": "Cambia password", "pt": "Alterar senha"},
    "change_password_current_label": {"de": "Aktuelles Passwort", "en": "Current password", "fr": "Mot de passe actuel", "it": "Password attuale", "pt": "Senha atual"},
    "change_password_new_label": {"de": "Neues Passwort", "en": "New password", "fr": "Nouveau mot de passe", "it": "Nuova password", "pt": "Nova senha"},
    "change_password_submit": {"de": "Passwort ändern", "en": "Change password", "fr": "Changer le mot de passe", "it": "Cambia password", "pt": "Alterar senha"},
    "change_password_wrong_current": {"de": "Aktuelles Passwort ist falsch.", "en": "Current password is incorrect.", "fr": "Le mot de passe actuel est incorrect.", "it": "La password attuale non è corretta.", "pt": "A senha atual está incorreta."},
    "change_password_too_short": {"de": "Neues Passwort braucht mindestens 6 Zeichen.", "en": "New password must be at least 6 characters.", "fr": "Le nouveau mot de passe doit comporter au moins 6 caractères.", "it": "La nuova password deve avere almeno 6 caratteri.", "pt": "A nova senha precisa ter no mínimo 6 caracteres."},
    "back_to_profile": {"de": "Zurück zum Profil", "en": "Back to profile", "fr": "Retour au profil", "it": "Torna al profilo", "pt": "Voltar ao perfil"},

    "danger_zone_title": {"de": "Gefahrenzone", "en": "Danger zone", "fr": "Zone de danger", "it": "Zona a rischio", "pt": "Zona de risco"},
    "delete_account_help": {
        "de": "Dein Konto wird deaktiviert und für 6 Monate aufbewahrt — so lange kannst du es inklusive deiner Notas wiederherstellen. Danach werden alle deine Daten und verbleibenden Notas endgültig gelöscht.",
        "en": "Your account will be deactivated and kept for 6 months — until then you can reactivate it, including your Notas. After that, all your data and remaining Notas are permanently deleted.",
        "fr": "Votre compte sera désactivé et conservé pendant 6 mois — d'ici là, vous pouvez le réactiver, Notas comprises. Ensuite, toutes vos données et vos Notas restantes seront définitivement supprimées.",
        "it": "Il tuo account verrà disattivato e conservato per 6 mesi — fino ad allora puoi riattivarlo, Notas incluse. Dopodiché tutti i tuoi dati e le Notas rimanenti verranno eliminati definitivamente.",
        "pt": "Sua conta será desativada e mantida por 6 meses — até lá, você pode reativá-la, incluindo suas Notas. Depois disso, todos os seus dados e Notas restantes serão excluídos definitivamente.",
    },
    "delete_account_toggle": {"de": "Konto löschen", "en": "Delete account", "fr": "Supprimer le compte", "it": "Elimina account", "pt": "Excluir conta"},
    "delete_account_confirm": {
        "de": "Konto wirklich löschen? Es wird für 6 Monate aufbewahrt und danach endgültig entfernt.",
        "en": "Really delete your account? It will be kept for 6 months and then permanently removed.",
        "fr": "Vraiment supprimer votre compte ? Il sera conservé 6 mois puis définitivement supprimé.",
        "it": "Eliminare davvero il tuo account? Verrà conservato per 6 mesi e poi rimosso definitivamente.",
        "pt": "Excluir mesmo sua conta? Ela será mantida por 6 meses e depois removida definitivamente.",
    },
    "delete_account_password_label": {"de": "Passwort zur Bestätigung", "en": "Password to confirm", "fr": "Mot de passe pour confirmer", "it": "Password per confermare", "pt": "Senha para confirmar"},
    "delete_account_submit": {"de": "Konto endgültig löschen", "en": "Delete my account", "fr": "Supprimer définitivement mon compte", "it": "Elimina definitivamente il mio account", "pt": "Excluir minha conta"},
    "delete_account_wrong_password": {"de": "Passwort ist falsch.", "en": "Password is incorrect.", "fr": "Le mot de passe est incorrect.", "it": "La password non è corretta.", "pt": "A senha está incorreta."},
    "account_deleted_banner": {
        "de": "Dein Konto wurde deaktiviert. Wenn du dich innerhalb von 6 Monaten erneut anmeldest, kannst du es reaktivieren.",
        "en": "Your account has been deactivated. If you log in again within 6 months, you can reactivate it.",
        "fr": "Votre compte a été désactivé. Si vous vous reconnectez dans les 6 mois, vous pourrez le réactiver.",
        "it": "Il tuo account è stato disattivato. Se accedi di nuovo entro 6 mesi, potrai riattivarlo.",
        "pt": "Sua conta foi desativada. Se você entrar novamente em até 6 meses, poderá reativá-la.",
    },

    "reactivate_title": {"de": "Konto reaktivieren", "en": "Reactivate account", "fr": "Réactiver le compte", "it": "Riattiva account", "pt": "Reativar conta"},
    "reactivate_text": {
        "de": "Dieses Konto wurde gelöscht, ist aber noch innerhalb der 6-Monats-Frist. Möchtest du es reaktivieren?",
        "en": "This account was deleted but is still within the 6-month window. Would you like to reactivate it?",
        "fr": "Ce compte a été supprimé mais est encore dans le délai de 6 mois. Souhaitez-vous le réactiver ?",
        "it": "Questo account è stato eliminato ma è ancora entro i 6 mesi. Vuoi riattivarlo?",
        "pt": "Esta conta foi excluída, mas ainda está dentro do prazo de 6 meses. Deseja reativá-la?",
    },
    "reactivate_submit": {"de": "Ja, Konto reaktivieren", "en": "Yes, reactivate my account", "fr": "Oui, réactiver mon compte", "it": "Sì, riattiva il mio account", "pt": "Sim, reativar minha conta"},

    # --- foto de perfil ---------------------------------------------------
    "register_avatar_label": {"de": "Profilfoto (optional)", "en": "Profile photo (optional)", "fr": "Photo de profil (facultatif)", "it": "Foto profilo (facoltativo)", "pt": "Foto de perfil (opcional)"},
    "register_avatar_help": {
        "de": "JPG, PNG oder WebP, max. 3 MB. Kann später in deinem Profil geändert werden.",
        "en": "JPG, PNG, or WebP, max 3 MB. Can be changed later in your profile.",
        "fr": "JPG, PNG ou WebP, max. 3 Mo. Modifiable plus tard dans votre profil.",
        "it": "JPG, PNG o WebP, max 3 MB. Modificabile in seguito nel tuo profilo.",
        "pt": "JPG, PNG ou WebP, máx. 3 MB. Pode ser alterada depois no seu perfil.",
    },
    "profile_avatar_label": {"de": "Profilfoto", "en": "Profile photo", "fr": "Photo de profil", "it": "Foto profilo", "pt": "Foto de perfil"},
    "profile_location_label": {"de": "Standort", "en": "Location", "fr": "Localisation", "it": "Posizione", "pt": "Localização"},
    "profile_location_help": {
        "de": "Wird für passende Vorschläge (z. B. in deiner Nähe) verwendet.",
        "en": "Used to find better matches near you.",
        "fr": "Utilisé pour trouver de meilleures correspondances près de chez vous.",
        "it": "Utilizzato per trovare corrispondenze migliori vicino a te.",
        "pt": "Usado para encontrar melhores combinações perto de você.",
    },
    "profile_avatar_remove": {"de": "Foto entfernen", "en": "Remove photo", "fr": "Supprimer la photo", "it": "Rimuovi foto", "pt": "Remover foto"},
    "profile_avatar_invalid": {
        "de": "Das Bild konnte nicht gespeichert werden (Format oder Größe nicht unterstützt — JPG/PNG/WebP, max. 3 MB). Der Rest wurde trotzdem gespeichert.",
        "en": "The image couldn't be saved (unsupported format or too large — JPG/PNG/WebP, max 3MB). Everything else was still saved.",
        "fr": "L'image n'a pas pu être enregistrée (format non pris en charge ou trop volumineuse — JPG/PNG/WebP, max 3 Mo). Le reste a quand même été enregistré.",
        "it": "Impossibile salvare l'immagine (formato non supportato o troppo grande — JPG/PNG/WebP, max 3MB). Il resto è stato comunque salvato.",
        "pt": "Não foi possível salvar a imagem (formato não suportado ou muito grande — JPG/PNG/WebP, máx. 3MB). O restante foi salvo mesmo assim.",
    },

    # --- matching listing alerts ------------------------------------
    "notify_matches_label": {"de": "Bei passenden Anzeigen per E-Mail benachrichtigen", "en": "Email me about matching listings", "fr": "M'avertir par e-mail des annonces correspondantes", "it": "Avvisami via email per annunci compatibili", "pt": "Avisar por e-mail sobre anúncios compatíveis"},
    "notify_matches_help": {
        "de": "Wenn jemand eine Anzeige postet, die zu deinem Profil passt (Stimmtyp bzw. Dirigent(in)), bekommst du sofort eine E-Mail.",
        "en": "When someone posts a listing matching your profile (voice type, or conductor role), you get an email right away.",
        "fr": "Quand quelqu'un publie une annonce correspondant à votre profil (tessiture ou rôle de chef de chœur), vous recevez un e-mail immédiatement.",
        "it": "Quando qualcuno pubblica un annuncio compatibile con il tuo profilo (tessitura o ruolo di direttore), ricevi subito un'email.",
        "pt": "Quando alguém publicar um anúncio compatível com seu perfil (tipo de voz ou regente), você recebe um e-mail na hora.",
    },

    # --- indicador de perfil completo --------------------------------------
    "completeness_label": {"de": "Profil vollständig", "en": "Profile complete", "fr": "Profil complet", "it": "Profilo completo", "pt": "Perfil completo"},
    "completeness_hint": {
        "de": "ein vollständigeres Profil wirkt vertrauenswürdiger und verbessert deine Treffer auf der Startseite",
        "en": "a more complete profile builds trust and improves your matches on the home page",
        "fr": "un profil plus complet inspire davantage confiance et améliore vos correspondances sur la page d'accueil",
        "it": "un profilo più completo ispira più fiducia e migliora le corrispondenze nella home",
        "pt": "um perfil mais completo passa mais confiança e melhora suas combinações na página inicial",
    },

    # --- exportar dados (GDPR/portabilidade) --------------------------------
    "export_data_link": {"de": "Meine Daten exportieren", "en": "Export my data", "fr": "Exporter mes données", "it": "Esporta i miei dati", "pt": "Exportar meus dados"},
    "export_data_help": {
        "de": "Lädt eine JSON-Datei mit allem herunter, was über dich gespeichert ist (Profil, Anzeigen, Nachrichten, Bewertungen).",
        "en": "Downloads a JSON file with everything stored about you (profile, listings, messages, ratings).",
        "fr": "Télécharge un fichier JSON avec tout ce qui est enregistré sur vous (profil, annonces, messages, évaluations).",
        "it": "Scarica un file JSON con tutto ciò che è archiviato su di te (profilo, annunci, messaggi, valutazioni).",
        "pt": "Baixa um arquivo JSON com tudo o que está salvo sobre você (perfil, anúncios, mensagens, avaliações).",
    },

    # --- favoritos -----------------------------------------------------------
    "favorite_add": {"de": "Favorisieren", "en": "Save", "fr": "Enregistrer", "it": "Salva", "pt": "Salvar"},
    "favorite_remove": {"de": "Aus Favoriten entfernen", "en": "Remove from favorites", "fr": "Retirer des favoris", "it": "Rimuovi dai preferiti", "pt": "Remover dos favoritos"},
    "favorite_marker": {"de": "Favorisiert", "en": "Saved", "fr": "Enregistré", "it": "Salvato", "pt": "Salvo"},
    "favorites_subtitle": {"de": "Anzeigen, die du dir für später gemerkt hast.", "en": "Listings you've saved for later.", "fr": "Annonces que vous avez enregistrées pour plus tard.", "it": "Annunci che hai salvato per dopo.", "pt": "Anúncios que você salvou para depois."},
    "favorites_empty": {"de": "Du hast noch keine Anzeigen favorisiert.", "en": "You haven't saved any listings yet.", "fr": "Vous n'avez encore enregistré aucune annonce.", "it": "Non hai ancora salvato annunci.", "pt": "Você ainda não salvou nenhum anúncio."},

    # --- new message notification ---------------------------------------
    "notify_messages_label": {"de": "Bei neuen Nachrichten per E-Mail benachrichtigen", "en": "Email me when I get a new message", "fr": "M'avertir par e-mail des nouveaux messages", "it": "Avvisami via email per i nuovi messaggi", "pt": "Avisar por e-mail quando eu receber uma mensagem"},
    "notify_messages_help": {
        "de": "Du bekommst eine E-Mail, sobald dir jemand eine Nachricht schickt (ohne den Inhalt der Nachricht — dafür musst du dich einloggen).",
        "en": "You'll get an email as soon as someone sends you a message (without the message content — you'll need to log in to read it).",
        "fr": "Vous recevrez un e-mail dès que quelqu'un vous envoie un message (sans le contenu du message — vous devrez vous connecter pour le lire).",
        "it": "Riceverai un'email non appena qualcuno ti invia un messaggio (senza il contenuto del messaggio — dovrai accedere per leggerlo).",
        "pt": "Você recebe um e-mail assim que alguém te enviar uma mensagem (sem o conteúdo — você precisa entrar no site para ler).",
    },

    # --- convide um amigo / referral -----------------------------------------
    "referral_section_title": {"de": "Freunde einladen", "en": "Invite a friend", "fr": "Inviter un(e) ami(e)", "it": "Invita un amico", "pt": "Convidar um amigo"},
    "referral_section_text": {
        "de": "Teile diesen Link — wer sich darüber anmeldet, zählt als deine Einladung.",
        "en": "Share this link — anyone who signs up through it counts as your invite.",
        "fr": "Partagez ce lien — toute personne qui s'inscrit via celui-ci compte comme votre invitation.",
        "it": "Condividi questo link — chiunque si registri tramite esso conta come tuo invito.",
        "pt": "Compartilhe este link — quem se cadastrar por ele conta como seu convite.",
    },
    "referral_count_label": {"de": "Eingeladene Personen", "en": "People invited", "fr": "Personnes invitées", "it": "Persone invitate", "pt": "Pessoas convidadas"},
    "referral_copy_button": {"de": "Link kopieren", "en": "Copy link", "fr": "Copier le lien", "it": "Copia link", "pt": "Copiar link"},
    "referral_copied": {"de": "Kopiert!", "en": "Copied!", "fr": "Copié !", "it": "Copiato!", "pt": "Copiado!"},

    # --- notas (banco de créditos) -------------------------------------------
    "notas_title": {"de": "Notas", "en": "Notas", "fr": "Notas", "it": "Notas", "pt": "Notas"},
    "notas_subtitle": {
        "de": "Deine Prämien fürs Einladen von Freunden — hier ansehen und einlösen.",
        "en": "Your rewards for inviting friends — view and redeem them here.",
        "fr": "Vos récompenses pour avoir invité des amis — consultez-les et échangez-les ici.",
        "it": "Le tue ricompense per aver invitato amici — vedile e riscattale qui.",
        "pt": "Suas recompensas por indicar amigos — veja e resgate aqui.",
    },
    "notas_balance_label": {"de": "verfügbare Notas", "en": "Notas available", "fr": "Notas disponibles", "it": "Notas disponibili", "pt": "Notas disponíveis"},
    "notas_next_credit_hint": {
        "de": "Noch {n} bestätigte Einladung(en) bis zur nächsten Nota.",
        "en": "{n} more verified referral(s) until your next Nota.",
        "fr": "Encore {n} parrainage(s) vérifié(s) avant votre prochaine Nota.",
        "it": "Ancora {n} referral verificati fino alla prossima Nota.",
        "pt": "Faltam {n} indicação(ões) verificada(s) para a próxima Nota.",
    },
    "notas_how_it_works": {
        "de": "Für alle {ratio} bestätigten Einladungen erhältst du 1 Nota — bestätigt heißt, die eingeladene Person hat ihre E-Mail verifiziert.",
        "en": "Every {ratio} verified referrals earns you 1 Nota — verified means the person you invited confirmed their e-mail.",
        "fr": "Chaque groupe de {ratio} parrainages vérifiés vous rapporte 1 Nota — vérifié signifie que la personne invitée a confirmé son e-mail.",
        "it": "Ogni {ratio} referral verificati ti fanno guadagnare 1 Nota — verificato significa che la persona invitata ha confermato la propria e-mail.",
        "pt": "A cada {ratio} indicações verificadas você ganha 1 Nota — verificada quer dizer que a pessoa indicada confirmou o e-mail dela.",
    },
    "notas_catalog_title": {"de": "Prämienkatalog", "en": "Redemption catalog", "fr": "Catalogue de récompenses", "it": "Catalogo premi", "pt": "Catálogo de recompensas"},
    "notas_item_profile_highlight_7d_title": {
        "de": "Profil 7 Tage hervorheben",
        "en": "Highlight profile for 7 days",
        "fr": "Mettre le profil en avant pendant 7 jours",
        "it": "Metti in evidenza il profilo per 7 giorni",
        "pt": "Destacar perfil por 7 dias",
    },
    "notas_item_profile_highlight_7d_desc": {
        "de": "Dein öffentliches Profil zeigt 7 Tage lang ein „Hervorgehoben“-Abzeichen.",
        "en": "Your public profile shows a \"featured\" badge for 7 days.",
        "fr": "Votre profil public affiche un badge « en vedette » pendant 7 jours.",
        "it": "Il tuo profilo pubblico mostra un badge \"in evidenza\" per 7 giorni.",
        "pt": "Seu perfil público mostra um selo de destaque por 7 dias.",
    },
    "notas_unit": {"de": "Notas", "en": "Notas", "fr": "Notas", "it": "Notas", "pt": "Notas"},
    "notas_redeem_button": {"de": "Einlösen", "en": "Redeem", "fr": "Échanger", "it": "Riscatta", "pt": "Resgatar"},
    # Confirmation dialog before redeeming a Notas item (19/09/2026,
    # Daniel: a click was applying the purchase with no confirmation).
    # {item}/{cost} are replaced in the template, same pattern as the
    # other {n}/{ratio} placeholders in this file.
    "notas_redeem_confirm": {
        "de": "„{item}“ für {cost} einlösen? Dies wird sofort von deinem Guthaben abgezogen.",
        "en": "Redeem \"{item}\" for {cost}? This will be deducted from your balance right away.",
        "fr": "Échanger « {item} » contre {cost} ? Ce montant sera déduit immédiatement de votre solde.",
        "it": "Riscattare \"{item}\" per {cost}? Verrà detratto subito dal tuo saldo.",
        "pt": "Resgatar \"{item}\" por {cost}? Isso será descontado do seu saldo imediatamente.",
    },
    "notas_insufficient_short": {
        "de": "Dir fehlen noch {n} Notas.",
        "en": "You're missing {n} Notas.",
        "fr": "Il vous manque {n} Notas.",
        "it": "Ti mancano {n} Notas.",
        "pt": "Faltam {n} Notas.",
    },
    "notas_buy_missing_link": {
        "de": "Fehlende Notas kaufen",
        "en": "Buy the missing Notas",
        "fr": "Acheter les Notas manquantes",
        "it": "Compra le Notas mancanti",
        "pt": "Comprar as Notas que faltam",
    },
    "notas_buy_stub_title": {
        "de": "Notas kaufen",
        "en": "Buy Notas",
        "fr": "Acheter des Notas",
        "it": "Compra Notas",
        "pt": "Comprar Notas",
    },
    "notas_buy_stub_missing": {
        "de": "Dir fehlen {n} Notas (ca. {eur} €) für diesen Artikel.",
        "en": "You're missing {n} Notas (about {eur} €) for this item.",
        "fr": "Il vous manque {n} Notas (environ {eur} €) pour cet article.",
        "it": "Ti mancano {n} Notas (circa {eur} €) per questo articolo.",
        "pt": "Faltam {n} Notas (cerca de {eur} €) para este item.",
    },
    "notas_buy_stub_body": {
        "de": "Der Kauf von Notas mit echtem Geld ist noch nicht verfügbar — wir arbeiten daran.",
        "en": "Buying Notas with real money isn't available yet — we're working on it.",
        "fr": "L'achat de Notas avec de l'argent réel n'est pas encore disponible — nous y travaillons.",
        "it": "L'acquisto di Notas con denaro reale non è ancora disponibile — ci stiamo lavorando.",
        "pt": "A compra de Notas com dinheiro de verdade ainda não está disponível — estamos trabalhando nisso.",
    },
    "notas_buy_stub_back": {
        "de": "Zurück zu Notas", "en": "Back to Notas", "fr": "Retour aux Notas",
        "it": "Torna a Notas", "pt": "Voltar pra Notas",
    },
    "notas_catalog_more_soon": {
        "de": "Mehr Prämien folgen bald.",
        "en": "More rewards coming soon.",
        "fr": "D'autres récompenses arrivent bientôt.",
        "it": "Altri premi in arrivo presto.",
        "pt": "Mais itens do catálogo em breve.",
    },
    "notas_ledger_title": {"de": "Verlauf", "en": "History", "fr": "Historique", "it": "Cronologia", "pt": "Extrato"},
    "notas_ledger_empty": {
        "de": "Noch keine Bewegungen.",
        "en": "No activity yet.",
        "fr": "Aucune activité pour le moment.",
        "it": "Ancora nessuna attività.",
        "pt": "Ainda sem movimentações.",
    },
    "notas_reason_referral_bonus": {
        "de": "Nota für bestätigte Einladungen",
        "en": "Nota for verified referrals",
        "fr": "Nota pour parrainages vérifiés",
        "it": "Nota per referral verificati",
        "pt": "Nota por indicações verificadas",
    },
    "notas_reason_redeem_profile_highlight_7d": {
        "de": "Eingelöst: Profil hervorheben (7 Tage)",
        "en": "Redeemed: profile highlight (7 days)",
        "fr": "Échangé : profil en vedette (7 jours)",
        "it": "Riscattato: profilo in evidenza (7 giorni)",
        "pt": "Resgatado: destaque de perfil (7 dias)",
    },
    # Notas v2 (2026-09-26): purchased/earned split, expiry, new ledger reasons, legal links.
    "notas_purchased_label": {"de": "Gekauft", "en": "Purchased", "fr": "Achetées", "it": "Acquistate", "pt": "Compradas"},
    "notas_earned_label": {"de": "Verdient", "en": "Earned", "fr": "Gagnées", "it": "Guadagnate", "pt": "Ganhas"},
    "notas_category_purchased": {"de": "gekauft", "en": "purchased", "fr": "achetées", "it": "acquistate", "pt": "compradas"},
    "notas_category_earned": {"de": "verdient", "en": "earned", "fr": "gagnées", "it": "guadagnate", "pt": "ganhas"},
    "notas_expires_on": {"de": "läuft ab am {date}", "en": "expires {date}", "fr": "expire le {date}", "it": "scade il {date}", "pt": "expira em {date}"},
    "notas_next_expiry_hint": {"de": "{amount} verdiente Notas laufen am {date} ab.", "en": "{amount} earned Notas expire on {date}.", "fr": "{amount} Notas gagnées expirent le {date}.", "it": "{amount} Notas guadagnate scadono il {date}.", "pt": "{amount} Notas ganhas expiram em {date}."},
    "notas_debt_hint": {"de": "Nach einer Rückerstattung ist dein Saldo um {amount} Notas im Minus. Neue Notas gleichen das zuerst aus.", "en": "After a refund your balance is {amount} Notas below zero. New Notas settle this first.", "fr": "Après un remboursement, votre solde est de {amount} Notas en négatif. Les nouvelles Notas le compensent d'abord.", "it": "Dopo un rimborso il tuo saldo è in negativo di {amount} Notas. Le nuove Notas lo compensano per prime.", "pt": "Após um reembolso, seu saldo está {amount} Notas negativo. Novas Notas compensam isso primeiro."},
    "notas_rules_hint": {"de": "Gekaufte Notas laufen nie ab und werden zuerst verwendet. Verdiente Notas laufen 18 Monate nach der Gutschrift ab.", "en": "Purchased Notas never expire and are used first. Earned Notas expire 18 months after they were credited.", "fr": "Les Notas achetées n'expirent jamais et sont utilisées en premier. Les Notas gagnées expirent 18 mois après leur crédit.", "it": "Le Notas acquistate non scadono mai e vengono usate per prime. Le Notas guadagnate scadono 18 mesi dopo l'accredito.", "pt": "Notas compradas nunca expiram e são usadas primeiro. Notas ganhas expiram 18 meses após o crédito."},
    "notas_reason_purchase": {"de": "Kauf", "en": "Purchase", "fr": "Achat", "it": "Acquisto", "pt": "Compra"},
    "notas_reason_earned_expired": {"de": "Abgelaufen (verdiente Notas)", "en": "Expired (earned Notas)", "fr": "Expirées (Notas gagnées)", "it": "Scadute (Notas guadagnate)", "pt": "Expiradas (Notas ganhas)"},
    "notas_reason_admin_refund": {"de": "Rückerstattung", "en": "Refund", "fr": "Remboursement", "it": "Rimborso", "pt": "Reembolso"},
    "notas_reason_stripe_refund": {"de": "Zahlung erstattet", "en": "Payment refunded", "fr": "Paiement remboursé", "it": "Pagamento rimborsato", "pt": "Pagamento reembolsado"},
    "notas_reason_stripe_dispute": {"de": "Zahlung angefochten", "en": "Payment disputed", "fr": "Paiement contesté", "it": "Pagamento contestato", "pt": "Pagamento contestado"},
    "notas_reason_stripe_dispute_won": {"de": "Anfechtung abgeschlossen", "en": "Dispute resolved", "fr": "Litige résolu", "it": "Contestazione risolta", "pt": "Contestação resolvida"},
    "notas_reason_admin_grant_credit": {"de": "Gutschrift vom Team", "en": "Credit from the team", "fr": "Crédit de l'équipe", "it": "Accredito dal team", "pt": "Crédito da equipe"},
    "notas_reason_admin_grant_debit": {"de": "Korrektur vom Team", "en": "Correction by the team", "fr": "Correction par l'équipe", "it": "Correzione del team", "pt": "Correção da equipe"},
    "footer_terms": {"de": "AGB", "en": "Terms", "fr": "CGU", "it": "Termini", "pt": "Termos"},
    "footer_withdrawal": {"de": "Widerruf", "en": "Withdrawal", "fr": "Rétractation", "it": "Recesso", "pt": "Arrependimento"},
    "terms_title": {"de": "Allgemeine Geschäftsbedingungen (AGB)", "en": "Terms and Conditions", "fr": "Conditions générales", "it": "Termini e condizioni", "pt": "Termos e condições"},
    "terms_version": {"de": "Stand: 26.09.2026", "en": "Version: 26 September 2026", "fr": "Version : 26/09/2026", "it": "Versione: 26/09/2026", "pt": "Versão: 26/09/2026"},
    "withdrawal_title": {"de": "Widerrufsbelehrung", "en": "Withdrawal notice", "fr": "Droit de rétractation", "it": "Diritto di recesso", "pt": "Direito de arrependimento"},
    "notas_buy_title": {"de": "Notas kaufen", "en": "Buy Notas", "fr": "Acheter des Notas", "it": "Acquista Notas", "pt": "Comprar Notas"},
    "notas_buy_intro": {"de": "Wähle ein Paket. 1 Nota = 1 EUR bzw. 1 CHF. Gekaufte Notas verfallen nie.", "en": "Choose a bundle. 1 Nota = 1 EUR or 1 CHF. Purchased Notas never expire.", "fr": "Choisissez un pack. 1 Nota = 1 EUR ou 1 CHF. Les Notas achetées n'expirent jamais.", "it": "Scegli un pacchetto. 1 Nota = 1 EUR o 1 CHF. Le Notas acquistate non scadono mai.", "pt": "Escolha um pacote. 1 Nota = 1 EUR ou 1 CHF. Notas compradas nunca expiram."},
    "notas_buy_button": {"de": "Weiter zur Zahlung", "en": "Continue to payment", "fr": "Passer au paiement", "it": "Procedi al pagamento", "pt": "Ir para o pagamento"},
    "notas_buy_waiver_label": {"de": "Ich akzeptiere die AGB und verlange, dass die Notas sofort gutgeschrieben werden. Mir ist bekannt, dass ich damit mein Widerrufsrecht mit der Gutschrift verliere.", "en": "I accept the Terms and request that the Notas be credited immediately. I understand that I lose my right of withdrawal once they are credited.", "fr": "J'accepte les CGU et demande que les Notas soient créditées immédiatement. Je sais que je perds mon droit de rétractation dès qu'elles sont créditées.", "it": "Accetto i Termini e chiedo che le Notas vengano accreditate subito. So che perdo il diritto di recesso una volta accreditate.", "pt": "Aceito os Termos e peço que as Notas sejam creditadas imediatamente. Sei que perco o direito de arrependimento assim que forem creditadas."},
    "notas_buy_waiver_required": {"de": "Bitte bestätige die AGB und die sofortige Gutschrift, um fortzufahren.", "en": "Please confirm the Terms and the immediate crediting to continue.", "fr": "Veuillez confirmer les CGU et le crédit immédiat pour continuer.", "it": "Conferma i Termini e l'accredito immediato per continuare.", "pt": "Confirme os Termos e o crédito imediato para continuar."},
    "notas_buy_error": {"de": "Die Zahlung konnte nicht gestartet werden. Bitte versuche es später erneut.", "en": "The payment couldn't be started. Please try again later.", "fr": "Le paiement n'a pas pu démarrer. Veuillez réessayer plus tard.", "it": "Impossibile avviare il pagamento. Riprova più tardi.", "pt": "Não foi possível iniciar o pagamento. Tente novamente mais tarde."},
    "notas_buy_cancelled": {"de": "Zahlung abgebrochen — es wurde nichts berechnet.", "en": "Payment cancelled — nothing was charged.", "fr": "Paiement annulé — rien n'a été débité.", "it": "Pagamento annullato — non è stato addebitato nulla.", "pt": "Pagamento cancelado — nada foi cobrado."},
    "notas_buy_payment_note": {"de": "Die Zahlung erfolgt sicher über Stripe; VokalBoard erhält keine Karten- oder Bankdaten.", "en": "Payment is processed securely by Stripe; VokalBoard never receives your card or bank details.", "fr": "Le paiement est traité en toute sécurité par Stripe ; VokalBoard ne reçoit jamais vos données bancaires.", "it": "Il pagamento è gestito in sicurezza da Stripe; VokalBoard non riceve mai i tuoi dati bancari.", "pt": "O pagamento é processado com segurança pela Stripe; o VokalBoard nunca recebe seus dados de cartão ou banco."},
    "notas_purchase_success": {"de": "Zahlung erhalten — deine Notas erscheinen in wenigen Sekunden. Lade die Seite neu, falls nicht.", "en": "Payment received — your Notas will appear in a few seconds. Reload the page if they don't.", "fr": "Paiement reçu — vos Notas apparaîtront dans quelques secondes. Rechargez la page sinon.", "it": "Pagamento ricevuto — le tue Notas appariranno tra pochi secondi. Ricarica la pagina se non compaiono.", "pt": "Pagamento recebido — suas Notas aparecem em alguns segundos. Recarregue a página se não aparecerem."},
    "notas_reason_listing_posted": {
        "de": "Nota für veröffentlichte Anzeige",
        "en": "Nota for a published listing",
        "fr": "Nota pour une annonce publiée",
        "it": "Nota per un annuncio pubblicato",
        "pt": "Nota por anúncio publicado",
    },
    "notas_redeemed_success": {
        "de": "Eingelöst! Die Änderung ist jetzt aktiv.",
        "en": "Redeemed! The change is now active.",
        "fr": "Échangé ! Le changement est maintenant actif.",
        "it": "Riscattato! La modifica è ora attiva.",
        "pt": "Resgatado! A mudança já está ativa.",
    },
    "notas_item_not_found": {
        "de": "Dieser Prämienartikel existiert nicht.",
        "en": "That reward item doesn't exist.",
        "fr": "Cet article de récompense n'existe pas.",
        "it": "Questo articolo premio non esiste.",
        "pt": "Esse item do catálogo não existe.",
    },
    "notas_insufficient_balance": {
        "de": "Du hast nicht genug Notas für diese Prämie.",
        "en": "You don't have enough Notas for this reward.",
        "fr": "Vous n'avez pas assez de Notas pour cette récompense.",
        "it": "Non hai abbastanza Notas per questo premio.",
        "pt": "Você não tem Notas suficientes para essa recompensa.",
    },
    "profile_highlighted_banner": {
        "de": "Hervorgehobenes Profil",
        "en": "Featured profile",
        "fr": "Profil en vedette",
        "it": "Profilo in evidenza",
        "pt": "Perfil em destaque",
    },

    # --- hall da fama ---------------------------------------------------------
    "hall_da_fama_title": {"de": "Ruhmeshalle", "en": "Hall of Fame", "fr": "Temple de la renommée", "it": "Bacheca della fama", "pt": "Hall da Fama"},
    "hall_da_fama_subtitle": {
        "de": "Nur für dich sichtbar: alle, die sich über deinen Link angemeldet und ihre E-Mail bestätigt haben.",
        "en": "Only visible to you: everyone who signed up through your link and verified their e-mail.",
        "fr": "Visible uniquement par vous : toutes les personnes inscrites via votre lien et ayant vérifié leur e-mail.",
        "it": "Visibile solo a te: tutte le persone che si sono registrate tramite il tuo link e hanno verificato l'e-mail.",
        "pt": "Só você vê: todo mundo que se cadastrou pelo seu link e confirmou o e-mail.",
    },
    "hall_da_fama_empty": {
        "de": "Noch niemand — teile deinen Einladungslink in deinem Profil.",
        "en": "No one yet — share your referral link from your profile.",
        "fr": "Personne pour l'instant — partagez votre lien de parrainage depuis votre profil.",
        "it": "Ancora nessuno — condividi il tuo link di invito dal tuo profilo.",
        "pt": "Ainda ninguém — compartilhe seu link de indicação no seu perfil.",
    },
    "hall_da_fama_share_hint": {
        "de": "Zu deinem Einladungslink →",
        "en": "Go to your referral link →",
        "fr": "Accéder à votre lien de parrainage →",
        "it": "Vai al tuo link di invito →",
        "pt": "Ir para seu link de indicação →",
    },

    # Hall da Fama polish, 19/09/2026: prominent CTA + copy-link button,
    # right on this page (the referral box on /profile still exists too —
    # this is the second, more visible entry point the plan asked for).
    "hall_da_fama_invite_cta": {
        "de": "Lade eine Freundin oder einen Freund ein!",
        "en": "Invite a friend!",
        "fr": "Invitez un(e) ami(e) !",
        "it": "Invita un amico!",
        "pt": "Convidar um amigo!",
    },

    "register_referred_notice": {
        "de": "Du wurdest von einer anderen Person eingeladen — willkommen!",
        "en": "You were invited by someone else — welcome!",
        "fr": "Vous avez été invité(e) par quelqu'un d'autre — bienvenue !",
        "it": "Sei stato invitato da qualcun altro — benvenuto!",
        "pt": "Você foi convidado(a) por outra pessoa — bem-vindo(a)!",
    },

    # Hall da Fama polish, 19/09/2026: named/photo version of the notice
    # above, shown when the referral code resolves to a real account
    # (register_referred_notice stays as the fallback for an unknown/
    # deleted code). {name} is replaced with the referrer's full_name.
    "register_referred_by_notice": {
        "de": "{name} hat dich eingeladen — willkommen!",
        "en": "{name} invited you — welcome!",
        "fr": "{name} vous a invité(e) — bienvenue !",
        "it": "{name} ti ha invitato — benvenuto!",
        "pt": "{name} convidou você — bem-vindo(a)!",
    },

    # Part 2 backlog item 4 (19/09/2026): the remaining five mascot
    # poses, designed with Daniel — see app/mascot_moments.py and
    # app/static/img/mascot/MANIFEST.md for the full writeup.
    "mascot_welcome_balloon": {
        "de": "Willkommen, {name}!",
        "en": "Welcome, {name}!",
        "fr": "Bienvenue, {name} !",
        "it": "Benvenuto/a, {name}!",
        "pt": "Bem-vindo(a), {name}!",
    },
    "mascot_reminder_evaluation": {
        "de": "Hey, {name}! Vergiss nicht, deinen Match zu bewerten!",
        "en": "Hey, {name}! Don't forget to evaluate your Match!",
        "fr": "Hé, {name} ! N'oubliez pas d'évaluer votre Match !",
        "it": "Ehi, {name}! Non dimenticare di valutare il tuo Match!",
        "pt": "Ei, {name}! Não esqueça de avaliar seu Match!",
    },
    "mascot_reminder_invitation": {
        "de": "Hey, {name}! Vergiss nicht, auf deine Einladung zu antworten!",
        "en": "Hey, {name}! Don't forget to respond to your invitation!",
        "fr": "Hé, {name} ! N'oubliez pas de répondre à votre invitation !",
        "it": "Ehi, {name}! Non dimenticare di rispondere al tuo invito!",
        "pt": "Ei, {name}! Não esqueça de responder ao seu convite!",
    },
    "mascot_reminder_profile": {
        "de": "Hey, {name}! Vergiss nicht, dein Profil zu vervollständigen!",
        "en": "Hey, {name}! Don't forget to complete your profile!",
        "fr": "Hé, {name} ! N'oubliez pas de compléter votre profil !",
        "it": "Ehi, {name}! Non dimenticare di completare il tuo profilo!",
        "pt": "Ei, {name}! Não esqueça de completar seu perfil!",
    },

    # Central de Notificações (19/09/2026, task #50) — designed with
    # Daniel via AskUserQuestion, see app/notification_center.py. The
    # dropdown chrome first, then one title_key per notification type
    # (rendered with title_params at display time — see
    # render_notification_title() in app/notification_center.py).
    "notification_center_title": {
        "de": "Benachrichtigungen", "en": "Notifications", "fr": "Notifications",
        "it": "Notifiche", "pt": "Notificações",
    },
    "notification_center_empty": {
        "de": "Noch keine Benachrichtigungen.", "en": "No notifications yet.",
        "fr": "Aucune notification pour l'instant.", "it": "Ancora nessuna notifica.",
        "pt": "Você ainda não tem notificações.",
    },
    "notification_center_mark_all_read": {
        "de": "Alle als gelesen markieren", "en": "Mark all as read",
        "fr": "Tout marquer comme lu", "it": "Segna tutte come lette",
        "pt": "Marcar todas como lidas",
    },
    "notification_profile_incomplete": {
        "de": "Vervollständige dein Profil, um mehr Sichtbarkeit zu bekommen.",
        "en": "Complete your profile to get more visibility.",
        "fr": "Complétez votre profil pour gagner en visibilité.",
        "it": "Completa il tuo profilo per ottenere più visibilità.",
        "pt": "Complete seu perfil para ganhar mais visibilidade.",
    },
    "notification_invitation_received": {
        "de": "{name} hat dir eine Einladung geschickt.",
        "en": "{name} sent you an invitation.",
        "fr": "{name} vous a envoyé une invitation.",
        "it": "{name} ti ha inviato un invito.",
        "pt": "{name} te enviou um convite.",
    },
    "notification_candidatura_received": {
        "de": "{name} hat sich auf deine Anzeige beworben.",
        "en": "{name} applied to your listing.",
        "fr": "{name} a postulé à votre annonce.",
        "it": "{name} si è candidato al tuo annuncio.",
        "pt": "{name} se candidatou ao seu anúncio.",
    },
    "notification_invitation_accepted": {
        "de": "{name} hat deine Einladung angenommen.",
        "en": "{name} accepted your invitation.",
        "fr": "{name} a accepté votre invitation.",
        "it": "{name} ha accettato il tuo invito.",
        "pt": "{name} aceitou seu convite.",
    },
    "notification_invitation_declined": {
        "de": "{name} hat deine Einladung abgelehnt.",
        "en": "{name} declined your invitation.",
        "fr": "{name} a décliné votre invitation.",
        "it": "{name} ha rifiutato il tuo invito.",
        "pt": "{name} recusou seu convite.",
    },
    "notification_match_formed": {
        "de": "Match mit {name} bestätigt!",
        "en": "Match with {name} confirmed!",
        "fr": "Match confirmé avec {name} !",
        "it": "Match con {name} confermato!",
        "pt": "Match com {name} confirmado!",
    },
    "notification_notas_expiring": {
        "de": "{amount} verdiente Notas laufen am {date} ab",
        "en": "{amount} earned Notas expire on {date}",
        "fr": "{amount} Notas gagnées expirent le {date}",
        "it": "{amount} Notas guadagnate scadono il {date}",
        "pt": "{amount} Notas ganhas expiram em {date}",
    },
    "notification_notas_credited": {
        "de": "{amount} Notas gutgeschrieben: {reason}",
        "en": "{amount} Notas credited: {reason}",
        "fr": "{amount} Notas crédités : {reason}",
        "it": "{amount} Notas accreditate: {reason}",
        "pt": "{amount} Notas creditadas: {reason}",
    },
    "notification_loja_redeemed": {
        "de": "\"{item}\" wurde eingelöst.",
        "en": "\"{item}\" was redeemed.",
        "fr": "\"{item}\" a été échangé.",
        "it": "\"{item}\" è stato riscattato.",
        "pt": "\"{item}\" foi resgatado.",
    },
    "notification_unread_messages": {"de": "Du hast {n} ungelesene Nachricht(en).", "en": "You have {n} unread message(s).", "fr": "Vous avez {n} message(s) non lu(s).", "it": "Hai {n} messaggio/i non letto/i.", "pt": "Você tem {n} mensagem(ns) não lida(s)."},
    "notification_new_message": {
        "de": "Neue Nachricht von {name}.",
        "en": "New message from {name}.",
        "fr": "Nouveau message de {name}.",
        "it": "Nuovo messaggio da {name}.",
        "pt": "Nova mensagem de {name}.",
    },
    # Relative-time labels for the dropdown (19/09/2026, matches
    # Daniel's reference screenshot's "20m ago"/"1h ago" style) — see
    # notification_relative_time() in app/notification_center.py.
    "notification_time_now": {
        "de": "gerade eben", "en": "just now", "fr": "à l'instant",
        "it": "proprio ora", "pt": "agora mesmo",
    },
    "notification_time_minutes": {
        "de": "vor {n} Min.", "en": "{n}m ago", "fr": "il y a {n} min",
        "it": "{n} min fa", "pt": "há {n} min",
    },
    "notification_time_hours": {
        "de": "vor {n} Std.", "en": "{n}h ago", "fr": "il y a {n} h",
        "it": "{n} ore fa", "pt": "há {n} h",
    },
    "notification_time_days": {
        "de": "vor {n} Tagen", "en": "{n}d ago", "fr": "il y a {n} j",
        "it": "{n} giorni fa", "pt": "há {n} d",
    },

    # Hall da Fama's rotating incentive line (Piscadinha, wink pose) —
    # one of these is picked at random per page load, right next to
    # the invite box already on the page (see hall_da_fama_invite_cta
    # above). {name} = the viewer's own first/full name.
    "hall_da_fama_incentive_1": {
        "de": "Piep, {name}! Du kannst ein Gratisjahr oder Geschenke bekommen, wenn du Leute einlädst! Probier's aus!",
        "en": "Piep, {name}! You can get a free year or gifts by inviting people! Try it out!",
        "fr": "Piep, {name} ! Vous pouvez obtenir une année gratuite ou des cadeaux en invitant des gens ! Essayez !",
        "it": "Piep, {name}! Puoi ottenere un anno gratis o regali invitando persone! Provaci!",
        "pt": "Piep, {name}! Você pode ganhar um ano grátis ou brindes convidando pessoas! Experimente!",
    },
    "hall_da_fama_incentive_2": {
        "de": "Hey, {name}! Vergiss nicht, Freunde einzuladen und Belohnungen zu verdienen!",
        "en": "Hey, {name}! Don't forget to invite friends and earn rewards!",
        "fr": "Hé, {name} ! N'oubliez pas d'inviter des ami(e)s et de gagner des récompenses !",
        "it": "Ehi, {name}! Non dimenticare di invitare amici e guadagnare ricompense!",
        "pt": "Hey, {name}! Não esqueça de convidar amigos e ganhar recompensas!",
    },
    "hall_da_fama_incentive_3": {
        "de": "{name}, jede eingeladene Person bringt dich näher an dein nächstes Geschenk!",
        "en": "{name}, every person you invite brings you closer to your next gift!",
        "fr": "{name}, chaque personne invitée vous rapproche de votre prochain cadeau !",
        "it": "{name}, ogni persona che inviti ti avvicina al tuo prossimo regalo!",
        "pt": "{name}, cada pessoa convidada te aproxima do seu próximo presente!",
    },
    "hall_da_fama_incentive_4": {
        "de": "Kennst du eine Sängerin, einen Sänger oder Dirigenten? Lade sie ein und sammelt gemeinsam Notas!",
        "en": "Know a singer or conductor who'd love VokalBoard? Invite them and stack up Notas together!",
        "fr": "Vous connaissez un(e) chanteur(se) ou chef(fe) d'orchestre ? Invitez-le/la et cumulez des Notas ensemble !",
        "it": "Conosci un cantante o un direttore d'orchestra? Invitalo e accumulate Notas insieme!",
        "pt": "Conhece um cantor ou maestro? Convide e acumulem Notas juntos!",
    },

    "listing_created_success": {
        "de": "Anzeige veröffentlicht!",
        "en": "Listing published!",
        "fr": "Annonce publiée !",
        "it": "Annuncio pubblicato!",
        "pt": "Anúncio publicado!",
    },

    "error_404_bird_alt": {
        "de": "Ein verwirrter Tangará, der sich verflogen hat",
        "en": "A confused Tangará who's lost its way",
        "fr": "Un Tangará confus qui a perdu son chemin",
        "it": "Un Tangará confuso che ha perso la strada",
        "pt": "Um Tangará confuso que se perdeu",
    },

    # --- bloquear pessoas ------------------------------------------------------
    "block_user_button": {"de": "Blockieren", "en": "Block", "fr": "Bloquer", "it": "Blocca", "pt": "Bloquear"},
    "unblock_user_button": {"de": "Blockierung aufheben", "en": "Unblock", "fr": "Débloquer", "it": "Sblocca", "pt": "Desbloquear"},
    "block_user_reason_label": {"de": "Grund (optional)", "en": "Reason (optional)", "fr": "Raison (facultatif)", "it": "Motivo (facoltativo)", "pt": "Motivo (opcional)"},
    "block_user_reason_placeholder": {"de": "Warum möchtest du diese Person blockieren?", "en": "Why are you blocking this person?", "fr": "Pourquoi bloquez-vous cette personne ?", "it": "Perché vuoi bloccare questa persona?", "pt": "Por que você quer bloquear esta pessoa?"},
    "block_user_confirm": {"de": "Person blockieren", "en": "Block this person", "fr": "Bloquer cette personne", "it": "Blocca questa persona", "pt": "Bloquear esta pessoa"},
    "blocked_users_title": {"de": "Blockierte Personen", "en": "Blocked people", "fr": "Personnes bloquées", "it": "Persone bloccate", "pt": "Pessoas bloqueadas"},
    "blocked_users_empty": {"de": "Du hast niemanden blockiert.", "en": "You haven't blocked anyone.", "fr": "Vous n'avez bloqué personne.", "it": "Non hai bloccato nessuno.", "pt": "Você não bloqueou ninguém."},
    "blocked_users_help": {
        "de": "Blockierte Personen können dir keine Nachrichten mehr schicken (und du ihnen auch nicht), ihre Anzeigen werden dir nicht mehr angezeigt, und ihr könnt euch gegenseitig nicht mehr die Profile ansehen.",
        "en": "Blocked people can no longer message you (or you them), their listings are hidden from your board, and neither of you can view the other's profile anymore.",
        "fr": "Les personnes bloquées ne peuvent plus vous envoyer de messages (ni vous à elles), leurs annonces vous sont masquées, et vous ne pouvez plus consulter mutuellement vos profils.",
        "it": "Le persone bloccate non possono più scriverti (né tu a loro), i loro annunci vengono nascosti dalla tua bacheca, e nessuno dei due può più vedere il profilo dell'altro.",
        "pt": "Pessoas bloqueadas não podem mais te enviar mensagens (nem você a elas), os anúncios delas ficam ocultos no seu mural, e nenhum dos dois pode mais ver o perfil do outro.",
    },
    "profile_unavailable_blocked": {
        "de": "Dieses Profil ist nicht verfügbar.",
        "en": "This profile is not available.",
        "fr": "Ce profil n'est pas disponible.",
        "it": "Questo profilo non è disponibile.",
        "pt": "Este perfil não está disponível.",
    },

    # --- report listing -----------------------------------------------------
    "report_listing_button": {"de": "Anzeige melden", "en": "Report listing", "fr": "Signaler l'annonce", "it": "Segnala annuncio", "pt": "Denunciar anúncio"},
    "report_listing_reason_label": {"de": "Warum meldest du diese Anzeige?", "en": "Why are you reporting this listing?", "fr": "Pourquoi signalez-vous cette annonce ?", "it": "Perché stai segnalando questo annuncio?", "pt": "Por que você está denunciando este anúncio?"},
    "report_listing_reason_placeholder": {
        "de": "Bitte kurz beschreiben (mind. 10 Zeichen)…",
        "en": "Please briefly describe why (at least 10 characters)…",
        "fr": "Merci de décrire brièvement (au moins 10 caractères)…",
        "it": "Descrivi brevemente il motivo (almeno 10 caratteri)…",
        "pt": "Descreva brevemente o motivo (mín. 10 caracteres)…",
    },
    "report_listing_reason_help": {
        "de": "Deine Meldung wird gespeichert und vom Betreiber des Portals geprüft.",
        "en": "Your report is recorded and reviewed by the site operator.",
        "fr": "Votre signalement est enregistré et examiné par l'exploitant du site.",
        "it": "La tua segnalazione viene registrata ed esaminata dal gestore del sito.",
        "pt": "Sua denúncia é registrada e analisada pelo responsável pelo site.",
    },
    "report_listing_confirm": {"de": "Meldung senden", "en": "Send report", "fr": "Envoyer le signalement", "it": "Invia segnalazione", "pt": "Enviar denúncia"},
    "report_listing_sent": {"de": "Danke, deine Meldung wurde gesendet.", "en": "Thanks, your report has been sent.", "fr": "Merci, votre signalement a été envoyé.", "it": "Grazie, la tua segnalazione è stata inviata.", "pt": "Obrigado, sua denúncia foi enviada."},
    "report_listing_already": {"de": "Du hast diese Anzeige bereits gemeldet.", "en": "You've already reported this listing.", "fr": "Vous avez déjà signalé cette annonce.", "it": "Hai già segnalato questo annuncio.", "pt": "Você já denunciou este anúncio."},

    # --- footer: impressum / code of conduct -------------------------------
    "footer_impressum": {"de": "Impressum", "en": "Legal notice", "fr": "Mentions légales", "it": "Note legali", "pt": "Aviso legal"},
    "footer_privacy": {"de": "Datenschutz", "en": "Privacy policy", "fr": "Confidentialité", "it": "Privacy", "pt": "Privacidade"},
    "footer_conduct": {"de": "Verhaltenskodex", "en": "Code of conduct", "fr": "Code de conduite", "it": "Codice di condotta", "pt": "Código de conduta"},

    # --- Impressum -------------------------------------------------------------
    "impressum_title": {"de": "Impressum", "en": "Legal notice (Impressum)", "fr": "Mentions légales", "it": "Note legali", "pt": "Aviso legal"},
    "impressum_operated_from_notice": {
        "de": "Dieses Portal wird von Brasilien aus betrieben.",
        "en": "This site is operated from Brazil.",
        "fr": "Ce site est exploité depuis le Brésil.",
        "it": "Questo sito è gestito dal Brasile.",
        "pt": "Este site é operado a partir do Brasil.",
    },

    # --- Datenschutzerklärung ---------------------------------------------------
    "privacy_title": {"de": "Datenschutzerklärung", "en": "Privacy policy", "fr": "Politique de confidentialité", "it": "Informativa sulla privacy", "pt": "Política de privacidade"},
    "privacy_disclaimer": {
        "de": "Diese Erklärung ist eine solide Vorlage, ersetzt aber keine juristische Prüfung — insbesondere Abschnitt 4 (internationale Datenübermittlung) muss noch bestätigt werden, bevor die Seite echte Nutzerdaten verarbeitet.",
        "en": "This notice is a solid template but does not replace legal review — section 4 (international data transfer) in particular still needs confirmation before the site processes real users' data.",
        "fr": "Cette notice est un modèle solide mais ne remplace pas un contrôle juridique — la section 4 (transfert international de données) en particulier doit encore être confirmée avant que le site ne traite de vraies données d'utilisateurs.",
        "it": "Questa informativa è un modello solido ma non sostituisce una revisione legale — in particolare la sezione 4 (trasferimento internazionale dei dati) deve ancora essere confermata prima che il sito tratti dati reali degli utenti.",
        "pt": "Este texto é um modelo sólido, mas não substitui revisão jurídica — a seção 4 (transferência internacional de dados) em especial ainda precisa ser confirmada antes de o site processar dados reais de usuários.",
    },

    # --- code of conduct -----------------------------------------------------
    "conduct_title": {"de": "Verhaltenskodex", "en": "Code of conduct", "fr": "Code de conduite", "it": "Codice di condotta", "pt": "Código de conduta"},
    "conduct_intro": {
        "de": "VokalBoard ist ein Ort, an dem sich Sänger(innen) und Dirigent(innen) respektvoll und professionell begegnen sollen. Diese Regeln gelten für alle.",
        "en": "VokalBoard is meant to be a place where singers and conductors meet respectfully and professionally. These rules apply to everyone.",
        "fr": "VokalBoard se veut un lieu où chanteurs et chefs de chœur se rencontrent avec respect et professionnalisme. Ces règles s'appliquent à tous.",
        "it": "VokalBoard vuole essere un luogo in cui cantanti e direttori si incontrano con rispetto e professionalità. Queste regole valgono per tutti.",
        "pt": "O VokalBoard quer ser um lugar onde cantores e regentes se encontram com respeito e profissionalismo. Estas regras valem para todos.",
    },

    # --- badges (light gamification, no ranking) -------------------------------
    "badges_title": {"de": "Auszeichnungen", "en": "Badges", "fr": "Distinctions", "it": "Distintivi", "pt": "Conquistas"},
    "badges_help": {
        "de": "Kleine Erinnerungen an das, was du schon erreicht hast — kein Ranking, kein Vergleich mit anderen.",
        "en": "A few reminders of what you've already achieved — no ranking, no comparison with anyone else.",
        "fr": "Quelques rappels de ce que vous avez déjà accompli — pas de classement, pas de comparaison avec les autres.",
        "it": "Piccoli promemoria di ciò che hai già raggiunto — nessuna classifica, nessun confronto con gli altri.",
        "pt": "Pequenos lembretes do que você já conquistou — sem ranking, sem comparação com outras pessoas.",
    },
    "badge_referral_label": {"de": "Botschafter(in)", "en": "Ambassador", "fr": "Ambassadeur/rice", "it": "Ambasciatore/rice", "pt": "Embaixador(a)"},
    "badge_referral_desc": {"de": "Hat mindestens eine Person eingeladen.", "en": "Invited at least one person.", "fr": "A invité au moins une personne.", "it": "Ha invitato almeno una persona.", "pt": "Convidou pelo menos uma pessoa."},
    "badge_listing_label": {"de": "Erste Anzeige", "en": "First listing", "fr": "Première annonce", "it": "Primo annuncio", "pt": "Primeiro anúncio"},
    "badge_listing_desc": {"de": "Hat mindestens eine Anzeige veröffentlicht.", "en": "Posted at least one listing.", "fr": "A publié au moins une annonce.", "it": "Ha pubblicato almeno un annuncio.", "pt": "Publicou pelo menos um anúncio."},
    "badge_contact_label": {"de": "Kontaktfreudig", "en": "Reached out", "fr": "Contact établi", "it": "Ha fatto rete", "pt": "Fez contato"},
    "badge_contact_desc": {"de": "Hat mindestens eine Nachricht verschickt.", "en": "Sent at least one message.", "fr": "A envoyé au moins un message.", "it": "Ha inviato almeno un messaggio.", "pt": "Enviou pelo menos uma mensagem."},
    "badge_profile_complete_label": {"de": "Profil komplett", "en": "Complete profile", "fr": "Profil complet", "it": "Profilo completo", "pt": "Perfil completo"},
    "badge_profile_complete_desc": {"de": "Profil zu 100% ausgefüllt.", "en": "Profile 100% complete.", "fr": "Profil complété à 100 %.", "it": "Profilo completato al 100%.", "pt": "Perfil 100% preenchido."},
    "badge_views_label": {"de": "Gefragt", "en": "In demand", "fr": "Très demandé(e)", "it": "Richiesto/a", "pt": "Em alta"},
    "badge_views_desc": {
        "de": "Profil wurde oft besucht (genaue Zahl bleibt privat).",
        "en": "Profile has been visited a lot (the exact number stays private).",
        "fr": "Le profil a été consulté de nombreuses fois (le nombre exact reste privé).",
        "it": "Il profilo è stato visitato molte volte (il numero esatto resta privato).",
        "pt": "O perfil foi bastante visitado (o número exato continua privado).",
    },
    "badge_fast_response_label": {"de": "Schnelle Antwort", "en": "Fast response", "fr": "Réponse rapide", "it": "Risposta rapida", "pt": "Resposta rápida"},
    "badge_fast_response_desc": {
        "de": "Hat mindestens einmal innerhalb von 24 Stunden geantwortet.",
        "en": "Replied to a message within 24 hours at least once.",
        "fr": "A répondu à un message en moins de 24 heures au moins une fois.",
        "it": "Ha risposto a un messaggio entro 24 ore almeno una volta.",
        "pt": "Respondeu a uma mensagem em até 24 horas pelo menos uma vez.",
    },
    "badge_anniversary_label": {"de": "Jahrestag", "en": "Anniversary", "fr": "Anniversaire", "it": "Anniversario", "pt": "Aniversário"},
    "badge_anniversary_desc": {"de": "Ist seit mindestens einem Jahr dabei.", "en": "Has been a member for at least a year.", "fr": "Membre depuis au moins un an.", "it": "Membro da almeno un anno.", "pt": "É membro há pelo menos um ano."},

    # --- aviso de caixa de spam (home) ----------------------------------------
    "spam_notice_text": {
        "de": "Tipp: Schau ab und zu in deinem Spam-Ordner nach und markiere E-Mails von uns als \"kein Spam\", damit dir keine Nachrichten-Alarme oder Antworten entgehen.",
        "en": "Tip: check your spam folder every now and then and mark emails from us as \"not spam\", so you don't miss message alerts or replies.",
        "fr": "Astuce : vérifiez de temps en temps votre dossier spam et marquez nos e-mails comme « non spam », pour ne manquer aucune alerte ou réponse.",
        "it": "Consiglio: controlla ogni tanto la cartella spam e contrassegna le nostre email come \"non spam\", per non perdere avvisi o risposte.",
        "pt": "Dica: dê uma olhada de vez em quando na sua caixa de spam e marque nossos e-mails como \"não é spam\", para não perder alertas de mensagens ou respostas.",
    },
    "spam_notice_dismiss": {"de": "Schließen", "en": "Dismiss", "fr": "Fermer", "it": "Chiudi", "pt": "Fechar"},

    # --- small inline bits that used to be hardcoded de/en ternaries in
    # templates (character-count suffix, "public view" link, year count) ---
    "chars_max_suffix": {"de": "Zeichen max.", "en": "characters max.", "fr": "caractères max.", "it": "caratteri max.", "pt": "caracteres no máx."},
    "public_view_label": {"de": "öffentliche Ansicht", "en": "public view", "fr": "vue publique", "it": "vista pubblica", "pt": "visão pública"},
    "year_singular": {"de": "Jahr", "en": "year", "fr": "an", "it": "anno", "pt": "ano"},
    "year_plural": {"de": "Jahre", "en": "years", "fr": "ans", "it": "anni", "pt": "anos"},

    # --- Buscar pessoas (people search) -----------------------------------
    "nav_search_people": {"de": "Personen suchen", "en": "Search people", "fr": "Rechercher des personnes", "it": "Cerca persone", "pt": "Buscar pessoas"},
    # "Buscar para este anúncio" (19/09/2026) — button on a listing card
    # in My Listings that jumps to /people pre-filtered for that listing.
    "listing_search_for_this_button": {
        "de": "Für diese Anzeige suchen", "en": "Search for this listing",
        "fr": "Rechercher pour cette annonce", "it": "Cerca per questo annuncio", "pt": "Buscar para este anúncio",
    },
    # Search People (19/09/2026) — shortcut shown only when the viewer
    # has at least one active seeking_* listing; sends them to My
    # Listings where the button above lives.
    "search_people_for_my_listing_link": {
        "de": "Für meine Anzeige suchen", "en": "Search for my listing",
        "fr": "Rechercher pour mon annonce", "it": "Cerca per il mio annuncio", "pt": "Buscar para meu anúncio",
    },
    "search_people_title": {"de": "Personen suchen", "en": "Search people", "fr": "Rechercher des personnes", "it": "Cerca persone", "pt": "Buscar pessoas"},
    "search_people_subtitle": {
        "de": "Finde Sänger(innen) und Dirigent(innen) direkt — nach Land, Region, Stadt oder Stimmlage.",
        "en": "Find singers and conductors directly — by country, state, city, or voice type.",
        "fr": "Trouvez directement des chanteurs et des chefs de chœur — par pays, région, ville ou tessiture.",
        "it": "Trova direttamente cantanti e direttori — per paese, regione, città o tessitura.",
        "pt": "Encontre cantores e regentes diretamente — por país, estado, cidade ou tipo de voz.",
    },
    "filter_all_roles": {"de": "Sänger(in) oder Dirigent(in)", "en": "Singer or conductor", "fr": "Chanteur ou chef de chœur", "it": "Cantante o direttore", "pt": "Cantor(a) ou regente"},
    "search_people_empty": {
        "de": "Niemand gefunden mit diesen Filtern.",
        "en": "No one found with these filters.",
        "fr": "Personne trouvé avec ces filtres.",
        "it": "Nessuno trovato con questi filtri.",
        "pt": "Ninguém encontrado com esses filtros.",
    },
    "search_people_view_profile": {"de": "Profil ansehen →", "en": "View profile →", "fr": "Voir le profil →", "it": "Vedi profilo →", "pt": "Ver perfil →"},
    "appear_in_search_label": {
        "de": "In der Personensuche erscheinen",
        "en": "Appear in people search",
        "fr": "Apparaître dans la recherche de personnes",
        "it": "Apparire nella ricerca di persone",
        "pt": "Aparecer na busca de pessoas",
    },
    "appear_in_search_help": {
        "de": "Wenn aktiviert, können andere Mitglieder dich über \"Personen suchen\" finden (Name, Stadt, Stimmlage). Betrifft nicht deine Anzeigen — die sind immer sichtbar.",
        "en": "When on, other members can find you through \"Search people\" (name, city, voice type). Doesn't affect your listings — those are always visible.",
        "fr": "Si activé, les autres membres peuvent vous trouver via « Rechercher des personnes » (nom, ville, tessiture). N'affecte pas vos annonces — elles restent toujours visibles.",
        "it": "Se attivo, gli altri membri possono trovarti tramite \"Cerca persone\" (nome, città, tessitura). Non riguarda i tuoi annunci — quelli sono sempre visibili.",
        "pt": "Quando ativado, outros membros podem te encontrar por \"Buscar pessoas\" (nome, cidade, tipo de voz). Não afeta seus anúncios — esses sempre ficam visíveis.",
    },
    "profile_share_button": {"de": "Profil teilen", "en": "Share profile", "fr": "Partager le profil", "it": "Condividi profilo", "pt": "Compartilhar"},
    "profile_edit_link": {"de": "Profil bearbeiten", "en": "Edit profile", "fr": "Modifier le profil", "it": "Modifica profilo", "pt": "Editar perfil"},
    "profile_edit_slug_hint": {"de": "Diesen Link bearbeiten", "en": "Edit this link", "fr": "Modifier ce lien", "it": "Modifica questo link", "pt": "Editar este link"},
    "profile_internal_id_label": {"de": "Interne ID", "en": "Internal ID", "fr": "ID interne", "it": "ID interno", "pt": "ID interno"},
    "profile_view_as_public": {
        "de": "So sehen es alle anderen",
        "en": "See what everyone else sees",
        "fr": "Voir ce que tout le monde voit",
        "it": "Guarda come lo vedono gli altri",
        "pt": "Ver como todo mundo vê",
    },
    "profile_slug_label": {"de": "Individueller Profillink", "en": "Custom profile link", "fr": "Lien de profil personnalisé", "it": "Link profilo personalizzato", "pt": "Link de perfil personalizado"},
    "profile_slug_help": {
        "de": "Nur Kleinbuchstaben, Zahlen und Bindestriche. Leer lassen, um /users/{id} zu behalten. Deine interne ID ({id}) bleibt in jedem Fall bestehen.",
        "en": "Lowercase letters, numbers, and hyphens only. Leave blank to keep /users/{id}. Your internal ID ({id}) stays the same either way.",
        "fr": "Lettres minuscules, chiffres et tirets uniquement. Laissez vide pour garder /users/{id}. Votre ID interne ({id}) reste inchangé dans tous les cas.",
        "it": "Solo lettere minuscole, numeri e trattini. Lascia vuoto per mantenere /users/{id}. Il tuo ID interno ({id}) resta comunque invariato.",
        "pt": "Somente letras minúsculas, números e hífens. Deixe em branco para manter /users/{id}. Seu ID interno ({id}) continua o mesmo de qualquer forma.",
    },
    "profile_slug_taken": {
        "de": "Dieser Link ist bereits vergeben — bitte wähle einen anderen.",
        "en": "This link is already taken — please choose another one.",
        "fr": "Ce lien est déjà utilisé — veuillez en choisir un autre.",
        "it": "Questo link è già in uso — scegline un altro.",
        "pt": "Este link já está em uso — escolha outro.",
    },
    "profile_slug_invalid": {
        "de": "Nur Kleinbuchstaben, Zahlen und Bindestriche erlaubt (3–60 Zeichen).",
        "en": "Only lowercase letters, numbers, and hyphens allowed (3-60 characters).",
        "fr": "Seuls les lettres minuscules, les chiffres et les tirets sont autorisés (3 à 60 caractères).",
        "it": "Sono ammessi solo lettere minuscole, numeri e trattini (3-60 caratteri).",
        "pt": "Somente letras minúsculas, números e hífens são permitidos (3 a 60 caracteres).",
    },

    # "Fale conosco" + "Reportar erro" — P6 close-out (19/09/2026).
    # See app/routers/support_routes.py and app/support_tickets.py.
    "footer_contact": {"en": "Contact us", "pt": "Fale conosco", "de": "Kontakt", "fr": "Nous contacter", "it": "Contattaci"},
    "contact_page_title": {"en": "Contact us", "pt": "Fale conosco", "de": "Kontakt", "fr": "Nous contacter", "it": "Contattaci"},
    "contact_page_help": {"en": "Send us a message — we'll get back to you by email.", "pt": "Mande uma mensagem — responderemos por e-mail.", "de": "Schick uns eine Nachricht — wir antworten dir per E-Mail.", "fr": "Envoyez-nous un message — nous vous répondrons par e-mail.", "it": "Mandaci un messaggio — ti risponderemo via e-mail."},
    "contact_subject_label": {"en": "Subject (optional)", "pt": "Assunto (opcional)", "de": "Betreff (optional)", "fr": "Objet (facultatif)", "it": "Oggetto (facoltativo)"},
    "contact_subject_placeholder": {"en": "What's this about?", "pt": "Sobre o que é?", "de": "Worum geht's?", "fr": "De quoi s'agit-il ?", "it": "Di cosa si tratta?"},
    "contact_description_label": {"en": "Message", "pt": "Mensagem", "de": "Nachricht", "fr": "Message", "it": "Messaggio"},
    "contact_description_placeholder": {"en": "Tell us what's going on…", "pt": "Conte o que está acontecendo…", "de": "Erzähl uns, worum es geht…", "fr": "Dites-nous ce qui se passe…", "it": "Raccontaci cosa sta succedendo…"},
    "contact_submit": {"en": "Send message", "pt": "Enviar mensagem", "de": "Nachricht senden", "fr": "Envoyer le message", "it": "Invia messaggio"},
    "contact_sent": {"en": "Message sent — we'll reply by email.", "pt": "Mensagem enviada — responderemos por e-mail.", "de": "Nachricht gesendet — wir antworten per E-Mail.", "fr": "Message envoyé — nous répondrons par e-mail.", "it": "Messaggio inviato — risponderemo via e-mail."},
    "contact_error_short": {"en": "Write at least 10 characters.", "pt": "Escreva pelo menos 10 caracteres.", "de": "Schreib mindestens 10 Zeichen.", "fr": "Écrivez au moins 10 caractères.", "it": "Scrivi almeno 10 caratteri."},
    "bug_report_button": {"en": "Report a bug", "pt": "Reportar erro", "de": "Fehler melden", "fr": "Signaler un bug", "it": "Segnala un errore"},
    "bug_report_title": {"en": "Report a bug", "pt": "Reportar erro", "de": "Fehler melden", "fr": "Signaler un bug", "it": "Segnala un errore"},
    "bug_report_help": {"en": "We'll automatically include this page's address, so you only need to describe what went wrong.", "pt": "Vamos incluir automaticamente o endereço desta página — você só precisa descrever o que deu errado.", "de": "Wir fügen automatisch die Adresse dieser Seite hinzu — beschreibe einfach, was schiefgelaufen ist.", "fr": "Nous ajouterons automatiquement l'adresse de cette page — décrivez simplement ce qui n'a pas fonctionné.", "it": "Includeremo automaticamente l'indirizzo di questa pagina — descrivi solo cosa è andato storto."},
    "bug_report_description_label": {"en": "What went wrong?", "pt": "O que deu errado?", "de": "Was ist schiefgelaufen?", "fr": "Qu'est-ce qui n'a pas fonctionné ?", "it": "Cosa è andato storto?"},
    "bug_report_description_placeholder": {"en": "Describe what happened, and what you expected instead…", "pt": "Descreva o que aconteceu e o que você esperava…", "de": "Beschreibe, was passiert ist, und was du stattdessen erwartet hast…", "fr": "Décrivez ce qui s'est passé et ce à quoi vous vous attendiez…", "it": "Descrivi cosa è successo e cosa ti aspettavi invece…"},
    "bug_report_cancel": {"en": "Cancel", "pt": "Cancelar", "de": "Abbrechen", "fr": "Annuler", "it": "Annulla"},
    "bug_report_submit": {"en": "Send report", "pt": "Enviar relato", "de": "Bericht senden", "fr": "Envoyer le signalement", "it": "Invia segnalazione"},
    "bug_report_sent": {"en": "Thanks — we received your report.", "pt": "Obrigado — recebemos seu relato.", "de": "Danke — wir haben deinen Bericht erhalten.", "fr": "Merci — nous avons bien reçu votre signalement.", "it": "Grazie — abbiamo ricevuto la tua segnalazione."},

    # P2 cluster (19/09/2026): Profile Wizard, CV export, solo/choir
    # works cards — see AI_CHANGELOG.md for the full writeup.
    "wizard_title": {"en": "Complete your profile", "pt": "Complete seu perfil", "de": "Profil vervollständigen", "fr": "Complétez votre profil", "it": "Completa il tuo profilo"},
    "wizard_intro": {"en": "A few quick steps so people can find and recognize you. You can always finish this later from your profile.", "pt": "Alguns passos rápidos para que as pessoas te encontrem e reconheçam. Você sempre pode terminar isso depois, no seu perfil.", "de": "Ein paar kurze Schritte, damit dich andere finden und erkennen. Du kannst das jederzeit später in deinem Profil fertigstellen.", "fr": "Quelques étapes rapides pour que les autres puissent vous trouver et vous reconnaître. Vous pouvez toujours terminer cela plus tard depuis votre profil.", "it": "Pochi passaggi veloci per farti trovare e riconoscere. Puoi sempre completarlo più tardi dal tuo profilo."},
    "wizard_step_photo_location": {"en": "Photo & location", "pt": "Foto e localização", "de": "Foto & Standort", "fr": "Photo et localisation", "it": "Foto e posizione"},
    "wizard_back": {"en": "Back", "pt": "Voltar", "de": "Zurück", "fr": "Retour", "it": "Indietro"},
    "wizard_next": {"en": "Next", "pt": "Próximo", "de": "Weiter", "fr": "Suivant", "it": "Avanti"},
    "wizard_skip": {"en": "Skip for now", "pt": "Pular por agora", "de": "Vorerst überspringen", "fr": "Passer pour l'instant", "it": "Salta per ora"},
    "wizard_finish": {"en": "Save & finish", "pt": "Salvar e concluir", "de": "Speichern & fertig", "fr": "Enregistrer et terminer", "it": "Salva e termina"},

    "cv_export_link": {"en": "Download CV (PDF)", "pt": "Baixar CV (PDF)", "de": "Lebenslauf herunterladen (PDF)", "fr": "Télécharger le CV (PDF)", "it": "Scarica il CV (PDF)"},

    "works_section_title": {"en": "My repertoire (solo & choir)", "pt": "Meu repertório (solo e coral)", "de": "Mein Repertoire (Solo & Chor)", "fr": "Mon répertoire (solo et chœur)", "it": "Il mio repertorio (solo e coro)"},
    "works_section_help": {"en": "Add pieces you want to show on your public profile, tagged as solo or choir work — a link to a video or audio recording is optional.", "pt": "Adicione peças que você quer mostrar no seu perfil público, marcadas como trabalho solo ou coral — um link para vídeo ou áudio é opcional.", "de": "Füge Stücke hinzu, die du auf deinem öffentlichen Profil zeigen möchtest, markiert als Solo- oder Chorwerk — ein Link zu Video oder Audio ist optional.", "fr": "Ajoutez des morceaux que vous souhaitez montrer sur votre profil public, marqués comme travail solo ou chorale — un lien vers une vidéo ou un enregistrement audio est facultatif.", "it": "Aggiungi brani che vuoi mostrare sul tuo profilo pubblico, contrassegnati come lavoro solista o corale — un link a un video o una registrazione audio è facoltativo."},
    "works_empty": {"en": "No works added yet.", "pt": "Nenhuma obra adicionada ainda.", "de": "Noch keine Werke hinzugefügt.", "fr": "Aucune œuvre ajoutée pour le moment.", "it": "Nessuna opera ancora aggiunta."},
    "works_max_reached": {"en": "You've reached the maximum number of works.", "pt": "Você atingiu o número máximo de obras.", "de": "Du hast die maximale Anzahl an Werken erreicht.", "fr": "Vous avez atteint le nombre maximum d'œuvres.", "it": "Hai raggiunto il numero massimo di opere."},
    "work_title_label": {"en": "Title", "pt": "Título", "de": "Titel", "fr": "Titre", "it": "Titolo"},
    "work_composer_label": {"en": "Composer", "pt": "Compositor", "de": "Komponist", "fr": "Compositeur", "it": "Compositore"},
    "work_category_label": {"en": "Category", "pt": "Categoria", "de": "Kategorie", "fr": "Catégorie", "it": "Categoria"},
    "work_category_solo": {"en": "Solo", "pt": "Solo", "de": "Solo", "fr": "Solo", "it": "Solo"},
    "work_category_choir": {"en": "Choir", "pt": "Coral", "de": "Chor", "fr": "Chœur", "it": "Coro"},
    "work_video_url_label": {"en": "Video link (optional)", "pt": "Link de vídeo (opcional)", "de": "Video-Link (optional)", "fr": "Lien vidéo (facultatif)", "it": "Link video (facoltativo)"},
    "work_audio_url_label": {"en": "Audio link (optional)", "pt": "Link de áudio (opcional)", "de": "Audio-Link (optional)", "fr": "Lien audio (facultatif)", "it": "Link audio (facoltativo)"},
    "work_add_button": {"en": "Add work", "pt": "Adicionar obra", "de": "Werk hinzufügen", "fr": "Ajouter une œuvre", "it": "Aggiungi opera"},
    "work_delete_button": {"en": "Remove", "pt": "Remover", "de": "Entfernen", "fr": "Supprimer", "it": "Rimuovi"},
    "work_watch_link": {"en": "Watch", "pt": "Assistir", "de": "Ansehen", "fr": "Regarder", "it": "Guarda"},
    "works_solo_title": {"en": "Solo repertoire", "pt": "Repertório solo", "de": "Solo-Repertoire", "fr": "Répertoire solo", "it": "Repertorio solista"},
    "works_choir_title": {"en": "Choir repertoire", "pt": "Repertório coral", "de": "Chor-Repertoire", "fr": "Répertoire choral", "it": "Repertorio corale"},
    "work_title_required": {"en": "Please enter a title for the work.", "pt": "Informe um título para a obra.", "de": "Bitte gib einen Titel für das Werk an.", "fr": "Veuillez indiquer un titre pour l'œuvre.", "it": "Inserisci un titolo per l'opera."},
    "work_invalid_category": {"en": "Please choose solo or choir.", "pt": "Escolha solo ou coral.", "de": "Bitte wähle Solo oder Chor.", "fr": "Veuillez choisir solo ou chœur.", "it": "Scegli solo o coro."},
    "work_max_works_reached": {"en": "You've reached the maximum number of works.", "pt": "Você atingiu o número máximo de obras.", "de": "Du hast die maximale Anzahl an Werken erreicht.", "fr": "Vous avez atteint le nombre maximum d'œuvres.", "it": "Hai raggiunto il numero massimo di opere."},
}


# Languages beyond the core five (zh/ko/ro/...) come from app/locales/<lang>.json
# — see app/i18n_locales.py and docs/I18N.md. Missing keys fall back to English.
from app.i18n_locales import merge_into as _merge_external_locales  # noqa: E402

_merge_external_locales(TRANSLATIONS)


def translate(key: str, lang: str) -> str:
    """Returns a translation, using English while a new locale is completed."""
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    return entry.get(lang) or entry.get("en") or entry.get(DEFAULT_LANGUAGE) or key

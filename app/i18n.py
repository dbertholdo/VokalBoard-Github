"""
Simple internationalization (i18n), with no external dependencies.

Each UI string has a key (e.g. "nav_login"), and each key has a
translation in German ("de") and English ("en"). The default language
is German, since the site's main audience is in Germany.

How it works in practice:
- `LanguageMiddleware` (in app/main.py) decides the request's language
  (querystring ?lang=.. > cookie > default "de") and stores it in
  `request.state.lang`.
- `app/render.py` injects a `t(key)` function into every template's
  context, which simply looks up this dictionary.
"""

SUPPORTED_LANGUAGES = ["de", "en"]
DEFAULT_LANGUAGE = "de"

TRANSLATIONS: dict[str, dict[str, str]] = {
    # --- navigation / layout -------------------------------------------------
    "nav_home": {"de": "Start", "en": "Home"},
    "nav_my_listings": {"de": "Meine Anzeigen", "en": "My listings"},
    "nav_favorites": {"de": "Favoriten", "en": "Favorites"},
    "nav_board": {"de": "Jobs", "en": "Jobs"},
    "nav_menu_toggle": {"de": "Menü", "en": "Menu"},
    "nav_profile": {"de": "Mein Profil", "en": "My profile"},
    "nav_login": {"de": "Anmelden", "en": "Log in"},
    "nav_register": {"de": "Registrieren", "en": "Sign up"},
    "nav_logout": {"de": "Abmelden", "en": "Log out"},
    "role_singer": {"de": "Sänger(in)", "en": "Singer"},
    "role_conductor": {"de": "Dirigent(in)", "en": "Conductor"},
    "footer_text": {
        "de": "Lernprojekt — verbindet Sänger(innen) und Dirigent(innen) in Deutschland.",
        "en": "Learning project — connecting singers and conductors in Germany.",
    },

    # --- home (boas-vindas + matches) ----------------------------------------
    "home_title": {"de": "Schwarzes Brett", "en": "Bulletin board"},
    "home_welcome": {"de": "Willkommen, {name}", "en": "Welcome, {name}"},
    "posts_feed_title": {"de": "Neuigkeiten", "en": "Announcements"},
    "post_read_more": {"de": "Weiterlesen", "en": "Read more"},
    "post_unpublished_notice": {"de": "Entwurf / nicht veröffentlicht — nur für Admins sichtbar", "en": "Draft / unpublished — visible to admins only"},
    "home_matches_title": {"de": "Das könnte zu dir passen", "en": "Matches for your profile"},
    "home_matches_subtitle": {
        "de": "Bis zu 5 Anzeigen, ausgewählt nach deiner Stimmlage/Rolle und Stadt.",
        "en": "Up to 5 listings, picked to match your voice type/role and city.",
    },
    "home_matches_empty": {
        "de": "Gerade nichts Passendes — wirf einen Blick auf die ganze Jobbörse.",
        "en": "Nothing matching right now — take a look at the full board.",
    },
    "home_anon_title": {"de": "Sänger(innen) und Dirigent(innen) finden sich hier", "en": "Where singers and conductors find each other"},
    "home_anon_subtitle": {
        "de": "Ein Schwarzes Brett für Gesuche und Angebote in Deutschland, Österreich und der Schweiz.",
        "en": "A bulletin board for job postings and availability across Germany, Austria, and Switzerland.",
    },
    "home_teaser_title": {"de": "Neueste Anzeigen", "en": "Latest listings"},
    "home_cta_register": {"de": "Kostenlos registrieren", "en": "Sign up for free"},
    "home_cta_login": {"de": "Anmelden", "en": "Log in"},
    "home_cta_browse": {"de": "Alle Anzeigen ansehen", "en": "View all listings"},

    # --- /board (quadro de avisos completo, com filtros) ---------------------
    "board_title": {"de": "Jobbörse", "en": "Jobs / Browse"},
    "board_subtitle": {
        "de": "Das vollständige Schwarze Brett — durchsuchen und filtern.",
        "en": "The full bulletin board — search and filter.",
    },
    "filter_search_placeholder": {"de": "Suche eingeben...", "en": "Type your search here..."},
    "filter_city_placeholder": {"de": "Stadt", "en": "City"},
    "filter_all_countries": {"de": "Alle Länder", "en": "All countries"},
    "filter_country_de": {"de": "Deutschland", "en": "Germany"},
    "filter_country_at": {"de": "Österreich", "en": "Austria"},
    "filter_country_ch": {"de": "Schweiz", "en": "Switzerland"},
    "filter_country_other": {"de": "Andere", "en": "Other"},
    "filter_all_types": {"de": "Alle Anzeigentypen", "en": "All listing types"},
    "filter_all_voice_types": {"de": "Alle Stimmlagen", "en": "All voice types"},
    "filter_hashtag_placeholder": {"de": "Komponist (Hashtag)", "en": "Composer (hashtag)"},
    "filter_button": {"de": "Filtern", "en": "Filter"},
    "filter_clear": {"de": "Filter zurücksetzen", "en": "Clear filters"},
    "empty_state": {"de": "Keine Anzeigen mit diesen Filtern gefunden.", "en": "No listings found with these filters."},
    "by_author": {"de": "von", "en": "by"},

    "listing_type_seeking_singer": {"de": "Dirigent(in) sucht Sänger(in)", "en": "Conductor seeking singer"},
    "listing_type_seeking_conductor": {"de": "Sänger(in) sucht Dirigent(in)", "en": "Singer seeking conductor"},
    "listing_type_singer_available": {"de": "Sänger(in) verfügbar", "en": "Singer available"},
    "listing_type_conductor_available": {"de": "Dirigent(in) verfügbar", "en": "Conductor available"},

    # --- listing detail ---------------------------------------------------
    "listing_not_found": {"de": "Anzeige nicht gefunden.", "en": "Listing not found."},
    "back_to_board": {"de": "Zurück zum Schwarzen Brett", "en": "Back to the board"},
    "contact_title": {"de": "Kontakt", "en": "Contact"},
    "view_profile": {"de": "Profil ansehen", "en": "View profile"},
    "delete_button": {"de": "Anzeige löschen", "en": "Delete listing"},
    "delete_confirm": {"de": "Diese Anzeige wirklich löschen?", "en": "Really delete this listing?"},
    "edit_button": {"de": "Bearbeiten", "en": "Edit"},
    "voice_type_all": {"de": "Alle Stimmlagen", "en": "All voice types"},

    # --- listing form -------------------------------------------------
    "listing_form_title": {"de": "Anzeige aufgeben", "en": "Post a listing"},
    "listing_form_edit_title": {"de": "Anzeige bearbeiten", "en": "Edit listing"},
    "listing_form_type_label": {"de": "Anzeigentyp", "en": "Listing type"},
    "listing_form_title_label": {"de": "Titel", "en": "Title"},
    "listing_form_description_label": {"de": "Beschreibung", "en": "Description"},
    "listing_form_city_label": {"de": "Stadt*", "en": "City*"},
    "listing_form_voice_type_label": {"de": "Stimmlage (falls zutreffend)", "en": "Voice type (if applicable)"},
    "listing_form_voice_type_required_label": {"de": "Stimmlage*", "en": "Voice type*"},
    "listing_form_repertoire_label": {"de": "Repertoire", "en": "Repertoire"},
    "listing_form_work_label": {"de": "Werk*", "en": "Work/Piece*"},
    "listing_form_repertoire_placeholder": {"de": "z.B. Mozart, Requiem", "en": "e.g. Mozart, Requiem"},
    "listing_form_venue_label": {"de": "Ort (Kirche, Saal, ...)", "en": "Venue (church, hall, ...)"},
    "listing_form_fee_label": {"de": "Cachê*", "en": "Fee*"},
    "listing_form_fee_placeholder": {"de": "z.B. 250€ oder \"nach Vereinbarung\"", "en": "e.g. €250 or \"negotiable\""},
    "listing_form_event_date_label": {"de": "Termin (optional)", "en": "Event date (optional)"},
    "listing_form_country_label": {"de": "Land", "en": "Country"},
    "listing_form_submit": {"de": "Veröffentlichen", "en": "Publish"},
    "listing_form_update_submit": {"de": "Aktualisieren", "en": "Update"},
    "error_required_fields": {
        "de": "Bitte füllen Sie Werk, Stadt, Cachê und Stimmlage aus.",
        "en": "Please fill in work, city, fee, and voice type.",
    },
    "error_listing_rate_limited": {
        "de": "Zu viele Anzeigen in kurzer Zeit — bitte warten Sie ein paar Minuten und versuchen Sie es erneut.",
        "en": "Too many listings in a short time — please wait a few minutes and try again.",
    },

    # --- login -----------------------------------------------------------------
    "login_title": {"de": "Anmelden", "en": "Log in"},
    "login_email_label": {"de": "E-Mail", "en": "Email"},
    "login_password_label": {"de": "Passwort", "en": "Password"},
    "login_submit": {"de": "Anmelden", "en": "Log in"},
    "login_no_account": {"de": "Noch kein Konto?", "en": "Don't have an account yet?"},
    "og_site_description": {
        "de": "Das Schwarze Brett für Sänger(innen) und Dirigent(innen) in Deutschland, Österreich und der Schweiz.",
        "en": "The bulletin board connecting singers and conductors in Germany, Austria and Switzerland.",
    },
    "login_error": {"de": "E-Mail oder Passwort falsch.", "en": "Incorrect email or password."},
    "login_error_locked": {
        "de": "Zu viele fehlgeschlagene Versuche. Bitte versuche es in {minutes} Minute(n) erneut.",
        "en": "Too many failed attempts. Please try again in {minutes} minute(s).",
    },

    # --- registro ----------------------------------------------------------------
    "register_title": {"de": "Konto erstellen", "en": "Create an account"},
    "register_category_label": {"de": "Ich bin", "en": "I am"},
    "register_category_soprano": {"de": "Sopran", "en": "Soprano"},
    "register_category_alto": {"de": "Alt", "en": "Alto"},
    "register_category_tenor": {"de": "Tenor", "en": "Tenor"},
    "register_category_baixo": {"de": "Bass", "en": "Bass"},
    "register_category_conductor": {"de": "Dirigent(in)", "en": "Conductor"},
    "register_fullname_label": {"de": "Vollständiger Name", "en": "Full name"},
    "register_email_label": {"de": "E-Mail", "en": "Email"},
    "register_password_label": {"de": "Passwort", "en": "Password"},
    "register_phone_label": {"de": "Telefon (optional)", "en": "Phone (optional)"},
    "register_bio_label": {"de": "Kurzbiografie (bis zu 1000 Zeichen)", "en": "Short biography (up to 1000 characters)"},
    "register_hashtags_label": {"de": "Komponisten-Hashtags (bis zu 10)", "en": "Composer hashtags (up to 10)"},
    "register_hashtags_help": {
        "de": "Komponisten, die Sie bereits gesungen haben, getrennt durch Kommas, z.B. Mozart, Verdi, Puccini",
        "en": "Composers you've already sung, separated by commas, e.g. Mozart, Verdi, Puccini",
    },
    "register_ensemble_label": {"de": "Chor/Orchester, den Sie vertreten (optional)", "en": "Choir/orchestra you represent (optional)"},
    "register_submit": {"de": "Konto erstellen", "en": "Create account"},
    "register_have_account": {"de": "Schon ein Konto?", "en": "Already have an account?"},
    "register_error_duplicate": {"de": "Es gibt bereits ein Konto mit dieser E-Mail.", "en": "An account with this email already exists."},
    "register_error_invalid_category": {"de": "Bitte wählen Sie eine gültige Kategorie.", "en": "Please choose a valid category."},
    "register_error_invalid_country": {"de": "Bitte wählen Sie ein gültiges Land.", "en": "Please choose a valid country."},
    "register_error_missing_location": {"de": "Bitte geben Sie Bundesland/Kanton und Stadt an.", "en": "Please provide your state/canton and city."},
    "register_error_too_many_tags": {
        "de": "Maximal 10 Komponisten-Hashtags erlaubt.",
        "en": "A maximum of 10 composer hashtags is allowed.",
    },
    "register_error_rate_limited": {
        "de": "Zu viele neue Konten von dieser Internetverbindung in kurzer Zeit. Bitte versuchen Sie es in etwas später erneut.",
        "en": "Too many new accounts from this network in a short time. Please try again a bit later.",
    },
    "password_rules_hint": {
        "de": "Mindestens 6 Zeichen, mit 1 Buchstaben, 1 Zahl und 1 Sonderzeichen (z. B. ! @ # $ % & *).",
        "en": "At least 6 characters, with 1 letter, 1 number and 1 special character (e.g. ! @ # $ % & *).",
    },
    "password_error_length": {"de": "Das Passwort braucht mindestens 6 Zeichen.", "en": "The password must be at least 6 characters long."},
    "password_error_letter": {"de": "Das Passwort braucht mindestens 1 Buchstaben.", "en": "The password must contain at least 1 letter."},
    "password_error_digit": {"de": "Das Passwort braucht mindestens 1 Zahl.", "en": "The password must contain at least 1 number."},
    "password_error_special": {
        "de": "Das Passwort braucht mindestens 1 Sonderzeichen (z. B. ! @ # $ % & *).",
        "en": "The password must contain at least 1 special character (e.g. ! @ # $ % & *).",
    },

    # --- my listings -------------------------------------------------------------
    "my_listings_title": {"de": "Meine Anzeigen", "en": "My listings"},
    "my_listings_empty": {"de": "Sie haben noch keine Anzeige veröffentlicht.", "en": "You haven't posted any listings yet."},
    "my_listings_publish_first": {"de": "Erste Anzeige veröffentlichen", "en": "Publish your first listing"},
    "inactive_label": {"de": "inaktiv", "en": "inactive"},

    # --- profile (own / public) -------------------------------------------------
    "profile_title": {"de": "Mein Profil", "en": "My profile"},
    "profile_voice_type_label": {"de": "Stimmlage", "en": "Voice type"},
    "profile_bio_label": {"de": "Biografie", "en": "Biography"},
    "profile_hashtags_label": {"de": "Komponisten", "en": "Composers"},
    "profile_ensemble_label": {"de": "Chor/Orchester", "en": "Choir/orchestra"},
    "profile_save": {"de": "Speichern", "en": "Save"},
    "profile_saved": {"de": "Profil aktualisiert.", "en": "Profile updated."},
    "public_profile_active_listings": {"de": "Aktive Anzeigen", "en": "Active listings"},
    "public_profile_none": {"de": "Keine aktiven Anzeigen.", "en": "No active listings."},
    "no_bio": {"de": "Noch keine Biografie.", "en": "No biography yet."},

    # --- audiobeispiele (links) ------------------------------------------------
    "audio_links_label": {"de": "Audiobeispiele (Links, bis zu 3)", "en": "Audio samples (links, up to 3)"},
    "audio_links_help": {
        "de": "Link zu YouTube, SoundCloud o.Ä. — einer pro Zeile oder durch Komma getrennt.",
        "en": "Link to YouTube, SoundCloud, etc. — one per line or comma-separated.",
    },
    "audio_links_title": {"de": "Hörbeispiele", "en": "Listen"},
    "audio_link_play": {"de": "▶ Anhören", "en": "▶ Listen"},

    # --- e-mail verification --------------------------------------------------
    "verify_banner_text": {
        "de": "Bitte bestätige deine E-Mail-Adresse, um Anzeigen zu veröffentlichen und Nachrichten zu senden.",
        "en": "Please verify your email address to post listings and send messages.",
    },
    "verify_banner_resend": {"de": "E-Mail erneut senden", "en": "Resend email"},
    "verify_success_title": {"de": "E-Mail bestätigt", "en": "Email verified"},
    "verify_success_message": {
        "de": "Deine E-Mail-Adresse wurde bestätigt. Du kannst jetzt Anzeigen veröffentlichen und Nachrichten senden.",
        "en": "Your email address has been verified. You can now post listings and send messages.",
    },
    "verify_invalid_title": {"de": "Link ungültig", "en": "Invalid link"},
    "verify_invalid_message": {
        "de": "Dieser Bestätigungslink ist ungültig oder abgelaufen.",
        "en": "This verification link is invalid or has expired.",
    },
    "verify_required_banner": {
        "de": "Bitte bestätige zuerst deine E-Mail-Adresse, bevor du das machst.",
        "en": "Please verify your email address before doing that.",
    },

    # --- esqueci/redefinir senha --------------------------------------------------
    "forgot_password_title": {"de": "Passwort vergessen?", "en": "Forgot password?"},
    "forgot_password_email_label": {"de": "E-Mail", "en": "Email"},
    "forgot_password_submit": {"de": "Link zum Zurücksetzen senden", "en": "Send reset link"},
    "forgot_password_sent_title": {"de": "E-Mail unterwegs", "en": "Email on its way"},
    "forgot_password_sent_message": {
        "de": "Falls diese E-Mail-Adresse registriert ist, haben wir einen Link zum Zurücksetzen des Passworts gesendet.",
        "en": "If this email address is registered, we've sent a password reset link.",
    },
    "reset_password_title": {"de": "Neues Passwort festlegen", "en": "Set a new password"},
    "reset_password_new_password_label": {"de": "Neues Passwort", "en": "New password"},
    "reset_password_submit": {"de": "Passwort speichern", "en": "Save password"},
    "reset_password_success_title": {"de": "Passwort geändert", "en": "Password changed"},
    "reset_password_success_message": {
        "de": "Dein Passwort wurde geändert. Du kannst dich jetzt anmelden.",
        "en": "Your password has been changed. You can now log in.",
    },
    "reset_password_invalid_title": {"de": "Link ungültig", "en": "Invalid link"},
    "reset_password_invalid_message": {
        "de": "Dieser Link ist ungültig oder abgelaufen. Fordere einen neuen an.",
        "en": "This link is invalid or has expired. Please request a new one.",
    },
    "login_forgot_password_link": {"de": "Passwort vergessen?", "en": "Forgot password?"},
    "back_to_login": {"de": "Zurück zum Login", "en": "Back to login"},

    # --- error pages (404 / generic error / 500) -------------------------
    "error_404_title": {"de": "Seite nicht gefunden", "en": "Page not found"},
    "error_404_message": {
        "de": "Diese Seite existiert nicht (mehr), oder der Link ist falsch.",
        "en": "This page doesn't exist (anymore), or the link is wrong.",
    },
    "error_generic_title": {"de": "Etwas ist schiefgelaufen", "en": "Something went wrong"},
    "error_generic_message": {
        "de": "Die Anfrage konnte nicht bearbeitet werden (Fehler {status}).",
        "en": "The request couldn't be processed (error {status}).",
    },
    "error_500_title": {"de": "Etwas ist schiefgelaufen", "en": "Something went wrong"},
    "error_500_message": {
        "de": "Ein unerwarteter Fehler ist aufgetreten. Wir wurden benachrichtigt — bitte versuchen Sie es später erneut.",
        "en": "An unexpected error occurred. We've been notified — please try again later.",
    },
    "error_back_home": {"de": "Zurück zur Startseite", "en": "Back to the homepage"},

    # --- indicador de data (bolinha colorida) --------------------------------------
    "event_status_upcoming": {"de": "Termin in der Zukunft", "en": "Upcoming event"},
    "event_status_soon": {"de": "Termin diese Woche", "en": "Happening this week"},
    "event_status_past": {"de": "Termin bereits vorbei", "en": "Event already passed"},

    # --- mensagens internas -------------------------------------------------------
    "nav_messages": {"de": "Nachrichten", "en": "Messages"},
    "messages_inbox_title": {"de": "Posteingang", "en": "Inbox"},
    "messages_sent_title": {"de": "Gesendet", "en": "Sent"},
    "messages_trash_title": {"de": "Papierkorb", "en": "Trash"},
    "messages_tab_inbox": {"de": "Posteingang", "en": "Inbox"},
    "messages_tab_sent": {"de": "Gesendet", "en": "Sent"},
    "messages_tab_trash": {"de": "Papierkorb", "en": "Trash"},
    "messages_empty_inbox": {"de": "Kein Posteingang bisher.", "en": "No messages yet."},
    "messages_empty_sent": {"de": "Noch nichts gesendet.", "en": "Nothing sent yet."},
    "messages_empty_trash": {"de": "Papierkorb ist leer.", "en": "Trash is empty."},
    "message_from": {"de": "von", "en": "from"},
    "message_to": {"de": "an", "en": "to"},
    "message_about_listing": {"de": "zu Anzeige", "en": "about listing"},
    "message_unread": {"de": "ungelesen", "en": "unread"},
    "message_trash_button": {"de": "In den Papierkorb", "en": "Move to trash"},
    "message_restore_button": {"de": "Wiederherstellen", "en": "Restore"},
    "message_empty_trash_button": {"de": "Papierkorb leeren", "en": "Empty trash"},
    "message_empty_trash_confirm": {
        "de": "Papierkorb wirklich leeren? Das löscht die Nachrichten endgültig (auch für die andere Person).",
        "en": "Really empty the trash? This permanently deletes the messages (for the other person too).",
    },
    "message_compose_title": {"de": "Neue Nachricht", "en": "New message"},
    "message_error_rate_limited": {
        "de": "Sie haben in der letzten Stunde schon viele Nachrichten verschickt. Bitte versuchen Sie es später erneut.",
        "en": "You've sent a lot of messages in the last hour. Please try again a bit later.",
    },
    "message_error_rate_limited_recipient": {
        "de": "Sie haben dieser Person in der letzten Stunde schon mehrmals geschrieben. Warten Sie kurz auf eine Antwort, bevor Sie erneut schreiben.",
        "en": "You've already written to this person several times in the last hour. Give them a bit of time to reply before writing again.",
    },
    "message_to_label": {"de": "An", "en": "To"},
    "message_body_label": {"de": "Nachricht", "en": "Message"},
    "message_send": {"de": "Senden", "en": "Send"},
    "message_reply": {"de": "Antworten", "en": "Reply"},
    "message_send_here": {"de": "Nachricht senden", "en": "Send a message"},

    # --- freemium: content locked without login ----------------------------------
    "locked_listing_title": {"de": "Details nur für Mitglieder", "en": "Details for members only"},
    "locked_listing_text": {
        "de": "Registriere dich kostenlos, um die vollständige Beschreibung und die Kontaktdaten zu sehen.",
        "en": "Sign up for free to see the full description and contact details.",
    },
    "locked_listing_unverified_title": {"de": "E-Mail-Bestätigung nötig", "en": "Email verification needed"},
    "locked_listing_unverified_text": {
        "de": "Bitte bestätige zuerst deine E-Mail-Adresse, um die vollständige Beschreibung und die Kontaktdaten zu sehen.",
        "en": "Please verify your email address first to see the full description and contact details.",
    },
    "locked_profile_title": {"de": "Profil nur für Mitglieder", "en": "Profile for members only"},
    "locked_profile_text": {
        "de": "Registriere dich kostenlos, um Biografie, Hörbeispiele und Anzeigen zu sehen.",
        "en": "Sign up for free to see the biography, audio samples, and listings.",
    },

    # --- "Post Job" (my listings + new listing button) ------------------
    "my_listings_new_button": {"de": "+ Neue Anzeige", "en": "+ New listing"},

    # --- cascading location (Country > State) + type (solo/choir) ---------
    "listing_form_state_label": {"de": "Bundesland / Kanton", "en": "State / Province"},
    "listing_form_state_other_placeholder": {"de": "Bundesland/Region eingeben", "en": "Enter state/region"},
    "listing_form_city_other_placeholder": {"de": "Stadt eingeben", "en": "Enter city"},
    "listing_form_city_not_listed": {"de": "Meine Stadt ist nicht dabei", "en": "My city isn't listed"},
    "listing_form_city_choose_from_list": {"de": "Aus Liste wählen", "en": "Choose from list"},
    "listing_form_ensemble_type_label": {"de": "Solo, Chor oder beides?", "en": "Solo, choir, or both?"},
    "ensemble_type_solo": {"de": "Solo", "en": "Solo"},
    "ensemble_type_choir": {"de": "Chor", "en": "Choir"},
    "ensemble_type_both": {"de": "Beides", "en": "Both"},
    "filter_all_states": {"de": "Alle Bundesländer", "en": "All states"},
    "filter_all_cities": {"de": "Alle Städte", "en": "All cities"},
    "filter_all_ensemble_types": {"de": "Solo/Chor: alle", "en": "Solo/Choir: all"},
    "filter_show_past": {"de": "Vergangene Termine anzeigen", "en": "Show past events"},
    "filter_period_from_label": {"de": "Zeitraum von", "en": "Period from"},
    "filter_period_to_label": {"de": "bis", "en": "to"},
    "board_results_label": {"de": "Ergebnisse", "en": "results"},

    # --- pagination -----------------------------------------------------------
    "pagination_prev": {"de": "Zurück", "en": "Previous"},
    "pagination_next": {"de": "Weiter", "en": "Next"},
    "pagination_page": {"de": "Seite", "en": "Page"},

    # --- "message already sent" -------------------------------------------------
    "already_messaged_text": {
        "de": "Du hast zu dieser Anzeige bereits eine Nachricht gesendet.",
        "en": "You've already sent a message about this listing.",
    },

    # --- redes sociais no perfil -----------------------------------------------
    "social_links_title": {"de": "Soziale Netzwerke", "en": "Social links"},
    "social_links_help": {
        "de": "Optional. Wird auf deinem öffentlichen Profil nur als Schaltfläche angezeigt (nicht als voller Link).",
        "en": "Optional. Shown on your public profile only as a button (not the full link).",
    },
    "social_platform_website": {"de": "Website", "en": "Website"},
    "social_platform_facebook": {"de": "Facebook", "en": "Facebook"},
    "social_platform_instagram": {"de": "Instagram", "en": "Instagram"},
    "social_platform_twitter": {"de": "Twitter", "en": "Twitter"},
    "social_platform_whatsapp": {"de": "WhatsApp", "en": "WhatsApp"},

    # --- star rating (private, only whoever received it sees it) ------------------
    "rating_widget_title": {"de": "Bewertung abgeben", "en": "Leave a rating"},
    "rating_widget_help": {
        "de": "Deine Bewertung ist nur für diese Person sichtbar — niemand sonst kann sie sehen.",
        "en": "Your rating is only visible to this person — no one else can see it.",
    },
    "rating_saved": {"de": "Bewertung gespeichert.", "en": "Rating saved."},
    "rating_stars_label": {"de": "Sterne (0–5)", "en": "Stars (0–5)"},
    "rating_comment_label": {"de": "Kommentar (optional)", "en": "Comment (optional)"},
    "rating_submit": {"de": "Bewertung senden", "en": "Submit rating"},
    "my_ratings_title": {"de": "Meine Bewertungen", "en": "My ratings"},
    "my_ratings_help": {
        "de": "Nur du siehst diese Bewertungen — sie sind privat.",
        "en": "Only you can see these ratings — they're private.",
    },
    "my_ratings_count_label": {"de": "Bewertungen", "en": "ratings"},
    "my_ratings_none": {"de": "Noch keine Bewertungen erhalten.", "en": "No ratings received yet."},

    # --- account: password, deletion and reactivation ------------------------------------
    "account_section_title": {"de": "Konto", "en": "Account"},
    "change_password_title": {"de": "Passwort ändern", "en": "Change password"},
    "change_password_current_label": {"de": "Aktuelles Passwort", "en": "Current password"},
    "change_password_new_label": {"de": "Neues Passwort", "en": "New password"},
    "change_password_submit": {"de": "Passwort ändern", "en": "Change password"},
    "change_password_wrong_current": {"de": "Aktuelles Passwort ist falsch.", "en": "Current password is incorrect."},
    "change_password_too_short": {"de": "Neues Passwort braucht mindestens 6 Zeichen.", "en": "New password must be at least 6 characters."},
    "back_to_profile": {"de": "Zurück zum Profil", "en": "Back to profile"},

    "danger_zone_title": {"de": "Gefahrenzone", "en": "Danger zone"},
    "delete_account_help": {
        "de": "Dein Konto wird deaktiviert und für 6 Monate aufbewahrt (falls du es wiederherstellen möchtest). Danach wird es endgültig gelöscht.",
        "en": "Your account will be deactivated and kept for 6 months (in case you want it back). After that it's permanently deleted.",
    },
    "delete_account_toggle": {"de": "Konto löschen", "en": "Delete account"},
    "delete_account_confirm": {
        "de": "Konto wirklich löschen? Es wird für 6 Monate aufbewahrt und danach endgültig entfernt.",
        "en": "Really delete your account? It will be kept for 6 months and then permanently removed.",
    },
    "delete_account_password_label": {"de": "Passwort zur Bestätigung", "en": "Password to confirm"},
    "delete_account_submit": {"de": "Konto endgültig löschen", "en": "Delete my account"},
    "delete_account_wrong_password": {"de": "Passwort ist falsch.", "en": "Password is incorrect."},
    "account_deleted_banner": {
        "de": "Dein Konto wurde deaktiviert. Wenn du dich innerhalb von 6 Monaten erneut anmeldest, kannst du es reaktivieren.",
        "en": "Your account has been deactivated. If you log in again within 6 months, you can reactivate it.",
    },

    "reactivate_title": {"de": "Konto reaktivieren", "en": "Reactivate account"},
    "reactivate_text": {
        "de": "Dieses Konto wurde gelöscht, ist aber noch innerhalb der 6-Monats-Frist. Möchtest du es reaktivieren?",
        "en": "This account was deleted but is still within the 6-month window. Would you like to reactivate it?",
    },
    "reactivate_submit": {"de": "Ja, Konto reaktivieren", "en": "Yes, reactivate my account"},

    # --- foto de perfil ---------------------------------------------------
    "register_avatar_label": {"de": "Profilfoto (optional)", "en": "Profile photo (optional)"},
    "register_avatar_help": {
        "de": "JPG, PNG oder WebP, max. 3 MB. Kann später in deinem Profil geändert werden.",
        "en": "JPG, PNG, or WebP, max 3 MB. Can be changed later in your profile.",
    },
    "profile_avatar_label": {"de": "Profilfoto", "en": "Profile photo"},
    "profile_location_label": {"de": "Standort", "en": "Location"},
    "profile_location_help": {
        "de": "Wird für passende Vorschläge (z. B. in deiner Nähe) verwendet.",
        "en": "Used to find better matches near you.",
    },
    "profile_avatar_remove": {"de": "Foto entfernen", "en": "Remove photo"},
    "profile_avatar_invalid": {
        "de": "Das Bild konnte nicht gespeichert werden (Format oder Größe nicht unterstützt — JPG/PNG/WebP, max. 3 MB). Der Rest wurde trotzdem gespeichert.",
        "en": "The image couldn't be saved (unsupported format or too large — JPG/PNG/WebP, max 3MB). Everything else was still saved.",
    },

    # --- matching listing alerts ------------------------------------
    "notify_matches_label": {"de": "Bei passenden Anzeigen per E-Mail benachrichtigen", "en": "Email me about matching listings"},
    "notify_matches_help": {
        "de": "Wenn jemand eine Anzeige postet, die zu deinem Profil passt (Stimmtyp bzw. Dirigent(in)), bekommst du sofort eine E-Mail.",
        "en": "When someone posts a listing matching your profile (voice type, or conductor role), you get an email right away.",
    },

    # --- indicador de perfil completo --------------------------------------
    "completeness_label": {"de": "Profil vollständig", "en": "Profile complete"},
    "completeness_hint": {
        "de": "ein vollständigeres Profil wirkt vertrauenswürdiger und verbessert deine Treffer auf der Startseite",
        "en": "a more complete profile builds trust and improves your matches on the home page",
    },

    # --- exportar dados (GDPR/portabilidade) --------------------------------
    "export_data_link": {"de": "Meine Daten exportieren", "en": "Export my data"},
    "export_data_help": {
        "de": "Lädt eine JSON-Datei mit allem herunter, was über dich gespeichert ist (Profil, Anzeigen, Nachrichten, Bewertungen).",
        "en": "Downloads a JSON file with everything stored about you (profile, listings, messages, ratings).",
    },

    # --- favoritos -----------------------------------------------------------
    "favorite_add": {"de": "Favorisieren", "en": "Save"},
    "favorite_remove": {"de": "Aus Favoriten entfernen", "en": "Remove from favorites"},
    "favorite_marker": {"de": "Favorisiert", "en": "Saved"},
    "favorites_subtitle": {"de": "Anzeigen, die du dir für später gemerkt hast.", "en": "Listings you've saved for later."},
    "favorites_empty": {"de": "Du hast noch keine Anzeigen favorisiert.", "en": "You haven't saved any listings yet."},

    # --- new message notification ---------------------------------------
    "notify_messages_label": {"de": "Bei neuen Nachrichten per E-Mail benachrichtigen", "en": "Email me when I get a new message"},
    "notify_messages_help": {
        "de": "Du bekommst eine E-Mail, sobald dir jemand eine Nachricht schickt (ohne den Inhalt der Nachricht — dafür musst du dich einloggen).",
        "en": "You'll get an email as soon as someone sends you a message (without the message content — you'll need to log in to read it).",
    },

    # --- convide um amigo / referral -----------------------------------------
    "referral_section_title": {"de": "Freunde einladen", "en": "Invite a friend"},
    "referral_section_text": {
        "de": "Teile diesen Link — wer sich darüber anmeldet, zählt als deine Einladung.",
        "en": "Share this link — anyone who signs up through it counts as your invite.",
    },
    "referral_count_label": {"de": "Eingeladene Personen", "en": "People invited"},
    "referral_copy_button": {"de": "Link kopieren", "en": "Copy link"},
    "referral_copied": {"de": "Kopiert!", "en": "Copied!"},
    "register_referred_notice": {
        "de": "Du wurdest von einer anderen Person eingeladen — willkommen!",
        "en": "You were invited by someone else — welcome!",
    },

    # --- bloquear pessoas ------------------------------------------------------
    "block_user_button": {"de": "Blockieren", "en": "Block"},
    "unblock_user_button": {"de": "Blockierung aufheben", "en": "Unblock"},
    "block_user_reason_label": {"de": "Grund (optional)", "en": "Reason (optional)"},
    "block_user_reason_placeholder": {"de": "Warum möchtest du diese Person blockieren?", "en": "Why are you blocking this person?"},
    "block_user_confirm": {"de": "Person blockieren", "en": "Block this person"},
    "blocked_users_title": {"de": "Blockierte Personen", "en": "Blocked people"},
    "blocked_users_empty": {"de": "Du hast niemanden blockiert.", "en": "You haven't blocked anyone."},
    "blocked_users_help": {
        "de": "Blockierte Personen können dir keine Nachrichten mehr schicken (und du ihnen auch nicht), ihre Anzeigen werden dir nicht mehr angezeigt, und ihr könnt euch gegenseitig nicht mehr die Profile ansehen.",
        "en": "Blocked people can no longer message you (or you them), their listings are hidden from your board, and neither of you can view the other's profile anymore.",
    },
    "profile_unavailable_blocked": {
        "de": "Dieses Profil ist nicht verfügbar.",
        "en": "This profile is not available.",
    },

    # --- report listing -----------------------------------------------------
    "report_listing_button": {"de": "Anzeige melden", "en": "Report listing"},
    "report_listing_reason_label": {"de": "Warum meldest du diese Anzeige?", "en": "Why are you reporting this listing?"},
    "report_listing_reason_placeholder": {
        "de": "Bitte kurz beschreiben (mind. 10 Zeichen)…",
        "en": "Please briefly describe why (at least 10 characters)…",
    },
    "report_listing_reason_help": {
        "de": "Deine Meldung wird gespeichert und vom Betreiber des Portals geprüft.",
        "en": "Your report is recorded and reviewed by the site operator.",
    },
    "report_listing_confirm": {"de": "Meldung senden", "en": "Send report"},
    "report_listing_sent": {"de": "Danke, deine Meldung wurde gesendet.", "en": "Thanks, your report has been sent."},
    "report_listing_already": {"de": "Du hast diese Anzeige bereits gemeldet.", "en": "You've already reported this listing."},

    # --- footer: impressum / code of conduct -------------------------------
    "footer_impressum": {"de": "Impressum", "en": "Legal notice"},
    "footer_privacy": {"de": "Datenschutz", "en": "Privacy policy"},
    "footer_conduct": {"de": "Verhaltenskodex", "en": "Code of conduct"},

    # --- Impressum -------------------------------------------------------------
    "impressum_title": {"de": "Impressum", "en": "Legal notice (Impressum)"},
    "impressum_operated_from_notice": {
        "de": "Dieses Portal wird von Brasilien aus betrieben.",
        "en": "This site is operated from Brazil.",
    },

    # --- Datenschutzerklärung ---------------------------------------------------
    "privacy_title": {"de": "Datenschutzerklärung", "en": "Privacy policy"},
    "privacy_disclaimer": {
        "de": "Diese Erklärung ist eine solide Vorlage, ersetzt aber keine juristische Prüfung — insbesondere Abschnitt 4 (internationale Datenübermittlung) muss noch bestätigt werden, bevor die Seite echte Nutzerdaten verarbeitet.",
        "en": "This notice is a solid template but does not replace legal review — section 4 (international data transfer) in particular still needs confirmation before the site processes real users' data.",
    },

    # --- code of conduct -----------------------------------------------------
    "conduct_title": {"de": "Verhaltenskodex", "en": "Code of conduct"},
    "conduct_intro": {
        "de": "VokalBoard ist ein Ort, an dem sich Sänger(innen) und Dirigent(innen) respektvoll und professionell begegnen sollen. Diese Regeln gelten für alle.",
        "en": "VokalBoard is meant to be a place where singers and conductors meet respectfully and professionally. These rules apply to everyone.",
    },

    # --- badges (light gamification, no ranking) -------------------------------
    "badges_title": {"de": "Auszeichnungen", "en": "Badges"},
    "badges_help": {
        "de": "Kleine Erinnerungen an das, was du schon erreicht hast — kein Ranking, kein Vergleich mit anderen.",
        "en": "A few reminders of what you've already achieved — no ranking, no comparison with anyone else.",
    },
    "badge_referral_label": {"de": "Botschafter(in)", "en": "Ambassador"},
    "badge_referral_desc": {"de": "Hat mindestens eine Person eingeladen.", "en": "Invited at least one person."},
    "badge_listing_label": {"de": "Erste Anzeige", "en": "First listing"},
    "badge_listing_desc": {"de": "Hat mindestens eine Anzeige veröffentlicht.", "en": "Posted at least one listing."},
    "badge_contact_label": {"de": "Kontaktfreudig", "en": "Reached out"},
    "badge_contact_desc": {"de": "Hat mindestens eine Nachricht verschickt.", "en": "Sent at least one message."},
    "badge_profile_complete_label": {"de": "Profil komplett", "en": "Complete profile"},
    "badge_profile_complete_desc": {"de": "Profil zu 100% ausgefüllt.", "en": "Profile 100% complete."},
    "badge_views_label": {"de": "Gefragt", "en": "In demand"},
    "badge_views_desc": {
        "de": "Profil wurde oft besucht (genaue Zahl bleibt privat).",
        "en": "Profile has been visited a lot (the exact number stays private).",
    },
    "badge_fast_response_label": {"de": "Schnelle Antwort", "en": "Fast response"},
    "badge_fast_response_desc": {
        "de": "Hat mindestens einmal innerhalb von 24 Stunden geantwortet.",
        "en": "Replied to a message within 24 hours at least once.",
    },
    "badge_anniversary_label": {"de": "Jahrestag", "en": "Anniversary"},
    "badge_anniversary_desc": {"de": "Ist seit mindestens einem Jahr dabei.", "en": "Has been a member for at least a year."},

    # --- aviso de caixa de spam (home) ----------------------------------------
    "spam_notice_text": {
        "de": "Tipp: Schau ab und zu in deinem Spam-Ordner nach und markiere E-Mails von uns als \"kein Spam\", damit dir keine Nachrichten-Alarme oder Antworten entgehen.",
        "en": "Tip: check your spam folder every now and then and mark emails from us as \"not spam\", so you don't miss message alerts or replies.",
    },
    "spam_notice_dismiss": {"de": "Schließen", "en": "Dismiss"},
}


def translate(key: str, lang: str) -> str:
    """Returns the translation of `key` in language `lang` (fallback: German, then the key itself)."""
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    return entry.get(lang) or entry.get(DEFAULT_LANGUAGE) or key

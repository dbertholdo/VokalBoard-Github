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

Language is a UI-only choice, independent from currency (EUR/CHF are
picked by country, not by language) — see app/financial_settings.py.
"""

SUPPORTED_LANGUAGES = ["de", "en", "fr", "it", "pt"]
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
}

TRANSLATIONS: dict[str, dict[str, str]] = {
    # --- navigation / layout -------------------------------------------------
    "nav_home": {"de": "Start", "en": "Home", "fr": "Accueil", "it": "Home", "pt": "Início"},
    "nav_my_listings": {"de": "Meine Anzeigen", "en": "My listings", "fr": "Mes annonces", "it": "I miei annunci", "pt": "Meus anúncios"},
    "nav_favorites": {"de": "Favoriten", "en": "Favorites", "fr": "Favoris", "it": "Preferiti", "pt": "Favoritos"},
    "nav_notas": {"de": "Punkte", "en": "Credits", "fr": "Crédits", "it": "Crediti", "pt": "Notas"},
    "nav_hall_da_fama": {"de": "Ruhmeshalle", "en": "Hall of Fame", "fr": "Temple de la renommée", "it": "Bacheca della fama", "pt": "Hall da Fama"},
    "nav_board": {"de": "Jobs", "en": "Jobs", "fr": "Annonces", "it": "Annunci", "pt": "Vagas"},
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
    "listing_form_edit_title": {"de": "Anzeige bearbeiten", "en": "Edit listing", "fr": "Modifier l'annonce", "it": "Modifica annuncio", "pt": "Editar anúncio"},
    "listing_form_type_label": {"de": "Anzeigentyp", "en": "Listing type", "fr": "Type d'annonce", "it": "Tipo di annuncio", "pt": "Tipo de anúncio"},
    "listing_form_title_label": {"de": "Titel", "en": "Title", "fr": "Titre", "it": "Titolo", "pt": "Título"},
    "listing_form_description_label": {"de": "Beschreibung", "en": "Description", "fr": "Description", "it": "Descrizione", "pt": "Descrição"},
    "listing_form_city_label": {"de": "Stadt*", "en": "City*", "fr": "Ville*", "it": "Città*", "pt": "Cidade*"},
    "listing_form_voice_type_label": {"de": "Stimmlage (falls zutreffend)", "en": "Voice type (if applicable)", "fr": "Tessiture (le cas échéant)", "it": "Tessitura (se applicabile)", "pt": "Tipo de voz (se aplicável)"},
    "listing_form_voice_type_required_label": {"de": "Stimmlage*", "en": "Voice type*", "fr": "Tessiture*", "it": "Tessitura*", "pt": "Tipo de voz*"},
    "listing_form_repertoire_label": {"de": "Repertoire", "en": "Repertoire", "fr": "Répertoire", "it": "Repertorio", "pt": "Repertório"},
    "listing_form_work_label": {"de": "Werk*", "en": "Work/Piece*", "fr": "Œuvre*", "it": "Opera*", "pt": "Obra*"},
    "listing_form_repertoire_placeholder": {"de": "z.B. Mozart, Requiem", "en": "e.g. Mozart, Requiem", "fr": "ex. Mozart, Requiem", "it": "es. Mozart, Requiem", "pt": "ex.: Mozart, Requiem"},
    "listing_form_venue_label": {"de": "Ort (Kirche, Saal, ...)", "en": "Venue (church, hall, ...)", "fr": "Lieu (église, salle, ...)", "it": "Luogo (chiesa, sala, ...)", "pt": "Local (igreja, sala, ...)"},
    "listing_form_fee_label": {"de": "Cachê*", "en": "Fee*", "fr": "Cachet*", "it": "Compenso*", "pt": "Cachê*"},
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
    "error_required_fields": {
        "de": "Bitte füllen Sie Werk, Stadt, Cachê und Stimmlage aus.",
        "en": "Please fill in work, city, fee, and voice type.",
        "fr": "Veuillez renseigner l'œuvre, la ville, le cachet et la tessiture.",
        "it": "Compila opera, città, compenso e tessitura.",
        "pt": "Preencha obra, cidade, cachê e tipo de voz.",
    },
    "error_listing_rate_limited": {
        "de": "Zu viele Anzeigen in kurzer Zeit — bitte warten Sie ein paar Minuten und versuchen Sie es erneut.",
        "en": "Too many listings in a short time — please wait a few minutes and try again.",
        "fr": "Trop d'annonces en peu de temps — veuillez patienter quelques minutes et réessayer.",
        "it": "Troppi annunci in poco tempo — attendi qualche minuto e riprova.",
        "pt": "Muitos anúncios em pouco tempo — aguarde alguns minutos e tente novamente.",
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
    "login_error": {"de": "E-Mail oder Passwort falsch.", "en": "Incorrect email or password.", "fr": "E-mail ou mot de passe incorrect.", "it": "Email o password errati.", "pt": "E-mail ou senha incorretos."},
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

    # --- profile (own / public) -------------------------------------------------
    "profile_title": {"de": "Mein Profil", "en": "My profile", "fr": "Mon profil", "it": "Il mio profilo", "pt": "Meu perfil"},
    "profile_voice_type_label": {"de": "Stimmlage", "en": "Voice type", "fr": "Tessiture", "it": "Tessitura", "pt": "Tipo de voz"},
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
    "filter_period_from_label": {"de": "Zeitraum von", "en": "Period from", "fr": "Période à partir de", "it": "Periodo da", "pt": "Período de"},
    "filter_period_to_label": {"de": "bis", "en": "to", "fr": "à", "it": "a", "pt": "até"},
    "board_results_label": {"de": "Ergebnisse", "en": "results", "fr": "résultats", "it": "risultati", "pt": "resultados"},

    # --- pagination -----------------------------------------------------------
    "pagination_prev": {"de": "Zurück", "en": "Previous", "fr": "Précédent", "it": "Precedente", "pt": "Anterior"},
    "pagination_next": {"de": "Weiter", "en": "Next", "fr": "Suivant", "it": "Successivo", "pt": "Próximo"},
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
        "de": "Dein Konto wird deaktiviert und für 6 Monate aufbewahrt (falls du es wiederherstellen möchtest). Danach wird es endgültig gelöscht.",
        "en": "Your account will be deactivated and kept for 6 months (in case you want it back). After that it's permanently deleted.",
        "fr": "Votre compte sera désactivé et conservé pendant 6 mois (au cas où vous souhaiteriez le récupérer). Après cela, il sera définitivement supprimé.",
        "it": "Il tuo account verrà disattivato e conservato per 6 mesi (nel caso tu voglia recuperarlo). Dopodiché verrà eliminato definitivamente.",
        "pt": "Sua conta será desativada e mantida por 6 meses (caso você queira recuperá-la). Depois disso, será excluída definitivamente.",
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
    "notas_title": {"de": "Punkte", "en": "Notas (credits)", "fr": "Notas (crédits)", "it": "Notas (crediti)", "pt": "Notas"},
    "notas_subtitle": {
        "de": "Deine Prämien fürs Einladen von Freunden — hier ansehen und einlösen.",
        "en": "Your rewards for inviting friends — view and redeem them here.",
        "fr": "Vos récompenses pour avoir invité des amis — consultez-les et échangez-les ici.",
        "it": "Le tue ricompense per aver invitato amici — vedile e riscattale qui.",
        "pt": "Suas recompensas por indicar amigos — veja e resgate aqui.",
    },
    "notas_balance_label": {"de": "verfügbare Punkte", "en": "notas available", "fr": "notas disponibles", "it": "notas disponibili", "pt": "notas disponíveis"},
    "notas_next_credit_hint": {
        "de": "Noch {n} bestätigte Einladung(en) bis zur nächsten Note.",
        "en": "{n} more verified referral(s) until your next nota.",
        "fr": "Encore {n} parrainage(s) vérifié(s) avant votre prochaine nota.",
        "it": "Ancora {n} referral verificati fino al prossimo nota.",
        "pt": "Faltam {n} indicação(ões) verificada(s) para a próxima nota.",
    },
    "notas_how_it_works": {
        "de": "Für alle {ratio} bestätigten Einladungen erhältst du 1 Note — bestätigt heißt, die eingeladene Person hat ihre E-Mail verifiziert.",
        "en": "Every {ratio} verified referrals earns you 1 nota — verified means the person you invited confirmed their e-mail.",
        "fr": "Chaque groupe de {ratio} parrainages vérifiés vous rapporte 1 nota — vérifié signifie que la personne invitée a confirmé son e-mail.",
        "it": "Ogni {ratio} referral verificati ti fanno guadagnare 1 nota — verificato significa che la persona invitata ha confermato la propria e-mail.",
        "pt": "A cada {ratio} indicações verificadas você ganha 1 nota — verificada quer dizer que a pessoa indicada confirmou o e-mail dela.",
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
    "notas_unit": {"de": "Punkte", "en": "notas", "fr": "notas", "it": "notas", "pt": "notas"},
    "notas_redeem_button": {"de": "Einlösen", "en": "Redeem", "fr": "Échanger", "it": "Riscatta", "pt": "Resgatar"},
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
        "de": "Note für bestätigte Einladungen",
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
        "de": "Du hast nicht genug Punkte für diese Prämie.",
        "en": "You don't have enough notas for this reward.",
        "fr": "Vous n'avez pas assez de notas pour cette récompense.",
        "it": "Non hai abbastanza notas per questo premio.",
        "pt": "Você não tem notas suficientes para essa recompensa.",
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

    "register_referred_notice": {
        "de": "Du wurdest von einer anderen Person eingeladen — willkommen!",
        "en": "You were invited by someone else — welcome!",
        "fr": "Vous avez été invité(e) par quelqu'un d'autre — bienvenue !",
        "it": "Sei stato invitato da qualcun altro — benvenuto!",
        "pt": "Você foi convidado(a) por outra pessoa — bem-vindo(a)!",
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
}


def translate(key: str, lang: str) -> str:
    """Returns the translation of `key` in language `lang` (fallback: German, then the key itself)."""
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    return entry.get(lang) or entry.get(DEFAULT_LANGUAGE) or key

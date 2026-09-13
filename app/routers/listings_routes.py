from fastapi import APIRouter, Request, Form, BackgroundTasks
from fastapi.responses import RedirectResponse, HTMLResponse

from app.database import fetch_all, fetch_one, execute, execute_returning
from app.auth import get_current_user
from app.render import render
from app.csrf import verify_csrf
from app.notifications import notify_matching_users
from app.badges import check_and_notify_new_badges
from app.locations import COUNTRY_OPTIONS, STATE_OPTIONS, get_city_options

router = APIRouter()

LISTING_TYPE_KEYS = [
    "seeking_singer",
    "seeking_conductor",
    "singer_available",
    "conductor_available",
]

ENSEMBLE_TYPE_KEYS = ["solo", "choir", "both"]

# "event_status" é calculado no próprio SQL (CASE), não fica guardado
# no banco — assim ele muda sozinho conforme os dias passam, sem
# precisar de nenhum job/rotina pra manter atualizado.
#   upcoming (verde) -> evento a mais de 7 dias no futuro
#   soon     (amarelo) -> evento dentro dos próximos 7 dias
#   past     (vermelho) -> evento já passou
#   NULL               -> anúncio sem data de evento (ex: disponibilidade)
EVENT_STATUS_SQL = """
    CASE
        WHEN l.event_date IS NULL THEN NULL
        WHEN l.event_date < CURRENT_DATE THEN 'past'
        WHEN l.event_date <= CURRENT_DATE + INTERVAL '7 days' THEN 'soon'
        ELSE 'upcoming'
    END AS event_status
"""

LISTING_COLUMNS = f"""
    l.id, l.title, l.description, l.city, l.state, l.country, l.listing_type,
    l.repertoire, l.venue, l.fee, l.ensemble_type, l.event_date, l.created_at,
    {EVENT_STATUS_SQL}
"""

BOARD_PAGE_SIZE = 20


def _job_fields_valid(listing_type: str, city: str, repertoire: str, fee: str) -> bool:
    """
    Anúncios do tipo 'seeking_singer' (procura-se cantor(a) para um
    trabalho) precisam de Obra, Cidade e Cachê preenchidos — conforme
    pedido. Tipo de voz não entra na validação porque "em branco" já
    significa "todas as vozes", uma escolha válida.
    """
    if listing_type != "seeking_singer":
        return True
    return bool(city.strip()) and bool(repertoire.strip()) and bool(fee.strip())


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    """
    Página inicial — agora uma tela de boas-vindas curta, não o quadro
    de avisos inteiro (isso foi para /board).

    Logado: "Bem-vindo(a), {nome}" + até 5 vagas que combinam com o
    perfil (cantor: anúncios 'seeking_singer' da própria categoria de
    voz; maestro(a): anúncios 'seeking_conductor'), priorizando
    anúncios da própria cidade.

    Sem login: um teaser com as 5 vagas mais recentes, sem os detalhes
    (modelo "freemium" — ver /board e /listings/{id} para o resto).
    """
    user = get_current_user(request)
    matches = []

    if user:
        match_params = {"city": f"%{user['city']}%" if user["city"] else ""}
        order_by_city = "CASE WHEN l.city ILIKE :city THEN 0 ELSE 1 END, l.created_at DESC" if user["city"] else "l.created_at DESC"

        if user["role"] == "singer":
            singer_profile = fetch_one(
                "SELECT voice_type_id FROM singer_profiles WHERE user_id = :id", {"id": user["id"]}
            )
            voice_type_id = singer_profile["voice_type_id"] if singer_profile else None
            conditions = [
                "l.is_active = TRUE",
                "l.listing_type = 'seeking_singer'",
                "(l.event_date IS NULL OR l.event_date >= CURRENT_DATE)",
                "NOT EXISTS (SELECT 1 FROM blocked_users bu WHERE (bu.blocker_id = :viewer_block_id AND bu.blocked_id = l.author_id) OR (bu.blocker_id = l.author_id AND bu.blocked_id = :viewer_block_id))",
            ]
            match_params["viewer_block_id"] = user["id"]
            if voice_type_id:
                conditions.append("(l.voice_type_id = :voice_type_id OR l.voice_type_id IS NULL)")
                match_params["voice_type_id"] = voice_type_id
            matches = fetch_all(
                f"""
                SELECT {LISTING_COLUMNS}, u.id AS author_id, u.full_name AS author_name, vt.name AS voice_type_name
                FROM listings l
                JOIN users u ON u.id = l.author_id AND u.deleted_at IS NULL
                LEFT JOIN voice_types vt ON vt.id = l.voice_type_id
                WHERE {" AND ".join(conditions)}
                ORDER BY {order_by_city}
                LIMIT 5
                """,
                match_params,
            )
        elif user["role"] == "conductor":
            match_params["viewer_block_id"] = user["id"]
            matches = fetch_all(
                f"""
                SELECT {LISTING_COLUMNS}, u.id AS author_id, u.full_name AS author_name, vt.name AS voice_type_name
                FROM listings l
                JOIN users u ON u.id = l.author_id AND u.deleted_at IS NULL
                LEFT JOIN voice_types vt ON vt.id = l.voice_type_id
                WHERE l.is_active = TRUE AND l.listing_type = 'seeking_conductor'
                    AND (l.event_date IS NULL OR l.event_date >= CURRENT_DATE)
                    AND NOT EXISTS (SELECT 1 FROM blocked_users bu WHERE (bu.blocker_id = :viewer_block_id AND bu.blocked_id = l.author_id) OR (bu.blocker_id = l.author_id AND bu.blocked_id = :viewer_block_id))
                ORDER BY {order_by_city}
                LIMIT 5
                """,
                match_params,
            )

    teaser_listings = []
    if not user:
        teaser_listings = fetch_all(
            f"""
            SELECT {LISTING_COLUMNS}, u.full_name AS author_name
            FROM listings l
            JOIN users u ON u.id = l.author_id AND u.deleted_at IS NULL
            WHERE l.is_active = TRUE AND (l.event_date IS NULL OR l.event_date >= CURRENT_DATE)
            ORDER BY l.created_at DESC
            LIMIT 5
            """
        )

    context = {
        "user": user,
        "matches": matches,
        "teaser_listings": teaser_listings,
        "verify_required": request.query_params.get("verify_required") == "1",
    }
    return render(request, "home.html", context)


@router.get("/board", response_class=HTMLResponse)
def board(
    request: Request,
    city: str = "",
    state: str = "",
    country: str = "",
    listing_type: str = "",
    voice_type_id: str = "",
    ensemble_type: str = "",
    q: str = "",
    tag: str = "",
    show_past: str = "",
    date_from: str = "",
    date_to: str = "",
    page: int = 1,
):
    """
    Quadro de avisos completo, com todos os filtros. Aberto para
    qualquer visitante (mesmo sem login) — o que fica bloqueado sem
    login é o *detalhe* de cada anúncio (/listings/{id}), não a lista.

    Anúncios com evento no passado ficam "arquivados" por padrão (não
    aparecem aqui, mas continuam no banco e acessíveis por link direto
    ou em /my-listings) — ?show_past=1 reexibe todos.

    Filtro de período (Zeitraum) — "não tenho nada marcado em agosto,
    me mostre o que existe entre 1º e 31/08": date_from/date_to filtram
    l.event_date dentro do intervalo. Como escolher um período explícito
    já é a pessoa dizendo exatamente qual janela de tempo importa pra
    ela, isso substitui o filtro padrão de "esconder passado" (inclusive
    permite buscar um período que já passou, de propósito). Anúncios
    sem event_date (ex: "disponível", sem data marcada) não têm como
    combinar com um período e ficam de fora quando esse filtro é usado.
    """
    user = get_current_user(request)

    conditions = ["l.is_active = TRUE"]
    params = {}

    # Quem a pessoa bloqueou some do quadro (anúncios dela não aparecem
    # mais) — bloquear é uma decisão de uma via só, não precisa checar
    # o sentido contrário aqui.
    if user:
        conditions.append(
            "NOT EXISTS (SELECT 1 FROM blocked_users bu WHERE (bu.blocker_id = :viewer_block_id AND bu.blocked_id = l.author_id) OR (bu.blocker_id = l.author_id AND bu.blocked_id = :viewer_block_id))"
        )
        params["viewer_block_id"] = user["id"]

    if not show_past and not date_from and not date_to:
        conditions.append("(l.event_date IS NULL OR l.event_date >= CURRENT_DATE)")

    if date_from:
        conditions.append("l.event_date >= :date_from")
        params["date_from"] = date_from

    if date_to:
        conditions.append("l.event_date <= :date_to")
        params["date_to"] = date_to

    if city:
        conditions.append("l.city ILIKE :city")
        params["city"] = f"%{city}%"

    if state:
        conditions.append("l.state = :state")
        params["state"] = state

    if country:
        conditions.append("l.country = :country")
        params["country"] = country

    if listing_type:
        conditions.append("l.listing_type = :listing_type")
        params["listing_type"] = listing_type

    if voice_type_id:
        conditions.append("l.voice_type_id = :voice_type_id")
        params["voice_type_id"] = int(voice_type_id)

    if ensemble_type:
        conditions.append("l.ensemble_type = :ensemble_type")
        params["ensemble_type"] = ensemble_type

    if q:
        conditions.append("(l.title ILIKE :q OR l.description ILIKE :q OR l.repertoire ILIKE :q)")
        params["q"] = f"%{q}%"

    if tag:
        conditions.append(
            "EXISTS (SELECT 1 FROM singer_composer_tags sct WHERE sct.user_id = l.author_id AND sct.tag ILIKE :tag)"
        )
        params["tag"] = f"%{tag}%"

    where_clause = " AND ".join(conditions)

    page = max(1, page)
    offset = (page - 1) * BOARD_PAGE_SIZE

    total_row = fetch_one(
        f"""
        SELECT count(*) AS n
        FROM listings l
        WHERE {where_clause}
        """,
        params,
    )
    total = total_row["n"] if total_row else 0
    total_pages = max(1, (total + BOARD_PAGE_SIZE - 1) // BOARD_PAGE_SIZE)

    # "is_saved": pra desenhar a estrelinha de favorito já marcada
    # certa em cada card, sem precisar de uma segunda consulta por
    # anúncio (N+1) — um EXISTS correlacionado resolve numa query só.
    # Sem login, ninguém tem favorito nenhum (:viewer_id = NULL não bate
    # com nada em saved_listings.user_id, que é NOT NULL).
    listings = fetch_all(
        f"""
        SELECT
            {LISTING_COLUMNS},
            u.id AS author_id, u.full_name AS author_name,
            vt.name AS voice_type_name,
            EXISTS (
                SELECT 1 FROM saved_listings sl
                WHERE sl.listing_id = l.id AND sl.user_id = :viewer_id
            ) AS is_saved
        FROM listings l
        JOIN users u ON u.id = l.author_id AND u.deleted_at IS NULL
        LEFT JOIN voice_types vt ON vt.id = l.voice_type_id
        WHERE {where_clause}
        ORDER BY l.created_at DESC
        LIMIT :limit OFFSET :offset
        """,
        {**params, "limit": BOARD_PAGE_SIZE, "offset": offset, "viewer_id": user["id"] if user else None},
    )

    voice_types = fetch_all("SELECT id, name FROM voice_types ORDER BY sort_order")

    context = {
        "user": user,
        "listings": listings,
        "voice_types": voice_types,
        "listing_type_keys": LISTING_TYPE_KEYS,
        "ensemble_type_keys": ENSEMBLE_TYPE_KEYS,
        "country_options": COUNTRY_OPTIONS,
        "state_options": STATE_OPTIONS,
        "city_options": get_city_options(),
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "filters": {
            "city": city,
            "state": state,
            "country": country,
            "listing_type": listing_type,
            "voice_type_id": voice_type_id,
            "ensemble_type": ensemble_type,
            "q": q,
            "tag": tag,
            "show_past": show_past,
            "date_from": date_from,
            "date_to": date_to,
        },
    }
    return render(request, "board.html", context)


@router.get("/listings/new", response_class=HTMLResponse)
def new_listing_form(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not user["email_verified"]:
        return RedirectResponse(url="/?verify_required=1", status_code=303)
    voice_types = fetch_all("SELECT id, name FROM voice_types ORDER BY sort_order")
    context = {
        "user": user,
        "voice_types": voice_types,
        "listing_type_keys": LISTING_TYPE_KEYS,
        "ensemble_type_keys": ENSEMBLE_TYPE_KEYS,
        "country_options": COUNTRY_OPTIONS,
        "state_options": STATE_OPTIONS,
        "city_options": get_city_options(),
        "values": {"country": "DE"},
        "is_edit": False,
        "listing_id": None,
        "error": None,
    }
    return render(request, "listing_form.html", context)


def _listing_form_error_context(user, listing_type, title, description, city, state, country,
                                 voice_type_id, repertoire, venue, fee, ensemble_type, event_date,
                                 is_edit, listing_id):
    voice_types = fetch_all("SELECT id, name FROM voice_types ORDER BY sort_order")
    return {
        "user": user,
        "voice_types": voice_types,
        "listing_type_keys": LISTING_TYPE_KEYS,
        "ensemble_type_keys": ENSEMBLE_TYPE_KEYS,
        "country_options": COUNTRY_OPTIONS,
        "state_options": STATE_OPTIONS,
        "city_options": get_city_options(),
        "values": {
            "listing_type": listing_type,
            "title": title,
            "description": description,
            "city": city,
            "state": state,
            "country": country,
            "voice_type_id": voice_type_id,
            "repertoire": repertoire,
            "venue": venue,
            "fee": fee,
            "ensemble_type": ensemble_type,
            "event_date": event_date,
        },
        "is_edit": is_edit,
        "listing_id": listing_id,
        "error": "error_required_fields",
    }


@router.post("/listings/new")
def create_listing(
    request: Request,
    background_tasks: BackgroundTasks,
    csrf_token: str = Form(""),
    listing_type: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    city: str = Form(""),
    state: str = Form(""),
    country: str = Form("DE"),
    voice_type_id: str = Form(""),
    repertoire: str = Form(""),
    venue: str = Form(""),
    fee: str = Form(""),
    ensemble_type: str = Form(""),
    event_date: str = Form(""),
):
    verify_csrf(request, csrf_token)

    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not user["email_verified"]:
        return RedirectResponse(url="/?verify_required=1", status_code=303)

    if country not in COUNTRY_OPTIONS:
        country = "DE"
    if ensemble_type not in ENSEMBLE_TYPE_KEYS:
        ensemble_type = None

    # "Estado" é obrigatório para qualquer anúncio (não só vagas) —
    # junto com Obra/Cidade/Cachê no caso específico de seeking_singer.
    if not state.strip() or not _job_fields_valid(listing_type, city, repertoire, fee):
        context = _listing_form_error_context(
            user, listing_type, title, description, city, state, country,
            voice_type_id, repertoire, venue, fee, ensemble_type, event_date, False, None,
        )
        return render(request, "listing_form.html", context, status_code=400)

    new_listing = execute_returning(
        """
        INSERT INTO listings (author_id, listing_type, title, description, city, state, country, voice_type_id, repertoire, venue, fee, ensemble_type, event_date)
        VALUES (:author_id, :listing_type, :title, :description, :city, :state, :country, :voice_type_id, :repertoire, :venue, :fee, :ensemble_type, :event_date)
        RETURNING id
        """,
        {
            "author_id": user["id"],
            "listing_type": listing_type,
            "title": title,
            "description": description,
            "city": city or None,
            "state": state.strip() or None,
            "country": country,
            "voice_type_id": int(voice_type_id) if voice_type_id else None,
            "repertoire": repertoire or None,
            "venue": venue or None,
            "fee": fee or None,
            "ensemble_type": ensemble_type,
            "event_date": event_date or None,
        },
    )

    # Alerta de anúncio compatível: manda e-mail pra quem tem o perfil
    # certo (cantor(a) da voz procurada, ou maestro(a)) — em segundo
    # plano, pra não atrasar o redirecionamento de quem postou.
    background_tasks.add_task(
        notify_matching_users,
        str(request.base_url),
        new_listing["id"],
        listing_type,
        title,
        city or None,
        user["id"],
        int(voice_type_id) if voice_type_id else None,
    )

    background_tasks.add_task(check_and_notify_new_badges, user["id"], str(request.base_url))

    return RedirectResponse(url="/my-listings", status_code=303)


@router.get("/listings/{listing_id}", response_class=HTMLResponse)
def listing_detail(request: Request, listing_id: int):
    listing = fetch_one(
        f"""
        SELECT
            {LISTING_COLUMNS}, l.author_id,
            u.full_name AS author_name, u.email AS author_email, u.phone AS author_phone,
            vt.name AS voice_type_name
        FROM listings l
        JOIN users u ON u.id = l.author_id AND u.deleted_at IS NULL
        LEFT JOIN voice_types vt ON vt.id = l.voice_type_id
        WHERE l.id = :id
        """,
        {"id": listing_id},
    )
    user = get_current_user(request)

    # "Mensagem já enviada para este anúncio" — não impede reenviar,
    # só evita que a pessoa esqueça e fique enchendo a caixa de
    # entrada de quem postou com a mesma pergunta várias vezes.
    already_messaged = False
    if user and listing and user["id"] != listing["author_id"]:
        existing_message = fetch_one(
            "SELECT 1 FROM messages WHERE sender_id = :sender AND listing_id = :listing_id LIMIT 1",
            {"sender": user["id"], "listing_id": listing_id},
        )
        already_messaged = existing_message is not None

    is_saved = False
    already_reported = False
    if user and listing:
        saved = fetch_one(
            "SELECT 1 FROM saved_listings WHERE user_id = :user_id AND listing_id = :listing_id",
            {"user_id": user["id"], "listing_id": listing_id},
        )
        is_saved = saved is not None

        reported = fetch_one(
            "SELECT 1 FROM listing_reports WHERE reporter_id = :user_id AND listing_id = :listing_id",
            {"user_id": user["id"], "listing_id": listing_id},
        )
        already_reported = reported is not None

    context = {
        "user": user,
        "listing": listing,
        "already_messaged": already_messaged,
        "is_saved": is_saved,
        "already_reported": already_reported,
        "reported_just_now": request.query_params.get("reported") == "1",
        # Freemium: sem login dá pra ver que o anúncio existe (título,
        # cidade, tipo, bolinha de status) mas não a descrição completa
        # nem os dados de contato — isso incentiva o cadastro.
        "locked": user is None,
    }
    return render(request, "listing_detail.html", context)


@router.post("/listings/{listing_id}/report")
def report_listing(request: Request, listing_id: int, csrf_token: str = Form(""), reason: str = Form("")):
    """
    Denunciar anúncio: exige que a pessoa escreva o motivo (mínimo de
    10 caracteres, reforçado também no banco via CHECK). Não existe
    nenhuma tela de moderação no site — as denúncias ficam guardadas
    em listing_reports pra serem consultadas direto no banco por quem
    administra o site (mesmo padrão já usado em profile_views).
    """
    verify_csrf(request, csrf_token)
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    listing = fetch_one("SELECT id, author_id FROM listings WHERE id = :id", {"id": listing_id})
    reason = reason.strip()
    if not listing or listing["author_id"] == user["id"] or len(reason) < 10:
        return RedirectResponse(url=f"/listings/{listing_id}", status_code=303)

    execute(
        "INSERT INTO listing_reports (listing_id, reporter_id, reason) VALUES (:listing_id, :reporter_id, :reason)",
        {"listing_id": listing_id, "reporter_id": user["id"], "reason": reason},
    )
    return RedirectResponse(url=f"/listings/{listing_id}?reported=1", status_code=303)


@router.get("/listings/{listing_id}/edit", response_class=HTMLResponse)
def edit_listing_form(request: Request, listing_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    listing = fetch_one("SELECT * FROM listings WHERE id = :id", {"id": listing_id})
    if not listing or listing["author_id"] != user["id"]:
        return RedirectResponse(url=f"/listings/{listing_id}", status_code=303)

    voice_types = fetch_all("SELECT id, name FROM voice_types ORDER BY sort_order")
    context = {
        "user": user,
        "voice_types": voice_types,
        "listing_type_keys": LISTING_TYPE_KEYS,
        "ensemble_type_keys": ENSEMBLE_TYPE_KEYS,
        "country_options": COUNTRY_OPTIONS,
        "state_options": STATE_OPTIONS,
        "city_options": get_city_options(),
        "values": listing,
        "is_edit": True,
        "listing_id": listing_id,
        "error": None,
    }
    return render(request, "listing_form.html", context)


@router.post("/listings/{listing_id}/edit")
def update_listing(
    request: Request,
    listing_id: int,
    csrf_token: str = Form(""),
    listing_type: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    city: str = Form(""),
    state: str = Form(""),
    country: str = Form("DE"),
    voice_type_id: str = Form(""),
    repertoire: str = Form(""),
    venue: str = Form(""),
    fee: str = Form(""),
    ensemble_type: str = Form(""),
    event_date: str = Form(""),
):
    verify_csrf(request, csrf_token)

    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    existing = fetch_one("SELECT author_id FROM listings WHERE id = :id", {"id": listing_id})
    if not existing or existing["author_id"] != user["id"]:
        return RedirectResponse(url=f"/listings/{listing_id}", status_code=303)

    if country not in COUNTRY_OPTIONS:
        country = "DE"
    if ensemble_type not in ENSEMBLE_TYPE_KEYS:
        ensemble_type = None

    if not state.strip() or not _job_fields_valid(listing_type, city, repertoire, fee):
        context = _listing_form_error_context(
            user, listing_type, title, description, city, state, country,
            voice_type_id, repertoire, venue, fee, ensemble_type, event_date, True, listing_id,
        )
        return render(request, "listing_form.html", context, status_code=400)

    execute(
        """
        UPDATE listings
        SET listing_type = :listing_type, title = :title, description = :description,
            city = :city, state = :state, country = :country, voice_type_id = :voice_type_id, repertoire = :repertoire,
            venue = :venue, fee = :fee, ensemble_type = :ensemble_type, event_date = :event_date, updated_at = now()
        WHERE id = :id
        """,
        {
            "id": listing_id,
            "listing_type": listing_type,
            "title": title,
            "description": description,
            "city": city or None,
            "state": state.strip() or None,
            "country": country,
            "voice_type_id": int(voice_type_id) if voice_type_id else None,
            "repertoire": repertoire or None,
            "venue": venue or None,
            "fee": fee or None,
            "ensemble_type": ensemble_type,
            "event_date": event_date or None,
        },
    )
    return RedirectResponse(url=f"/listings/{listing_id}", status_code=303)


@router.post("/listings/{listing_id}/delete")
def delete_listing(request: Request, listing_id: int, csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)

    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    listing = fetch_one("SELECT author_id FROM listings WHERE id = :id", {"id": listing_id})
    if listing and listing["author_id"] == user["id"]:
        execute("DELETE FROM listings WHERE id = :id", {"id": listing_id})
    return RedirectResponse(url="/", status_code=303)


@router.get("/my-listings", response_class=HTMLResponse)
def my_listings(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    listings = fetch_all(
        f"""
        SELECT l.id, l.title, l.listing_type, l.city, l.is_active, l.created_at, {EVENT_STATUS_SQL}
        FROM listings l
        WHERE l.author_id = :author_id
        ORDER BY l.created_at DESC
        """,
        {"author_id": user["id"]},
    )
    context = {
        "user": user,
        "listings": listings,
    }
    return render(request, "my_listings.html", context)


@router.post("/listings/{listing_id}/save")
def save_listing(request: Request, listing_id: int, csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    listing = fetch_one("SELECT id FROM listings WHERE id = :id", {"id": listing_id})
    if listing:
        # ON CONFLICT DO NOTHING: favoritar de novo algo que já está
        # favoritado simplesmente não faz nada (idempotente), em vez
        # de dar erro de UNIQUE constraint.
        execute(
            """
            INSERT INTO saved_listings (user_id, listing_id) VALUES (:user_id, :listing_id)
            ON CONFLICT (user_id, listing_id) DO NOTHING
            """,
            {"user_id": user["id"], "listing_id": listing_id},
        )
    return RedirectResponse(url=f"/listings/{listing_id}", status_code=303)


@router.post("/listings/{listing_id}/unsave")
def unsave_listing(request: Request, listing_id: int, csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    execute(
        "DELETE FROM saved_listings WHERE user_id = :user_id AND listing_id = :listing_id",
        {"user_id": user["id"], "listing_id": listing_id},
    )
    # Se veio da própria página de favoritos, volta pra lá (senão o
    # item "desaparecido" ainda apareceria até o próximo refresh);
    # senão volta pro anúncio como de costume.
    referer = request.headers.get("referer", "")
    if "/my-favorites" in referer:
        return RedirectResponse(url="/my-favorites", status_code=303)
    return RedirectResponse(url=f"/listings/{listing_id}", status_code=303)


@router.get("/my-favorites", response_class=HTMLResponse)
def my_favorites(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    listings = fetch_all(
        f"""
        SELECT {LISTING_COLUMNS}, u.id AS author_id, u.full_name AS author_name, vt.name AS voice_type_name,
            sl.created_at AS saved_at
        FROM saved_listings sl
        JOIN listings l ON l.id = sl.listing_id
        JOIN users u ON u.id = l.author_id AND u.deleted_at IS NULL
        LEFT JOIN voice_types vt ON vt.id = l.voice_type_id
        WHERE sl.user_id = :user_id
        ORDER BY sl.created_at DESC
        """,
        {"user_id": user["id"]},
    )
    context = {
        "user": user,
        "listings": listings,
    }
    return render(request, "my_favorites.html", context)

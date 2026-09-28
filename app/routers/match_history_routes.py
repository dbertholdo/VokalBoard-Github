"""Owner/admin-only Match history. Moderation alone does not grant access."""
from datetime import date
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from app.auth import get_current_user
from app.csrf import verify_csrf
from app.database import fetch_all, fetch_one
from app.match_history import can_view_match_history
from app.match_evaluations import CATEGORIES, can_evaluate, get_my_evaluations, submit_evaluation
from app.invoice_deadlines import can_request_match_invoice
from app.invoice_match_drafts import get_drafts
from app.fees import format_fee
from app.i18n import translate
from app.render import render
from app.match_service import count_pending_for_user

router = APIRouter()


# ONE Matches page (menu reorg 2026-09-28): "Confirmed" = confirmed and the
# event hasn't passed; "History & ratings" = everything else (where the
# 14-day evaluation happens). An admin looking at someone (?user_id=) sees all.
_EVENT_DATE_SQL = "NULLIF(COALESCE(m.listing_snapshot->>'event_date', l.event_date::text), '')::date"
_VIEW_CLAUSES = {
    'all': '',
    'confirmed': f"AND m.status = 'confirmed' AND ({_EVENT_DATE_SQL} IS NULL OR {_EVENT_DATE_SQL} >= CURRENT_DATE)",
    'history': f"AND NOT (m.status = 'confirmed' AND ({_EVENT_DATE_SQL} IS NULL OR {_EVENT_DATE_SQL} >= CURRENT_DATE))",
}

_HISTORY_SQL = '''
        SELECT m.id, m.status, m.created_at, m.completed_at, m.invoice_sent_at,
               COALESCE(m.listing_snapshot->>'title',l.title) AS title,
               COALESCE(m.listing_snapshot->>'event_date',l.event_date::text) AS event_date,
               COALESCE(m.listing_snapshot->>'fee',l.fee) AS legacy_fee,
               COALESCE(v.fee_amount, (m.listing_snapshot->>'fee_amount')::numeric) AS fee_amount,
               COALESCE(v.fee_currency, m.listing_snapshot->>'fee_currency') AS fee_currency,
               COALESCE(v.fee_negotiable, (m.listing_snapshot->>'fee_negotiable')::boolean, FALSE) AS fee_negotiable,
               artist.full_name AS artist_name, contractor.full_name AS contractor_name,
               m.artist_user_id, m.contractor_user_id,
               artist.email AS artist_email, artist.phone AS artist_phone,
               contractor.email AS contractor_email, contractor.phone AS contractor_phone
        FROM job_matches m
        LEFT JOIN listings l ON l.id = m.listing_id
        LEFT JOIN listing_vacancies v ON v.id = m.vacancy_id
        JOIN users artist ON artist.id = m.artist_user_id
        JOIN users contractor ON contractor.id = m.contractor_user_id
        WHERE (m.artist_user_id = :owner OR m.contractor_user_id = :owner) '''
_HISTORY_ORDER = ' ORDER BY m.created_at DESC, m.id DESC LIMIT 21 OFFSET :offset'


@router.get('/matches')
def matches_entry(request: Request):
    """Top-bar "Matches": Open when something waits for my answer, else Confirmed."""
    viewer = get_current_user(request)
    if not viewer:
        return RedirectResponse('/login', status_code=303)
    return RedirectResponse('/invitations?tab=pending' if count_pending_for_user(viewer['id']) else '/profile/matches?view=confirmed',
                            status_code=303)


@router.get('/profile/matches')
def match_history(request: Request, user_id: int | None = None, page: int = 1, view: str = 'confirmed'):
    viewer = get_current_user(request)
    if not viewer:
        return RedirectResponse('/login', status_code=303)
    owner_id = viewer['id'] if user_id is None else user_id
    if not can_view_match_history(viewer, owner_id):
        raise HTTPException(status_code=403)
    page = max(1, page)
    view = 'all' if user_id is not None and owner_id != viewer['id'] else (view if view in ('confirmed', 'history') else 'confirmed')
    rows = fetch_all(_HISTORY_SQL + _VIEW_CLAUSES[view] + _HISTORY_ORDER,  # nosec B608 - fixed clause from _VIEW_CLAUSES
                     {'owner': owner_id, 'offset': (page - 1) * 20})

    # P2.C: e-mail and phone are only ever shown here, once a Match
    # exists between the two people — regardless of the phone's own
    # public-profile visibility setting. "cancelled" matches don't
    # reveal contact info (the match never actually happened).
    page_rows = rows[:20]
    own_list = owner_id == viewer['id']
    # Batched per page (CLAUDE.md §4) instead of one query per Match.
    my_evaluations = get_my_evaluations([r['id'] for r in page_rows], viewer['id']) if own_list else {}
    drafts = get_drafts([r['id'] for r in page_rows]) if own_list else {}
    negotiable_label = translate('fee_negotiable_label', getattr(getattr(request, 'state', None), 'lang', 'de'))
    matches = []
    for row in page_rows:
        m = dict(row)
        # #55: the fee comes from the matched vacancy (listings.fee is legacy text).
        m['fee'] = (format_fee(m['fee_amount'], m['fee_currency'] or 'EUR', m['fee_negotiable'], negotiable_label)
                    or m['legacy_fee'])
        is_artist = m['artist_user_id'] == owner_id
        counterpart_email = m['contractor_email'] if is_artist else m['artist_email']
        counterpart_phone = m['contractor_phone'] if is_artist else m['artist_phone']
        m['reveal_contact'] = m['status'] in ('confirmed', 'completed') and owner_id == viewer['id']
        m['counterpart_email'] = counterpart_email if m['reveal_contact'] else None
        m['counterpart_phone'] = counterpart_phone if m['reveal_contact'] else None

        # P3.F: só o próprio dono desta lista pode avaliar (não faz
        # sentido o Admin avaliar em nome de alguém) — e só dentro da
        # janela de 14 dias após o evento. A avaliação em si (se já foi
        # dada) é secreta mesmo pro próprio avaliador ver de volta aqui
        # além de "já avaliei" — nunca mostramos a nota do OUTRO lado.
        m['can_evaluate'] = False
        m['my_evaluation'] = None
        event_date = row['event_date']
        try:
            event_date = date.fromisoformat(str(event_date)) if event_date else None
        except ValueError:
            event_date = None
        if owner_id == viewer['id']:
            m['can_evaluate'] = can_evaluate(m['status'], event_date)
            if m['can_evaluate']:
                m['my_evaluation'] = my_evaluations.get(m['id'])

        # P4: botões de Rechnung — só pro próprio dono desta lista (nunca
        # pro Admin agindo por outra pessoa). O rascunho em si (se
        # existir) é criptografado — só sabemos o status, nunca o
        # conteúdo, até alguém abrir o preview (ver invoice_match_drafts.py).
        m['is_issuer'] = m['artist_user_id'] == owner_id
        m['invoice_draft'] = None
        m['can_request_invoice'] = False
        if owner_id == viewer['id'] and m['status'] != 'cancelled':
            m['invoice_draft'] = drafts.get(m['id'])
            if not m['invoice_draft'] and not m['invoice_sent_at']:
                m['can_request_invoice'] = can_request_match_invoice(event_date, date.today())
        matches.append(m)

    response = render(request, 'match_history.html', {
        'user': viewer, 'matches': matches, 'has_next': len(rows) > 20, 'page': page, 'view': view,
        'eval_categories': list(CATEGORIES.keys()),
    })
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@router.post('/profile/matches/{match_id}/evaluate')
def submit_match_evaluation(
    request: Request, match_id: int, csrf_token: str = Form(''),
    punctuality: int = Form(...), preparation: int = Form(...), musicality: int = Form(...),
    communication: int = Form(...), collaboration: int = Form(...),
):
    """P3.F: só quem participou do Match pode avaliar o OUTRO lado, só
    dentro da janela de 14 dias. Secreto — o outro lado nunca vê essa
    nota, em lugar nenhum (ver app/match_evaluations.py)."""
    verify_csrf(request, csrf_token)
    viewer = get_current_user(request)
    if not viewer:
        return RedirectResponse('/login', status_code=303)

    match = fetch_one(
        '''
        SELECT m.status, m.artist_user_id, m.contractor_user_id, l.event_date
        FROM job_matches m
        LEFT JOIN listings l ON l.id = m.listing_id
        WHERE m.id = :id
        ''',
        {'id': match_id},
    )
    if not match or viewer['id'] not in (match['artist_user_id'], match['contractor_user_id']):
        raise HTTPException(status_code=404)
    if not can_evaluate(match['status'], match['event_date']):
        return RedirectResponse('/profile/matches?eval_error=1', status_code=303)

    rated_id = match['contractor_user_id'] if viewer['id'] == match['artist_user_id'] else match['artist_user_id']
    try:
        submit_evaluation(match_id, viewer['id'], rated_id, {
            'punctuality': punctuality, 'preparation': preparation, 'musicality': musicality,
            'communication': communication, 'collaboration': collaboration,
        })
    except ValueError:
        return RedirectResponse('/profile/matches?eval_error=1', status_code=303)
    return RedirectResponse('/profile/matches?evaluated=1', status_code=303)

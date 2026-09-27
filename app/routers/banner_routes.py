from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from app.database import engine, fetch_all, fetch_one
from app.permissions import require_level, LEVEL_GOD
from app.csrf import verify_csrf
from app.client_ip import get_client_ip
from app.render import render
from app.banners import AUDIENCES, safe_banner_link

router = APIRouter()
STATES = {'active': 'Active', 'inactive': 'Inactive', 'deleted': 'Deleted', 'all': 'All'}

def authorize(request):
    user = require_level(request, LEVEL_GOD)
    if not user:
        raise HTTPException(403)
    return user

def audit(conn, request, user, action, banner_id):
    conn.execute(text('''INSERT INTO audit_log (actor_user_id, action, details, ip_address)
        VALUES (:actor, :action, :details, :ip)'''),
        {'actor': user['id'], 'action': 'banner_' + action,
         'details': f'banner_id={banner_id}', 'ip': get_client_ip(request)})

@router.get('/admin/banners')
def index(request: Request, state: str = 'active', edit: int = 0, page: int = 1):
    user = authorize(request)
    clauses = {'active': 'is_active AND deleted_at IS NULL',
               'inactive': 'NOT is_active AND deleted_at IS NULL',
               'deleted': 'deleted_at IS NOT NULL', 'all': 'TRUE'}
    state = state if state in clauses else 'active'
    page = max(1, page)
    rows = fetch_all('SELECT * FROM site_banners WHERE ' + clauses[state] +
                     ' ORDER BY id DESC LIMIT 21 OFFSET :offset', {'offset': (page - 1) * 20})
    return render(request, 'admin_banners.html', {
        'user': user, 'banners': rows[:20], 'has_next': len(rows) > 20,
        'page': page, 'state': state, 'states': STATES, 'audiences': AUDIENCES,
        'editing': fetch_one('SELECT * FROM site_banners WHERE id=:id AND deleted_at IS NULL', {'id': edit}) if edit else None,
        'voices': fetch_all('SELECT id, name FROM voice_types ORDER BY sort_order, id'),
    })

@router.post('/admin/banners/save')
def save(request: Request, csrf_token: str = Form(''), banner_id: int = Form(0),
         title: str = Form(...), body: str = Form(...), link_url: str = Form(''),
         audience: str = Form('all'), voice_type_id: str = Form(''), is_active: str = Form('')):
    user = authorize(request)
    verify_csrf(request, csrf_token)
    title, body = title.strip(), body.strip()
    if not title or len(title) > 150 or not body or len(body) > 500 or len(link_url) > 500 or audience not in AUDIENCES:
        raise HTTPException(400, 'Confira os limites de texto e o público selecionado.')
    try:
        link = safe_banner_link(link_url)
        voice = int(voice_type_id) if voice_type_id else None
    except ValueError:
        raise HTTPException(400, 'Link ou voz inválidos.')
    if voice is not None and (audience != 'singer' or not fetch_one('SELECT id FROM voice_types WHERE id=:id', {'id': voice})):
        raise HTTPException(400, 'Escolha Cantores para segmentar por voz.')
    params = dict(title=title, body=body, link=link, audience=audience, voice=voice, active=bool(is_active), id=banner_id)
    with engine.begin() as conn:
        if banner_id:
            row = conn.execute(text('''UPDATE site_banners SET title=:title, body=:body,
                link_url=:link, audience=:audience, voice_type_id=:voice, is_active=:active,
                updated_at=now() WHERE id=:id AND deleted_at IS NULL RETURNING id'''), params).first()
        else:
            row = conn.execute(text('''INSERT INTO site_banners
                (title,body,link_url,audience,voice_type_id,is_active)
                VALUES (:title,:body,:link,:audience,:voice,:active) RETURNING id'''), params).first()
        if not row:
            raise HTTPException(404)
        audit(conn, request, user, 'edit' if banner_id else 'create', row[0])
    return RedirectResponse('/admin/banners?state=all', status_code=303)

@router.post('/admin/banners/{banner_id}/{action}')
def change(request: Request, banner_id: int, action: str, csrf_token: str = Form('')):
    user = authorize(request)
    verify_csrf(request, csrf_token)
    updates = {
        'activate': ('is_active=TRUE', 'deleted_at IS NULL'),
        'deactivate': ('is_active=FALSE', 'deleted_at IS NULL'),
        'delete': ('is_active=FALSE, deleted_at=now()', 'deleted_at IS NULL'),
        'restore': ('is_active=FALSE, deleted_at=NULL', 'deleted_at IS NOT NULL'),
    }
    if action not in updates:
        raise HTTPException(404)
    assignment, condition = updates[action]
    with engine.begin() as conn:
        row = conn.execute(text(f'UPDATE site_banners SET {assignment}, updated_at=now() WHERE id=:id AND {condition} RETURNING id'), {'id': banner_id}).first()
        if not row:
            raise HTTPException(404)
        audit(conn, request, user, action, banner_id)
    return RedirectResponse('/admin/banners?state=all', status_code=303)

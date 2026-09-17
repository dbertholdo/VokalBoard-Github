import uuid
import pytest
from app.database import execute, fetch_one
from app.banners import visible_banners
from tests.test_security import register_test_user, extract_csrf

@pytest.fixture
def banner_admin(client):
    uid, _, _ = register_test_user(client)
    execute('UPDATE users SET role_level=3 WHERE id=:id', {'id': uid})
    title = 'banner_test_' + uuid.uuid4().hex
    yield uid, title
    execute("DELETE FROM audit_log WHERE actor_user_id=:id AND action LIKE 'banner_%'", {'id': uid})
    execute('DELETE FROM site_banners WHERE title=:title', {'title': title})

def test_banner_lifecycle_audit_and_public_display(client, banner_admin):
    uid, title = banner_admin
    token = extract_csrf(client.get('/admin/banners').text)
    data = dict(csrf_token=token, title=title, body='<script>alert(1)</script>', audience='all', is_active='1', link_url='/board')
    assert client.post('/admin/banners/save', data=data, follow_redirects=False).status_code == 303
    bid = fetch_one('SELECT id FROM site_banners WHERE title=:t', {'t': title})['id']
    response = client.get('/')
    assert title in response.text and '&lt;script&gt;alert(1)&lt;/script&gt;' in response.text
    data.update(banner_id=bid, body='Edited text')
    assert client.post('/admin/banners/save', data=data, follow_redirects=False).status_code == 303
    assert 'Edited text' in client.get('/').text
    for action in ('deactivate', 'activate', 'delete', 'restore'):
        assert client.post(f'/admin/banners/{bid}/{action}', data={'csrf_token': token}, follow_redirects=False).status_code == 303
        row = fetch_one('SELECT * FROM site_banners WHERE id=:id', {'id': bid})
        assert row['is_active'] == (action == 'activate')
        assert bool(row['deleted_at']) == (action == 'delete')
        assert (title in client.get('/').text) == (action == 'activate')
    assert fetch_one("SELECT count(*) n FROM audit_log WHERE actor_user_id=:id AND action LIKE 'banner_%'", {'id':uid})['n'] == 6

def test_banner_permissions_csrf_and_invalid_link(client, banner_admin):
    uid, title = banner_admin
    token = extract_csrf(client.get('/admin/banners').text)
    data = dict(title=title, body='text', audience='all')
    assert client.post('/admin/banners/save', data=data).status_code == 400
    assert client.post('/admin/banners/save', data={**data, 'csrf_token':token, 'link_url':'javascript:alert(1)'}).status_code == 400
    for level in (0,1,2):
        execute('UPDATE users SET role_level=:level WHERE id=:id', {'level':level, 'id':uid})
        assert client.get('/admin/banners').status_code == 403
        assert client.post('/admin/banners/save', data={**data, 'csrf_token':token}).status_code == 403
        assert client.post('/admin/banners/1/activate', data={'csrf_token':token}).status_code == 403

def test_banner_audiences_and_secondary_voice(client, banner_admin):
    uid, title = banner_admin
    voice = fetch_one("SELECT id FROM voice_types WHERE name='Tenor'")['id']
    execute('INSERT INTO singer_profile_voice_types (user_id,voice_type_id) VALUES (:u,:v) ON CONFLICT DO NOTHING', {'u':uid,'v':voice})
    token = extract_csrf(client.get('/admin/banners').text)
    data = dict(csrf_token=token, title=title, body='text', audience='singer', voice_type_id=str(voice), is_active='1')
    client.post('/admin/banners/save', data=data)
    user = {'id':uid, 'role':'singer'}
    assert title in [b['title'] for b in visible_banners(user)]
    assert title not in [b['title'] for b in visible_banners(None)]
    assert title not in [b['title'] for b in visible_banners({'id':uid,'role':'conductor'})]
    execute("UPDATE site_banners SET audience='no_subscription',voice_type_id=NULL WHERE title=:t", {'t':title})
    assert title in [b['title'] for b in visible_banners(user)]
    # Existing subscription schema permits a lifetime subscription (NULL expiry).
    execute("INSERT INTO subscriptions (user_id,is_active,price_paid_cents,currency) VALUES (:u,TRUE,590,'EUR')", {'u':uid})
    assert title not in [b['title'] for b in visible_banners(user)]

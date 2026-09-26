"""Lifecycle integration tests. Destructive worker runs ONLY on a dedicated test DB."""
from datetime import date, datetime, timedelta, timezone
import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.database import engine, execute, fetch_one
from app.retention_rules import availability_valid, warning_days
from app.retention_worker import run_retention
from tests.test_security import register_test_user, extract_csrf


@pytest.fixture
def db():
    if 'retention_test' not in engine.url.database:
        pytest.skip('Lifecycle integration requires dedicated retention_test database')
    conn = engine.connect()
    tx = conn.begin()
    yield conn
    tx.rollback()
    conn.close()


def user(conn):
    return conn.execute(text("INSERT INTO users(email,password_hash,full_name,role) VALUES(:e,'x','Test musician','singer') RETURNING id"),
                        {'e':f'sectest_{uuid.uuid4().hex}@example.com'}).scalar_one()


def listing(conn, owner, event='CURRENT_DATE', available=False):
    kind = 'singer_available' if available else 'seeking_singer'
    return conn.execute(text(f"""INSERT INTO listings(author_id,listing_type,title,description,event_date,available_from,available_until)
        VALUES(:u,:kind,'Test work','Description',{event},
               {'CURRENT_DATE' if available else 'NULL'}, {'CURRENT_DATE+29' if available else 'NULL'}) RETURNING id"""),
        {'u':owner, 'kind':kind}).scalar_one()


def test_period_and_warning_boundaries():
    assert availability_valid('2026-09-01','2026-09-30')
    assert availability_valid('2026-09-01','2026-09-01')
    assert not availability_valid('2026-09-01','2026-10-01')
    assert not availability_valid('2026-09-02','2026-09-01')
    assert not availability_valid('bad','2026-09-01')
    now = datetime.now(timezone.utc)
    # Messenger (2026-09-26): 60-day expiry, "!" during the last 10 days.
    assert warning_days(now-timedelta(days=50),now)==10
    assert warning_days(now-timedelta(days=59),now)==1
    assert warning_days(now-timedelta(days=49),now) is None
    assert warning_days(now-timedelta(days=60),now) is None


def test_quota_and_edit_and_delete_slot(db):
    owner=user(db)
    first=listing(db,owner,available=True)
    listing(db,owner,available=True)
    db.execute(text('UPDATE listings SET title=title WHERE id=:id'),{'id':first})
    with pytest.raises(IntegrityError, match='availability_limit'):
        with db.begin_nested():
            listing(db,owner,available=True)
    db.execute(text('UPDATE listings SET archived_at=now(),deleted_at=now() WHERE id=:id'),{'id':first})
    listing(db,owner,available=True)


def test_retention_boundaries_and_audit(db):
    owner=user(db)
    recent=listing(db,owner,'CURRENT_DATE-29')
    archived=listing(db,owner,'CURRENT_DATE-30')
    old=listing(db,owner,'CURRENT_DATE-91')
    preview=run_retention(db, dry_run=True)
    assert preview['listings_purge'] >= 1
    assert db.execute(text('SELECT archived_at FROM listings WHERE id=:id'),{'id':archived}).scalar() is None
    assert db.execute(text('SELECT id FROM visible_listings WHERE id=:id'),{'id':recent}).scalar()==recent
    assert db.execute(text('SELECT id FROM visible_listings WHERE id=:id'),{'id':archived}).scalar() is None
    run_retention(db)
    assert db.execute(text('SELECT archived_at FROM listings WHERE id=:id'),{'id':archived}).scalar() is not None
    assert db.execute(text('SELECT id FROM listings WHERE id=:id'),{'id':old}).scalar() is None
    actions=db.execute(text("SELECT action FROM content_lifecycle_log WHERE entity_type='listings' AND entity_id=:id"),{'id':old}).scalars().all()
    assert set(actions)=={'posted','archived','purged'}
    count=db.execute(text('SELECT count(*) FROM content_lifecycle_log')).scalar()
    run_retention(db)
    assert db.execute(text('SELECT count(*) FROM content_lifecycle_log')).scalar()==count


def test_match_survives_listing_purge(db):
    artist,contractor=user(db),user(db)
    job=listing(db,contractor,'CURRENT_DATE-91')
    vacancy=db.execute(text('INSERT INTO listing_vacancies(listing_id,voice_type_id) SELECT :l,id FROM voice_types LIMIT 1 RETURNING id'),{'l':job}).scalar_one()
    match=db.execute(text('INSERT INTO job_matches(listing_id,vacancy_id,artist_user_id,contractor_user_id) VALUES(:l,:v,:a,:c) RETURNING id'),{'l':job,'v':vacancy,'a':artist,'c':contractor}).scalar_one()
    run_retention(db)
    row=db.execute(text('SELECT * FROM job_matches WHERE id=:id'),{'id':match}).mappings().one()
    assert row['listing_id'] is None and row['vacancy_id'] is None
    assert row['listing_snapshot']['title']=='Test work'
    assert row['artist_user_id']==artist


def test_manual_archive_preserves_final_match_details(db):
    artist,contractor=user(db),user(db)
    job=listing(db,contractor,'CURRENT_DATE+10')
    match=db.execute(text('INSERT INTO job_matches(listing_id,artist_user_id,contractor_user_id) VALUES(:l,:a,:c) RETURNING id'),{'l':job,'a':artist,'c':contractor}).scalar_one()
    db.execute(text("UPDATE listings SET title='Final agreed work', archived_at=now()-interval '60 days', deleted_at=now()-interval '60 days' WHERE id=:id"),{'id':job})
    run_retention(db)
    row=db.execute(text('SELECT * FROM job_matches WHERE id=:id'),{'id':match}).mappings().one()
    assert row['listing_id'] is None
    assert row['listing_snapshot']['title']=='Final agreed work'


def test_availability_expires_from_end_not_event(db):
    owner=user(db)
    job=listing(db,owner,'CURRENT_DATE-100',available=True)
    run_retention(db)
    assert db.execute(text('SELECT id FROM visible_listings WHERE id=:id'),{'id':job}).scalar()==job
    db.execute(text('UPDATE listings SET available_from=CURRENT_DATE-59,available_until=CURRENT_DATE-30 WHERE id=:id'),{'id':job})
    run_retention(db)
    assert db.execute(text('SELECT id FROM visible_listings WHERE id=:id'),{'id':job}).scalar() is None
    assert db.execute(text('SELECT id FROM listings WHERE id=:id'),{'id':job}).scalar()==job


def test_history_http_privacy(client):
    from fastapi.testclient import TestClient
    from app.main import app
    owner,_,_=register_test_user(client)
    assert client.get('/profile/matches').status_code==200
    assert 'no-store' in client.get('/profile/matches').headers['cache-control']
    other=TestClient(app)
    stranger,_,_=register_test_user(other)
    assert other.get(f'/profile/matches?user_id={owner}').status_code==403
    execute('UPDATE users SET role_level=1 WHERE id=:u',{'u':stranger})
    assert other.get(f'/profile/matches?user_id={owner}').status_code==403
    execute('UPDATE users SET role_level=2 WHERE id=:u',{'u':stranger})
    assert other.get(f'/profile/matches?user_id={owner}').status_code==200
    assert TestClient(app).get('/profile/matches',follow_redirects=False).status_code==303


def test_conversation_activity_and_no_resurrection(db):
    a,b=user(db),user(db)
    def send(age):
        return db.execute(text("INSERT INTO messages(sender_id,recipient_id,body,created_at) VALUES(:a,:b,'Test',now()-make_interval(days=>:days)) RETURNING id"),{'a':a,'b':b,'days':age}).scalar_one()
    old=send(61)  # conversation expired (60 days) — its history must not come back
    new=send(0)
    assert db.execute(text('SELECT id FROM messages WHERE id=:id'),{'id':old}).scalar() is None
    assert db.execute(text('SELECT id FROM visible_messages WHERE id=:id'),{'id':new}).scalar()==new
    conv=db.execute(text('SELECT conversation_id FROM messages WHERE id=:id'),{'id':new}).scalar()
    db.execute(text("UPDATE conversations SET last_activity_at=now()-interval '61 days' WHERE id=:id"),{'id':conv})
    assert db.execute(text('SELECT id FROM visible_messages WHERE id=:id'),{'id':new}).scalar() is None
    run_retention(db)
    assert db.execute(text('SELECT id FROM messages WHERE id=:id'),{'id':new}).scalar() is None
    assert db.execute(text('SELECT id FROM conversations WHERE id=:id'),{'id':conv}).scalar() is None


def test_reply_resets_clock_read_does_not(db):
    a,b=user(db),user(db)
    old=db.execute(text("INSERT INTO messages(sender_id,recipient_id,body,created_at) VALUES(:a,:b,'Old',now()-interval '25 days') RETURNING id"),{'a':a,'b':b}).scalar_one()
    clock=lambda: db.execute(text('SELECT c.last_activity_at FROM conversations c JOIN messages m ON m.conversation_id=c.id WHERE m.id=:id'),{'id':old}).scalar()
    before=clock()
    db.execute(text('UPDATE messages SET read_at=now() WHERE id=:id'),{'id':old})
    assert clock()==before
    db.execute(text("INSERT INTO messages(sender_id,recipient_id,body) VALUES(:b,:a,'Reply')"),{'a':a,'b':b})
    assert clock()>before


def test_availability_http_and_private_expired_urls(client, monkeypatch):
    import app.routers.listings_routes as routes
    monkeypatch.setattr(routes,'notify_matching_users',lambda *args:None)
    monkeypatch.setattr(routes,'check_and_notify_new_badges',lambda *args:None)
    uid,_,_=register_test_user(client)
    execute('UPDATE users SET email_verified=TRUE WHERE id=:u',{'u':uid})
    token=extract_csrf(client.get('/listings/new').text)
    today=date.today()
    data={'csrf_token':token,'listing_type':'singer_available','title':'Availability','description':'Test',
          'available_from':str(today),'available_until':str(today+timedelta(days=29))}
    assert client.post('/listings/new',data=data,follow_redirects=False).status_code==303
    assert client.post('/listings/new',data=data,follow_redirects=False).status_code==303
    assert client.post('/listings/new',data=data,follow_redirects=False).status_code==400
    row=fetch_one('SELECT * FROM listings WHERE author_id=:u ORDER BY id LIMIT 1',{'u':uid})
    assert row['country'] is None and row['available_until'] == today+timedelta(days=29)
    execute('UPDATE listings SET archived_at=now() WHERE id=:id',{'id':row['id']})
    response=client.get('/listings/'+str(row['id']))
    assert 'Availability' not in response.text

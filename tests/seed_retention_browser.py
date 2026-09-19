"""Disposable browser fixture; refuses any non-retention_test database.

Run as python -m tests.seed_retention_browser in the isolated test container.
Credentials below are synthetic, local-test-only, not application secrets.
"""
from uuid import uuid4
from sqlalchemy import text
from app.database import engine
from app.auth import hash_password


def main():
    if 'retention_test' not in (engine.url.database or ''):
        raise RuntimeError('Only a dedicated retention_test database is allowed')
    email = f'sectest_browser_{uuid4().hex[:8]}@example.com'
    with engine.begin() as conn:
        uid = conn.execute(text("""INSERT INTO users(email,password_hash,full_name,role,email_verified)
            VALUES(:email,:password,'Retention Browser QA','singer',TRUE) RETURNING id"""),
            {'email':email,'password':hash_password('Local-test-only-482!')}).scalar_one()
        peer = conn.execute(text("""INSERT INTO users(email,password_hash,full_name,role,email_verified)
            VALUES(:email,'disabled','QA Partner','conductor',TRUE) RETURNING id"""),
            {'email':f'sectest_peer_{uuid4().hex}@example.com'}).scalar_one()
        for index in range(21):
            conn.execute(text("""INSERT INTO listings(author_id,listing_type,title,description,event_date,city,repertoire,fee)
                VALUES(:u,'seeking_singer',:title,'Synthetic browser fixture',CURRENT_DATE+10,'Berlin','Test work','100 EUR')"""),
                {'u':peer,'title':f'Retention QA {index:02}'})
        conn.execute(text("""INSERT INTO messages(sender_id,recipient_id,body,created_at)
            VALUES(:peer,:u,'QA inactivity warning',now()-interval '25 days')"""),{'u':uid,'peer':peer})
        conn.execute(text("""INSERT INTO job_matches(artist_user_id,contractor_user_id,listing_snapshot)
            VALUES(:u,:peer,'{"title":"QA preserved Match"}')"""),{'u':uid,'peer':peer})
        # Trigger snapshots a real listing; this synthetic Match represents an already-purged one.
        conn.execute(text("""UPDATE job_matches SET listing_snapshot='{"title":"QA preserved Match"}'
            WHERE artist_user_id=:u"""),{'u':uid})
    print('Browser fixture login:', email, '/ Local-test-only-482!')


if __name__ == '__main__':
    main()

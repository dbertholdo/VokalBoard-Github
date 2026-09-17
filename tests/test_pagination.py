"""Real database/HTML regressions for both paginated searches."""
import re
import uuid
from html.parser import HTMLParser

from app.database import execute
from tests.test_security import register_test_user


class ResultsParser(HTMLParser):
    def __init__(self, html, result_id):
        super().__init__()
        self.inside = False
        self.cards = []
        self.pages = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'section' and attrs.get('id') in ('board-results', 'people-results'):
            self.inside = True
        if self.inside and tag == 'a':
            href = attrs.get('href', '')
            if href.startswith(('/listings/', '/users/', '/u/')):
                self.cards.append(href)
            elif 'page=' in href:
                self.pages.append(href)

    def handle_endtag(self, tag):
        if tag == 'section':
            self.inside = False


def test_board_pages_filters_bounds_and_container(client):
    uid, _, _ = register_test_user(client)
    marker = 'pagination_' + uuid.uuid4().hex
    for i in range(21):
        execute("""INSERT INTO listings (author_id, listing_type, title, description, city, country, event_date, created_at)
                   VALUES (:u, 'seeking_singer', :t, 'Pagination test', 'Berlin', 'DE', CURRENT_DATE+10, '2026-01-01')""",
                {'u': uid, 't': f'{marker}_{i}'})
    try:
        first = client.get('/board', params={'q': marker, 'page': 1})
        second = client.get('/board', params={'q': marker, 'page': 2})
        a, b = ResultsParser(first.text, 'board-results'), ResultsParser(second.text, 'board-results')
        assert len(a.cards) == 20 and len(b.cards) == 1
        assert not set(a.cards) & set(b.cards)
        assert all(marker in href for href in a.pages + b.pages)
        for page, expected in [(-5, a.cards), (99999, b.cards)]:
            assert ResultsParser(client.get('/board', params={'q': marker, 'page': page}).text, 'board-results').cards == expected
        assert not ResultsParser(client.get('/board?q=nonexistent_' + marker).text, 'board-results').cards
        assert '/static/js/search-pagination.js' in first.text
    finally:
        execute('DELETE FROM listings WHERE author_id=:u AND title LIKE :t', {'u': uid, 't': marker+'%'})


def test_people_pages_bounds_and_access(client):
    assert client.get('/people', follow_redirects=False).status_code == 303
    uid, _, _ = register_test_user(client)
    execute('UPDATE users SET email_verified=TRUE WHERE id=:u', {'u': uid})
    marker = 'pagination_' + uuid.uuid4().hex
    try:
        for i in range(21):
            execute("""INSERT INTO users (email, password_hash, full_name, role, city, email_verified, created_at)
                       VALUES (:e, 'not-a-login-hash', :n, 'singer', :c, TRUE, '2026-01-01')""",
                    {'e': f'sectest_{marker}_{i}@example.com', 'n': f'Pagination {i}', 'c': marker})
        first = client.get('/people', params={'city': marker})
        second = client.get('/people', params={'city': marker, 'page': 2})
        a, b = ResultsParser(first.text, 'people-results'), ResultsParser(second.text, 'people-results')
        assert len(a.cards) == 20 and len(b.cards) == 1
        assert not set(a.cards) & set(b.cards)
        assert all(marker in href for href in a.pages + b.pages)
        assert ResultsParser(client.get('/people', params={'city': marker, 'page': 99999}).text, 'people-results').cards == b.cards
        assert '/static/js/search-pagination.js' in first.text
    finally:
        execute('DELETE FROM users WHERE city=:c AND email LIKE :e', {'c': marker, 'e': 'sectest_%'})

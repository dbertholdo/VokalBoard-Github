"""Database-free access regression; full HTTP/SQL checks run in integration suite."""
import ast
import importlib.util
from datetime import date
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('history_policy', ROOT / 'app/match_history.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class Denied(Exception):
    def __init__(self, status_code):
        self.status_code = status_code


class MatchHistoryTests(unittest.TestCase):
    def make_route(self, viewer):
        source = (ROOT / 'app/routers/match_history_routes.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef))
        fn.decorator_list = []
        calls = []
        namespace = {
            'Request': object, 'HTTPException': Denied,
            'get_current_user': lambda request: viewer,
            'can_view_match_history': policy.can_view_match_history,
            'RedirectResponse': lambda url, status_code: (url, status_code),
            'fetch_all': lambda sql, params: calls.append((sql, params)) or [],
            'render': lambda *args: SimpleNamespace(headers={}),
            # P3.F additions used by match_history(): kept as inert stubs
            # here since this test is DB-free/policy-only (secrecy/eval
            # window behavior itself is covered by the integration suite).
            'date': date,
            'CATEGORIES': {'punctuality': 'eval_category_punctuality'},
            'can_evaluate': lambda *a, **k: False,
            'get_my_evaluation': lambda *a, **k: None,
            # 2026-09-27: batched per-page lookups + fee formatting.
            'get_my_evaluations': lambda *a, **k: {},
            'get_drafts': lambda *a, **k: {},
            'translate': lambda key, lang: key,
            'format_fee': lambda *a, **k: None,
        }
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<history route>', 'exec'), namespace)
        return namespace['match_history'], calls

    def test_anonymous_redirects_without_query(self):
        route, calls = self.make_route(None)
        self.assertEqual(route(object()), ('/login', 303))
        self.assertEqual(calls, [])

    def test_owner_can_read_own_history(self):
        route, calls = self.make_route({'id': 10, 'role_level': 0})
        result = route(object())
        self.assertEqual(calls[0][1]['owner'], 10)
        self.assertEqual(result.headers['Cache-Control'], 'private, no-store')

    def test_other_users_and_moderators_denied_before_query(self):
        for level in (0, 1):
            route, calls = self.make_route({'id': 10, 'role_level': level})
            with self.assertRaises(Denied) as raised:
                route(object(), user_id=99)
            self.assertEqual(raised.exception.status_code, 403)
            self.assertEqual(calls, [])

    def test_admins_can_select_owner_and_paginate(self):
        for level in (2, 3):
            route, calls = self.make_route({'id': 10, 'role_level': level})
            route(object(), user_id=99, page=2)
            self.assertEqual(calls[0][1], {'owner': 99, 'offset': 20})

    def test_submenu_has_no_fake_download(self):
        source = (ROOT / 'app/templates/_profile_menu.html').read_text(encoding='utf-8')
        # 7 real links since the 19/09/2026 menu reorg (item #51): view/edit
        # profile, Digital Pass, favorites, messages, match history,
        # Rechnungmaker. Invitations moved to the top nav, and the old
        # disabled "download" placeholder was replaced by the real
        # Digital Pass page — so no fake/disabled entry may remain.
        self.assertEqual(source.count('<a '), 7)
        self.assertIn('href="/profile/matches"', source)
        self.assertIn('href="/rechnungmaker"', source)
        self.assertIn('href="/profile/digital-pass"', source)
        self.assertNotIn('aria-disabled="true"', source)
        self.assertNotIn('nav_profile_download', source)


if __name__ == '__main__':
    unittest.main()

"""Fast, database-free guards for the private profile layout."""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProfileLayoutTests(unittest.TestCase):
    def test_template_structure_and_cards(self):
        source = (ROOT / 'app/templates/profile.html').read_text(encoding='utf-8')
        # Structural guard only; actual Jinja rendering belongs to integration tests.
        stack = []
        for token in re.findall(r'{%[-+]?\s*(\w+)', source):
            if token in ('if', 'for', 'block'):
                stack.append(token)
            elif token in ('endif', 'endfor', 'endblock'):
                self.assertTrue(stack)
                self.assertEqual(stack.pop(), token[3:])
        self.assertFalse(stack)
        # 8 cards since 19/09/2026: the nested "Weitere Stimmlagen"
        # (extra voice types) fieldset was removed on purpose (To-do 1.1).
        self.assertEqual(source.count('<fieldset'), 8)
        self.assertEqual(source.count('</fieldset>'), 8)
        self.assertLess(source.index('badges-box'), source.index('action="/profile"'))
        self.assertGreater(source.index('profile-account-area'), source.index('</form>'))
        self.assertEqual(source.count('<section'), source.count('</section>'))

    def test_form_contract_preserved(self):
        source = (ROOT / 'app/templates/profile.html').read_text(encoding='utf-8')
        forms = re.findall(r'<form\b[^>]*>.*?</form>', source, re.S)
        # profile editor, block list, delete account + P2 works (add, delete).
        self.assertEqual(len(forms), 5)
        editor = next(form for form in forms if 'action="/profile"' in form)
        self.assertIn('enctype="multipart/form-data"', editor)
        for name in ('csrf_token', 'avatar', 'remove_avatar', 'notify_matches', 'notify_messages',
                     'preferred_language', 'appear_in_search', 'profile_slug', 'voice_type_id',
                     'bio', 'composer_hashtags', 'audio_links', 'ensemble_name', 'social_{{ platform }}'):
            self.assertIn(f'name="{name}"', editor)
        self.assertIn('{% include "_location_fields.html" %}', editor)
        for form in forms:
            self.assertEqual(form.count('<form'), 1)
            self.assertIn('name="csrf_token"', form)

    def test_new_labels_are_translated(self):
        tree = ast.parse((ROOT / 'app/i18n.py').read_text(encoding='utf-8'))
        translations = ast.literal_eval(next(n.value for n in tree.body
            if isinstance(n, ast.AnnAssign) and n.target.id == 'TRANSLATIONS'))
        for key in ('profile_preferences_card', 'profile_visibility_card', 'profile_professional_card',
                    'profile_email_language', 'profile_email_language_help', 'profile_account_controls',
                    'profile_account_private_help'):
            self.assertTrue({'de', 'en', 'fr', 'it', 'pt'} <= translations[key].keys())


if __name__ == '__main__':
    unittest.main()

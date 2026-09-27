"""Brand rollout contracts, contrast and real-page smoke tests (isolated DB)."""
from pathlib import Path
import re
import pytest
from tests.brand_contract import verify
from tests.test_security import register_test_user
from app.database import execute

ROOT = Path(__file__).resolve().parents[1]


def test_brand_functional_markup_preserved():
    verify()


def test_brand_assets_and_template_coverage():
    base=(ROOT/'app/templates/base.html').read_text(encoding='utf-8')
    assert '/static/css/brand.css?v=20260927-2' in base
    assert 'vokalboard-lockup-navy.svg' in base
    for path in (ROOT/'app/templates').glob('*.html'):
        if not path.name.startswith('_') and path.name != 'base.html':
            assert re.search(r"{%\s*extends\s+['\"]base\.html['\"]\s*%}", path.read_text(encoding='utf-8')), path.name
    for name in ('navy','white'):
        svg=(ROOT/f'app/static/img/brand/vokalboard-lockup-{name}.svg').read_text()
        assert '<text' not in svg and '<path' in svg
    assert (ROOT/'app/static/fonts/manrope/LICENSE.txt').is_file()


@pytest.mark.parametrize('foreground,background',[
    ('17283F','F5F7FA'),('526176','FFFFFF'),('FFFFFF','635BDE'),
    ('FFFFFF','5148C5'),('176545','EAF6EF'),('805000','FFF4DB'),
    ('B42338','FFF0F2'),('2457A0','EDF4FF')])
def test_brand_text_contrast(foreground,background):
    def luminance(value):
        channels=[int(value[i:i+2],16)/255 for i in (0,2,4)]
        linear=[c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in channels]
        return sum(a*b for a,b in zip(linear,(.2126,.7152,.0722)))
    a,b=sorted([luminance(foreground),luminance(background)])
    assert (b+.05)/(a+.05)>=4.5


def test_brand_authenticated_page_families(client):
    uid,_,_=register_test_user(client)
    execute('UPDATE users SET email_verified=TRUE,role_level=3,is_admin=TRUE WHERE id=:u',{'u':uid})
    routes=['/','/board','/board?urgent=1','/listings/new','/my-listings','/my-favorites',
            '/people','/profile','/profile/wizard','/profile/digital-pass',f'/users/{uid}',
            '/profile/matches','/invitations','/messages','/messages/sent','/messages/trash',
            '/notas','/notas/comprar-notas','/hall-da-fama','/rechnungmaker?tab=avulso',
            '/rechnungmaker?tab=match','/contato','/admin','/admin/users',f'/admin/users/{uid}',
            '/admin/analytics','/admin/posts','/admin/banners','/admin/loja','/admin/emails',
            '/admin/emails/periodic/new','/admin/tickets','/financeiro',
            '/financeiro/extrato-geral','/financeiro/conceder','/assinar',
            '/impressum','/datenschutz','/code-of-conduct','/profile/change-password']
    for route in routes:
        response=client.get(route)
        assert response.status_code==200, (route,response.status_code)
        assert '/static/css/brand.css?v=20260927-2' in response.text, route

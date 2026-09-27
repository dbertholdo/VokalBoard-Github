"""Banner selection independent of the administration UI."""
from urllib.parse import urlsplit
from app.database import fetch_all

AUDIENCES = {'all': 'Everyone (incl. visitors)', 'singer': 'Singers',
             'conductor': 'Conductors', 'no_subscription': 'Users without an active subscription'}

def safe_banner_link(value):
    value = value.strip()
    if not value:
        return None
    if any(ord(c) <= 32 for c in value) or '\\' in value:
        raise ValueError('Invalid link.')
    parsed = urlsplit(value)
    if value.startswith('/') and not value.startswith('//'):
        return value
    if parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password:
        return value
    raise ValueError('Use um caminho /pagina ou um link https:// válido.')

def visible_banners(user):
    return fetch_all('''
        SELECT b.id, b.title, b.body, b.link_url FROM site_banners b
        WHERE b.is_active AND b.deleted_at IS NULL AND (
          b.audience = 'all' OR
          (:user_id IS NOT NULL AND (
            b.audience = :role OR
            (b.audience = 'no_subscription' AND NOT EXISTS (
              SELECT 1 FROM subscriptions s WHERE s.user_id = :user_id
                AND s.is_active AND (s.expires_at IS NULL OR s.expires_at > now())
            ))
          ))
        ) AND (b.voice_type_id IS NULL OR (:role = 'singer' AND (
          EXISTS (SELECT 1 FROM singer_profile_voice_types v
                  WHERE v.user_id = :user_id AND v.voice_type_id = b.voice_type_id)
          OR EXISTS (SELECT 1 FROM singer_profiles p
                     WHERE p.user_id = :user_id AND p.voice_type_id = b.voice_type_id)
        ))) ORDER BY b.created_at DESC, b.id DESC
    ''', {'user_id': user['id'] if user else None, 'role': user['role'] if user else None})

"""Private Match history access policy, independent of public profiles."""


def can_view_match_history(viewer: dict, owner_id: int) -> bool:
    return viewer['id'] == owner_id or (viewer.get('role_level') or 0) >= 2

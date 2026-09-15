"""
"Destaques da semana" (home page column) — a short list of people
shown to every logged-in visitor on the home page. Deliberately mixes
three sources into ONE undistinguished list (no "paid" label, no
different styling) so it never turns into a pay-to-be-seen wall:

1. Whoever redeemed the "profile highlight" reward in Notas
   (users.profile_highlighted_until still in the future) — always
   shown, since redeeming is itself an explicit opt-in to visibility.
2. This month's top referrers (from referral_events, antifraud-backed
   — see app/referrals.py) — a way to surface active community
   members, not just people who paid.
3. Fallback: most-visited profiles this week (profile_views) — so the
   column is never empty even on a quiet month.

Fair rotation: candidates from (2) and (3) are ordered by
highlight_shown_count ASC / last_highlighted_at ASC (see db/schema.sql)
so the same few popular profiles don't dominate every single day —
whoever has been shown least (or longest ago) gets priority for the
remaining slots. Only (2)/(3) picks consume this bookkeeping; a paid
highlight from (1) doesn't "use up" anyone's fair-rotation turn.

Respects users.appear_in_search for the (2)/(3) fallback pool (the
same opt-out used by "Buscar pessoas") — a paid highlight (1) is its
own explicit opt-in and isn't gated by that flag.
"""
from app.database import fetch_all, execute

WEEKLY_HIGHLIGHTS_LIMIT = 6

# How many candidates to pull from each fallback source before mixing
# — wider than the final limit so the fairness sort below has enough
# people to choose from, not just whoever happens to rank #1.
_CANDIDATE_POOL_SIZE = 20


def get_weekly_highlights(viewer_id: int, limit: int = WEEKLY_HIGHLIGHTS_LIMIT) -> list[dict]:
    base_conditions = """
        u.deleted_at IS NULL
        AND u.id != :viewer_id
        AND NOT EXISTS (
            SELECT 1 FROM blocked_users bu
            WHERE (bu.blocker_id = :viewer_id AND bu.blocked_id = u.id)
               OR (bu.blocker_id = u.id AND bu.blocked_id = :viewer_id)
        )
    """
    params = {"viewer_id": viewer_id}

    # 1. Paid highlights (explicit opt-in via Notas redemption) — always included.
    paid = fetch_all(
        f"""
        SELECT u.id, u.full_name, u.role, u.city, u.avatar_url, u.profile_slug
        FROM users u
        WHERE {base_conditions} AND u.profile_highlighted_until > now()
        ORDER BY u.profile_highlighted_until DESC
        """,  # nosec B608 - base_conditions is a fixed fragment, all real values are parameters.
        params,
    )
    chosen_ids = {row["id"] for row in paid}
    highlights = list(paid)

    remaining = limit - len(highlights)
    if remaining <= 0:
        return highlights[:limit]

    # 2. This month's top referrers (antifraud-backed count from referral_events).
    top_referrers = fetch_all(
        f"""
        SELECT u.id, u.full_name, u.role, u.city, u.avatar_url, u.profile_slug,
               u.highlight_shown_count, u.last_highlighted_at
        FROM users u
        JOIN (
            SELECT referrer_user_id, COUNT(*) AS n
            FROM referral_events
            WHERE credited_at > now() - INTERVAL '30 days'
            GROUP BY referrer_user_id
        ) re ON re.referrer_user_id = u.id
        WHERE {base_conditions} AND u.appear_in_search = TRUE
        ORDER BY re.n DESC
        LIMIT :pool_size
        """,  # nosec B608 - same fixed base_conditions.
        {**params, "pool_size": _CANDIDATE_POOL_SIZE},
    )

    # 3. Fallback: most-visited profiles this week.
    most_visited = fetch_all(
        f"""
        SELECT u.id, u.full_name, u.role, u.city, u.avatar_url, u.profile_slug,
               u.highlight_shown_count, u.last_highlighted_at
        FROM users u
        JOIN (
            SELECT profile_user_id, COUNT(*) AS n
            FROM profile_views
            WHERE viewed_at > now() - INTERVAL '7 days'
            GROUP BY profile_user_id
        ) pv ON pv.profile_user_id = u.id
        WHERE {base_conditions} AND u.appear_in_search = TRUE
        ORDER BY pv.n DESC
        LIMIT :pool_size
        """,  # nosec B608 - same fixed base_conditions.
        {**params, "pool_size": _CANDIDATE_POOL_SIZE},
    )

    # Merge (2) and (3) into one pool, de-duplicated, excluding whoever
    # is already shown via a paid highlight.
    pool_by_id: dict[int, dict] = {}
    for row in top_referrers + most_visited:
        if row["id"] not in chosen_ids:
            pool_by_id[row["id"]] = row

    # Fair rotation: least-shown / longest-since-shown first.
    fallback_sorted = sorted(
        pool_by_id.values(),
        key=lambda r: (r["highlight_shown_count"], r["last_highlighted_at"] or ""),
    )

    picked = fallback_sorted[:remaining]
    for row in picked:
        execute(
            "UPDATE users SET highlight_shown_count = highlight_shown_count + 1, last_highlighted_at = now() WHERE id = :id",
            {"id": row["id"]},
        )
        highlights.append(
            {
                "id": row["id"],
                "full_name": row["full_name"],
                "role": row["role"],
                "city": row["city"],
                "avatar_url": row["avatar_url"],
                "profile_slug": row["profile_slug"],
            }
        )

    return highlights

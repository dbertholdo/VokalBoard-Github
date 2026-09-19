"""
Part 2 backlog, item 4 (19/09/2026) — the remaining five Tangará mascot
poses (see app/static/img/mascot/MANIFEST.md), designed together with
Daniel via AskUserQuestion and then refined by his direct answers:

- Acolhedor (welcoming): a "Welcome, {name}!" balloon toast, shown once
  per login (not once ever — every login), sliding in from a random
  screen edge, gone after 2s. Trigger: app/routers/auth_routes.py sets
  a one-shot session flag on successful login; app/render.py reads and
  clears it so it fires on the very next page render, wherever that is.
- Atento (attentive): a "Hey, {name}! Don't forget to <ONE thing>"
  balloon, gone after 2s. Daniel: "All of them" — i.e. all three
  candidate reminders (pending evaluation / pending invitation /
  incomplete profile) are wired up, but only the single highest-
  priority one is ever shown, and only once per session (this is a
  nudge, not a per-page nag — matches the "no reproach" rule in the
  manifest). pending_reminder_key() below picks it.
- Joinha (thumbs-up) and Piscadinha (wink) don't need a shared service
  — they're wired directly into their own success templates
  (notas.html, profile.html, my_listings.html) and hall_da_fama.html /
  the 404 page respectively.

Priority order for the ONE reminder (most time-boxed first): a pending
post-Match evaluation (ticking down inside its 14-day window) beats a
pending invitation (no visible deadline, but blocks a Match from ever
forming) beats an incomplete profile (no deadline at all). Reuses the
evaluation/invitation COUNTS app/render.py already computes for the nav
badges on every logged-in page load — no extra query for those two;
the profile check only runs (one cheap query) when both counts are
zero, so this never adds N+1-style cost to the page.
"""
from app.database import fetch_one


def _profile_incomplete(user: dict) -> bool:
    if not user.get("avatar_url"):
        return True
    table = "singer_profiles" if user.get("role") == "singer" else "conductor_profiles"
    row = fetch_one(f"SELECT bio FROM {table} WHERE user_id = :id", {"id": user["id"]})  # nosec B608 - table is one of two fixed literals, never user input
    return not (row and row.get("bio"))


def pending_reminder_key(user: dict, pending_evaluations_count: int, pending_invitations_count: int) -> str | None:
    """i18n message KEY (see app/i18n.py) for the single most relevant
    pending item, or None if there's nothing to nudge about right now."""
    if pending_evaluations_count:
        return "mascot_reminder_evaluation"
    if pending_invitations_count:
        return "mascot_reminder_invitation"
    if _profile_incomplete(user):
        return "mascot_reminder_profile"
    return None

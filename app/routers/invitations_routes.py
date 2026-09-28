"""
P3.B — candidatura espontânea (a singer applies to a vacancy),
convite pelo diretório (a contractor invites a singer they found on
/people or on a public profile), and the shared "responder" flow
(accept/decline) for both. All three write to the same
job_invitations table — see app/match_service.py for the actual rule
on who may start and who must respond to each row.

Kept out of listings_routes.py on purpose (CLAUDE.md "Fat Routers
Proibidos" — this is its own concern, not listing CRUD) and out of
match_service.py (that module is atomic DB transitions only, no
HTTP/template concerns).
"""
from app.vacancies import get_listing_invitations
from fastapi import APIRouter, Request, Form, BackgroundTasks
from fastapi.responses import RedirectResponse, HTMLResponse

from app.database import fetch_all, fetch_one
from app.auth import get_current_user
from app.render import render
from app.csrf import verify_csrf
from app.match_service import create_invitation, respond_invitation
from app.notifications import notify_invitation_created, notify_invitation_responded, notify_vacancy_filled_elsewhere
from app.notification_center import create_notification

from app.safe_redirect import safe_path

router = APIRouter()


@router.post("/vacancies/{vacancy_id}/apply")
def apply_to_vacancy(request: Request, background_tasks: BackgroundTasks, vacancy_id: int, csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    vacancy = fetch_one(
        "SELECT lv.listing_id, l.author_id FROM listing_vacancies lv JOIN listings l ON l.id = lv.listing_id WHERE lv.id = :id",
        {"id": vacancy_id},
    )
    listing_id = vacancy["listing_id"] if vacancy else None

    result = create_invitation(vacancy_id, artist_user_id=user["id"], initiated_by_user_id=user["id"])
    if result["ok"]:
        background_tasks.add_task(notify_invitation_created, str(request.base_url), result["id"])
        # Central de Notificações (task #50) — the contractor gets a
        # bell notification for the candidatura, same as the e-mail above.
        create_notification(
            vacancy["author_id"], "candidatura_received", "notification_candidatura_received",
            {"name": user["full_name"]}, link_url=f"/listings/{listing_id}/candidates",
        )
    redirect_url = f"/listings/{listing_id}" if listing_id else "/board"
    query = "applied=1" if result["ok"] else f"invite_error={result['reason']}"
    return RedirectResponse(url=f"{redirect_url}?{query}", status_code=303)


@router.post("/listings/{listing_id}/invite")
def invite_artist(
    request: Request,
    background_tasks: BackgroundTasks,
    listing_id: int,
    artist_user_id: int = Form(...),
    vacancy_id: int = Form(...),
    next: str = Form(""),
    csrf_token: str = Form(""),
):
    verify_csrf(request, csrf_token)
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    listing = fetch_one("SELECT author_id FROM listings WHERE id = :id", {"id": listing_id})
    fallback = safe_path(next, f"/users/{artist_user_id}")
    if not listing or listing["author_id"] != user["id"]:
        return RedirectResponse(url=f"{fallback}?invite_error=invitation_error_not_allowed", status_code=303)

    result = create_invitation(vacancy_id, artist_user_id=artist_user_id, initiated_by_user_id=user["id"])
    if result["ok"]:
        background_tasks.add_task(notify_invitation_created, str(request.base_url), result["id"])
        create_notification(
            artist_user_id, "invitation_received", "notification_invitation_received",
            {"name": user["full_name"]}, link_url="/invitations",
        )
    query = "invited=1" if result["ok"] else f"invite_error={result['reason']}"
    return RedirectResponse(url=f"{fallback}?{query}", status_code=303)


@router.get("/invitations", response_class=HTMLResponse)
def my_invitations(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    # Four buckets, kept deliberately simple (no N+1 — one query each,
    # not one per row): what I need to respond to vs. what I'm just
    # waiting on someone else for, split by which side of the
    # transaction I'm on.
    common_select = """
        SELECT ji.id, ji.status, ji.expires_at, ji.created_at,
               l.id AS listing_id, l.title AS listing_title, l.event_date,
               vt.name AS voice_type_name, lv.fee_amount, lv.fee_currency, lv.fee_negotiable,
               artist.id AS artist_id, artist.full_name AS artist_name, artist.avatar_url AS artist_avatar_url,
               contractor.id AS contractor_id, contractor.full_name AS contractor_name
        FROM job_invitations ji
        JOIN listing_vacancies lv ON lv.id = ji.vacancy_id
        JOIN listings l ON l.id = lv.listing_id
        LEFT JOIN voice_types vt ON vt.id = lv.voice_type_id
        JOIN users artist ON artist.id = ji.artist_user_id
        JOIN users contractor ON contractor.id = l.author_id
    """  # LEFT JOIN voice_types: a seeking_conductor vacancy has voice_type_id NULL.

    invites_received = fetch_all(
        common_select + " WHERE ji.artist_user_id = :id AND ji.initiated_by_user_id <> :id ORDER BY ji.status = 'pending' DESC, ji.created_at DESC",
        {"id": user["id"]},
    )
    applications_sent = fetch_all(
        common_select + " WHERE ji.artist_user_id = :id AND ji.initiated_by_user_id = :id ORDER BY ji.created_at DESC",
        {"id": user["id"]},
    )
    applications_received = fetch_all(
        common_select + " WHERE l.author_id = :id AND ji.initiated_by_user_id = ji.artist_user_id ORDER BY ji.status = 'pending' DESC, ji.created_at DESC",
        {"id": user["id"]},
    )
    invites_sent = fetch_all(
        common_select + " WHERE l.author_id = :id AND ji.initiated_by_user_id = l.author_id ORDER BY ji.created_at DESC",
        {"id": user["id"]},
    )

    # Menu reorg (19/09/2026, task #51) — side-nav's "Matches" group
    # links straight into ?tab=pending/history; filters the four
    # buckets already fetched above in Python (they're small per-user
    # lists) rather than adding tab-specific SQL branches to every
    # query. No tab (or an unrecognized one) shows everything, same as
    # this page always has.
    active_tab = request.query_params.get("tab")
    if active_tab in ("pending", "history"):
        want_pending = active_tab == "pending"
        invites_received = [r for r in invites_received if (r["status"] == "pending") == want_pending]
        applications_sent = [r for r in applications_sent if (r["status"] == "pending") == want_pending]
        applications_received = [r for r in applications_received if (r["status"] == "pending") == want_pending]
        invites_sent = [r for r in invites_sent if (r["status"] == "pending") == want_pending]
    else:
        active_tab = "all"

    context = {
        "user": user,
        "invites_received": invites_received,
        "applications_sent": applications_sent,
        "applications_received": applications_received,
        "invites_sent": invites_sent,
        "active_tab": active_tab,
        "applied": request.query_params.get("applied") == "1",
        "invited": request.query_params.get("invited") == "1",
        "invite_error": request.query_params.get("invite_error"),
        "responded": request.query_params.get("responded"),
    }
    return render(request, "invitations.html", context)


@router.get("/listings/{listing_id}/candidates", response_class=HTMLResponse)
def listing_candidates(request: Request, listing_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    listing = fetch_one("SELECT id, title, author_id FROM listings WHERE id = :id", {"id": listing_id})
    if not listing or listing["author_id"] != user["id"]:
        return RedirectResponse(url="/my-listings", status_code=303)

    candidacies, invites_sent = get_listing_invitations(listing_id)

    context = {
        "user": user,
        "listing": listing,
        "candidacies": candidacies,
        "invites_sent": invites_sent,
        "invited": request.query_params.get("invited") == "1",
        "invite_error": request.query_params.get("invite_error"),
        "responded": request.query_params.get("responded"),
    }
    return render(request, "listing_candidates.html", context)


@router.post("/invitations/{invitation_id}/respond")
def respond_to_invitation(
    request: Request,
    background_tasks: BackgroundTasks,
    invitation_id: int,
    action: str = Form(...),
    next: str = Form(""),
    csrf_token: str = Form(""),
):
    verify_csrf(request, csrf_token)
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    result = respond_invitation(invitation_id, acting_user_id=user["id"], action=action)
    fallback = safe_path(next, "/invitations")
    if result["ok"]:
        accepted = bool(result.get("match_id"))
        background_tasks.add_task(notify_invitation_responded, str(request.base_url), invitation_id, accepted)
        # P3.D: every other invitation/candidatura this accept just closed
        # out (vacancy fully filled — see match_service.respond_invitation)
        # gets its own "vaga já preenchida" e-mail.
        for other_id in result.get("filled_other_ids", []):
            background_tasks.add_task(notify_vacancy_filled_elsewhere, str(request.base_url), other_id)

        # Central de Notificações (task #50): let the initiator know
        # how their invitation/candidatura was answered, and — on
        # accept — a Match-formed bell for BOTH sides.
        invite_row = fetch_one(
            """
            SELECT ji.initiated_by_user_id, ji.artist_user_id, l.author_id AS contractor_user_id,
                   artist.full_name AS artist_name, contractor.full_name AS contractor_name
            FROM job_invitations ji
            JOIN listing_vacancies lv ON lv.id = ji.vacancy_id
            JOIN listings l ON l.id = lv.listing_id
            JOIN users artist ON artist.id = ji.artist_user_id
            JOIN users contractor ON contractor.id = l.author_id
            WHERE ji.id = :id
            """,
            {"id": invitation_id},
        )
        if invite_row:
            if invite_row["initiated_by_user_id"] != user["id"]:
                if accepted:
                    create_notification(
                        invite_row["initiated_by_user_id"], "invitation_accepted", "notification_invitation_accepted",
                        {"name": user["full_name"]}, link_url="/invitations",
                    )
                else:
                    create_notification(
                        invite_row["initiated_by_user_id"], "invitation_declined", "notification_invitation_declined",
                        {"name": user["full_name"]}, link_url="/invitations",
                    )
            if accepted:
                create_notification(
                    invite_row["artist_user_id"], "match_formed", "notification_match_formed",
                    {"name": invite_row["contractor_name"]}, link_url="/profile/matches",
                )
                create_notification(
                    invite_row["contractor_user_id"], "match_formed", "notification_match_formed",
                    {"name": invite_row["artist_name"]}, link_url="/profile/matches",
                )
        query = "responded=accepted" if accepted else "responded=declined"
    else:
        query = f"invite_error={result['reason']}"
    return RedirectResponse(url=f"{fallback}?{query}", status_code=303)

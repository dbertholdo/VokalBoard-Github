import json
from app import store
from app.referrals import settle_for_invitee
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Form, BackgroundTasks, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, Response

from app.database import fetch_all, fetch_one, execute
from app.accounts import confirm_current_password
from app.auth import get_current_user, hash_password
from app.render import render
from app.csrf import verify_csrf
from app.avatars import save_avatar, remove_existing_avatar, avatar_path_for
from app.referrals import ensure_referral_code, get_referral_stats
from app.badges import get_user_badges, with_profile_complete, check_and_notify_new_badges, top_badges, badge_label
from app.match_evaluations import get_quality_tiers
from app.locations import COUNTRY_OPTIONS, STATE_OPTIONS, get_city_options
from app.password_policy import password_error
from app.i18n import translate
from app.singer_works import (
    get_works,
    get_works_by_category,
    add_work,
    delete_work,
    WorkValidationError,
    MAX_WORKS,
    MAX_TITLE_LENGTH as MAX_WORK_TITLE_LENGTH,
    MAX_COMPOSER_LENGTH as MAX_WORK_COMPOSER_LENGTH,
)
from app.cv_pdf import CvDocument, CvWork, render_cv_pdf
from app.languages import (
    SPOKEN_LANGUAGE_OPTIONS,
    OTHER_LANGUAGE_CODE,
    MAX_SPOKEN_LANGUAGES,
    get_spoken_languages,
    get_spoken_language_names,
    parse_spoken_languages_form,
)

from app.profiles import (
    MAX_COMPOSER_TAGS, MAX_BIO_LENGTH, MAX_AUDIO_LINKS, SOCIAL_PLATFORMS,
    ProfileError, clean_profile_input, save_profile, profile_public_url, public_base_url, save_rating,
    get_singer_profile, get_extra_voice_types, get_all_voice_type_names, get_conductor_profile,
    get_composer_tags, get_audio_links, get_social_links, get_my_ratings, get_rating_summary,
    get_rating_given, compute_profile_completeness, get_blocked_users,
)

router = APIRouter()

# "Cooldown" window for profile view counting: the same session
# (same browser) only generates a new row in profile_views per
# profile every 12h, even if the person hits F5 several times.
VIEW_COOLDOWN_SECONDS = 12 * 60 * 60



def _my_profile_context(request: Request, user: dict, error: str | None = None, saved: bool = False) -> dict:
    singer_profile = get_singer_profile(user["id"]) if user["role"] == "singer" else None
    extra_voice_types = get_extra_voice_types(user["id"]) if user["role"] == "singer" else []
    conductor_profile = get_conductor_profile(user["id"]) if user["role"] == "conductor" else None
    composer_tags = get_composer_tags(user["id"]) if user["role"] == "singer" else []
    audio_links = get_audio_links(user["id"]) if user["role"] == "singer" else []
    social_links = get_social_links(user["id"])
    role_profile = singer_profile if user["role"] == "singer" else conductor_profile

    referral_code = ensure_referral_code(user["id"], user.get("referral_code"))
    user["referral_code"] = referral_code
    referral_url = f"{public_base_url(request)}/register?ref={referral_code}"

    completeness = compute_profile_completeness(user, role_profile, composer_tags, audio_links, social_links)
    badges = with_profile_complete(get_user_badges(user["id"]), completeness["percent"])
    ui_lang = getattr(request.state, "lang", "de")

    return {
        "user": user,
        "referral_url": referral_url,
        "referral_count": get_referral_stats(user["id"])["count"],
        "blocked_users": get_blocked_users(user["id"]),
        "badges": badges,
        # P3.F: selos de qualidade — SÓ na própria /profile (nunca em
        # public_profile.html), "estilo Uber" (pode subir/descer),
        # agregado, nunca mostra quem avaliou (ver app/match_evaluations.py).
        "quality_tiers": get_quality_tiers(user["id"]),
        "voice_types": fetch_all("SELECT id, name FROM voice_types ORDER BY sort_order"),
        "singer_profile": singer_profile,
        "extra_voice_type_ids": {v["id"] for v in extra_voice_types},
        # P2.B — spoken languages (any role). spoken_languages: saved rows
        # to pre-fill the form fields; spoken_language_options: fixed
        # list (+ "Outra") to build the <select>s.
        "spoken_languages": get_spoken_languages(user["id"]),
        "spoken_language_options": SPOKEN_LANGUAGE_OPTIONS,
        "other_language_code": OTHER_LANGUAGE_CODE,
        "max_spoken_languages": MAX_SPOKEN_LANGUAGES,
        "ui_lang": ui_lang,
        "conductor_profile": conductor_profile,
        "composer_tags": composer_tags,
        "audio_links": audio_links,
        "social_links": social_links,
        "social_platforms": SOCIAL_PLATFORMS,
        # Ratings received — ONLY show up here, on the person's own
        # profile page (private, never on /users/{id}).
        "my_ratings": get_my_ratings(user["id"]),
        "rating_summary": get_rating_summary(user["id"]),
        "completeness": completeness,
        "max_bio_length": MAX_BIO_LENGTH,
        "max_composer_tags": MAX_COMPOSER_TAGS,
        "max_audio_links": MAX_AUDIO_LINKS,
        "country_options": COUNTRY_OPTIONS,
        "state_options": STATE_OPTIONS,
        "city_options": get_city_options(),
        # P2 cluster (19/09/2026) — solo/choir "works" a singer manages
        # here and that show up split into two card groups on their
        # public profile (see app/singer_works.py).
        "my_works": get_works(user["id"]) if user["role"] == "singer" else [],
        "max_works": MAX_WORKS,
        "max_work_title_length": MAX_WORK_TITLE_LENGTH,
        "max_work_composer_length": MAX_WORK_COMPOSER_LENGTH,
        "error": error,
        "saved": saved,
    }


@router.get("/profile", response_class=HTMLResponse)
def my_profile(request: Request, background_tasks: BackgroundTasks):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    # "Lazy" check of tiered badges that depend only on time passing
    # (anniversary) or on data that changes outside a direct action
    # (views) — since the project doesn't use any internal cron, we
    # take advantage of the most natural and frequent visit (the
    # person opening their own profile) to recalculate and, if that's
    # the case, send the "new badge" e-mail.
    background_tasks.add_task(check_and_notify_new_badges, user["id"], str(request.base_url))

    context = _my_profile_context(request, user, saved=request.query_params.get("saved") == "1")
    return render(request, "profile.html", context)


@router.post("/profile")
async def update_profile(request: Request, background_tasks: BackgroundTasks, csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    form = await request.form()
    try:
        data = clean_profile_input(user, form)
    except ProfileError as exc:
        return render(request, "profile.html", _my_profile_context(request, user, error=exc.key), status_code=400)
    # Spoken languages (P2.B): parallel "spoken_language_code"/"spoken_language_custom" rows.
    spoken = parse_spoken_languages_form(form.getlist("spoken_language_code"), form.getlist("spoken_language_custom"))
    save_profile(user, data, spoken)

    # Photo last: an invalid file no longer stops the rest of the form from saving
    # (the "profile_avatar_invalid" message promises exactly that).
    avatar = form.get("avatar")
    if form.get("remove_avatar"):
        remove_existing_avatar(user["id"])
        execute("UPDATE users SET avatar_url = NULL WHERE id = :id", {"id": user["id"]})
    elif avatar is not None and getattr(avatar, "filename", ""):
        new_avatar_url = await save_avatar(user["id"], avatar)
        if not new_avatar_url:
            context = _my_profile_context(request, get_current_user(request), error="profile_avatar_invalid")
            return render(request, "profile.html", context, status_code=400)
        execute("UPDATE users SET avatar_url = :avatar_url WHERE id = :id", {"avatar_url": new_avatar_url, "id": user["id"]})

    background_tasks.add_task(check_and_notify_new_badges, user["id"], str(request.base_url))
    settle_for_invitee(user["id"])  # a complete profile unlocks the referrer's Nota
    return RedirectResponse(url="/profile?saved=1", status_code=303)


@router.get("/profile/change-password", response_class=HTMLResponse)
def change_password_form(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return render(request, "change_password.html", {"user": user, "error": None})


@router.post("/profile/change-password")
def change_password_submit(
    request: Request,
    csrf_token: str = Form(""),
    current_password: str = Form(...),
    new_password: str = Form(...),
):
    verify_csrf(request, csrf_token)
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    if not confirm_current_password(user, current_password):
        return render(
            request, "change_password.html",
            {"user": user, "error": "change_password_wrong_current"},
            status_code=400,
        )

    pw_error = password_error(new_password)
    if pw_error:
        return render(
            request, "change_password.html",
            {"user": user, "error": pw_error},
            status_code=400,
        )

    execute(
        "UPDATE users SET password_hash = :hash WHERE id = :id",
        {"hash": hash_password(new_password), "id": user["id"]},
    )
    return RedirectResponse(url="/profile?saved=1", status_code=303)


@router.post("/profile/delete-account")
def delete_account_submit(request: Request, csrf_token: str = Form(""), current_password: str = Form(...)):
    """
    Soft delete: sets deleted_at = now() and drops the session. The
    account becomes "invisible" (get_current_user, author joins etc.
    filter on deleted_at IS NULL) but the data stays in the database
    for 6 months — if the person tries to log in again during that
    period, they fall into the reactivation flow (see
    /reactivate-account in auth_routes.py). After 6 months the
    retention worker deletes it for good (app/account_purge.py).
    """
    verify_csrf(request, csrf_token)
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    if not confirm_current_password(user, current_password):
        context = _my_profile_context(request, user, error="delete_account_wrong_password")
        return render(request, "profile.html", context, status_code=400)

    execute("UPDATE users SET deleted_at = now() WHERE id = :id", {"id": user["id"]})
    request.session.clear()
    return RedirectResponse(url="/?account_deleted=1", status_code=303)


@router.get("/profile/export")
def export_my_data(request: Request):
    """
    Data export (GDPR Art. 20 — right to portability): a JSON with
    everything the person has registered in the system, to download.
    Deliberately does NOT include password_hash (it isn't "your data"
    in the portability sense, it's an authentication secret) nor
    other people's data beyond what's already necessary to give
    context to the person's own messages/ratings.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    user_id = user["id"]

    account = fetch_one(
        "SELECT id, email, full_name, role, city, state, country, phone, phone_visibility, email_verified, avatar_url, notify_matches, notify_messages, preferred_language, profile_slug, appear_in_search, created_at FROM users WHERE id = :id",
        {"id": user_id},
    )
    listings = fetch_all(
        "SELECT id, listing_type, title, description, city, state, country, repertoire, venue, fee, ensemble_type, event_date, is_active, created_at FROM visible_listings WHERE author_id = :id ORDER BY created_at",
        {"id": user_id},
    )
    messages_sent = fetch_all(
        "SELECT id, recipient_id, listing_id, body, created_at FROM visible_messages WHERE sender_id = :id ORDER BY created_at",
        {"id": user_id},
    )
    messages_received = fetch_all(
        "SELECT id, sender_id, listing_id, body, created_at, read_at FROM visible_messages WHERE recipient_id = :id ORDER BY created_at",
        {"id": user_id},
    )
    ratings_received = get_my_ratings(user_id)
    ratings_given = fetch_all(
        "SELECT rated_id, stars, comment, created_at FROM ratings WHERE rater_id = :id ORDER BY created_at",
        {"id": user_id},
    )
    saved_listings = fetch_all(
        "SELECT listing_id, created_at FROM saved_listings WHERE user_id = :id ORDER BY created_at",
        {"id": user_id},
    )

    works = fetch_all(
        "SELECT title, composer, category, video_url, audio_url, created_at FROM singer_works WHERE user_id = :id ORDER BY sort_order, id",
        {"id": user_id},
    )
    spoken_languages = fetch_all(
        "SELECT language_code, custom_name FROM user_spoken_languages WHERE user_id = :id ORDER BY sort_order, id",
        {"id": user_id},
    )
    notas_ledger = fetch_all(
        "SELECT delta, reason, category, expires_at, created_at FROM credit_ledger WHERE user_id = :id ORDER BY created_at, id",
        {"id": user_id},
    )
    # Own side only: the other party appears as a user id, like messages above.
    invitations = fetch_all(
        """
        SELECT ji.vacancy_id, lv.listing_id, ji.artist_user_id, ji.initiated_by_user_id, ji.status,
               ji.created_at, ji.responded_at
        FROM job_invitations ji JOIN listing_vacancies lv ON lv.id = ji.vacancy_id
        WHERE :id IN (ji.artist_user_id, ji.initiated_by_user_id)
        ORDER BY ji.created_at
        """,
        {"id": user_id},
    )
    matches = fetch_all(
        """
        SELECT listing_id, artist_user_id, contractor_user_id, status, created_at, completed_at
        FROM job_matches WHERE :id IN (artist_user_id, contractor_user_id) ORDER BY created_at
        """,
        {"id": user_id},
    )

    export = {
        "account": account,
        "singer_profile": get_singer_profile(user_id) if user["role"] == "singer" else None,
        "conductor_profile": get_conductor_profile(user_id) if user["role"] == "conductor" else None,
        "composer_tags": get_composer_tags(user_id) if user["role"] == "singer" else [],
        "audio_links": get_audio_links(user_id) if user["role"] == "singer" else [],
        "social_links": get_social_links(user_id),
        "listings_posted": listings,
        "messages_sent": messages_sent,
        "messages_received": messages_received,
        "ratings_received": ratings_received,
        "ratings_given": ratings_given,
        "saved_listings": saved_listings,
        "works": works,
        "spoken_languages": spoken_languages,
        "notas_ledger": notas_ledger,
        "invitations_and_applications": invitations,
        "matches": matches,
    }

    body = json.dumps(export, indent=2, ensure_ascii=False, default=str)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="vokalboard-data-{user_id}.json"'},
    )


@router.get("/profile/wizard", response_class=HTMLResponse)
def profile_wizard(request: Request):
    """
    P2 cluster, Profile Wizard (19/09/2026) — decided with Daniel via
    AskUserQuestion ("1 and 2"): the SAME fields/form as /profile,
    just walked through step by step with a progress bar (see
    profile_wizard.html), submitting to the existing POST /profile
    below — no duplicated validation logic. Reachable two ways: the
    one-time automatic redirect right after signup when the profile is
    still incomplete (see app/routers/listings_routes.py home()), and
    anytime afterward on demand (linked from the Atento mascot nudge,
    see mascot_reminder_key handling in app/templates/base.html).
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    # Marks the automatic-redirect gate as spent the first time this
    # person actually reaches the wizard — whether they got here via
    # that auto-redirect or clicked the link themselves. Only ever
    # writes once (IS NULL guard); doesn't affect being able to come
    # back to this page manually later.
    if not user.get("profile_wizard_seen_at"):
        execute("UPDATE users SET profile_wizard_seen_at = now() WHERE id = :id", {"id": user["id"]})

    context = _my_profile_context(request, user)
    return render(request, "profile_wizard.html", context)


@router.post("/profile/works/add")
def add_singer_work(
    request: Request,
    csrf_token: str = Form(""),
    title: str = Form(""),
    composer: str = Form(""),
    category: str = Form(""),
    video_url: str = Form(""),
    audio_url: str = Form(""),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    verify_csrf(request, csrf_token)
    if user["role"] != "singer":
        raise HTTPException(status_code=403)

    try:
        add_work(user["id"], title, composer, category, video_url, audio_url)
    except WorkValidationError as exc:
        context = _my_profile_context(request, user, error=f"work_{exc}")
        return render(request, "profile.html", context, status_code=400)

    return RedirectResponse(url="/profile?saved=1#works", status_code=303)


@router.post("/profile/works/{work_id}/delete")
def delete_singer_work(request: Request, work_id: int, csrf_token: str = Form("")):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    verify_csrf(request, csrf_token)

    delete_work(user["id"], work_id)
    return RedirectResponse(url="/profile?saved=1#works", status_code=303)


@router.get("/profile/digital-pass", response_class=HTMLResponse)
def digital_pass(request: Request):
    """
    Digital Pass (19/09/2026, task #51) — landing page for two tools:
    the CV export (already built, see download_cv_pdf() right below —
    just surfaced here with its own real download button) and a
    business card generator based on that same CV (Daniel: "só colocar
    para design ainda, não executar" — design/placement only for now,
    the actual generator isn't built). Kept as its own stub page
    rather than another disabled line in _profile_menu.html so the
    "coming soon" state has somewhere to actually explain itself.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return render(request, "digital_pass_stub.html", {"user": user})


@router.get("/profile/cv.pdf")
def download_cv_pdf(request: Request):
    """
    P2 cluster, CV export (19/09/2026) — stateless PDF generation (see
    app/cv_pdf.py, same "no filesystem access" shape as the Rechnung
    generator in app/invoice_pdf.py).

    Redesigned 19/09/2026 to fix two bugs Daniel found (the photo
    wasn't included, no QR Code was generated) and to make the PDF
    look like the profile's own "id card" (photo, role/voice line,
    badge pills, highlighted-profile banner) instead of a plain text
    CV — see app/cv_pdf.py's own docstring for the visual reasoning.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    account = fetch_one(
        "SELECT email, phone, phone_visibility, profile_highlighted_until FROM users WHERE id = :id",
        {"id": user["id"]},
    )
    is_singer = user["role"] == "singer"
    role_profile = get_singer_profile(user["id"]) if is_singer else get_conductor_profile(user["id"])
    works = get_works_by_category(user["id"]) if is_singer else {"solo": [], "choir": []}
    lang = getattr(request.state, "lang", "de")

    if is_singer:
        headline = role_profile.get("voice_type_name") if role_profile else ""
        if role_profile and role_profile.get("fach"):
            headline = f"{headline} — {role_profile['fach']}" if headline else role_profile["fach"]
    else:
        headline = role_profile.get("ensemble_name") if role_profile else ""

    profile_slug = user.get("profile_slug")
    profile_url = profile_public_url(request.base_url, user["id"], profile_slug)

    # Same "top 3 unlocked badges" the public profile card shows (see
    # app/badges.py:top_badges + public_profile.html's badge-row),
    # resolved to display text here since the PDF has no t() available.
    badge_labels = [badge_label(b, lang) for b in top_badges(user["id"], limit=3)]

    is_highlighted = bool(
        account
        and account["profile_highlighted_until"]
        and account["profile_highlighted_until"] > datetime.now(timezone.utc)
    )

    cv = CvDocument(
        full_name=user["full_name"],
        role_label=translate("role_singer" if is_singer else "role_conductor", lang),
        headline=headline or "",
        city=user.get("city") or "",
        country=user.get("country") or "",
        bio=(role_profile.get("bio") if role_profile else "") or "",
        # Respects the same visibility choice as the public profile —
        # a CV downloaded by the person themselves still shouldn't
        # leak a phone number they explicitly kept private, since a
        # PDF is easy to forward on.
        phone=(account["phone"] or "") if account and account["phone_visibility"] == "public" else "",
        email=account["email"] if account else "",
        profile_url=profile_url,
        # FIX (19/09/2026): the photo wasn't making it into the PDF —
        # avatar_path_for() is the same helper the upload/removal flow
        # already uses (app/avatars.py), so this reads the exact file
        # the person's own avatar was last saved to. cv_pdf.py falls
        # back to an initial-letter circle if the path doesn't exist
        # (no avatar set, or a stale avatar_url after a removal).
        avatar_path=avatar_path_for(user["id"]) if user.get("avatar_url") else "",
        badges=badge_labels,
        is_highlighted=is_highlighted,
        spoken_languages=get_spoken_language_names(user["id"], lang),
        composer_tags=get_composer_tags(user["id"]) if is_singer else [],
        solo_works=[CvWork(title=w["title"], composer=w.get("composer") or "") for w in works["solo"]],
        choir_works=[CvWork(title=w["title"], composer=w.get("composer") or "") for w in works["choir"]],
        audio_links=get_audio_links(user["id"]) if is_singer else [],
    )
    pdf_bytes = render_cv_pdf(cv)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="vokalboard-cv-{user["id"]}.pdf"'},
    )


@router.post("/users/{user_id}/block")
def block_user(request: Request, user_id: int, csrf_token: str = Form(""), reason: str = Form("")):
    """
    Blocking someone: from now on neither side can send the other a
    message (checked in messages_routes.py), and the blocked
    person's listings disappear from /board and from the Home
    matches for whoever blocked them (see the NOT EXISTS filters in
    listings_routes.py). A reason is optional here (unlike reporting
    a listing, which requires one) — blocking is a personal decision,
    no justification needed.
    """
    verify_csrf(request, csrf_token)
    viewer = get_current_user(request)
    if not viewer:
        return RedirectResponse(url="/login", status_code=303)
    if viewer["id"] == user_id:
        return RedirectResponse(url=f"/users/{user_id}", status_code=303)

    target = fetch_one("SELECT id FROM users WHERE id = :id", {"id": user_id})
    if target:
        execute(
            """
            INSERT INTO blocked_users (blocker_id, blocked_id, reason) VALUES (:blocker_id, :blocked_id, :reason)
            ON CONFLICT (blocker_id, blocked_id) DO NOTHING
            """,
            {"blocker_id": viewer["id"], "blocked_id": user_id, "reason": reason.strip()[:500] or None},
        )
    return RedirectResponse(url=f"/users/{user_id}?blocked=1", status_code=303)


@router.post("/users/{user_id}/unblock")
def unblock_user(request: Request, user_id: int, csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)
    viewer = get_current_user(request)
    if not viewer:
        return RedirectResponse(url="/login", status_code=303)

    execute(
        "DELETE FROM blocked_users WHERE blocker_id = :blocker_id AND blocked_id = :blocked_id",
        {"blocker_id": viewer["id"], "blocked_id": user_id},
    )
    referer = request.headers.get("referer", "")
    if "/profile" in referer:
        return RedirectResponse(url="/profile", status_code=303)
    return RedirectResponse(url=f"/users/{user_id}", status_code=303)


@router.post("/users/{user_id}/rate")
def rate_user(
    request: Request,
    user_id: int,
    csrf_token: str = Form(""),
    stars: int = Form(...),
    comment: str = Form(""),
    listing_id: str = Form(""),
):
    verify_csrf(request, csrf_token)
    viewer = get_current_user(request)
    if not viewer:
        return RedirectResponse(url="/login", status_code=303)
    if not save_rating(viewer, user_id, stars, comment, listing_id):
        return RedirectResponse(url=f"/users/{user_id}", status_code=303)
    return RedirectResponse(url=f"/users/{user_id}?rated=1", status_code=303)


@router.get("/users/{user_id}", response_class=HTMLResponse)
def public_profile(request: Request, user_id: int, background_tasks: BackgroundTasks):
    profile_user = fetch_one(
        f"""
        SELECT id, email, full_name, role, city, phone, phone_visibility, avatar_url, profile_slug, profile_highlighted_until,
               {store.super_user_sql("users")} AS is_super_user, {store.verified_sql("users")} AS is_verified,
               {store.supporter_sql("users")} AS is_supporter
        FROM users WHERE id = :id AND deleted_at IS NULL
        """,  # nosec B608 - fixed fragments from app/store.py
        {"id": user_id},
    )
    if not profile_user:
        raise HTTPException(status_code=404)
    is_highlighted = bool(
        profile_user
        and profile_user["profile_highlighted_until"]
        and profile_user["profile_highlighted_until"] > datetime.now(timezone.utc)
    )

    singer_profile = None
    conductor_profile = None
    composer_tags = []
    audio_links = []
    if profile_user:
        if profile_user["role"] == "singer":
            singer_profile = get_singer_profile(user_id)
            composer_tags = get_composer_tags(user_id)
            audio_links = get_audio_links(user_id)
        else:
            conductor_profile = get_conductor_profile(user_id)

        # Visit log — doesn't show up on any screen, it's just for
        # you (the admin) to query directly in the database. Doesn't
        # count the person themselves visiting their own profile.
        #
        # To prevent hitting F5 on the page from inflating the count,
        # each session (browser cookie, already used for login/CSRF)
        # only counts as a new visit to this profile once every
        # VIEW_COOLDOWN. It's not foolproof (clearing cookies or
        # using an incognito tab gets around it), but that's
        # acceptable for a lightweight metric — it's not worth
        # tracking IP to close this gap completely, which would go
        # against the project's "profile_views is private and
        # minimal" principle.
        viewer = get_current_user(request)
        if not viewer or viewer["id"] != user_id:
            session_key = f"viewed_profile_{user_id}"
            last_viewed = request.session.get(session_key)
            now_ts = datetime.now(timezone.utc).timestamp()
            if not last_viewed or (now_ts - last_viewed) > VIEW_COOLDOWN_SECONDS:
                request.session[session_key] = now_ts
                execute(
                    "INSERT INTO profile_views (profile_user_id, viewer_user_id) VALUES (:profile_id, :viewer_id)",
                    {"profile_id": user_id, "viewer_id": viewer["id"] if viewer else None},
                )
                # The visit may have made the profile OWNER cross a
                # "views" threshold (100/500/1000) — check and notify
                # THEM, not whoever is visiting.
                background_tasks.add_task(check_and_notify_new_badges, user_id, str(request.base_url))

    listings = fetch_all(
        """
        SELECT id, title, listing_type, city, created_at,
            CASE
                WHEN event_date IS NULL THEN NULL
                WHEN event_date < CURRENT_DATE THEN 'past'
                WHEN event_date <= CURRENT_DATE + INTERVAL '7 days' THEN 'soon'
                ELSE 'upcoming'
            END AS event_status
        FROM visible_listings
        WHERE author_id = :author_id AND is_active = TRUE
        ORDER BY created_at DESC
        """,
        {"author_id": user_id},
    )

    viewer = get_current_user(request)

    # Social networks: only make sense to show when the profile isn't
    # "locked" (visitor logged in), otherwise it would be one more
    # piece of data exposed for free to whoever hasn't signed up.
    social_links = get_social_links(user_id) if profile_user and viewer is not None else {}

    # The rating I (the viewer) already gave this person, to
    # pre-fill the rating form. This is different from "ratings this
    # person received" (my_ratings/rating_summary) — that's private
    # and NEVER shows up here, only on /profile (the person
    # themselves seeing what they received). Here there's only the
    # widget to give/update a rating.
    rating_given = None
    can_rate = False
    is_blocked = False
    # A block needs to be invisible from BOTH sides, otherwise it
    # doesn't help much — if I blocked someone (or was blocked by
    # them), neither of us should be able to see the other's profile,
    # not just exchange messages. "blocked_either_way" covers both
    # directions.
    blocked_either_way = False
    if profile_user and viewer is not None and viewer["id"] != user_id:
        can_rate = True
        rating_given = get_rating_given(viewer["id"], user_id)
        blocked_row = fetch_one(
            "SELECT 1 FROM blocked_users WHERE blocker_id = :blocker_id AND blocked_id = :blocked_id",
            {"blocker_id": viewer["id"], "blocked_id": user_id},
        )
        is_blocked = blocked_row is not None

        blocked_other_way = fetch_one(
            "SELECT 1 FROM blocked_users WHERE blocker_id = :blocker_id AND blocked_id = :blocked_id",
            {"blocker_id": user_id, "blocked_id": viewer["id"]},
        )
        blocked_either_way = is_blocked or (blocked_other_way is not None)
        # Same rule as save_rating(): no widget across a block or for unverified accounts.
        can_rate = not blocked_either_way and bool(viewer.get("email_verified"))

    # Badges: only the unlocked ones show up on the public profile
    # (the profile doesn't get cluttered with "locked achievements"
    # for visitors) — the person themselves sees all of them, locked
    # or not, in /profile.
    # P3.B: if I (the viewer) have my own open vacancies and this
    # profile belongs to a singer OR a conductor, offer to invite them
    # directly — "convite pelo diretório". Only listings I OWN with at
    # least one vacancy that still has room, and only ever from HERE
    # (not shown to the artist themselves). FIX (19/09/2026): used to
    # be singer-only — conductors had no vaga/invite path at all until
    # today (see app/vacancies.py's module docstring); a viewer with an
    # active seeking_conductor listing can now invite a conductor here
    # too. LEFT JOIN voice_types: a seeking_conductor vacancy has
    # voice_type_id = NULL.
    invitable_vacancies = []
    if (
        profile_user
        and viewer is not None
        and viewer["id"] != user_id
        and profile_user["role"] in ("singer", "conductor")
        and not blocked_either_way
    ):
        invitable_vacancies = fetch_all(
            """
            SELECT lv.id AS vacancy_id, lv.total_slots, lv.filled_slots,
                   l.id AS listing_id, l.title AS listing_title, vt.name AS voice_type_name
            FROM listing_vacancies lv
            JOIN listings l ON l.id = lv.listing_id
            LEFT JOIN voice_types vt ON vt.id = lv.voice_type_id
            WHERE l.author_id = :viewer_id AND l.is_active = TRUE
              AND l.listing_type = :expected_listing_type
              AND lv.filled_slots < lv.total_slots
              AND NOT EXISTS (
                  SELECT 1 FROM job_invitations ji
                  WHERE ji.vacancy_id = lv.id AND ji.artist_user_id = :profile_id AND ji.status = 'pending'
              )
            ORDER BY l.created_at DESC
            """,
            {
                "viewer_id": viewer["id"], "profile_id": user_id,
                "expected_listing_type": "seeking_singer" if profile_user["role"] == "singer" else "seeking_conductor",
            },
        )

    badges = []
    if profile_user and not blocked_either_way:
        role_profile_for_badges = singer_profile if profile_user["role"] == "singer" else conductor_profile
        completeness_pct = compute_profile_completeness(
            profile_user, role_profile_for_badges, composer_tags, audio_links, social_links
        )["percent"]
        all_badges = with_profile_complete(get_user_badges(user_id), completeness_pct)
        badges = [b for b in all_badges if b["unlocked"]]

    context = {
        "user": viewer,
        "profile_user": profile_user,
        "singer_profile": singer_profile,
        "conductor_profile": conductor_profile,
        "composer_tags": composer_tags,
        "audio_links": audio_links,
        "social_links": social_links,
        "social_platforms": SOCIAL_PLATFORMS,
        "can_rate": can_rate,
        "rating_given": rating_given,
        "is_blocked": is_blocked,
        "blocked_either_way": blocked_either_way,
        "badges": badges,
        "is_highlighted": is_highlighted,
        "listings": listings,
        # Primary voice + extra voices (singer_profile_voice_types),
        # deduplicated — P2.A. Empty for conductors/composers.
        "all_voice_names": get_all_voice_type_names(user_id) if profile_user and profile_user["role"] == "singer" else [],
        # Spoken languages (P2.B) — any role.
        "spoken_language_names": get_spoken_language_names(user_id, getattr(request.state, "lang", "de")) if profile_user else [],
        # P3.B: "convidar para uma vaga" widget data + flash messages
        # from the invite form's redirect back to this same page.
        "invitable_vacancies": invitable_vacancies,
        "invited": request.query_params.get("invited") == "1",
        "invite_error": request.query_params.get("invite_error"),
        # Freemium: without login you can only see name/role/city —
        # bio, hashtags, audio links and listings stay behind signup.
        "locked": viewer is None,
        # P2 cluster (19/09/2026) — solo vs. choir repertoire cards
        # (see app/singer_works.py). Empty for conductors/composers and
        # for the locked (not-logged-in) freemium view, same gating as
        # audio_links/composer_tags above.
        "works_by_category": (
            get_works_by_category(user_id)
            if profile_user and profile_user["role"] == "singer" and viewer is not None
            else {"solo": [], "choir": []}
        ),
        "profile_share_url": profile_public_url(request.base_url, profile_user["id"], profile_user["profile_slug"]),
    }
    return render(request, "public_profile.html", context)

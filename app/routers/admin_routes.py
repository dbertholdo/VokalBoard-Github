"""
Admin panel — overview (reports/blocks/numbers, read-only) + user
management (/admin/users), which does allow real actions: manually
confirming an email, sending a password reset link, promoting/removing
admin status, deactivating/reactivating, or permanently deleting an
account. It doesn't replace Adminer (see docker-compose.yml, the
"adminer" service) for deeper/one-off edits to the database, but it
covers day-to-day actions without needing to open SQL.

Protection: users.is_admin (see db/schema.sql). There's no admin
signup through the UI — the FIRST admin becomes admin only via a
direct UPDATE on the database:

    UPDATE users SET is_admin = TRUE WHERE email = 'your-email@example.com';

(see README, "Admin level" section). After that, promoting other
people can be done from here (/admin/users/{id}).
"""
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse

from app.database import fetch_all, fetch_one, execute, execute_returning, transaction
from app.account_purge import erase_account
from app.avatars import remove_existing_avatar
from app.match_evaluations import get_quality_tiers
from app.referrals import record_referral_verification, get_credit_ledger
from app.notas_wallet import get_credit_balance, refund_ledger_entry
from app.highlights import adjust_highlight_days, MAX_HIGHLIGHT_DAYS_ADJUSTMENT
from app.moderation import resolve_report, apply_moderation_punishment, unban_user, get_moderation_history, PUNISHMENT_TYPES
from app.email import send_email
from app.email_localization import report_resolved_email, moderation_punishment_email
from app.shop_catalog import (
    list_all_catalog_items,
    toggle_catalog_item_active,
    create_catalog_item,
    update_catalog_item,
    get_shop_history,
    count_shop_history,
    SHOP_HISTORY_PAGE_SIZE,
    ALLOWED_ICONS,
    DEFAULT_ICON,
)
from app.auth import get_current_user
from app.render import render
from app.csrf import verify_csrf
from app.routers.auth_routes import send_password_reset_email
from app import messenger
from app.admin_nav import admin_attention_counts
from app.permissions import require_level, sync_is_admin_flag, log_audit_action, reauthenticate, LEVEL_COMMON, LEVEL_MODERATOR, LEVEL_ADMIN, LEVEL_GOD
from app.richtext import sanitize_post_body
from app.post_images import save_post_image
from app.system_flags import is_compatibility_score_visible, set_compatibility_score_visible
from app.feature_usage import get_feature_usage_totals
from app.email_layout import (
    get_email_layout_settings,
    update_email_layout_settings,
    update_email_template,
    reset_email_template,
    render_email,
    DEFAULT_TEMPLATE_HTML,
)
from app.periodic_mails import (
    FREQUENCIES,
    list_periodic_mails,
    get_periodic_mail,
    create_periodic_mail,
    update_periodic_mail,
    set_periodic_mail_active,
    delete_periodic_mail,
    render_body_preview,
)

router = APIRouter()

POST_TITLE_MAX_LENGTH = 150
# Much larger than before (used to be 4000): the body now stores the
# editor's HTML (formatting tags + <img src="/post-images/..."> also
# count as characters), not just plain text — see app/richtext.py.
POST_BODY_MAX_LENGTH = 20000

ADMIN_USERS_PAGE_SIZE = 30

# Column/expression used in ORDER BY for each sort option — a fixed
# allowlist, never the raw query string value, so it can't open up a
# SQL injection hole via a URL parameter.
ADMIN_USER_SORT_OPTIONS = {
    "newest": "u.created_at DESC",
    "rating": "avg_rating DESC NULLS LAST, rating_count DESC",
    "views": "profile_views DESC",
    "engagement": "messages_received DESC",
    "name": "u.full_name ASC",
}


def _password_ok(request: Request, admin: dict, password: str, action: str, user_id: int) -> bool:
    """Step-up auth for privilege changes and irreversible actions (CLAUDE.md §2.4);
    failed attempts are audited too."""
    if reauthenticate(request, admin, password):
        return True
    log_audit_action(request, admin, f"{action}_failed_auth", f"user_id={user_id}")
    return False


def require_admin(request: Request) -> dict | None:
    """Returns the logged-in user if they have level >= 2 (admin), else None.

    Still called require_admin (instead of renaming it to
    require_level_2 everywhere) so we don't need to touch the 15 calls
    already scattered across this file — but underneath it already
    uses the level scale (see app/permissions.py). Level 3 (god mode)
    also passes here, since 3 >= 2.
    """
    return require_level(request, LEVEL_ADMIN)


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    # FIX (19/09/2026, Daniel: a real Admin-level account couldn't open
    # the Admin button at all, while a God Mode account could — this
    # route was requiring LEVEL_GOD just to VIEW the dashboard, which
    # both contradicted app/permissions.py's own documented level
    # scale (level 2/admin = "everything the /admin panel already did
    # before levels existed") and every other admin sub-page below
    # this one (/admin/users, /admin/analytics, /admin/posts, ... all
    # already use require_admin() = LEVEL_ADMIN). Viewing the
    # dashboard — stats, the reports/blocks list — is read-only; the
    # actions that actually DO something sensitive (accept/reject a
    # report with a punishment, unban, grant admin/god, toggle
    # banners/Capitalism Mode) each keep their own require_level(...,
    # LEVEL_GOD) call right below, unchanged, so this fix only restores
    # the level-2 VIEW access the rest of the system already assumed
    # existed — it does not hand out any new punishment/privilege power.
    admin = require_admin(request)
    if not admin:
        # Intentionally does NOT distinguish "not an admin" from "page
        # doesn't exist" for someone probing the URL — just redirects
        # to the home page, with no specific error message.
        return RedirectResponse(url="/", status_code=303)

    stats = {
        "users": fetch_one("SELECT COUNT(*) AS n FROM users WHERE deleted_at IS NULL")["n"],
        "listings": fetch_one("SELECT COUNT(*) AS n FROM visible_listings WHERE is_active = TRUE")["n"],
        "messages": fetch_one("SELECT COUNT(*) AS n FROM visible_messages")["n"],
        "blocked_pairs": fetch_one("SELECT COUNT(*) AS n FROM blocked_users")["n"],
        "open_reports": fetch_one("SELECT COUNT(*) AS n FROM listing_reports WHERE status = 'open'")["n"],
    }

    context = {
        "user": admin,
        "stats": stats,
        "feature_usage": get_feature_usage_totals(),
    }
    return render(request, "admin.html", context)


@router.get("/admin/reports", response_class=HTMLResponse)
def admin_reports(request: Request, tab: str = "listings"):
    """Moderation in one place (docs/specs/ADMIN_REORG.md): listing reports,
    reported messages, blocks. Admins review; only God Mode acts."""
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    tab = tab if tab in ("listings", "messages", "blocks") else "listings"
    context = {"user": admin, "tab": tab, "can_act": (admin.get("role_level") or 0) >= LEVEL_GOD,
               "counts": admin_attention_counts(), "reports": [], "message_reports": [], "blocks": []}
    if tab == "listings":
        context["reports"] = fetch_all(
            """
            SELECT lr.id, lr.reason, lr.created_at, lr.status,
                   l.id AS listing_id, l.title AS listing_title,
                   ru.full_name AS reporter_name, au.full_name AS author_name
            FROM listing_reports lr
            JOIN visible_listings l ON l.id = lr.listing_id
            JOIN users ru ON ru.id = lr.reporter_id
            JOIN users au ON au.id = l.author_id
            ORDER BY (lr.status = 'open') DESC, lr.created_at DESC
            LIMIT 50
            """
        )
    elif tab == "messages":
        context["message_reports"] = messenger.open_message_reports()
    else:
        context["blocks"] = fetch_all(
            """
            SELECT bu.id, bu.reason, bu.created_at,
                   bkr.full_name AS blocker_name, bkd.full_name AS blocked_name
            FROM blocked_users bu
            JOIN users bkr ON bkr.id = bu.blocker_id
            JOIN users bkd ON bkd.id = bu.blocked_id
            ORDER BY bu.created_at DESC
            LIMIT 50
            """
        )
    return render(request, "admin_reports.html", context)


@router.post("/admin/reports/{report_id}/accept")
def admin_accept_report(request: Request, report_id: int, csrf_token: str = Form(...), punishment: str = Form("")):
    """"No botão de denúncia precisamos definir alguma forma de
    warning/punição/banimento" (pedido do Daniel, P6) — aceitar uma
    denúncia agora também aplica (opcionalmente) uma punição ao autor
    do anúncio, escolhida no mesmo formulário. `punishment` vazio =
    aceita sem punir a conta (ex.: já resolvido de outro jeito)."""
    admin = require_level(request, LEVEL_GOD)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    if punishment and punishment not in PUNISHMENT_TYPES:
        return RedirectResponse(url="/admin?report_error=1", status_code=303)

    report = resolve_report(report_id, accepted=True, admin_id=admin["id"])
    if not report:
        return RedirectResponse(url="/admin/reports", status_code=303)

    subject, html = report_resolved_email(
        report.get("preferred_language"), report["reporter_name"], report["listing_title"], True,
    )
    send_email(report["reporter_email"], subject, html)

    if punishment:
        apply_moderation_punishment(report["author_id"], punishment, report_id, admin["id"])
        subject, html = moderation_punishment_email(
            report.get("author_preferred_language"), report["author_name"], report["listing_title"], punishment,
        )
        send_email(report["author_email"], subject, html)
        log_audit_action(request, admin, "moderation_punishment", f"user_id={report['author_id']} punishment={punishment} report_id={report_id}")

    return RedirectResponse(url="/admin/reports", status_code=303)


@router.post("/admin/reports/{report_id}/reject")
def admin_reject_report(request: Request, report_id: int, csrf_token: str = Form(...)):
    """Rejeitar NUNCA aplica punição — só fecha a denúncia e avisa quem
    denunciou que não foi encontrada violação (ver
    report_resolved_email())."""
    admin = require_level(request, LEVEL_GOD)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    report = resolve_report(report_id, accepted=False, admin_id=admin["id"])
    if report:
        subject, html = report_resolved_email(
            report.get("preferred_language"), report["reporter_name"], report["listing_title"], False,
        )
        send_email(report["reporter_email"], subject, html)
    return RedirectResponse(url="/admin/reports", status_code=303)


@router.post("/admin/message-reports/{report_id}/{action}")
def admin_resolve_message_report(request: Request, report_id: int, action: str, csrf_token: str = Form(...)):
    """Dismiss a reported message, or remove it. God Mode only, like listing
    reports (Daniel, 2026-09-26: moderators don't act on reports)."""
    admin = require_level(request, LEVEL_GOD)
    if not admin or action not in ("dismiss", "remove"):
        return RedirectResponse(url="/admin/reports?tab=messages", status_code=303)
    verify_csrf(request, csrf_token)
    if messenger.resolve_message_report(report_id, admin["id"], remove_message=action == "remove"):
        log_audit_action(request, admin, f"message_report_{action}", f"message_report_id={report_id}")
    return RedirectResponse(url="/admin/reports?tab=messages", status_code=303)


@router.post("/admin/users/{user_id}/unban")
def admin_unban_user(request: Request, user_id: int, csrf_token: str = Form(...)):
    """Reverte um banimento — sempre manual, exige God Mode (mesmo
    nível que aplica a punição em primeiro lugar), mesmo a página
    /admin/users/{id} sendo acessível a partir do nível Admin comum."""
    admin = require_level(request, LEVEL_GOD)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    unban_user(user_id)
    log_audit_action(request, admin, "admin_unban_user", f"user_id={user_id}")
    return RedirectResponse(url=f"/admin/users/{user_id}?unban_done=1", status_code=303)


@router.get("/admin/users", response_class=HTMLResponse)
def admin_users_list(request: Request, q: str = "", sort: str = "newest", page: int = 1, active_only: str = ""):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)

    sort = sort if sort in ADMIN_USER_SORT_OPTIONS else "newest"
    page = max(page, 1)
    offset = (page - 1) * ADMIN_USERS_PAGE_SIZE
    search = f"%{q.strip()}%" if q.strip() else "%"
    # "Lista de usuários ativos filtrável" (pedido do Daniel, P6) — só
    # exclui quem desativou a própria conta (users.deleted_at); usuários
    # com role_level baixo/sem verificação continuam contando como
    # "ativos" (não confundir com "email_verified").
    active_only_flag = active_only == "1"
    active_clause = "AND u.deleted_at IS NULL" if active_only_flag else ""

    # Aggregated subqueries (profile views, average rating/count of
    # ratings RECEIVED, messages received) joined via LEFT JOIN so a
    # user with none of these yet doesn't disappear from the results.
    base_query = f"""
        SELECT u.id, u.full_name, u.email, u.role, u.city, u.state, u.country,
               u.is_admin, u.role_level, u.email_verified, u.deleted_at, u.created_at,
               COALESCE(pv.profile_views, 0) AS profile_views,
               COALESCE(r.avg_rating, NULL) AS avg_rating,
               COALESCE(r.rating_count, 0) AS rating_count,
               COALESCE(m.messages_received, 0) AS messages_received
        FROM users u
        LEFT JOIN (
            SELECT profile_user_id, COUNT(*) AS profile_views
            FROM profile_views GROUP BY profile_user_id
        ) pv ON pv.profile_user_id = u.id
        LEFT JOIN (
            SELECT rated_id, AVG(stars)::numeric(3,2) AS avg_rating, COUNT(*) AS rating_count
            FROM ratings GROUP BY rated_id
        ) r ON r.rated_id = u.id
        LEFT JOIN (
            SELECT recipient_id, COUNT(*) AS messages_received
            FROM visible_messages GROUP BY recipient_id
        ) m ON m.recipient_id = u.id
        WHERE (u.full_name ILIKE :search OR u.email ILIKE :search) {active_clause}
        ORDER BY {ADMIN_USER_SORT_OPTIONS[sort]}
        LIMIT :limit OFFSET :offset
    """  # nosec B608 - ORDER BY comes only from ADMIN_USER_SORT_OPTIONS (a fixed
         # allowlist, `sort` already validated against its keys above); active_clause
         # is also a fixed literal ("" or the hardcoded AND above, never user input
         # interpolated directly) — the actual search values (search, limit, offset)
         # are all passed as parameters.
    users = fetch_all(base_query, {"search": search, "limit": ADMIN_USERS_PAGE_SIZE, "offset": offset})

    total = fetch_one(
        f"SELECT COUNT(*) AS n FROM users u WHERE (u.full_name ILIKE :search OR u.email ILIKE :search) {active_clause}",  # nosec B608 - same fixed active_clause
        {"search": search},
    )["n"]

    context = {
        "user": admin,
        "users": users,
        "q": q,
        "sort": sort,
        "page": page,
        "total": total,
        "page_size": ADMIN_USERS_PAGE_SIZE,
        "has_next": offset + ADMIN_USERS_PAGE_SIZE < total,
        "has_prev": page > 1,
        "sort_options": list(ADMIN_USER_SORT_OPTIONS.keys()),
        "active_only": active_only_flag,
    }
    return render(request, "admin_users.html", context)


@router.get("/admin/users/{user_id}", response_class=HTMLResponse)
def admin_user_detail(request: Request, user_id: int):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)

    target = fetch_one("SELECT * FROM users WHERE id = :id", {"id": user_id})
    if not target:
        return RedirectResponse(url="/admin/users", status_code=303)

    stats = {
        "profile_views": fetch_one(
            "SELECT COUNT(*) AS n FROM profile_views WHERE profile_user_id = :id", {"id": user_id}
        )["n"],
        "avg_rating": fetch_one(
            "SELECT AVG(stars)::numeric(3,2) AS n FROM ratings WHERE rated_id = :id", {"id": user_id}
        )["n"],
        "rating_count": fetch_one(
            "SELECT COUNT(*) AS n FROM ratings WHERE rated_id = :id", {"id": user_id}
        )["n"],
        "listings": fetch_one(
            "SELECT COUNT(*) AS n FROM visible_listings WHERE author_id = :id AND is_active = TRUE", {"id": user_id}
        )["n"],
        "messages_sent": fetch_one(
            "SELECT COUNT(*) AS n FROM visible_messages WHERE sender_id = :id", {"id": user_id}
        )["n"],
        "messages_received": fetch_one(
            "SELECT COUNT(*) AS n FROM visible_messages WHERE recipient_id = :id", {"id": user_id}
        )["n"],
    }

    recent_ratings = fetch_all(
        """
        SELECT rt.stars, rt.comment, rt.created_at, u.full_name AS rater_name
        FROM ratings rt JOIN users u ON u.id = rt.rater_id
        WHERE rt.rated_id = :id ORDER BY rt.created_at DESC LIMIT 20
        """,
        {"id": user_id},
    )

    # P3.F: selos de qualidade (média corrente por categoria, estilo Uber)
    # — agregado só, o Admin pode ver o mesmo que o próprio dono vê na
    # /profile, mas NUNCA quem avaliou ou a nota individual de um Match
    # (ver app/match_evaluations.py — secreto por decisão do Daniel).
    quality_tiers = get_quality_tiers(user_id)

    context = {
        "user": admin,
        "target": target,
        "stats": stats,
        "recent_ratings": recent_ratings,
        "quality_tiers": quality_tiers,
        "is_self": target["id"] == admin["id"],
        # Extrato de Notas — pedido do Daniel (18/09/2026, painel de
        # Admin da Loja): buscar um usuário e ver o extrato dele. Mostra
        # o extrato COMPLETO (não só compras da loja) — pra suporte,
        # ver bônus/recompensas junto com resgates dá o quadro inteiro.
        "notas_balance": get_credit_balance(user_id),
        "notas_ledger": get_credit_ledger(user_id, limit=100),
        # IDs de linhas de débito já reembolsadas (ver refund-notas
        # abaixo) — pra esconder o botão "Reembolsar" de quem já foi
        # reembolsado (idempotência visual; o backend também impede via
        # idempotency_key).
        "refunded_ledger_ids": {
            row["reference_id"]
            for row in fetch_all(
                "SELECT reference_id FROM credit_ledger WHERE user_id = :id AND reason = 'admin_refund' AND reference_id IS NOT NULL",
                {"id": user_id},
            )
        },
        "max_highlight_days_adjustment": MAX_HIGHLIGHT_DAYS_ADJUSTMENT,
        # Histórico de punições de moderação (P6, 18/09/2026) — ver
        # app/moderation.py.
        "moderation_history": get_moderation_history(user_id),
    }
    return render(request, "admin_user_detail.html", context)


@router.post("/admin/users/{user_id}/highlight-days")
def admin_adjust_highlight_days(request: Request, user_id: int, days: int = Form(...), csrf_token: str = Form(...)):
    """"Adicionar/remover dias" (pedido do Daniel, painel de Admin,
    P6) — dá ou tira dias de destaque de perfil manualmente (cortesia
    de suporte, corrigir um resgate com bug, etc.), sem passar pela
    Loja/Notas. `days` pode ser negativo pra remover."""
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    if abs(days) > MAX_HIGHLIGHT_DAYS_ADJUSTMENT:
        return RedirectResponse(url=f"/admin/users/{user_id}?highlight_error=1", status_code=303)

    adjust_highlight_days(user_id, days)
    log_audit_action(request, admin, "admin_highlight_days_adjust", f"user_id={user_id} days={days}")
    return RedirectResponse(url=f"/admin/users/{user_id}?highlight_updated=1", status_code=303)


@router.post("/admin/users/{user_id}/refund-notas/{ledger_id}")
def admin_refund_notas(request: Request, user_id: int, ledger_id: int, csrf_token: str = Form(...)):
    """"Reembolso" (pedido do Daniel, painel de Admin, P6) — credita de
    volta o valor de UMA linha de débito específica do extrato de
    Notas desse usuário (ex.: resgate de item da Loja que deu bug).
    Só aceita reembolsar uma linha que (a) é realmente um débito
    (delta < 0) e (b) pertence a esse usuário — nunca um valor "total"
    vindo do formulário. `idempotency_key` amarrada ao `ledger_id`
    impede reembolsar a mesma linha duas vezes por engano (duplo
    clique/F5)."""
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    # A linha precisa pertencer a ESSE usuário — refund_ledger_entry()
    # sozinha não checa isso (é chamada também de /financeiro/estornos,
    # que não tem um user_id de URL pra comparar), então a checagem
    # fica aqui, na rota, antes de delegar.
    entry = fetch_one(
        "SELECT id FROM credit_ledger WHERE id = :id AND user_id = :uid",
        {"id": ledger_id, "uid": user_id},
    )
    if not entry:
        return RedirectResponse(url=f"/admin/users/{user_id}?refund_error=1", status_code=303)

    credited, _ = refund_ledger_entry(ledger_id, admin["id"])
    if not credited:
        return RedirectResponse(url=f"/admin/users/{user_id}?refund_error=1", status_code=303)
    log_audit_action(request, admin, "admin_refund_notas", f"user_id={user_id} ledger_id={ledger_id}")
    return RedirectResponse(url=f"/admin/users/{user_id}?refund_done=1", status_code=303)


@router.post("/admin/users/{user_id}/verify-email")
def admin_verify_email(request: Request, user_id: int, csrf_token: str = Form(...)):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    execute("UPDATE users SET email_verified = TRUE WHERE id = :id", {"id": user_id})
    record_referral_verification(user_id)
    log_audit_action(request, admin, "admin_verify_email", f"user_id={user_id}")
    return RedirectResponse(url=f"/admin/users/{user_id}", status_code=303)


@router.post("/admin/users/{user_id}/send-reset")
def admin_send_reset(request: Request, user_id: int, csrf_token: str = Form(...)):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    target = fetch_one("SELECT id, email, full_name, preferred_language FROM users WHERE id = :id", {"id": user_id})
    if target:
        send_password_reset_email(request, target["id"], target["email"], target["full_name"], target.get("preferred_language"))
        log_audit_action(request, admin, "admin_send_password_reset", f"user_id={user_id}")
    return RedirectResponse(url=f"/admin/users/{user_id}?reset_sent=1", status_code=303)


@router.post("/admin/toggle-compatibility-score-visible")
def admin_toggle_compatibility_score_visible(request: Request, csrf_token: str = Form(...)):
    """
    P3.E: on/off for showing the "% compatibilidade" signal to end
    users (see app/compatibility.py, app/system_flags.py). Not a Red
    Zone action — it's not financial/destructive, just a display
    toggle — so any LEVEL_GOD admin can flip it, no password
    re-auth, same as toggle-admin/toggle-god-mode above.
    """
    admin = require_level(request, LEVEL_GOD)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    set_compatibility_score_visible(not is_compatibility_score_visible(), admin["id"])
    log_audit_action(request, admin, "toggle_compatibility_score_visible", f"now={is_compatibility_score_visible()}")
    return RedirectResponse(url="/financeiro?saved=1", status_code=303)


@router.post("/admin/users/{user_id}/toggle-admin")
def admin_toggle_admin(request: Request, user_id: int, csrf_token: str = Form(...), current_password: str = Form("")):
    # Raising or removing privileges is a God Mode action.  A regular admin
    # must never be able to create another admin account.
    admin = require_level(request, LEVEL_GOD)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    # Protection against self-removal: an admin can't revoke their own
    # access from here (to avoid the last admin account accidentally
    # locking itself out). To remove yourself, another admin has to do it.
    if user_id == admin["id"]:
        return RedirectResponse(url=f"/admin/users/{user_id}?self_demote_blocked=1", status_code=303)

    target = fetch_one("SELECT role_level FROM users WHERE id = :id", {"id": user_id})
    if not target:
        return RedirectResponse(url="/admin/users", status_code=303)
    if not _password_ok(request, admin, current_password, "toggle_admin", user_id):
        return RedirectResponse(url=f"/admin/users/{user_id}?auth_failed=1", status_code=303)

    # Toggles only between regular (0) and admin (2) — promoting
    # someone to god mode (3, with access to the Red Zone) is a
    # separate, more sensitive action, and only another god mode user
    # can do it (see admin_toggle_god below). If the person was already
    # level 3, a toggle here demotes them to 0 (doesn't leave them
    # "half-promoted" at 2).
    new_level = LEVEL_COMMON if target["role_level"] >= LEVEL_ADMIN else LEVEL_ADMIN
    execute("UPDATE users SET role_level = :level WHERE id = :id", {"level": new_level, "id": user_id})
    sync_is_admin_flag(user_id, new_level)
    log_audit_action(request, admin, "toggle_admin", f"user_id={user_id} level {target['role_level']}->{new_level}")
    return RedirectResponse(url=f"/admin/users/{user_id}", status_code=303)


@router.post("/admin/users/{user_id}/toggle-god-mode")
def admin_toggle_god_mode(request: Request, user_id: int, csrf_token: str = Form(...), current_password: str = Form("")):
    """Promotes/demotes between admin (2) and god mode (3) — the Red Zone
    is only visible at level 3. Intentionally only another god mode
    user can do this (being a regular admin isn't enough), so it
    doesn't become a side door into the financial panel.
    """
    admin = require_level(request, LEVEL_GOD)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    if user_id == admin["id"]:
        return RedirectResponse(url=f"/admin/users/{user_id}?self_demote_blocked=1", status_code=303)

    target = fetch_one("SELECT role_level FROM users WHERE id = :id", {"id": user_id})
    if not target or target["role_level"] < LEVEL_ADMIN:
        # Only promotes/demotes someone who is already admin (2) — to
        # become god mode you first need to be a regular admin, one
        # step at a time.
        return RedirectResponse(url=f"/admin/users/{user_id}", status_code=303)
    if not _password_ok(request, admin, current_password, "toggle_god_mode", user_id):
        return RedirectResponse(url=f"/admin/users/{user_id}?auth_failed=1", status_code=303)

    new_level = LEVEL_ADMIN if target["role_level"] >= LEVEL_GOD else LEVEL_GOD
    execute("UPDATE users SET role_level = :level WHERE id = :id", {"level": new_level, "id": user_id})
    sync_is_admin_flag(user_id, new_level)
    log_audit_action(request, admin, "toggle_god_mode", f"user_id={user_id} level {target['role_level']}->{new_level}")
    return RedirectResponse(url=f"/admin/users/{user_id}", status_code=303)


@router.post("/admin/users/{user_id}/deactivate")
def admin_deactivate(request: Request, user_id: int, csrf_token: str = Form(...)):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    if user_id == admin["id"]:
        return RedirectResponse(url=f"/admin/users/{user_id}?self_demote_blocked=1", status_code=303)

    execute("UPDATE users SET deleted_at = now() WHERE id = :id", {"id": user_id})
    log_audit_action(request, admin, "admin_deactivate_user", f"user_id={user_id}")
    return RedirectResponse(url=f"/admin/users/{user_id}", status_code=303)


@router.post("/admin/users/{user_id}/reactivate")
def admin_reactivate(request: Request, user_id: int, csrf_token: str = Form(...)):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    # Banimento é diferente de desativação (ver app/moderation.py) —
    # essa rota nunca deve reverter um ban por engano/URL manipulada;
    # só POST /admin/users/{id}/unban (God Mode) faz isso.
    target = fetch_one("SELECT banned_at FROM users WHERE id = :id", {"id": user_id})
    if target and target["banned_at"]:
        return RedirectResponse(url=f"/admin/users/{user_id}", status_code=303)

    execute("UPDATE users SET deleted_at = NULL WHERE id = :id", {"id": user_id})
    log_audit_action(request, admin, "admin_reactivate_user", f"user_id={user_id}")
    return RedirectResponse(url=f"/admin/users/{user_id}", status_code=303)


@router.post("/admin/users/{user_id}/delete-forever")
def admin_delete_forever(request: Request, user_id: int, csrf_token: str = Form(...), current_password: str = Form("")):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    if user_id == admin["id"]:
        return RedirectResponse(url=f"/admin/users/{user_id}?self_demote_blocked=1", status_code=303)

    # Irreversible: password re-check + audit (CLAUDE.md §2.4). Same erase as the
    # 6-month purge — Matches block a plain DELETE (that used to be a 500).
    if not _password_ok(request, admin, current_password, "admin_delete_forever", user_id):
        return RedirectResponse(url=f"/admin/users/{user_id}?auth_failed=1", status_code=303)
    if not fetch_one("SELECT 1 FROM users WHERE id = :id", {"id": user_id}):
        return RedirectResponse(url="/admin/users", status_code=303)
    with transaction() as conn:
        erase_account(conn, user_id)
    remove_existing_avatar(user_id)
    log_audit_action(request, admin, "admin_delete_forever", f"user_id={user_id}")
    return RedirectResponse(url="/admin/users?deleted=1", status_code=303)


# ------------------------------------------------------------
# Loja (P5 — painel de Admin, 18/09/2026). Pedido do Daniel: um menu
# dedicado pra controlar a loja — ativar/desativar produto (ex.: bug
# num item, sem tirar a loja inteira do ar) + histórico geral das
# transações da loja. "Busca por usuário e extrato" reaproveita
# /admin/users (busca já existente) — o extrato em si foi adicionado
# à página /admin/users/{id} (ver admin_user_detail acima), em vez de
# duplicar uma busca de usuário só pra loja.
# ------------------------------------------------------------
ADMIN_LOJA_HISTORY_PAGE_SIZE = SHOP_HISTORY_PAGE_SIZE


@router.get("/admin/loja", response_class=HTMLResponse)
def admin_loja(request: Request, page: int = 1, created: str = "", updated: str = "", error: str = ""):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)

    page = max(page, 1)
    offset = (page - 1) * ADMIN_LOJA_HISTORY_PAGE_SIZE
    total_history = count_shop_history()

    context = {
        "user": admin,
        "catalog_items": list_all_catalog_items(),
        "allowed_icons": ALLOWED_ICONS,
        "history": get_shop_history(limit=ADMIN_LOJA_HISTORY_PAGE_SIZE, offset=offset),
        "page": page,
        "total_history": total_history,
        "page_size": ADMIN_LOJA_HISTORY_PAGE_SIZE,
        "has_next": offset + ADMIN_LOJA_HISTORY_PAGE_SIZE < total_history,
        "has_prev": page > 1,
        "created": created,
        "updated": updated,
        "error": error,
    }
    return render(request, "admin_loja.html", context)


@router.post("/admin/loja/catalog/{item_id}/toggle-active")
def admin_loja_toggle_catalog_item(request: Request, item_id: int, csrf_token: str = Form(...)):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    toggle_catalog_item_active(item_id)
    return RedirectResponse(url="/admin/loja", status_code=303)


def _parse_catalog_cost(raw: str) -> Decimal | None:
    """Aceita tanto "3" quanto "3,50" (vírgula, formato do site) ou
    "3.50" — devolve None se não for um número válido ou não for
    positivo."""
    try:
        value = Decimal(raw.strip().replace(",", "."))
    except (InvalidOperation, AttributeError):
        return None
    if value <= 0:
        return None
    return value


@router.post("/admin/loja/catalog/new")
def admin_loja_create_catalog_item(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    cost: str = Form(...),
    icon: str = Form(DEFAULT_ICON),
    csrf_token: str = Form(...),
):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    parsed_cost = _parse_catalog_cost(cost)
    if not title.strip() or not description.strip() or parsed_cost is None:
        return RedirectResponse(url="/admin/loja?error=invalid_item", status_code=303)

    create_catalog_item(title, description, parsed_cost, icon)
    return RedirectResponse(url="/admin/loja?created=1", status_code=303)


@router.post("/admin/loja/catalog/{item_id}/edit")
def admin_loja_edit_catalog_item(
    request: Request,
    item_id: int,
    title: str = Form(...),
    description: str = Form(...),
    cost: str = Form(...),
    icon: str = Form(DEFAULT_ICON),
    csrf_token: str = Form(...),
):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    parsed_cost = _parse_catalog_cost(cost)
    if not title.strip() or not description.strip() or parsed_cost is None:
        return RedirectResponse(url="/admin/loja?error=invalid_item", status_code=303)

    update_catalog_item(item_id, title, description, parsed_cost, icon)
    return RedirectResponse(url="/admin/loja?updated=1", status_code=303)


# ------------------------------------------------------------
# Layout compartilhado de e-mails (P6, 18/09/2026). Pedido do Daniel:
# editar o layout (logo, cor de destaque, emoji de cabeçalho,
# assinatura, rodapé) de TODOS os e-mails automáticos num lugar só —
# ver app/email_layout.py (render_email(), chamado automaticamente por
# app/email.py's send_email() em TODOS os ~16 pontos de envio do
# site). O "corpo mudar automaticamente baseado no objetivo do
# e-mail" já acontecia naturalmente antes disso — cada função decide
# o próprio conteúdo; esta tela só edita o envelope ao redor.
# ------------------------------------------------------------

SAMPLE_EMAIL_BODY_PREVIEW = """
    <p>Olá Maria,</p>
    <p>Este é um exemplo de corpo de e-mail — o texto real muda
    conforme o motivo do envio (confirmação de cadastro, novo convite,
    lembrete, etc.), mas o layout ao redor é sempre este.</p>
    <p><a href="#">https://exemplo.com/link</a></p>
"""


@router.get("/admin/emails", response_class=HTMLResponse)
def admin_emails(request: Request, tab: str = "form", updated: str = "", error: str = ""):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)

    tab = tab if tab in ("form", "code", "periodic") else "form"
    settings = get_email_layout_settings()
    context = {
        "user": admin,
        "tab": tab,
        "settings": settings,
        "default_template_html": DEFAULT_TEMPLATE_HTML,
        "preview_html": render_email(SAMPLE_EMAIL_BODY_PREVIEW),
        "updated": updated,
        "error": error,
        # Only actually used by the "Periodic" tab, but cheap enough
        # (a handful of rows, admin-only page) to just always fetch —
        # avoids a second round-trip route just for this list.
        "periodic_mails": list_periodic_mails() if tab == "periodic" else [],
    }
    return render(request, "admin_emails.html", context)


# ------------------------------------------------------------
# Periodic mails (P0 backlog item: daily/weekly/monthly reports) —
# built 19/09/2026 at Daniel's request. See app/periodic_mails.py's
# module docstring for the full design (recipients fixed to the admin
# team this round, body-only editing, scheduling). List lives on the
# "Periodic" tab of /admin/emails above; these are its create/edit/
# pause/delete actions.
# ------------------------------------------------------------

@router.get("/admin/emails/periodic/new", response_class=HTMLResponse)
def admin_periodic_mail_new(request: Request, error: str = ""):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)

    context = {
        "user": admin,
        "mail": None,
        "frequencies": FREQUENCIES,
        "error": error,
        "preview_html": "",
    }
    return render(request, "admin_periodic_mail_form.html", context)


@router.post("/admin/emails/periodic/new")
def admin_periodic_mail_create(
    request: Request,
    # Default "" (not Form(...)): FastAPI turns a blank required field into a
    # raw 422 page; app/periodic_mails.py validates and we redirect with
    # error=dados_invalidos instead.
    name: str = Form(""),
    subject: str = Form(""),
    body_html: str = Form(""),
    frequency: str = Form(""),
    csrf_token: str = Form(...),
):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    new_id = create_periodic_mail(name, subject, body_html, frequency, admin["id"])
    if new_id is None:
        return RedirectResponse(url="/admin/emails/periodic/new?error=dados_invalidos", status_code=303)

    log_audit_action(request, admin, "create_periodic_mail", f"periodic_mail_id={new_id} name={name.strip()[:80]}")
    return RedirectResponse(url="/admin/emails?tab=periodic&updated=1", status_code=303)


@router.get("/admin/emails/periodic/{mail_id}/edit", response_class=HTMLResponse)
def admin_periodic_mail_edit_form(request: Request, mail_id: int, error: str = ""):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)

    mail = get_periodic_mail(mail_id)
    if not mail:
        return RedirectResponse(url="/admin/emails?tab=periodic", status_code=303)

    context = {
        "user": admin,
        "mail": mail,
        "frequencies": FREQUENCIES,
        "error": error,
        "preview_html": render_body_preview(mail["body_html"]),
    }
    return render(request, "admin_periodic_mail_form.html", context)


@router.post("/admin/emails/periodic/{mail_id}/edit")
def admin_periodic_mail_update(
    request: Request,
    mail_id: int,
    # Default "" (not Form(...)): FastAPI turns a blank required field into a
    # raw 422 page; app/periodic_mails.py validates and we redirect with
    # error=dados_invalidos instead.
    name: str = Form(""),
    subject: str = Form(""),
    body_html: str = Form(""),
    frequency: str = Form(""),
    csrf_token: str = Form(...),
):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    ok = update_periodic_mail(mail_id, name, subject, body_html, frequency, admin["id"])
    if not ok:
        return RedirectResponse(url=f"/admin/emails/periodic/{mail_id}/edit?error=dados_invalidos", status_code=303)

    log_audit_action(request, admin, "update_periodic_mail", f"periodic_mail_id={mail_id}")
    return RedirectResponse(url="/admin/emails?tab=periodic&updated=1", status_code=303)


@router.post("/admin/emails/periodic/{mail_id}/toggle")
def admin_periodic_mail_toggle(request: Request, mail_id: int, is_active: str = Form(...), csrf_token: str = Form(...)):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    set_periodic_mail_active(mail_id, is_active == "1", admin["id"])
    log_audit_action(request, admin, "toggle_periodic_mail", f"periodic_mail_id={mail_id} is_active={is_active == '1'}")
    return RedirectResponse(url="/admin/emails?tab=periodic&updated=1", status_code=303)


@router.post("/admin/emails/periodic/{mail_id}/delete")
def admin_periodic_mail_delete(request: Request, mail_id: int, csrf_token: str = Form(...)):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    delete_periodic_mail(mail_id)
    log_audit_action(request, admin, "delete_periodic_mail", f"periodic_mail_id={mail_id}")
    return RedirectResponse(url="/admin/emails?tab=periodic&updated=1", status_code=303)


@router.post("/admin/emails")
async def admin_emails_update(
    request: Request,
    accent_color: str = Form(...),
    header_emoji: str = Form(...),
    signature: str = Form(...),
    footer: str = Form(...),
    csrf_token: str = Form(...),
    logo: UploadFile | None = File(None),
):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    logo_url = None  # None = mantém o logo atual (não reenviar arquivo toda vez)
    if logo is not None and logo.filename:
        logo_url = await save_post_image(logo)  # mesmo validador/processamento já usado nos posts do blog

    update_email_layout_settings(logo_url, accent_color, header_emoji, signature, footer, admin["id"])
    return RedirectResponse(url="/admin/emails?updated=1", status_code=303)


@router.post("/admin/emails/template")
def admin_emails_update_template(request: Request, template_html: str = Form(...), csrf_token: str = Form(...)):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    ok = update_email_template(template_html, admin["id"])
    if not ok:
        return RedirectResponse(url="/admin/emails?tab=code&error=invalid_template", status_code=303)
    return RedirectResponse(url="/admin/emails?tab=code&updated=1", status_code=303)


@router.post("/admin/emails/template/reset")
def admin_emails_reset_template(request: Request, csrf_token: str = Form(...)):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    reset_email_template(admin["id"])
    return RedirectResponse(url="/admin/emails?tab=code&updated=1", status_code=303)


# Weekday names for Postgres's EXTRACT(dow ...), which returns
# 0 = Sunday, 1 = Monday, ..., 6 = Saturday.
_WEEKDAY_NAMES = {
    "de": ["Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"],
    "en": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
}


@router.get("/admin/analytics", response_class=HTMLResponse)
def admin_analytics(request: Request):
    """
    "Analytics" panel — read-only, meant to give a pulse on site usage
    (when people visit most, where they come from, who comes back)
    without needing to touch SQL every time.

    All queries here are aggregated (counts/averages) — never shows
    which PERSON visited what; site_visits (see db/schema.sql) is
    already logged without storing identity, by design.
    """
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)

    lang = getattr(request.state, "lang", "de")

    # --- General visits: today / week / month / year ------------------
    visits_totals = fetch_one(
        """
        SELECT
            COUNT(*) FILTER (WHERE visited_at >= date_trunc('day', now())) AS today,
            COUNT(*) FILTER (WHERE visited_at >= date_trunc('week', now())) AS this_week,
            COUNT(*) FILTER (WHERE visited_at >= date_trunc('month', now())) AS this_month,
            COUNT(*) FILTER (WHERE visited_at >= date_trunc('year', now())) AS this_year,
            COUNT(*) AS all_time
        FROM site_visits
        """
    )

    # --- Pulse: day of week / hour of day / day of month -------
    # "Average" = total visits in that group ÷ how many distinct
    # calendar days that group has already appeared in the table —
    # this way a Sunday with only 2 weeks of data isn't
    # under-represented compared to a Monday with 8 weeks of history.
    by_weekday_raw = fetch_all(
        """
        SELECT
            EXTRACT(dow FROM visited_at)::int AS dow,
            COUNT(*) AS total,
            COUNT(DISTINCT date_trunc('day', visited_at)) AS distinct_days
        FROM site_visits
        GROUP BY dow
        ORDER BY dow
        """
    )
    weekday_names = _WEEKDAY_NAMES.get(lang, _WEEKDAY_NAMES["de"])
    by_weekday = [
        {
            "label": weekday_names[row["dow"]],
            "total": row["total"],
            "avg": round(row["total"] / row["distinct_days"], 1) if row["distinct_days"] else 0,
        }
        for row in by_weekday_raw
    ]

    by_hour_raw = fetch_all(
        """
        SELECT EXTRACT(hour FROM visited_at)::int AS hour, COUNT(*) AS total
        FROM site_visits GROUP BY hour ORDER BY hour
        """
    )
    by_hour = {row["hour"]: row["total"] for row in by_hour_raw}
    max_hour_total = max(by_hour.values()) if by_hour else 0
    by_hour_chart = [
        {"hour": h, "total": by_hour.get(h, 0), "pct": round(100 * by_hour.get(h, 0) / max_hour_total) if max_hour_total else 0}
        for h in range(24)
    ]

    by_day_of_month_raw = fetch_all(
        """
        SELECT EXTRACT(day FROM visited_at)::int AS dom, COUNT(*) AS total
        FROM site_visits GROUP BY dom ORDER BY dom
        """
    )
    by_day_of_month = {row["dom"]: row["total"] for row in by_day_of_month_raw}
    max_dom_total = max(by_day_of_month.values()) if by_day_of_month else 0
    by_day_of_month_chart = [
        {"day": d, "total": by_day_of_month.get(d, 0), "pct": round(100 * by_day_of_month.get(d, 0) / max_dom_total) if max_dom_total else 0}
        for d in range(1, 32)
    ]

    # --- Active users ---------------------------------------------
    active_users = fetch_one(
        """
        SELECT
            COUNT(*) FILTER (WHERE last_seen_at >= now() - interval '5 minutes') AS active_now,
            COUNT(*) FILTER (WHERE last_seen_at >= now() - interval '60 minutes') AS active_last_hour
        FROM users WHERE deleted_at IS NULL
        """
    )

    # --- Registered users by city / state / country / voice -----------------
    by_city = fetch_all(
        """
        SELECT city, COUNT(*) AS n FROM users
        WHERE deleted_at IS NULL AND city IS NOT NULL AND city <> ''
        GROUP BY city ORDER BY n DESC LIMIT 15
        """
    )
    by_state = fetch_all(
        """
        SELECT state, COUNT(*) AS n FROM users
        WHERE deleted_at IS NULL AND state IS NOT NULL AND state <> ''
        GROUP BY state ORDER BY n DESC LIMIT 15
        """
    )
    by_country = fetch_all(
        "SELECT country, COUNT(*) AS n FROM users WHERE deleted_at IS NULL GROUP BY country ORDER BY n DESC"
    )
    by_voice_type = fetch_all(
        """
        SELECT vt.name, COUNT(*) AS n
        FROM singer_profiles sp
        JOIN users u ON u.id = sp.user_id AND u.deleted_at IS NULL
        LEFT JOIN voice_types vt ON vt.id = sp.voice_type_id
        GROUP BY vt.name ORDER BY n DESC
        """
    )

    # --- Conversion funnel -------------------------------------------
    funnel = fetch_one(
        """
        SELECT
            COUNT(*) AS registered,
            COUNT(*) FILTER (WHERE email_verified) AS verified,
            COUNT(DISTINCT l.author_id) AS posted_listing
        FROM users u
        LEFT JOIN visible_listings l ON l.author_id = u.id
        WHERE u.deleted_at IS NULL
        """
    )

    # --- Message reply rate ---------------------------------
    # Counted by PAIR of people (not per individual message): of the
    # conversations that have exchanged at least 1 message, how many
    # got a reply (a message in both directions)?
    reply_stats = fetch_one(
        """
        WITH pairs AS (
            SELECT LEAST(sender_id, recipient_id) AS a, GREATEST(sender_id, recipient_id) AS b, sender_id
            FROM visible_messages
        ),
        conversations AS (
            SELECT a, b, COUNT(DISTINCT sender_id) AS distinct_senders
            FROM pairs GROUP BY a, b
        )
        SELECT
            COUNT(*) AS total_conversations,
            COUNT(*) FILTER (WHERE distinct_senders = 2) AS replied_conversations
        FROM conversations
        """
    )
    reply_rate_pct = (
        round(100 * reply_stats["replied_conversations"] / reply_stats["total_conversations"])
        if reply_stats["total_conversations"] else None
    )

    # --- Distribution of ratings and listing type --------------------
    ratings_distribution = fetch_all(
        "SELECT stars, COUNT(*) AS n FROM ratings GROUP BY stars ORDER BY stars DESC"
    )
    listing_type_distribution = fetch_all(
        "SELECT listing_type, COUNT(*) AS n FROM visible_listings WHERE is_active = TRUE GROUP BY listing_type ORDER BY n DESC"
    )

    # --- Retention -------------------------------------------------------
    # % of people who registered X or more days ago and still showed
    # signs of life (last_seen_at) X days AFTER registering.
    retention = fetch_one(
        """
        SELECT
            COUNT(*) FILTER (WHERE created_at <= now() - interval '7 days') AS eligible_7d,
            COUNT(*) FILTER (
                WHERE created_at <= now() - interval '7 days' AND last_seen_at >= created_at + interval '7 days'
            ) AS retained_7d,
            COUNT(*) FILTER (WHERE created_at <= now() - interval '30 days') AS eligible_30d,
            COUNT(*) FILTER (
                WHERE created_at <= now() - interval '30 days' AND last_seen_at >= created_at + interval '30 days'
            ) AS retained_30d
        FROM users WHERE deleted_at IS NULL
        """
    )
    retention_7d_pct = round(100 * retention["retained_7d"] / retention["eligible_7d"]) if retention["eligible_7d"] else None
    retention_30d_pct = round(100 * retention["retained_30d"] / retention["eligible_30d"]) if retention["eligible_30d"] else None

    # --- Language and traffic source --------------------------------------
    by_lang = fetch_all("SELECT lang, COUNT(*) AS n FROM site_visits GROUP BY lang ORDER BY n DESC")
    by_referrer = fetch_all(
        """
        SELECT COALESCE(referrer_domain, '(direct / unknown)') AS origem, COUNT(*) AS n
        FROM site_visits GROUP BY referrer_domain ORDER BY n DESC LIMIT 15
        """
    )

    context = {
        "user": admin,
        "visits_totals": visits_totals,
        "by_weekday": by_weekday,
        "by_hour_chart": by_hour_chart,
        # Same data as by_weekday/by_hour_chart, just in the
        # {label, value} format that app/static/js/financial-charts.js
        # expects for the bar/pie/line selector (see Red Zone).
        "by_weekday_json": [{"label": w["label"], "value": w["avg"]} for w in by_weekday],
        "by_hour_json": [{"label": f"{h['hour']:02d}:00", "value": h["total"]} for h in by_hour_chart if h["total"] > 0],
        "by_day_of_month_chart": by_day_of_month_chart,
        "active_users": active_users,
        "by_city": by_city,
        "by_state": by_state,
        "by_country": by_country,
        "by_voice_type": by_voice_type,
        "funnel": funnel,
        "reply_rate_pct": reply_rate_pct,
        "reply_stats": reply_stats,
        "ratings_distribution": ratings_distribution,
        "listing_type_distribution": listing_type_distribution,
        "retention_7d_pct": retention_7d_pct,
        "retention_30d_pct": retention_30d_pct,
        "retention": retention,
        "by_lang": by_lang,
        "by_referrer": by_referrer,
    }
    return render(request, "admin_analytics.html", context)


# ------------------------------------------------------------
# Posts (feed of announcements/partnerships/tips on the home page) —
# only admins create, edit, or unpublish them. See db/schema.sql
# (posts table) and app/routers/listings_routes.py::home() (where the
# feed is read back).
# ------------------------------------------------------------

@router.get("/admin/posts", response_class=HTMLResponse)
def admin_posts_list(request: Request):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)

    posts = fetch_all(
        """
        SELECT p.id, p.title, p.body, p.is_published, p.created_at, u.full_name AS author_name
        FROM posts p
        JOIN users u ON u.id = p.author_id
        ORDER BY p.created_at DESC
        """
    )
    context = {
        "user": admin,
        "posts": posts,
        "created": request.query_params.get("created") == "1",
        "title_max": POST_TITLE_MAX_LENGTH,
        "body_max": POST_BODY_MAX_LENGTH,
    }
    return render(request, "admin_posts.html", context)


@router.post("/admin/posts")
def admin_posts_create(
    request: Request,
    csrf_token: str = Form(...),
    title: str = Form(...),
    body: str = Form(...),
):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    title = title.strip()
    body = body.strip()
    if not title or not body:
        return RedirectResponse(url="/admin/posts?error=empty", status_code=303)
    if len(title) > POST_TITLE_MAX_LENGTH or len(body) > POST_BODY_MAX_LENGTH:
        # We don't truncate the HTML at the limit (could split a tag in
        # half and leave broken markup) — instead, ask the person to
        # shorten it and resubmit.
        return RedirectResponse(url="/admin/posts?error=too_long", status_code=303)

    # The editor (app/static/js/post-editor.js) sends raw HTML — only
    # what's on the allowlist gets passed through from here on (see
    # app/richtext.py); any <script>/onclick/etc is stripped, not
    # escaped (the templates use {{ post.body | safe }}).
    body = sanitize_post_body(body)
    if not body.strip():
        return RedirectResponse(url="/admin/posts?error=empty", status_code=303)

    execute_returning(
        "INSERT INTO posts (author_id, title, body) VALUES (:author_id, :title, :body) RETURNING id",
        {"author_id": admin["id"], "title": title, "body": body},
    )
    return RedirectResponse(url="/admin/posts?created=1", status_code=303)


@router.post("/admin/posts/upload-image")
async def admin_posts_upload_image(request: Request, image: UploadFile = File(...)):
    """
    Called by the editor's image button (app/static/js/post-editor.js,
    via fetch/FormData) — returns {"url": "/post-images/..."} to
    insert into the text, or 400 if the file isn't a valid image.
    Requires the same CSRF token as any other POST (sent in the
    X-CSRF-Token header, since this is a fetch() call and not a
    regular <form>).
    """
    admin = require_admin(request)
    if not admin:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    verify_csrf(request, request.headers.get("x-csrf-token", ""))

    url = await save_post_image(image)
    if not url:
        return JSONResponse({"error": "invalid_image"}, status_code=400)
    return JSONResponse({"url": url})


@router.post("/admin/posts/{post_id}/toggle-publish")
def admin_posts_toggle_publish(request: Request, post_id: int, csrf_token: str = Form(...)):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    execute("UPDATE posts SET is_published = NOT is_published WHERE id = :id", {"id": post_id})
    return RedirectResponse(url="/admin/posts", status_code=303)


@router.post("/admin/posts/{post_id}/delete")
def admin_posts_delete(request: Request, post_id: int, csrf_token: str = Form(...)):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    verify_csrf(request, csrf_token)

    execute("DELETE FROM posts WHERE id = :id", {"id": post_id})
    return RedirectResponse(url="/admin/posts", status_code=303)

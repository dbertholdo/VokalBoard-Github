"""Visit beacon + Red Zone bot-traffic page (2026-09-28; rules in app/traffic.py)."""
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.client_ip import get_client_ip
from app.i18n import DEFAULT_LANGUAGE
from app.permissions import LEVEL_GOD, require_level
from app.render import render
from app.traffic import bot_name, bot_traffic_summary, record_bot_hit, record_human_visit

router = APIRouter()


@router.post("/visit")
def visit_beacon(request: Request, r: str = Form("")):
    """Sent by every normal page (see base.html). No CSRF token: it only ever
    adds one anonymous count, at most once per visitor / 12 h (app/traffic.py)."""
    name = bot_name(request.headers.get("user-agent"))
    if name:
        record_bot_hit(name)  # headless browsers run JS too
    else:
        record_human_visit(
            get_client_ip(request), request.headers.get("user-agent", ""),
            request.cookies.get("lang", DEFAULT_LANGUAGE), r[:500], request.url.netloc,
            bool(request.session.get("user_id")),
        )
    return Response(status_code=204)


@router.get("/financeiro/bots", response_class=HTMLResponse)
def bot_traffic_page(request: Request, days: int = 30):
    admin = require_level(request, LEVEL_GOD)
    if not admin:
        return RedirectResponse(url="/", status_code=303)
    days = days if days in (7, 30, 90) else 30
    return render(request, "admin_bot_traffic.html", {"user": admin, "days": days, **bot_traffic_summary(days)})

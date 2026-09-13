"""
Páginas "estáticas" de conteúdo legal/institucional: Impressum e
Código de Conduta. Não dependem de login nem de banco de dados —
só texto renderizado a partir dos templates.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.auth import get_current_user
from app.render import render

router = APIRouter()


@router.get("/impressum", response_class=HTMLResponse)
def impressum(request: Request):
    return render(request, "impressum.html", {"user": get_current_user(request)})


@router.get("/datenschutz", response_class=HTMLResponse)
def datenschutz(request: Request):
    return render(request, "datenschutz.html", {"user": get_current_user(request)})


@router.get("/code-of-conduct", response_class=HTMLResponse)
def code_of_conduct(request: Request):
    return render(request, "code_of_conduct.html", {"user": get_current_user(request)})

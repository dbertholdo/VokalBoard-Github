"""
Proteção CSRF (Cross-Site Request Forgery) — implementação manual e
simples do padrão "synchronizer token", sem depender de bibliotecas
externas, pra você ver exatamente como funciona.

A ideia, resumida:
1. Quando a pessoa carrega uma página com um formulário, geramos um
   token aleatório e guardamos ele na sessão dela (cookie assinado).
2. O mesmo token vai escondido dentro do formulário (<input type="hidden">).
3. Quando o formulário é enviado (POST), comparamos o token que veio
   no formulário com o que está guardado na sessão. Só deixamos a ação
   acontecer se os dois baterem.

Por que isso importa: um cookie de sessão sozinho NÃO prova que foi
você quem clicou o botão — o navegador manda cookies automaticamente
em qualquer requisição pro domínio, inclusive uma disparada por um
site malicioso em outra aba (ex: um <form> escondido em outro site que
envia POST pra "seuapp.com/listings/5/delete"). Como o token CSRF só
existe dentro do HTML da sua própria página (o site malicioso não tem
como ler ou adivinhar esse valor), ele funciona como uma prova de que
o formulário realmente veio do seu site.
"""
import secrets

from fastapi import Request, HTTPException

SESSION_KEY = "csrf_token"


def get_or_create_csrf_token(request: Request) -> str:
    token = request.session.get(SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[SESSION_KEY] = token
    return token


def verify_csrf(request: Request, submitted_token: str) -> None:
    """Levanta um erro 400 se o token não bater. Chame no início de todo POST."""
    expected = request.session.get(SESSION_KEY)
    if not expected or not submitted_token or not secrets.compare_digest(expected, submitted_token):
        raise HTTPException(status_code=400, detail="Invalid or missing CSRF token. Please reload the page and try again.")

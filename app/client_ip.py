"""
Descobrir o IP de quem está fazendo a requisição.

Por trás de uma plataforma como Railway (ou qualquer proxy reverso),
`request.client.host` é o IP do PRÓPRIO proxy, não da pessoa de
verdade — o IP real vem no cabeçalho `X-Forwarded-For`, que o proxy
adiciona. Usado só pelo freio de cadastro em massa (ver
app/register_throttle.py); NUNCA é guardado permanentemente em lugar
nenhum, só comparado num contador temporário.
"""
from fastapi import Request


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        # O cabeçalho pode ter uma lista "cliente, proxy1, proxy2" —
        # o primeiro da lista é sempre o mais próximo do navegador.
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

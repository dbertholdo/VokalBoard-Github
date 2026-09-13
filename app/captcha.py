"""
Proteção anti-bot em duas camadas, seguindo o mesmo padrão de "backend
plugável" já usado em app/email.py (console vs. Resend):

1. Honeypot (sempre ativo, ZERO configuração): um campo a mais no
   formulário (ver HONEYPOT_FIELD), escondido via CSS fora da tela
   (não display:none — leitores de tela ignoram melhor um campo
   "off-screen" que ainda existe no DOM, mas continua invisível pra
   qualquer humano de verdade). Bots simples preenchem TODOS os
   campos de um formulário automaticamente, então se esse campo vier
   preenchido, é quase certeza que foi um bot. Isso sozinho já barra
   a maioria dos bots genéricos, sem precisar de nenhuma chave/serviço
   externo.

2. Cloudflare Turnstile (opcional, precisa de chaves suas): um
   desafio "quase invisível" (normalmente nem pede clique) que
   confirma que quem está enviando é humano, sem os problemas de
   privacidade do reCAPTCHA do Google (não usa cookies de rastreio
   entre sites). Só liga se você configurar TURNSTILE_SITE_KEY e
   TURNSTILE_SECRET_KEY no .env (ver .env.example) — sem isso, o site
   segue protegido só pelo honeypot, o que já é uma barreira real
   contra o caso mais comum (bots genéricos, não gente tentando
   especificamente abusar do seu site).

Como conseguir as chaves do Turnstile (grátis): crie uma conta em
https://dash.cloudflare.com/ (não precisa migrar seu domínio pra lá,
o Turnstile funciona à parte) → Turnstile → Add site → copie o "Site
Key" (público, vai no HTML) e o "Secret Key" (privado, só no .env).
"""
import os
import httpx

# Nome do campo-armadilha. Deliberadamente um nome "tentador" pra
# autofill/bots (parece um campo de verdade) — ver o CSS
# ".honeypot-field" em style.css que o esconde de humanos.
HONEYPOT_FIELD = "website"

TURNSTILE_SITE_KEY = os.getenv("TURNSTILE_SITE_KEY", "")
TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY", "")
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def captcha_enabled() -> bool:
    """True só quando as duas chaves do Turnstile estão configuradas."""
    return bool(TURNSTILE_SITE_KEY and TURNSTILE_SECRET_KEY)


def is_bot(honeypot_value: str) -> bool:
    """Honeypot preenchido = quase certeza de bot. Checado sempre, com ou sem Turnstile."""
    return bool((honeypot_value or "").strip())


def verify_turnstile(token: str) -> bool:
    """
    Verifica o token do widget do Turnstile com a Cloudflare.

    Se o Turnstile não estiver configurado (sem as duas chaves), não
    bloqueia ninguém — o honeypot sozinho segue sendo a proteção
    nesse caso, pra não travar o cadastro de quem está só rodando o
    projeto localmente sem ter configurado nada extra.
    """
    if not captcha_enabled():
        return True
    if not token:
        return False
    try:
        resp = httpx.post(
            TURNSTILE_VERIFY_URL,
            data={"secret": TURNSTILE_SECRET_KEY, "response": token},
            timeout=5.0,
        )
        return bool(resp.json().get("success"))
    except Exception:
        # Cloudflare fora do ar não deveria travar o cadastro/reset de
        # senha de ninguém — deixa passar (o honeypot continua ativo).
        return True

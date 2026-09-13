"""
Envio de e-mail, com dois "backends" trocáveis por variável de ambiente:

- EMAIL_BACKEND=console (padrão): não envia nada de verdade, só imprime
  o conteúdo do e-mail no terminal/log. Perfeito pra desenvolver e
  testar localmente sem precisar de credenciais de verdade — o link de
  verificação/recuperação de senha aparece direto no log do servidor.
- EMAIL_BACKEND=resend: envia de verdade via API da Resend
  (https://resend.com), que tem camada gratuita para baixo volume.
  Defina RESEND_API_KEY e EMAIL_FROM no .env quando for usar.

Trocar de provedor de e-mail no futuro (Postmark, SendGrid, etc.) é só
adicionar mais um `elif` aqui — o resto da aplicação chama sempre a
mesma função `send_email()` e nem sabe qual backend está ativo.
"""
import os

import httpx

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "console")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "VokalBoard <onboarding@resend.dev>")


def send_email(to: str, subject: str, html: str) -> None:
    if EMAIL_BACKEND == "resend" and RESEND_API_KEY:
        try:
            httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={"from": EMAIL_FROM, "to": [to], "subject": subject, "html": html},
                timeout=10,
            )
        except httpx.HTTPError as exc:
            # Não derruba a requisição do usuário por causa de um problema no envio de e-mail.
            print(f"[email] falha ao enviar via Resend: {exc}")
    else:
        print(
            "\n---- EMAIL (console backend — configure EMAIL_BACKEND=resend para enviar de verdade) ----\n"
            f"Para: {to}\nAssunto: {subject}\n\n{html}\n"
            "-------------------------------------------------------------------------------------\n"
        )

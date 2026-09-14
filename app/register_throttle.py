"""
Freio contra criação em massa de contas falsas por script — por IP,
bem mais suave que o bloqueio de login (ver app/login_throttle.py) de
propósito: aqui uma rede compartilhada (várias pessoas no mesmo Wi-Fi
de faculdade, escritório, operadora de celular com NAT) é comum e não
deveria travar cadastro de gente de verdade.

Regra: no máximo MAX_REGISTRATIONS_PER_WINDOW contas criadas pelo
mesmo IP dentro de WINDOW_MINUTES — depois disso, pede pra esperar a
janela passar (ela reseta sozinha, sem ficar bloqueado "pra sempre").

Importante: isso só entra em ação no PASSO FINAL de /register (conta
criada com sucesso). NUNCA afeta login, reenvio de e-mail de
verificação ou redefinição de senha — ninguém fica impedido de entrar
na própria conta ou recuperar o acesso por causa disso.
"""
from datetime import datetime, timedelta, timezone

from app.database import fetch_one, execute

MAX_REGISTRATIONS_PER_WINDOW = 5
WINDOW_MINUTES = 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_registration_throttled(ip_address: str) -> bool:
    """True se esse IP já criou contas demais na janela atual."""
    row = fetch_one(
        "SELECT attempt_count, window_started_at FROM registration_attempts WHERE ip_address = :ip",
        {"ip": ip_address},
    )
    if not row:
        return False

    window_expired = (_now() - row["window_started_at"]) > timedelta(minutes=WINDOW_MINUTES)
    if window_expired:
        return False

    return row["attempt_count"] >= MAX_REGISTRATIONS_PER_WINDOW


def record_registration(ip_address: str) -> None:
    """Chamado só depois que uma conta É CRIADA com sucesso — soma 1 ao contador da janela atual."""
    row = fetch_one(
        "SELECT attempt_count, window_started_at FROM registration_attempts WHERE ip_address = :ip",
        {"ip": ip_address},
    )

    window_expired = row and (_now() - row["window_started_at"]) > timedelta(minutes=WINDOW_MINUTES)

    if not row or window_expired:
        execute(
            """
            INSERT INTO registration_attempts (ip_address, attempt_count, window_started_at)
            VALUES (:ip, 1, now())
            ON CONFLICT (ip_address) DO UPDATE SET attempt_count = 1, window_started_at = now()
            """,
            {"ip": ip_address},
        )
    else:
        execute(
            "UPDATE registration_attempts SET attempt_count = attempt_count + 1 WHERE ip_address = :ip",
            {"ip": ip_address},
        )

"""
Bloqueio progressivo de tentativas de login (proteção contra ataque de
força bruta), guardado na tabela login_lockouts (ver db/schema.sql).

Regra: 5 tentativas de senha erradas seguidas -> bloqueia o login
daquele e-mail por 5 minutos. Se a pessoa errar de novo depois que o
bloqueio acabar, o próximo é de 10 minutos; depois 1 hora; depois 24
horas — e fica em 24h se continuar errando além disso. Acertar a senha
zera tudo (a linha é apagada, volta pro estágio inicial).

Guardado por e-mail (não por user_id) de propósito: assim o bloqueio
também vale pra tentativas contra um e-mail que nem tem conta aqui,
sem dar nenhuma pista a mais pra quem está tentando adivinhar se
aquele e-mail está cadastrado ou não.
"""
from datetime import datetime, timedelta, timezone

from app.database import fetch_one, execute

MAX_ATTEMPTS_PER_STAGE = 5

# Duração de cada bloqueio, em minutos, por estágio (0 = primeiro
# bloqueio que a pessoa leva, 1 = segundo, ...). Fica travado no
# último valor da lista se continuar errando além disso.
LOCKOUT_MINUTES_BY_STAGE = [5, 10, 60, 60 * 24]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def check_lockout(email: str) -> int | None:
    """
    Devolve quantos segundos ainda faltam pro bloqueio acabar, ou None
    se esse e-mail não estiver bloqueado no momento (nunca visto antes,
    ou o bloqueio anterior já expirou).
    """
    row = fetch_one("SELECT locked_until FROM login_lockouts WHERE email = :email", {"email": email})
    if not row or not row["locked_until"]:
        return None

    remaining = (row["locked_until"] - _now()).total_seconds()
    return int(remaining) if remaining > 0 else None


def record_failure(email: str) -> None:
    """
    Registra uma tentativa de senha errada. Se essa tentativa completar
    o limite do estágio atual (MAX_ATTEMPTS_PER_STAGE), ativa o
    bloqueio com a duração daquele estágio e avança pro próximo (mais
    longo, até o teto de LOCKOUT_MINUTES_BY_STAGE).
    """
    row = fetch_one(
        "SELECT failed_count, stage FROM login_lockouts WHERE email = :email", {"email": email}
    )
    failed_count = (row["failed_count"] if row else 0) + 1
    stage = row["stage"] if row else 0

    locked_until = None
    if failed_count >= MAX_ATTEMPTS_PER_STAGE:
        stage_index = min(stage, len(LOCKOUT_MINUTES_BY_STAGE) - 1)
        locked_until = _now() + timedelta(minutes=LOCKOUT_MINUTES_BY_STAGE[stage_index])
        stage = min(stage + 1, len(LOCKOUT_MINUTES_BY_STAGE) - 1)
        failed_count = 0

    execute(
        """
        INSERT INTO login_lockouts (email, failed_count, stage, locked_until, updated_at)
        VALUES (:email, :failed_count, :stage, :locked_until, now())
        ON CONFLICT (email) DO UPDATE SET
            failed_count = :failed_count,
            stage = :stage,
            locked_until = :locked_until,
            updated_at = now()
        """,
        {"email": email, "failed_count": failed_count, "stage": stage, "locked_until": locked_until},
    )


def reset(email: str) -> None:
    """Zera o histórico de tentativas — chamado quando o login dá certo."""
    execute("DELETE FROM login_lockouts WHERE email = :email", {"email": email})

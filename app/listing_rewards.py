"""
Recompensa por publicar vaga — P5 Etapa 1 (18/09/2026), REDESENHADA
19/09/2026 (Part 2 backlog, item 2 — decisões tomadas com o Daniel via
AskUserQuestion nesta sessão).

Histórico: a primeira versão (18/09/2026) creditava 0,50 Nota na hora,
pra qualquer `listing_type`, via `background_tasks.add_task(...)` logo
após a publicação — nenhuma espera, só o teto semanal como antifraude.
Isso foi substituído por este desenho mais forte:

  - **Valor por tipo:** 0,50 Nota pra vaga de verdade (`seeking_singer`/
    `seeking_conductor` — "alguém precisa de um artista"), 0,10 Nota pra
    autoanúncio de disponibilidade (`singer_available`/
    `conductor_available` — mais fácil de publicar sem custo real, por
    isso o valor menor).
  - **Teto semanal:** 3 recompensas por semana por pessoa, ÚNICO
    (somado entre os 4 tipos, não um teto por tipo).
  - **Tempo mínimo ativo:** a vaga precisa ficar publicada (ativa, não
    arquivada/apagada/desativada) por 48 horas antes da recompensa —
    evita postar-e-apagar em massa só pra acumular Notas. EXCEÇÃO: uma
    vaga marcada como urgente (Zona de Alerta) não espera as 48h —
    ainda conta pro teto semanal, só não pelo tempo mínimo (decisão do
    Daniel: urgência é genuína, não devia competir com antifraude de
    farming).

Por causa do tempo mínimo, a recompensa não é mais instantânea — vira
trabalho do `app/listing_reward_worker.py` (7º worker do site), que
roda de hora em hora como os outros: acha vagas elegíveis (ainda
ativas, ainda não recompensadas, urgentes OU criadas há 48h+) e
credita. `listings_routes.py` NÃO chama mais nada daqui diretamente na
publicação — só o worker credita, de forma assíncrona por natureza
(uma vaga marcada urgente na hora da criação é pega no próximo ciclo
do worker, não instantaneamente — mesma cadência de 1h dos outros 6
workers do site).
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import text

from app.notas_wallet import count_credits_since, credit_notas

JOB_LISTING_TYPES = {"seeking_singer", "seeking_conductor"}
SELF_AD_LISTING_TYPES = {"singer_available", "conductor_available"}

JOB_POSTING_REWARD = Decimal("0.50")
SELF_AD_REWARD = Decimal("0.10")

LISTING_POSTED_WEEKLY_CAP = 3
MIN_ACTIVE_HOURS_BEFORE_REWARD = 48

_REASON = "listing_posted"


def reward_amount_for(listing_type: str) -> Decimal | None:
    """Nota value for this listing_type, or None if this type never
    earns the reward (defensive — every current listing_type is one of
    the two sets above, but a future new type falls through safely
    here instead of crediting an undefined amount)."""
    if listing_type in JOB_LISTING_TYPES:
        return JOB_POSTING_REWARD
    if listing_type in SELF_AD_LISTING_TYPES:
        return SELF_AD_REWARD
    return None


def find_reward_eligible_listings(conn) -> list:
    """Listings that: are still up (active, not archived/soft-deleted),
    haven't already been rewarded (no matching idempotency_key in
    credit_ledger), and are either urgent (no wait) or old enough
    (MIN_ACTIVE_HOURS_BEFORE_REWARD have passed since creation)."""
    rows = conn.execute(
        text(
            f"""
            SELECT l.id, l.author_id, l.listing_type
            FROM listings l
            WHERE l.is_active = TRUE AND l.deleted_at IS NULL AND l.archived_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM credit_ledger cl
                  WHERE cl.idempotency_key = 'listing_posted:' || l.id
              )
              AND (l.is_urgent = TRUE OR l.created_at <= now() - interval '{MIN_ACTIVE_HOURS_BEFORE_REWARD} hours')
            ORDER BY l.created_at
            """
        )
    ).mappings().all()
    return list(rows)


def award_listing_posted_reward(user_id: int, listing_id: int, listing_type: str) -> bool:
    """
    Credita a Nota certa pra esse tipo de anúncio, respeitando o teto
    semanal (soma os 4 tipos). Retorna False sem creditar nada se o
    tipo não é elegível (reward_amount_for retorna None) ou se o teto
    já foi atingido — nunca levanta erro, pra nunca quebrar o chamador
    (o worker) por causa de uma única recompensa que não deu certo.

    `idempotency_key=f"listing_posted:{listing_id}"` garante que a
    MESMA vaga nunca credita duas vezes, mesmo se o worker rodar de
    novo antes do próximo ciclo (crash/restart) — e é também o que
    `find_reward_eligible_listings()` usa pra não devolver a mesma vaga
    outra vez.
    """
    amount = reward_amount_for(listing_type)
    if amount is None:
        return False

    since = datetime.now(timezone.utc) - timedelta(days=7)
    already_this_week = count_credits_since(user_id, _REASON, since)
    if already_this_week >= LISTING_POSTED_WEEKLY_CAP:
        return False

    return credit_notas(
        user_id, amount, _REASON,
        reference_id=listing_id, idempotency_key=f"{_REASON}:{listing_id}",
    )

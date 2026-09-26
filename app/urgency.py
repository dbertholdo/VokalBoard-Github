"""
Sistema de Urgência — P5 Etapa 2 (18/09/2026).

Decisões confirmadas com o Daniel (17/09 e reconfirmadas 18/09/2026):
- Cada pessoa recebe 1 token de urgência GRÁTIS por semana — não
  acumula (se não usar, não soma pra semana seguinte).
- Com 0 tokens, dá pra "comprar urgência" pagando o equivalente a 2
  Euros em Notas (1 Nota ~ 1 Euro/Franco, ver CLAUDE.md Seção 1) — ou
  seja, 2 Notas.
- Vale só pra vagas do tipo seeking_singer/seeking_conductor (ver
  URGENCY_ELIGIBLE_LISTING_TYPES em app/routers/listings_routes.py) —
  quem publica um autoanúncio de disponibilidade não tem "vaga" pra
  marcar como urgente.
- Marcar como urgente pode acontecer no formulário de criação OU
  depois, via botão — as duas chamam mark_listing_urgent() abaixo.
- Recompensa de conclusão: 0,50 Nota (metade do "preço cheio" de 1
  Nota) pra quem publicou, quando o Match acontece pela plataforma —
  ver app/match_service.py (fica lá, não aqui, porque precisa estar
  na MESMA transação que cria o Match).
"""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import text

from app.database import engine, fetch_one
from app.notas_wallet import debit_in_tx

URGENCY_PURCHASE_COST_NOTAS = Decimal("2")
URGENCY_MATCH_REWARD_NOTAS = Decimal("0.50")
FREE_TOKENS_PER_WEEK = 1


class UrgencyUnavailable(Exception):
    """Sem token grátis e sem saldo de Notas suficiente pra comprar."""


class ListingNotEligible(Exception):
    """A vaga não existe, não é do usuário, já é urgente, ou o tipo não é elegível."""


def _week_start(today: date | None = None) -> date:
    """Segunda-feira (ISO) da semana de `today` — a "janela" que o
    token grátis usa pra não acumular de uma semana pra outra."""
    today = today or date.today()
    return today - timedelta(days=today.weekday())


def get_urgency_status(user_id: int, today: date | None = None) -> dict:
    """Pro badge/aviso na UI: quantos tokens grátis sobraram essa
    semana (0 ou 1) e qual o custo em Notas se precisar comprar."""
    week = _week_start(today)
    row = fetch_one(
        "SELECT free_used FROM urgency_weekly_usage WHERE user_id = :uid AND usage_week = :week",
        {"uid": user_id, "week": week},
    )
    free_used = row["free_used"] if row else 0
    return {
        "free_tokens_left": max(0, FREE_TOKENS_PER_WEEK - free_used),
        "purchase_cost_notas": URGENCY_PURCHASE_COST_NOTAS,
    }


def mark_listing_urgent(user_id: int, listing_id: int, today: date | None = None) -> str:
    """
    Marca a vaga como urgente, consumindo o token grátis da semana se
    disponível, ou debitando URGENCY_PURCHASE_COST_NOTAS Notas caso
    contrário. Retorna "free" ou "purchased".

    Levanta ListingNotEligible (vaga não é sua / tipo errado / já
    urgente) ou UrgencyUnavailable (sem token e sem saldo).

    Tudo numa única transação — trava a linha da vaga primeiro (evita
    marcar a mesma vaga urgente duas vezes em paralelo), depois decide
    token-grátis-ou-compra e já atualiza a vaga, sem deixar nenhum
    estado parcial (nunca "Notas debitadas mas vaga não marcada").
    """
    week = _week_start(today)
    with engine.begin() as conn:
        listing = conn.execute(
            text("SELECT id, author_id, listing_type, is_urgent FROM listings WHERE id = :id FOR UPDATE"),
            {"id": listing_id},
        ).mappings().first()
        if not listing or listing["author_id"] != user_id:
            raise ListingNotEligible("not_found_or_not_owner")
        if listing["listing_type"] not in ("seeking_singer", "seeking_conductor"):
            raise ListingNotEligible("wrong_listing_type")
        if listing["is_urgent"]:
            raise ListingNotEligible("already_urgent")

        conn.execute(
            text(
                "INSERT INTO urgency_weekly_usage (user_id, usage_week, free_used) "
                "VALUES (:uid, :week, 0) ON CONFLICT (user_id, usage_week) DO NOTHING"
            ),
            {"uid": user_id, "week": week},
        )
        free_used = conn.execute(
            text(
                "UPDATE urgency_weekly_usage SET free_used = free_used + 1 "
                "WHERE user_id = :uid AND usage_week = :week AND free_used < :cap "
                "RETURNING free_used"
            ),
            {"uid": user_id, "week": week, "cap": FREE_TOKENS_PER_WEEK},
        ).scalar_one_or_none()

        if free_used is not None:
            result = "free"
        else:
            # Notas v2: spend order (purchased first) + lot tracking live in the wallet.
            if not debit_in_tx(conn, user_id, URGENCY_PURCHASE_COST_NOTAS, "urgency_purchase", reference_id=listing_id):
                raise UrgencyUnavailable("insufficient_balance")
            result = "purchased"

        conn.execute(
            text("UPDATE listings SET is_urgent = TRUE, urgent_marked_at = now() WHERE id = :id"),
            {"id": listing_id},
        )
    return result

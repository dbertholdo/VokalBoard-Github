"""
P3.F: avaliação pós-Match, 5 categorias (1-5 estrelas cada), mútua.

SECRETO por decisão do Daniel (18/09/2026): "igual Uber, ninguém vê quem
avaliou e como". Este módulo nunca retorna uma linha de `match_evaluations`
individualmente — só médias agregadas por categoria (get_quality_tiers).
Nenhuma rota deve fazer SELECT direto em `match_evaluations` fora daqui.

Progressão de selo "estilo Uber": o tier NUNCA é armazenado, é sempre a
média CORRENTE de todas as avaliações recebidas naquela categoria — pode
subir ou descer com o tempo, diferente dos badges de marco (app/badges.py)
que só sobem, uma vez desbloqueados. Por isso este módulo é separado de
app/badges.py: aquele é público (perfil público), este é sempre privado
(só o próprio dono e o Admin, nunca `public_profile.html`).
"""
from datetime import date, timedelta
from app.database import fetch_all, fetch_one, execute

EVALUATION_WINDOW_DAYS = 14

# Nomes finais confirmados em 18/09/2026 — coluna do banco : chave de
# i18n do rótulo (ver app/i18n.py, prefixo "eval_category_").
CATEGORIES = {
    "punctuality": "eval_category_punctuality",       # Pünktlichkeit
    "preparation": "eval_category_preparation",         # Vorbereitung
    "musicality": "eval_category_musicality",           # Musikalität
    "communication": "eval_category_communication",     # Professionelle Kommunikation
    "collaboration": "eval_category_collaboration",     # Angenehme Zusammenarbeit
}

# Mínimo de avaliações recebidas antes de mostrar qualquer tier naquela
# categoria (evita expor um selo baseado numa única nota) — número
# sugerido pelo Claude, não conferido dígito a dígito com o Daniel, só o
# modelo geral ("estilo Uber", média corrente) foi confirmado.
MIN_EVALUATIONS_FOR_TIER = 3

# Cortes da média corrente — do mais alto pro mais baixo, primeiro que
# bater vale (ver _tier_for_average). "bronze" é o piso, uma vez que o
# mínimo de avaliações foi atingido.
TIER_CUTOFFS = [
    (4.5, "platinum"),
    (4.0, "gold"),
    (3.5, "silver"),
]
DEFAULT_TIER = "bronze"


def _tier_for_average(avg: float) -> str:
    for cutoff, tier in TIER_CUTOFFS:
        if avg >= cutoff:
            return tier
    return DEFAULT_TIER


def evaluation_window(event_date) -> tuple[date, date]:
    """A janela abre no dia do evento (já aconteceu) e fica disponível
    por exatamente 14 dias depois — sub-aba de "Meus Matches"."""
    opens_at = event_date
    closes_at = event_date + timedelta(days=EVALUATION_WINDOW_DAYS)
    return opens_at, closes_at


def can_evaluate(status: str, event_date, today: date | None = None) -> bool:
    """Match não cancelado, evento já aconteceu, dentro dos 14 dias."""
    if status == "cancelled" or not event_date:
        return False
    today = today or date.today()
    opens_at, closes_at = evaluation_window(event_date)
    return opens_at <= today <= closes_at


def get_my_evaluation(match_id: int, rater_id: int) -> dict | None:
    """A própria avaliação que ESTE usuário deu nesse Match (pra
    pré-preencher o formulário se ele quiser revisar) — nunca a do outro
    lado."""
    return fetch_one(
        """
        SELECT punctuality, preparation, musicality, communication, collaboration
        FROM match_evaluations
        WHERE match_id = :match_id AND rater_id = :rater_id
        """,
        {"match_id": match_id, "rater_id": rater_id},
    )


def submit_evaluation(match_id: int, rater_id: int, rated_id: int, scores: dict) -> None:
    """Cria ou atualiza (upsert) a avaliação deste rater pra este match —
    permite revisar enquanto a janela de 14 dias ainda está aberta. O
    chamador (rota) já deve ter validado can_evaluate() e que rater_id/
    rated_id são de fato os dois lados do Match."""
    for key in CATEGORIES:
        value = scores.get(key)
        if not isinstance(value, int) or not (1 <= value <= 5):
            raise ValueError(f"invalid score for {key}")
    execute(
        """
        INSERT INTO match_evaluations (match_id, rater_id, rated_id, punctuality, preparation, musicality, communication, collaboration)
        VALUES (:match_id, :rater_id, :rated_id, :punctuality, :preparation, :musicality, :communication, :collaboration)
        ON CONFLICT (match_id, rater_id) DO UPDATE
        SET punctuality = EXCLUDED.punctuality, preparation = EXCLUDED.preparation,
            musicality = EXCLUDED.musicality, communication = EXCLUDED.communication,
            collaboration = EXCLUDED.collaboration, updated_at = now()
        """,
        {
            "match_id": match_id, "rater_id": rater_id, "rated_id": rated_id,
            **{key: scores[key] for key in CATEGORIES},
        },
    )


def get_quality_tiers(user_id: int) -> dict:
    """Selos privados de qualidade deste usuário — SÓ agregado (contagem
    + média corrente + tier por categoria), nunca uma linha individual.
    Só deve ser chamado pra mostrar pro próprio dono do perfil ou pro
    Admin — nunca em public_profile.html."""
    row = fetch_one(
        """
        SELECT
            COUNT(*) AS n,
            AVG(punctuality) AS avg_punctuality,
            AVG(preparation) AS avg_preparation,
            AVG(musicality) AS avg_musicality,
            AVG(communication) AS avg_communication,
            AVG(collaboration) AS avg_collaboration
        FROM match_evaluations
        WHERE rated_id = :user_id
        """,
        {"user_id": user_id},
    )
    result = {}
    for key in CATEGORIES:
        avg = row[f"avg_{key}"] if row else None
        count = row["n"] if row else 0
        if not count or count < MIN_EVALUATIONS_FOR_TIER or avg is None:
            result[key] = {"count": count or 0, "average": None, "tier": None}
        else:
            result[key] = {"count": count, "average": round(float(avg), 2), "tier": _tier_for_average(float(avg))}
    return result


def get_pending_evaluations(user_id: int, today: date | None = None) -> list[dict]:
    """Matches deste usuário, dentro da janela de 14 dias, que ELE ainda
    não avaliou o outro lado — usado pro badge de navegação e pelo
    worker de lembrete (app/match_evaluation_reminder_worker.py)."""
    today = today or date.today()
    rows = fetch_all(
        """
        SELECT m.id AS match_id, m.artist_user_id, m.contractor_user_id, m.status,
               l.event_date, l.title AS listing_title
        FROM job_matches m
        JOIN listings l ON l.id = m.listing_id
        WHERE (m.artist_user_id = :user_id OR m.contractor_user_id = :user_id)
          AND m.status != 'cancelled'
          AND l.event_date IS NOT NULL
          AND l.event_date <= :today
          AND l.event_date >= :window_start
          AND NOT EXISTS (
              SELECT 1 FROM match_evaluations me
              WHERE me.match_id = m.id AND me.rater_id = :user_id
          )
        """,
        {"user_id": user_id, "today": today, "window_start": today - timedelta(days=EVALUATION_WINDOW_DAYS)},
    )
    pending = []
    for row in rows:
        is_artist = row["artist_user_id"] == user_id
        pending.append({
            "match_id": row["match_id"],
            "listing_title": row["listing_title"],
            "rated_id": row["contractor_user_id"] if is_artist else row["artist_user_id"],
        })
    return pending

"""Contador simples de uso de ferramentas do site (Admin > "Ferramentas
mais usadas" — pedido do Daniel, 18/09/2026, junto com a Etapa 3 do P4:
"quero que haja uma forma de trackear quais ferramentas do site são mais
usadas. E isso inclui Rechnung maker.").

Deliberadamente genérico — qualquer parte do site pode chamar
`record_feature_usage("uma_chave")` pra contar um uso; não é específico
do Rechnungmaker, só é o primeiro a usar. Contagem MENSAL (mesmo padrão
de `invoice_monthly_usage` em app/invoice_service.py) pra dar ao Admin
uma noção de tendência, não só um total acumulado desde sempre.
"""
from datetime import date

from sqlalchemy import text

from app.database import engine, fetch_all

# Rótulo de exibição pro Admin — uma chave sem entrada aqui aparece com
# o próprio key (com "_" virando espaço, capitalizado), então uma
# feature nova já funciona mesmo sem atualizar este dicionário.
FEATURE_LABELS = {
    "rechnungmaker": "Rechnungmaker",
}


def record_feature_usage(feature_key: str, when: date | None = None) -> None:
    when = when or date.today()
    usage_month = when.replace(day=1)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO feature_usage_monthly (feature_key, usage_month, count)
                VALUES (:feature_key, :usage_month, 1)
                ON CONFLICT (feature_key, usage_month) DO UPDATE
                SET count = feature_usage_monthly.count + 1
                """
            ),
            {"feature_key": feature_key, "usage_month": usage_month},
        )


def get_feature_usage_totals() -> list[dict]:
    """Pro Admin: total histórico + uso do mês corrente, por ferramenta,
    da mais usada pra menos usada. Uma única query agregada (nunca um
    SELECT por ferramenta num loop — ver CLAUDE.md Seção 4.2)."""
    current_month = date.today().replace(day=1)
    rows = fetch_all(
        """
        SELECT feature_key, SUM(count) AS total,
               COALESCE(SUM(count) FILTER (WHERE usage_month = :current_month), 0) AS this_month
        FROM feature_usage_monthly
        GROUP BY feature_key
        ORDER BY total DESC, feature_key ASC
        """,
        {"current_month": current_month},
    )
    return [
        {
            "key": row["feature_key"],
            "label": FEATURE_LABELS.get(row["feature_key"], row["feature_key"].replace("_", " ").title()),
            "total": row["total"],
            "this_month": row["this_month"],
        }
        for row in rows
    ]

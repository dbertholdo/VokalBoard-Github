"""
Apaga DEFINITIVAMENTE contas que foram excluídas (soft delete,
`users.deleted_at` preenchido) há mais de 6 meses.

Por que um script separado, e não um job dentro do app?
---------------------------------------------------------
O resto do projeto evita propositalmente qualquer job/cron rodando
*dentro* do próprio app (ver EVENT_STATUS_SQL e o arquivamento de
eventos passados em app/routers/listings_routes.py, que preferem
calcular tudo "na consulta" em vez de um worker em background). Uma
exclusão definitiva de dados é uma operação sensível demais pra
deixar presa a um processo de longa duração dentro do FastAPI — é
mais simples, mais seguro e mais fácil de auditar rodar isso como um
script avulso, disparado de fora (cron do sistema operacional, ou
manualmente).

Como agendar (exemplo com cron do Linux, 1x por dia às 4h):
    0 4 * * * cd /caminho/do/projeto && ./venv/bin/python scripts/purge_deleted_accounts.py >> /var/log/maestro_purge.log 2>&1

Uso manual:
    python scripts/purge_deleted_accounts.py           # apaga de verdade
    python scripts/purge_deleted_accounts.py --dry-run # só mostra quem seria apagado
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

# Garante que "app" (o pacote do projeto) seja encontrado mesmo rodando
# este script de dentro de scripts/ (ex: `python scripts/purge_deleted_accounts.py`).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import fetch_all, execute

RETENTION_MONTHS = 6


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Só lista quem seria apagado, sem apagar de verdade.",
    )
    args = parser.parse_args()

    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_MONTHS * 30)

    candidates = fetch_all(
        "SELECT id, email, full_name, deleted_at FROM users WHERE deleted_at IS NOT NULL AND deleted_at < :cutoff",
        {"cutoff": cutoff},
    )

    if not candidates:
        print("Nenhuma conta passou dos 6 meses de exclusão. Nada a fazer.")
        return

    print(f"{len(candidates)} conta(s) passaram do prazo de retenção (excluídas antes de {cutoff.date()}):")
    for row in candidates:
        print(f"  - #{row['id']} {row['email']} ({row['full_name']}) — excluída em {row['deleted_at']}")

    if args.dry_run:
        print("\n--dry-run: nada foi apagado.")
        return

    for row in candidates:
        # ON DELETE CASCADE nas tabelas relacionadas (singer_profiles,
        # conductor_profiles, listings, messages, user_social_links,
        # ratings etc — ver db/schema.sql) cuida do resto.
        execute("DELETE FROM users WHERE id = :id", {"id": row["id"]})

    print(f"\n{len(candidates)} conta(s) apagada(s) definitivamente.")


if __name__ == "__main__":
    main()

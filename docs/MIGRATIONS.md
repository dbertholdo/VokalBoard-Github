# Production migrations — rules and history

Moved verbatim from `AGENTS.md` on 2026-09-26 (summary stays in `AGENTS.md`). Read this only when a task touches `db/schema.sql` or `db/migrations/`.

## Regra em vigor desde 18/09/2026: sem migração em produção até nova ordem

Decisão do usuário (Daniel), válida para Codex e Claude, até que ele diga o
contrário:

- **Não aplicar nenhuma migração no Postgres de produção (Railway) neste
  período.** O `db/schema.sql` e os arquivos em `db/migrations/` continuam
  sendo criados/atualizados normalmente a cada mudança de schema — isso não
  muda —, mas ninguém deve instruir o usuário a rodar SQL no Railway nem
  assumir que uma migração pendente já foi aplicada lá.
- Motivo: a caixa "Query" do Railway não roda direito scripts com blocos
  `DO $$...$$` / `CREATE FUNCTION ... $$...$$` (ela quebra o script no `;` de
  dentro do bloco e devolve um erro de sintaxe genérico, sem linha). Isso já
  causou uma quebra em produção (coluna `appear_in_search` ausente) e travou
  a tentativa seguinte de aplicar a migração de retenção.
- **Continuar implementando funcionalidades normalmente** (rotas, templates,
  serviços, migrações novas quando precisarem de coluna/tabela nova) — só não
  empurrar nada para o banco de produção nesse meio tempo.
- Quando o usuário voltar e pedir, o trabalho será consolidar todas as
  migrações pendentes (a partir de `2026-09-15_buscar_pessoas.sql`) em uma
  migração única e aplicá-la via `psql` (linha de comando) contra a URL de
  conexão do Railway — não pela caixa "Query" do painel —, porque `psql`
  entende blocos `$$` corretamente e mostra o erro real, com linha, se houver
  algum.
- Antes de aplicar essa migração futura, perguntar ao usuário se já existem
  cadastros reais no banco de produção; se ainda for só ambiente de teste,
  uma instalação limpa a partir de `db/schema.sql` (que já é cumulativo) é
  mais simples e segura do que encadear migração por migração.

## 2026-09-26 — Messenger + #55 also folded in

`2026-09-26_messenger.sql` (conversations, contact pairs, reports, 60-day
view/trigger) and `2026-09-26_listing_terms.sql` (#55: job listings' copy
of voice/fee cleared + constraint, `listing_terms` view) were appended to
the consolidated file in that order, each verified the same way
(idempotent, pg_dump-identical to `schema.sql`).

## 2026-09-26 — Notas v2 folded into the consolidated file

`db/migrations/2026-09-26_notas_v2.sql` (purchased/earned category, expiry,
`credit_lot_usage`, backfill) was appended to the consolidated file before its
final `COMMIT`. Verified on its own: applied twice to a DB built from the
previous `schema.sql` (idempotent), and the result is pg_dump-identical to the
current `schema.sql`. Existing credits become *earned* with 18 months counted
from the day the migration runs (not retroactive).

## Consolidated migration built 19/09/2026 — read this before touching the pending migrations

`db/migrations/CONSOLIDATED_2026-09-19_pending_since_0915.sql` is the
single-file consolidation described above — all 26 files from
`2026-09-15_buscar_pessoas.sql` through `2026-09-19_periodic_mails.sql`,
concatenated. Built by Claude, at Daniel's request, explicitly NOT applied
(he said "don't execute" — it's prepared, not run). Its own header comment
has the full apply instructions; this section is the "why", for whichever
agent (Codex or Claude) touches this next.

**Two separate SQL problems, easy to confuse — both are explained here on
purpose:**

1. **The Railway web Query box mis-splits `$$`-quoted blocks** (`DO
   $$...$$`, `CREATE FUNCTION ... $$...$$`) — described above, this is why
   the file must be applied with `psql -v ON_ERROR_STOP=1 -f
   CONSOLIDATED_....sql`, never pasted into the dashboard's Query box.
   `2026-09-18_retention.sql` alone defines five trigger functions this
   way and cannot be rewritten without dollar-quoting, so this constraint
   is permanent for this file — don't try to "simplify it away" by
   removing the `$$` blocks.

2. **A genuine migration-ordering bug**, found by actually test-running the
   consolidated file against a reconstructed pre-migration baseline before
   ever considering handing it to Daniel (never just eyeball a concatenated
   migration file — run it): in plain filename/chronological order,
   `2026-09-18_p5_etapa2_urgencia.sql` runs before `2026-09-18_retention.sql`
   (`p` sorts before `r`), but `p5_etapa2_urgencia.sql` does `CREATE OR
   REPLACE VIEW visible_listings AS SELECT * FROM listings WHERE
   archived_at IS NULL AND deleted_at IS NULL ...` — and `archived_at` /
   `deleted_at` on `listings` are only added by `retention.sql`. Applied in
   filename order, this fails with `ERROR: column "archived_at" does not
   exist`. The consolidated file fixes this by running `retention.sql`
   immediately after `2026-09-18_p5_etapa1_notas_wallet_foundation.sql`,
   before `p5_etapa2_urgencia.sql` — confirmed safe because `retention.sql`
   only depends on `job_matches`/`listing_vacancies`, both created much
   earlier (17/09). **If any more migrations get added to this pending
   batch before it's finally applied, re-run/re-verify the consolidated
   file rather than just re-concatenating** — don't assume filename order
   is dependency order; this file is proof it sometimes isn't.

Verification performed (not just written, actually run): applied the
consolidated file with `psql -v ON_ERROR_STOP=1` against a database
reconstructed to approximate pre-2026-09-15 state, reached `COMMIT` with
exit code 0 and zero warnings, and `pg_dump --schema-only` diffed
byte-identical (ignoring ownership/privileges) against a database loaded
straight from the current `db/schema.sql`. No `DROP TABLE`/`DROP
COLUMN`/`TRUNCATE`/unguarded `DELETE` anywhere in the 26 source files.

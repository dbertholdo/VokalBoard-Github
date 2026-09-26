# Coordenação entre agentes

## Document hierarchy — MAIN HIERARCHY FOR ALL AIs (Daniel's decision, 2026-09-26)

Same hierarchy as `CLAUDE.md` §0. Read in order and stop as soon as you have enough context:

1. `AGENTS.md` (this file) / `CLAUDE.md` — stable rules.
2. **`HANDOFF.md` — current state. Always read it first; it is usually enough.**
3. `AI_CHANGELOG.md` — recent history only (≤ ~300 lines). Read the top entry, or more only when needed.
4. `docs/changelog-archive/` — old history. **Grep only, never read in full.**
5. `PLANO_EXECUTIVO_ORGANIZADO.md`, `docs/` (index: `docs/README.md` — visual rollout, migrations, i18n), `MANIFEST.md` files — only when the task touches them.

Also check `git status` before editing. **At the end of every material change:** (a) rewrite `HANDOFF.md` to reflect the new current state (≤ ~80 lines, remove resolved items); (b) add a ≤10-line English entry at the top of `AI_CHANGELOG.md` (files, tests run and result, next verifiable step); (c) if the changelog passes ~300 lines, move the oldest entries verbatim to `docs/changelog-archive/`. Never delete history, never record secrets, and never call a phase done without running the applicable tests.

## Migrations — summary (full rules and history: `docs/MIGRATIONS.md`)

- **No migration on production Postgres (Railway) until Daniel says otherwise** (rule since 18/09/2026). Keep updating `db/schema.sql` and `db/migrations/` normally; never tell the user to run SQL on Railway.
- Pending batch: `db/migrations/CONSOLIDATED_2026-09-19_pending_since_0915.sql` — ready, NOT applied. Apply only with `psql -v ON_ERROR_STOP=1 -f …`, never the Railway Query box (it breaks `$$` blocks).
- Any new migration must be folded into that file **and re-verified by actually running it** — filename order is not dependency order (see `docs/MIGRATIONS.md`).
- Before applying, ask Daniel whether production already has real users.

# HANDOFF — current state (read this first)

> **Rewrite, don't append.** Every agent updates this file at the end of a task so it always reflects *now*. Keep it under ~80 lines. History goes in `AI_CHANGELOG.md` (≤10-line entries).
> Last updated: 2026-09-26 — Claude (all 18 failing tests fixed; suite green). Before reading any big file, see the "Large files" list in `CLAUDE.md` §0.

## 1. Repo state
- Branch `main`, not pushed. Visual batch `20260925-1` and the doc hierarchy are committed.
- **Test suite GREEN (2026-09-26):** 278 passed + 10 retention = **0 failures**, stable over 3 full runs. Run it with `scripts/test_in_docker.sh` (isolated DBs, throwaway `vb-test` container; needs `docker compose up -d db web`).

## 2. Work split (Daniel's decision, 2026-09-24)
- **Codex:** visual/CSS only. **Claude:** functional code, test failures, business flows.
- Preserve each other's changes; check `git status` before editing.

## 3. Next up
1. **Visual/a11y issues below (§4)** — Codex's side, or Claude if Daniel reassigns. `/listings/new` missing labels is the most user-impacting.
2. **Open decisions (§5)** — need Daniel's answer; they block #49 (translations).
3. Browser-check #52 (fee warning, §6), then the backlog Daniel prioritizes.
4. Not yet run: `bandit`/`pip-audit` (in requirements-dev.txt), review of dependency warnings.

## 4. Open visual/a11y issues (found by Codex 2026-09-25, not fixed)
- **High:** `/rechnungmaker?tab=avulso` at 320px — preview table/totals break values across many lines (don't touch PDF generation).
- **Medium:** `/profile/wizard` photo step, 320px — help text overlaps the file input by 8px (`margin-top:-8px`).
- **Medium:** `/listings/new` vacancy rows — voice/qty/fee/currency fields have no label/aria-label.
- **Low:** logged-in header ~250px tall on mobile.
- Never verified: physical phone, Safari/Firefox, real 200% zoom, screen reader, performance. No bundled CJK font yet (system fallbacks only).

## 5. Open decisions — need Daniel's answer before work starts
1. **fr vs es:** `app/i18n.py` supports de/en/**fr**/it/pt, but `CLAUDE.md` §1 says "espanhol". Options: (a) keep French, fix the doc; (b) replace fr with es; (c) add es too. Blocks task #49 (zh/ko/ro translations are still 0%).
2. **Moderator permissions:** `permissions.py` says level 1 can act on reports, but `admin_accept_report`/`admin_reject_report` require `LEVEL_GOD`. It's a one-line change, but it's a policy call, so it needs an explicit yes.

## 6. Backlog (not started without Daniel's go-ahead)
- #52 fee warning on publish — **implemented 2026-09-21**, still needs a browser check (de + en; `seeking_singer` and `singer_available`).
- #53 Messenger/Inbox redesign — needs a design conversation first.
- #55 Match phase 2 — read `listing_vacancies` directly, drop the mirror columns on `listings`.
- Dependency warnings (Starlette/httpx, passlib/crypt, ReportLab/ast) — not reviewed.

## 7. Standing constraints
- **No production migrations/deploy** without Daniel's explicit order. The pending schema is `db/migrations/CONSOLIDATED_2026-09-19_pending_since_0915.sql` (ready, NOT applied). Apply only with `psql -v ON_ERROR_STOP=1 -f …`, never Railway's Query box. Any new migration must be folded into that file and re-verified. Details: `docs/MIGRATIONS.md`.
- Tests: `scripts/test_in_docker.sh` uses DBs `vokalboard_test` / `vokalboard_retention_test` (recreated with `--recreate`). Codex's older browser-QA setup: container `vokalboard-brand-qa`, localhost:8002 (may not be running). The suite deletes `sectest_` users, so don't run it alongside browser fixtures on the same DB.
- Zona de Alerta = urgency; Red Zone = admin; God Mode = powers. Admin/God Mode UI is English-only (`t_en()`).

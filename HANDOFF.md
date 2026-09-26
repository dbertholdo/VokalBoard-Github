# HANDOFF — current state (read this first)

> **Rewrite, don't append.** Every agent updates this file at the end of a task so it always reflects *now*. Keep it under ~80 lines. History goes in `AI_CHANGELOG.md` (≤10-line entries).
> Last updated: 2026-09-26 — Claude (visual/a11y fixes, #52 bug fix, security scan, i18n groundwork, docs reorganized). Before reading any big file, see the "Large files" list in `CLAUDE.md` §0.

## 1. Repo state
- Branch `main`, not pushed. Everything below is committed.
- **Tests GREEN:** 284 passed + 10 retention, 0 failed. Run `scripts/test_in_docker.sh` (isolated DBs, throwaway `vb-test` container; needs `docker compose up -d db web`; `--recreate` after schema changes).
- Security: `bandit` — 0 high; 7 medium/low-confidence B608 reviewed, all false positives (fixed allowlisted SQL fragments). `pip-audit` — production deps clean; dev `pytest` bumped 8.3.3 → 9.0.3 (advisory PYSEC-2026-1845), suite passes on it.
- Static assets are cache-versioned `?v=20260926-1` (style.css, brand.css; listing-form.js `-2`). Bump on every CSS/JS change; `tests/test_brand_visual.py` asserts the brand.css version.

## 2. Work split (Daniel's decision, 2026-09-24)
- **Codex:** visual/CSS. **Claude:** functional code, tests, business flows. On 2026-09-26 Daniel had Claude take Codex's open a11y list (done, §4).
- Preserve each other's changes; check `git status` before editing.

## 3. Next up
1. **Translations zh/ko/ro** — tooling ready, 0% translated. Follow `docs/I18N.md` (batches of ~80 keys via `scripts/i18n_tool.py`). Confirm the proposed tone + fee terminology with Daniel first (§5).
2. **Open decisions** (§5) — need Daniel.
3. Backlog (§6) in the order Daniel picks.

## 4. Visual/a11y — fixed and browser-verified 2026-09-26 (Chromium, 320px + desktop)
- `/listings/new` vacancy rows: every control has a visible, associated label; conductor mode hides the whole labelled field.
- `/profile/wizard` photo step: help text no longer overlaps the file input (was −8px, now +4px). Same fix after buttons (+8px).
- `/rechnungmaker?tab=avulso` 320px: amounts stay on one line (table scrolls inside), totals full width. PDF untouched.
- Logged-in mobile header: ~251px → 130px; links duplicated in the ☰ side menu are hidden ≤860px (badges still in side menu).
- Still never verified: physical phones, Safari/Firefox, real 200% zoom, screen reader, performance, bundled CJK font.

## 5. Open decisions — need Daniel's answer
1. **fr vs es:** code ships **fr**, `CLAUDE.md` §1 says "espanhol". (a) keep fr + fix doc, (b) replace fr with es, (c) add es too. Adding es is now the 5-step recipe in `docs/I18N.md`.
2. **Moderator permissions:** `permissions.py` says level 1 can act on reports, but `admin_accept_report`/`admin_reject_report` require `LEVEL_GOD`. One-line change, policy call.
3. **Fee terminology:** "Cachê" vs "Honorar" in German (listing form label vs other strings); tone for zh/ko/ro (proposal in `docs/I18N.md`).

## 6. Backlog (not started without Daniel's go-ahead)
- #53 Messenger/Inbox redesign — needs a design conversation first.
- #55 Match phase 2 — read `listing_vacancies` directly, drop the mirror columns on `listings`.
- Dependency deprecation warnings (Starlette/httpx, passlib/crypt, ReportLab/ast) — not blocking.

## 7. Standing constraints
- **No production migrations/deploy** without Daniel's explicit order. Pending schema: `db/migrations/CONSOLIDATED_2026-09-19_pending_since_0915.sql` (ready, NOT applied). `psql -v ON_ERROR_STOP=1 -f …` only, never Railway's Query box. New migrations must be folded in and re-verified. Details: `docs/MIGRATIONS.md`.
- Test DBs `vokalboard_test` / `vokalboard_retention_test` are disposable (script recreates them). Older QA DBs from 18/09 and 24/09 belong to earlier sessions — leave them. The suite deletes `sectest_` users.
- Zona de Alerta = urgency; Red Zone = admin; God Mode = powers. Admin/God Mode UI is English-only (`t_en()`).
- Docs map: `docs/README.md`. Obsolete files live in `docs/archive/` (search-ignored).

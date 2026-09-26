# HANDOFF — current state (read this first)

> **Rewrite, don't append.** Every agent updates this file at the end of a task so it always reflects *now*. Keep it under ~80 lines. History goes in `AI_CHANGELOG.md` (≤10-line entries).
> Last updated: 2026-09-26 — Claude (doc hierarchy + token optimization; no code changed). Before reading any big file, see the "Large files" list in `CLAUDE.md` §0.

## 1. Repo state
- Branch `main`. **Uncommitted:** Codex's visual batch `20260925-1` (`brand.css`, `base.html` CSS cache version, `admin_emails.html`, `admin_periodic_mail_form.html`, `tests/test_brand_visual.py`, `VISUAL_ROLLOUT.md`) plus the 2026-09-26 doc/token restructure (`CLAUDE.md`, `AGENTS.md`, `HANDOFF.md`, `.ignore`, `docs/`). Browser-checked by Codex, not committed yet.
- Test suite (last full run 2026-09-25, isolated QA DB): **267 passed, 18 failed, 3 warnings**. Not green.

## 2. Work split (Daniel's decision, 2026-09-24)
- **Codex:** visual/CSS only. **Claude:** functional code, test failures, business flows.
- Preserve each other's changes; check `git status` before editing.

## 3. Next up — Claude: the 18 failing tests
Reproduce first; decide per failure whether it's a product bug, a stale test or a fixture problem. Don't blame the redesign without evidence.

| Test file | Fails | Symptom |
|---|---:|---|
| `test_admin_report_moderation.py` | 3 | Listing setup returned None before moderation |
| `test_moderation_punishments_and_estornos.py` | 4 | Listing setup returned None |
| `test_urgency_routes.py` | 3 | Urgent create → 400; urgent button/listing missing |
| `test_profile_layout.py` | 2 | Field/card counts differ from expectations |
| `test_financial.py` | 1 | Level-2 access got 200, expected 303 |
| `test_mascot_moments.py` | 1 | "Joinha" after redeem: asset not found |
| `test_match_history_access.py` | 1 | Submenu item count differs |
| `test_p2_wizard_cv_works.py` | 1 | Private phone found in PDF bytes — check extracted text before calling it a leak |
| `test_periodic_mails.py` | 1 | Blank fields → 422, expected 303 |
| `test_security.py` (AdminPosts) | 1 | Expected post not found in HTML |

**Likely root cause for 10/18 (static read, 2026-09-26, not yet run):** `test_admin_report_moderation`, `test_moderation_punishments_and_estornos` and `test_urgency_routes` post a `seeking_singer` listing with the old standalone `voice_type_id=""` and no vacancy rows. Since 19/09 `_job_fields_valid()` (`app/routers/listings_routes.py:103`) requires ≥1 vacancy row, so creation is rejected → listing None / 400. Probably stale test fixtures, not a product bug: fix the `_listing_data` helpers to send a vacancy row and re-run.
**Needs Docker Desktop running** (tests use the compose Postgres; no local `.env`).

Token tip: `pytest tests -q --tb=line -p no:warnings` for the list, then one file at a time with `--tb=short`.

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
- QA environment (may not be running): container `vokalboard-brand-qa`, localhost:8002, DB `vokalboard_brand_retention_test_20260924`. The suite deletes `sectest` users, so don't run it alongside browser fixtures.
- Zona de Alerta = urgency; Red Zone = admin; God Mode = powers. Admin/God Mode UI is English-only (`t_en()`).

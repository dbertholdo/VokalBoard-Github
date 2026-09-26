# HANDOFF — current state (read this first)

> **Rewrite, don't append.** Every agent updates this file at the end of a task so it always reflects *now*. Keep it under ~80 lines. History goes in `AI_CHANGELOG.md` (≤10-line entries).
> Last updated: 2026-09-26 — Claude (Notas v2 implemented: purchased/earned, 18-month expiry, Stripe checkout + webhook, Terms/withdrawal pages). Before reading any big file, see the "Large files" list in `CLAUDE.md` §0.

## 1. Repo state
- Branch `main`, not pushed. Everything below is committed.
- **Tests GREEN:** 307 passed + 10 retention, 0 failed. Run `scripts/test_in_docker.sh` (isolated DBs, throwaway `vb-test` container; needs `docker compose up -d db web`; `--recreate` after schema changes).
- Security: `bandit` — 0 high; 7 medium/low-confidence B608 reviewed, all false positives (fixed allowlisted SQL fragments). `pip-audit` — production deps clean; dev `pytest` bumped 8.3.3 → 9.0.3 (advisory PYSEC-2026-1845), suite passes on it.
- Static assets are cache-versioned `?v=20260926-1` (style.css, brand.css; listing-form.js `-2`). Bump on every CSS/JS change; `tests/test_brand_visual.py` asserts the brand.css version.

## 2. Work split (Daniel's decision, 2026-09-24)
- **Codex:** visual/CSS. **Claude:** functional code, tests, business flows. On 2026-09-26 Daniel had Claude take Codex's open a11y list (done, §4).
- Preserve each other's changes; check `git status` before editing.

## 3. Next up
1. **Notas v2 go-live (N6) — Daniel:** Stripe test mode first → add `STRIPE_SECRET_KEY` (restricted) + `STRIPE_WEBHOOK_SECRET` in Railway; webhook `https://<domain>/webhooks/stripe` with events `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `charge.refunded`, `charge.dispute.created`, `charge.dispute.closed`; test with card 4242…; then live keys + **Capitalism Mode ON** (Red Zone). Needs the pending migration applied first (§7). Spec + as-built notes: `docs/specs/NOTAS_V2.md`.
2. **Messenger IN PROGRESS** — spec `docs/specs/MESSENGER.md` (Daniel 2026-09-26: max 1 e-mail/recipient/day; desktop popup bubble → small chat window with minimize/close; report message = yes). Done: M1 (conversations/contact_pairs/message_reports, backfill, trigger files every message into its pair's conversation, 60-day view + retention; migration folded into CONSOLIDATED). **Next: M2 — app/messenger.py rules (block > contact/Match > request, 1 msg until accepted) + send/accept/decline/hide/report routes.** Stages: M1 schema · M2 service+routes · M3 chat page · M4 polling/badges/5-min notification · M5 desktop bubble+windows · M6 e-mail limit + admin report queue.
3. **Languages es → ro → zh → ko** — route in `docs/I18N.md` (661 public keys each, 0% done).
4. Confirm the Railway `retention_worker` service runs — it now also does the account purge and Notas expiry.

## 4. Visual/a11y — fixed and browser-verified 2026-09-26 (Chromium, 320px + desktop)
- `/listings/new` vacancy rows: every control has a visible, associated label; conductor mode hides the whole labelled field.
- `/profile/wizard` photo step: help text no longer overlaps the file input (was −8px, now +4px). Same fix after buttons (+8px).
- `/rechnungmaker?tab=avulso` 320px: amounts stay on one line (table scrolls inside), totals full width. PDF untouched.
- Logged-in mobile header: ~251px → 130px; links duplicated in the ☰ side menu are hidden ≤860px (badges still in side menu).
- Still never verified: physical phones, Safari/Firefox, real 200% zoom, screen reader, performance, bundled CJK font.

## 5. Decisions (Daniel, 2026-09-26) — settled, don't reopen
- **Languages:** fr stays core (de/en/fr/it/pt). **es** joins zh/ko/ro as an *added* language: public/user site only; admin area English-only for added languages (existing core-language admin text untouched).
- **Moderators (level 1)** do NOT act on reports — accept/reject stays God Mode only (`permissions.py` docstring updated).
- **Fee wording:** German "Honorar" everywhere (listing form label fixed); Italian unified on "compenso"; added languages use the common modern term (glossary in `docs/I18N.md`).
- **Notas v2:** purchased spent first, never expire; earned expire 18 months after crediting; 6-month reactivation then erasure; Kleinunternehmer (§ 19 UStG, no VAT); no lawyer review of `/agb` `/widerruf`.
- Still open, low priority: legal pages (Impressum/Datenschutz/Code of Conduct) are out of scope for added languages unless Daniel decides otherwise.

## 6. Backlog (not started without Daniel's go-ahead)
- #53 Messenger — designed, see `docs/specs/MESSENGER.md` (awaiting approval).
- #55 Match phase 2 — read `listing_vacancies` directly, drop the mirror columns on `listings`.
- Dependency deprecation warnings (Starlette/httpx, passlib/crypt, ReportLab/ast) — not blocking.

## 7. Standing constraints
- **No production migrations/deploy** without Daniel's explicit order. Pending schema: `db/migrations/CONSOLIDATED_2026-09-19_pending_since_0915.sql` (ready, NOT applied). `psql -v ON_ERROR_STOP=1 -f …` only, never Railway's Query box. New migrations must be folded in and re-verified. Details: `docs/MIGRATIONS.md`.
- Test DBs `vokalboard_test` / `vokalboard_retention_test` are disposable (script recreates them). Older QA DBs from 18/09 and 24/09 belong to earlier sessions — leave them. The suite deletes `sectest_` users.
- Zona de Alerta = urgency; Red Zone = admin; God Mode = powers. Admin/God Mode UI is English-only (`t_en()`).
- Docs map: `docs/README.md`. Obsolete files live in `docs/archive/` (search-ignored).

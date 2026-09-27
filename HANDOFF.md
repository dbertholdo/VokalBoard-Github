# HANDOFF — current state (read this first)

> **Rewrite, don't append.** Every agent updates this file at the end of a task so it always reflects *now*. Keep it under ~80 lines. History goes in `AI_CHANGELOG.md` (≤10-line entries).
> Last updated: 2026-09-27 — Claude (cleanup sweep sections 1–5: account, profile/search, jobs/Matches, Messenger/notifications, Rechnungmaker; mascot size + 3 s minimum). Before reading any big file, see the "Large files" list in `CLAUDE.md` §0.

## 1. Repo state
- Branch `main`, not pushed. Everything below is committed.
- **Tests GREEN:** 371 passed + 10 retention, 0 failed, **0 warnings**. Run `scripts/test_in_docker.sh` (isolated DBs, throwaway `vb-test` container; needs `docker compose up -d db web`; `--recreate` after schema changes).
- Security: `bandit` — 0 high; 7 medium/low-confidence B608 reviewed, all false positives (fixed allowlisted SQL fragments). `pip-audit` — prod + dev clean (2026-09-26). passlib removed (bcrypt direct, hashes compatible), ReportLab 4.5.1, httpx2 for tests.
- Static assets are cache-versioned: style.css `?v=20260927-4`, brand.css `20260927-2`, listing-form.js `-2`, messenger.js `20260927-1`. Bump on every CSS/JS change; `tests/test_brand_visual.py` asserts the brand.css version.

## 2. Work split (Daniel's decision, 2026-09-24)
- **Codex:** visual/CSS. **Claude:** functional code, tests, business flows. On 2026-09-26 Daniel had Claude take Codex's open a11y list (done, §4).
- Preserve each other's changes; check `git status` before editing.

## 3. Next up
0. **Cleanup sweep (Daniel, 2026-09-27: payments only after every section is clean).** Done: 1 account, 2 profile & people search, 3 jobs & Matches, 4 Messenger & notifications, 5 Rechnungmaker (details in `AI_CHANGELOG.md`). Next: **6 Notas (no live payments) → 7 Admin/God Mode/Red Zone.** Per section: bugs/edge cases in the browser (a Latin + a CJK language, 375px), security, move logic out of routers into `app/*` services (pattern: `app/accounts.py`, `app/profiles.py`, `app/listings_service.py`; redirects from user/header input go through `app/safe_redirect.safe_path`), no per-row queries (§4), a11y. Browser checks: throwaway server on the test DB (never the dev/prod DB); the local `web` container is a stale 2026-09-17 image.
   - **Rechnungmaker v2 — PLAN ONLY, not started:** `docs/specs/RECHNUNGMAKER_V2.md` (country templates, invoice language, reverse charge, "?" help on every field, phase 2 QR-bill/GiroCode). Build only after Daniel's go.
   - **Deploy note:** set `SITE_BASE_URL` (the public https domain) in Railway — share links and the CV now use it (before, they were hardcoded to `vokalboard.de`).
1. **Notas v2 go-live (N6) — Daniel, LAST (decision 2026-09-27: payments only after every section/feature is clean):** Stripe test mode first → add `STRIPE_SECRET_KEY` (restricted) + `STRIPE_WEBHOOK_SECRET` in Railway; webhook `https://<domain>/webhooks/stripe` with events `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `charge.refunded`, `charge.dispute.created`, `charge.dispute.closed`; test with card 4242…; then live keys + **Capitalism Mode ON** (Red Zone). Needs the pending migration applied first (§7). Spec + as-built notes: `docs/specs/NOTAS_V2.md`.
2. **Messenger DONE (M1–M6)** — `docs/specs/MESSENGER.md` (as-built notes at the top). Goes live with the pending migration (§7). Suggested follow-up when Daniel wants: a browser pass on real phones.
3. **Languages:** es, ro, zh, ko DONE — UI 694/694 + all e-mails; zh/ko have a self-hosted CJK font (`app/static/fonts/noto-cjk/MANIFEST.md`; rerun `scripts/subset_cjk_fonts.py` after editing zh/ko.json). All AI drafts; native review still to do.
4. Confirm the Railway `retention_worker` service runs — it now also does the account purge, Notas expiry and the 60-day conversation deletion.

## 4. Visual/a11y — fixed and browser-verified 2026-09-26 (Chromium, 320px + desktop)
- `/listings/new` vacancy rows: every control has a visible, associated label; conductor mode hides the whole labelled field.
- `/profile/wizard` photo step: help text no longer overlaps the file input (was −8px, now +4px). Same fix after buttons (+8px).
- `/rechnungmaker?tab=avulso` 320px: amounts stay on one line (table scrolls inside), totals full width. PDF untouched.
- Logged-in mobile header: ~251px → 130px; links duplicated in the ☰ side menu are hidden ≤860px (badges still in side menu).
- Still never verified: physical phones, Safari/Firefox, real 200% zoom, screen reader, performance, CJK font on real phones/macOS.

## 5. Decisions (Daniel, 2026-09-26) — settled, don't reopen
- **Languages:** fr stays core (de/en/fr/it/pt). **es** joins zh/ko/ro as an *added* language: public/user site only; admin area English-only for added languages (existing core-language admin text untouched).
- **Moderators (level 1)** do NOT act on reports — accept/reject stays God Mode only (`permissions.py` docstring updated).
- **Fee wording:** German "Honorar" everywhere (listing form label fixed); Italian unified on "compenso"; added languages use the common modern term (glossary in `docs/I18N.md`).
- **Notas v2:** purchased spent first, never expire; earned expire 18 months after crediting; 6-month reactivation then erasure; Kleinunternehmer (§ 19 UStG, no VAT); no lawyer review of `/agb` `/widerruf`.
- Still open, low priority: legal pages (Impressum/Datenschutz/Code of Conduct) are out of scope for added languages unless Daniel decides otherwise.

## 6. Backlog (not started without Daniel's go-ahead)
- Accessibility pass; migration dry run (Daniel: "not yet"). Rebuild the stale local `web` dev container (2026-09-17 image, no code mount).

## 7. Standing constraints
- **No production migrations/deploy** without Daniel's explicit order. Pending schema: `db/migrations/CONSOLIDATED_2026-09-19_pending_since_0915.sql` (ready, NOT applied). `psql -v ON_ERROR_STOP=1 -f …` only, never Railway's Query box. New migrations must be folded in and re-verified. Details: `docs/MIGRATIONS.md`.
- Test DBs `vokalboard_test` / `vokalboard_retention_test` are disposable (script recreates them). Older QA DBs from 18/09 and 24/09 belong to earlier sessions — leave them. The suite deletes `sectest_` users.
- Zona de Alerta = urgency; Red Zone = admin; God Mode = powers. Admin/God Mode UI is English-only (`t_en()`).
- Docs map: `docs/README.md`. Obsolete files live in `docs/archive/` (search-ignored).

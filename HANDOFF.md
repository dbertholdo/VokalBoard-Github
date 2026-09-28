# HANDOFF — current state (read this first)

> **Rewrite, don't append.** Every agent updates this file at the end of a task so it always reflects *now*. Keep it under ~80 lines. History goes in `AI_CHANGELOG.md` (≤10-line entries).
> Last updated: 2026-09-27 — Claude (cleanup sweep sections 1–6: account, profile/search, jobs/Matches, Messenger/notifications, Rechnungmaker, Notas; mascot size + 3 s minimum). Before reading any big file, see the "Large files" list in `CLAUDE.md` §0.

## 1. Repo state
- Branch `main`, pushed to GitHub (Daniel pushes; the agent never does). Tagged `v1.1.3` = cleanup sections 1–7 done (2026-09-27).
- **Tests GREEN:** 375 passed + 10 retention, 0 failed, **0 warnings**. Run `scripts/test_in_docker.sh` (isolated DBs, throwaway `vb-test` container; needs `docker compose up -d db web`; `--recreate` after schema changes).
- Security: `bandit` — 0 high; 7 medium/low-confidence B608 reviewed, all false positives (fixed allowlisted SQL fragments). `pip-audit` — prod + dev clean (2026-09-26). passlib removed (bcrypt direct, hashes compatible), ReportLab 4.5.1, httpx2 for tests.
- Static assets are cache-versioned: style.css `?v=20260927-6`, brand.css `20260927-2`, listing-form.js `-2`, messenger.js `20260927-1`. Bump on every CSS/JS change; `tests/test_brand_visual.py` asserts the brand.css version.

## 2. Work split (Daniel's decision, 2026-09-24)
- **Codex:** visual/CSS. **Claude:** functional code, tests, business flows. On 2026-09-26 Daniel had Claude take Codex's open a11y list (done, §4).
- Preserve each other's changes; check `git status` before editing.

## 3. Next up (plan for the next session — Daniel, 2026-09-27)
**Uncommitted work in the tree (Docker was down → NOT tested):**
- Rechnungmaker highlight: purple pill in the top bar (also for visitors), purple first row in the phone side menu with subtitle; removed from `_profile_menu.html`; new key `rechnungmaker_subtitle` (9 langs); CSS `.nav-highlight` / `.side-nav-highlight`; style.css `?v=20260927-6`.
- `app/invoice_countries.py` (new, not wired yet): country profiles DE/AT/CH/OTHER, legal notes in DE/EN/FR/IT, tax-ID labels, doc labels, number/date formats, `resolve_tax()`, `client_data()` for the preview JSON, legacy-preset mapping.
- First step next session: start Docker → `scripts/test_in_docker.sh` (CJK fonts may need `scripts/subset_cjk_fonts.py` for the new zh/ko subtitle) → browser check of the nav (desktop, phone, visitor) → commit.

**Bugs B1–B5 from production testing — ALL DONE 2026-09-28** (Daniel: re-check on production after the next deploy):
- B1 Match flow: the author sees Applications with inline Accept/Decline on their own listing page (`_candidacy_list.html`, shared with `/listings/{id}/candidates`; query in `app/vacancies.get_listing_invitations`); artists get a big "I'm available!" button, wrong role gets an explanation.
- B2 Mascot nudge: every reminder links to its page (profile→wizard, evaluation→/profile/matches, invitation→/invitations?tab=pending), 6 s hold, stays while hovered/focused. (QA's case: it was the evaluation nudge, which had no link.)
- B3 Chat: Enter sends / Shift+Enter new line on the full page too (IME-safe `isComposing`).
- B4 Chat: "Hide" → "Archive" (9 langs), new Archived tab + Unarchive; archived chats return on a new message, 60-day rule unchanged.
- B5 CI: bandit findings fixed; workflow on checkout@v5 / setup-python@v6 / Python 3.12 / Postgres 18. Watch the next push goes green.

**Then, in this order (Daniel, 2026-09-27 evening — everything below is APPROVED, just build it):**
1. **Rechnungmaker name translated everywhere in the UI** (supersedes "one official name + subtitle"): non-German users must understand it — de "Rechnungmaker", en "Invoice Maker", fr "Créateur de factures", it "Generatore di fatture", pt "Gerador de Faturas (NF)", es "Generador de facturas", ro "Generator de facturi", zh "发票生成器", ko "인보이스 생성기". Nav, page titles, menus, e-mails, admin. Only the downloaded invoice keeps the German product name "Rechnungmaker" (PDF footer). Daniel confirmed: the invoice DOCUMENT language choice (DE/EN/FR/IT, v2 spec) stays. The bug he sees: `nav_rechnungmaker` (and page titles/tab labels) is literally "Rechnungmaker" in every language — translate the key(s) and grep templates/Python for hardcoded "Rechnungmaker"/"Rechnung Maker" in the top bar, side bar, profile menu, page title, e-mails.
2. **Visitors see the Rechnungmaker blurred** (same anon-gate pattern as listings: `.anon-gate` in listing_detail.html) with a sign-up/login pop-up — instead of a redirect to /login.
3. **Referral reward: 1 Nota per 1 successful registration** (today: 1 Nota per `CREDIT_REFERRALS_PER_CREDIT` verified referrals) **+ anti-fraud**: only after the invited person verifies e-mail AND shows real activity (e.g. completed profile or 7 days active); one reward per e-mail ever (exists: hashed e-mail); normalize Gmail dots/+tags; block disposable e-mail domains; limit rewards per referrer per day/month; flag many sign-ups from the same IP/device for admin review; admin can reverse fraudulent rewards (audit-logged). Update Terms/Notas texts in 9 langs.
3b. **Bots in analytics** (Daniel: can't tell real users from bots): today every non-static GET is counted (`VisitTrackingMiddleware`, `site_visits`). Plan: (1) skip bot user agents / empty UA / non-2xx (probes like /wp-admin) / HEAD; (2) count a visit only when a tiny same-origin JS beacon fires after page load (bots rarely run JS; no cookies, no personal data); (3) add `site_visits.is_bot` (small migration, tolerate missing column); **Daniel: bots must NOT appear in the normal analytics at all** — all charts/totals count humans only; bot traffic lives on its own out-of-sight page (e.g. Red Zone → "Bot traffic"), no bot numbers on /admin/analytics. Optional, Daniel's call: Cloudflare free plan (Bot Fight Mode) in front of Railway.
3c. **Support-ticket spam** (Daniel: SEO spam arriving as anonymous "Bug report"): `/support/report-bug` accepts anonymous posts with NO captcha, honeypot or rate limit (`/contato` already needs login). Plan: (1) show the Report-a-bug button to logged-in members only; (2) honeypot + per-IP rate limit on every public form (`app/captcha.is_bot`, `app/register_throttle` pattern); (3) Turnstile: code exists (`app/captcha.py`, `_captcha_fields.html` on register + forgot-password) but is OFF unless `TURNSTILE_SITE_KEY`/`TURNSTILE_SECRET_KEY` are set in Railway — Daniel creates the free keys at dash.cloudflare.com → Turnstile; (4) "likely spam" flag (links, sales phrases); (5) **Delete button for tickets in /admin/tickets** (none exists today — Daniel can't remove spam): single + bulk "delete all marked spam", audit-logged.
4. **Menu reorganization — APPROVED by Daniel:** `[Rechnungmaker] Jobs▾ People Messages Matches 🔔 avatar▾ 🌐`; ONE Matches page (Open · Confirmed · History & ratings); avatar menu = profile + Rewards (Notas · Hall of Fame) + Log out; no duplicates; phone menu same order.
5. **Rechnungmaker v2 phase 1** (`docs/specs/RECHNUNGMAKER_V2.md`): wire `invoice_countries.py` into PDF (doc language, labels, number/date formats, currencies EUR CHF USD GBP BRL), routes + Match drafts, form (country + invoice language, options per country, reverse-charge client VAT ID, no-JS "Apply"), preview JS from embedded JSON, "?" help on every field (~33 texts × 9 langs, site language), disclaimer, remember country/language (small migration; tolerate missing columns), pre-fill, tests, screenshot demo.
6. **Rechnungmaker v2 phase 2:** Swiss QR-bill + GiroCode (ask before installing packages).
6a. **Code of Conduct in every language** (Daniel: shown in German for fr/it/pt/es/ro/zh/ko): `code_of_conduct.html` only has `en` + German fallback → all 9 (+ tr later). **Also check the other legal pages** (agb, datenschutz, widerruf, impressum): if de/en only, propose translations marked "for information — the German version is binding" (Daniel decides; earlier rule: legal pages out of scope for added languages).
6b. **Turkish (tr)** as the next added language (Daniel, 2026-09-27): public/user site only like es/ro/zh/ko (admin stays English) — follow `docs/I18N.md` (locale file, UI texts, e-mails, glossary: fee/negotiable/tone); Latin script, no font work.
6d. **Analytics charts: labels overlap** (Daniel's screenshot): weekday names collide ("TuesdayWednesdayThursday"), the hour-of-day axis is an unreadable run of "00010203…". Fix: short labels (Mon/Tue… in English — admin is English-only), show every 3rd hour (00, 03, 06…) or rotate, value labels that don't overlap, responsive sizing at phone width. **Daniel: keep the current colours** — only readability matters; vertical (rotated) axis labels are fine.
6c. **Language-menu flags** (Daniel: shows "DE/GB/FR" letters): flags are emoji (🇩🇪…), which Windows can't render → ship small SVG flags (e.g. flag-icons, MIT — licence file + MANIFEST, ask before downloading) for de/gb/fr/it/br/es/cn/kr/ro (+ tr); keep a text fallback + `alt`/`aria-hidden` so screen readers read the language name.
7. **Function catalogue** (after everything else): a page/document listing every site feature (for users and/or Daniel — format to decide).
8. Later: admin browser/phone check, accessibility pass.

**Daniel's go-live items:** DONE 2026-09-27 — DB update applied, latest deployed, Postgres password reset, SITE_BASE_URL, Railway settings. Still: Stripe last; native-speaker review of es/ro/zh/ko.

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

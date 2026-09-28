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
`app/invoice_countries.py` (country profiles DE/AT/CH/OTHER, notes, labels, formats, `resolve_tax()`) is committed but NOT wired yet — item 5.

**Bugs B1–B5 from production testing — ALL DONE 2026-09-28** (Daniel: re-check on production after the next deploy):
- B1 Match flow: the author sees Applications with inline Accept/Decline on their own listing page (`_candidacy_list.html`, shared with `/listings/{id}/candidates`; query in `app/vacancies.get_listing_invitations`); artists get a big "I'm available!" button, wrong role gets an explanation.
- B2 Mascot nudge: every reminder links to its page (profile→wizard, evaluation→/profile/matches, invitation→/invitations?tab=pending), 6 s hold, stays while hovered/focused. (QA's case: it was the evaluation nudge, which had no link.)
- B3 Chat: Enter sends / Shift+Enter new line on the full page too (IME-safe `isComposing`).
- B4 Chat: "Hide" → "Archive" (9 langs), new Archived tab + Unarchive; archived chats return on a new message, 60-day rule unchanged.
- B5 CI: bandit findings fixed; workflow on checkout@v5 / setup-python@v6 / Python 3.12 / Postgres 18. Watch the next push goes green.

**Then, in this order (Daniel, 2026-09-27 evening — everything below is APPROVED, just build it):**
1. ~~Rechnungmaker name translated~~ DONE 2026-09-28: `nav_rechnungmaker` per language (de keeps "Rechnungmaker"), page h1/title use it, pt texts + pt e-mails say "fatura"; subtitle is now a tagline. Invoice PDF/preview stay German (footer untouched).
2. ~~Visitors see it blurred~~ DONE 2026-09-28: `/rechnungmaker` for visitors/unconfirmed = empty tool blurred + `inert` behind a sign-up/login card (`.anon-gate-overlay`); login now accepts a same-site `next`.
3. ~~Referral reward~~ DONE 2026-09-28 (code; **needs Daniel to apply `db/migrations/2026-09-28_referral_rewards.sql` via psql** — until then the old 1-per-10 rule stays active): 1 Nota per referral once the invitee confirmed e-mail + completed profile (or 7 days active, came back another day); one per inbox (`app/email_identity.py`: Gmail dots/+tags), throwaway domains blocked; max 3/day, 20/month (extra waits); 3+ referred sign-ups from one IP → flagged; `/admin/referrals` approve/reject/reverse (password + audit_log); settled on verify/login/profile save/opening /notas (no worker needed); Terms 3.5 (en+de) + Notas texts (9 langs).
3b. ~~Bots~~ DONE 2026-09-28: Analytics counts only JS-beacon visits (`POST /visit`); bots/probes → `bot_traffic_daily`, Red Zone → Bot traffic. **Needs `2026-09-28_bot_traffic.sql`** (psql). Note: visit numbers drop from now on — that's the bots leaving. Cloudflare still optional (Daniel).
3c. ~~Ticket spam~~ DONE 2026-09-28: bug report members-only; honeypot + 5/hour per IP and account; "Likely spam" filter/tag (live heuristic); delete one / all spam with password + audit_log. Turnstile still off until Daniel sets the keys.
4. ~~Menu reorganization~~ DONE 2026-09-28: top bar `[Rechnungmaker] Jobs▾ People Messages Matches 🔔 avatar▾ 🌐` (logo = home); `/matches` → Open (`/invitations?tab=pending`) if something waits, else Confirmed; tabs `_matches_tabs.html` (Open · Confirmed · History & ratings = `/profile/matches?view=`); avatar menu `_profile_menu.html` = profile pages + Rewards (Notas, Hall of Fame) + Admin + Log out; Jobs `_jobs_menu.html`; phone side menu same order, same partials.
4b. ~~SEO~~ DONE 2026-09-28 (`app/seo.py`): fixed bug — every page had the same <title> (templates' `{% block title %}` was ignored); keyword titles/descriptions for home + board in 9 langs; canonical + hreflang (?lang=xx, de = no param) on every page and in sitemap.xml; JSON-LD WebSite/Organization + **JobPosting** on active seeking_* listings (visitor-visible data only); visitor landing keyword section; sitemap adds /rechnungmaker + /agb; URLs use SITE_BASE_URL. Daniel: Google Search Console → set `GOOGLE_SITE_VERIFICATION` in Railway, submit /sitemap.xml. Open decision: Google Jobs ranks listings with a full description higher — visitors (and Google) see only a teaser today (P3.D choice).
5. ~~Rechnungmaker v2 phase 1~~ DONE 2026-09-28: `app/invoice_form.py` (read/normalize/to_document, prefs, Match pre-fill of fee+currency+event date+client+title), `app/invoice_form_context.py`, `app/schema_features.has_columns`; PDF + live preview in DE/EN/FR/IT with country number/date formats, 5 currencies, reverse charge needs client VAT ID; `_invoice_fields.html` grouped fields + "?" on every field (68 keys × 9 langs; click/tap/Enter, Esc closes); Match form checkbox "Invoice the person who posted the job" (Daniel); no-JS "Apply country"; old `invoice_tax_presets.py` removed (old drafts still build). **Needs `2026-09-28_invoice_prefs.sql`** (until then no remembering). Native review of the help texts = Daniel's go-live item.
5b. ~~Cancel a confirmed Match~~ DONE 2026-09-28 (`app/match_cancellation.py`): either side, until 7 days before the event (after that the card says to contact the other person), reason ≥ 50 chars; slot reopens + listing un-paused, invoice draft dropped, urgent-listing reward taken back; other side gets e-mail + bell, admins get a bell; `/admin/cancellations` (nav badge): Warn (password) / Dismiss, 3 warnings = 30 days no applying/inviting/accepting (`users.matches_blocked_until`), **Lift block** (password) = Daniel's "unban"; all audit-logged. **Needs `2026-09-28_match_cancellations.sql`** (until then no cancel option, nobody blocked).
6. **Rechnungmaker v2 phase 2:** Swiss QR-bill + GiroCode (ask before installing packages).
6a. **Code of Conduct in every language** (Daniel: shown in German for fr/it/pt/es/ro/zh/ko): `code_of_conduct.html` only has `en` + German fallback → all 9 (+ tr later). **Also check the other legal pages** (agb, datenschutz, widerruf, impressum): if de/en only, propose translations marked "for information — the German version is binding" (Daniel decides; earlier rule: legal pages out of scope for added languages).
6b. **Turkish (tr)** as the next added language (Daniel, 2026-09-27): public/user site only like es/ro/zh/ko (admin stays English) — follow `docs/I18N.md` (locale file, UI texts, e-mails, glossary: fee/negotiable/tone); Latin script, no font work.
6d. **Analytics charts: labels overlap** (Daniel's screenshot): weekday names collide ("TuesdayWednesdayThursday"), the hour-of-day axis is an unreadable run of "00010203…". Fix: short labels (Mon/Tue… in English — admin is English-only), show every 3rd hour (00, 03, 06…) or rotate, value labels that don't overlap, responsive sizing at phone width. **Daniel: keep the current colours** — only readability matters; vertical (rotated) axis labels are fine.
6c. **Language-menu flags** (Daniel: shows "DE/GB/FR" letters): flags are emoji (🇩🇪…), which Windows can't render → ship small SVG flags (e.g. flag-icons, MIT — licence file + MANIFEST, ask before downloading) for de/gb/fr/it/br/es/cn/kr/ro (+ tr); keep a text fallback + `alt`/`aria-hidden` so screen readers read the language name.
7. **Function catalogue** (after everything else): a page/document listing every site feature (for users and/or Daniel — format to decide).
8. Later: admin browser/phone check, accessibility pass.

**Daniel's go-live items:** DONE 2026-09-27 — DB update applied, latest deployed, Postgres password reset, SITE_BASE_URL, Railway settings. Still: Stripe last; native-speaker review of es/ro/zh/ko. New: apply `2026-09-28_referral_rewards.sql` + `2026-09-28_bot_traffic.sql` + `2026-09-28_invoice_prefs.sql` + `2026-09-28_match_cancellations.sql` (psql, not the Query box). Google Search Console (4b).

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

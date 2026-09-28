# VokalBoard — Shared AI changelog (recent entries only)

**Read `HANDOFF.md` first** — it holds the current state. This file is history, not a briefing: read only the top entry unless you need more context. See the "Document hierarchy" section in `CLAUDE.md` / `AGENTS.md`.

**Entry rules (from 2026-09-26):**
- New entries go at the top, in English, **≤ 10 lines**: what changed (files), tests run + result, next safe step. No long caveat lists — put open items in `HANDOFF.md` instead.
- Record only verifiable facts. No tokens, passwords, database URLs or personal data.
- Never delete entries; correct them with a new entry.
- **Rotation:** when this file passes ~300 lines, move the oldest entries verbatim to `docs/changelog-archive/` (one file per period). Moving is not deleting.
- Older history: `docs/changelog-archive/` (`AI_CHANGELOG_until_2026-09-19.md`, `AI_CHANGELOG_2026-09-21_to_2026-09-24.md`) — grep it, never read it in full. Also see git history and `docs/changelog-archive/CHANGELOG_2026-09-14.md`.

## 2026-09-28 — Claude — bugs B1–B4 (Match flow, mascot link, chat Enter, archive)
- B1: listing page shows the author's applications with Accept/Decline (`_candidacy_list.html`, `vacancies.get_listing_invitations`); "I'm available!" button; wrong-role hint.
- B2: all mascot nudges link somewhere; hover/focus pauses the hide. B3: Enter sends on /messages (messenger.js).
- B4: Archived tab + Unarchive (`messenger.unarchive_conversation`, folder "archived"); "Hide" renamed "Archive".
- 9 new/changed i18n keys (9 langs), CJK fonts re-subset; cache: style 20260928-1, messenger.js 20260928-1, fonts-cjk 20260928-1.
- Tests: new test_listing_match_flow.py + archive tests; full suite 382 passed / 7 skipped + retention. Next: item 1 (translate Rechnungmaker name).

## 2026-09-28 — Claude — B5: GitHub Actions green again
- Cause: `bandit -r app -ll` exited 1 on 7 medium B608 findings (all false positives).
- listing_rewards, notifications, periodic_mail_worker: SQL rebuilt with bound parameters; retention_worker, banner_routes: `# nosec B608` on the flagged lines.
- `.github/workflows/security.yml`: checkout@v5, setup-python@v6, Python 3.12, Postgres 18 (match production).
- Tests: 378 passed / 7 skipped + retention 10 passed (docker). Next: B1 Match flow.

## 2026-09-27 — Claude — cleanup section 7 (admin): English, refund re-auth, user tabs
- User page split into tabs (`?tab=account|notas|reviews|moderation|danger`, no JS); action redirects land on the right tab; times via `local_time`.
- Password re-check (+ failed-attempt audit) on BOTH Notas refunds (`/admin/users/{id}/refund-notas/…` was level-2 with no check; `/financeiro/estornos/notas/…`).
- Last Portuguese in the admin translated (general ledger, user page, sheet title). Tables in `.table-scroll`.
- Tests: 378 passed + 10 retention (refund tests now send the password; brand contract regenerated for the 2 rewritten templates).

## 2026-09-27 — Claude — cleanup section 7 (admin), part B in progress
- Grouped English admin sidebar (`_admin_nav.html`, counts via `app/admin_nav.py`, level 2+ only; duplicate subnav removed); new `/admin/reports` (listings/messages/blocks; only God Mode sees action buttons) and `/financeiro/audit`; compatibility switch moved to Red Zone settings; slim dashboard ("Needs attention").
- English: banners (+ labels in `app/banners.py`), e-mails, periodic mail form, shop catalog, refunds. Tables wrapped in `.table-scroll`. style.css `?v=20260927-5`.
- Tests: 378 passed + 10 retention. Remaining items listed in HANDOFF §3.

## 2026-09-27 — Claude — cleanup section 6 (Notas, no live payments)
- Shop redeem now ONE transaction (`shop_catalog.redeem_item`): debit + the item's effect commit together (the highlight used to be applied in a second transaction), user row locked before the double-submit check (two quick clicks could stack a second 7-day highlight).
- Stripe webhook (still off): sessions without our metadata return "not_ours" instead of a 500 Stripe retries for days; refund/dispute amounts computed after locking the user (two events at once could debit twice).
- Invite links (Hall of Fame, profile) + checkout return URL use `profiles.public_base_url()` (SITE_BASE_URL). Notas subtitle no longer says "rewards for inviting friends" only (9 langs).
- Reviewed OK: urgency purchase, listing rewards (weekly cap, live listings only), referral credit idempotency, expiry.
- Docs: `docs/specs/ADMIN_REORG.md` (Daniel's decisions for section 7); RECHNUNGMAKER_V2 decisions updated.
- Browser (390 zh + 1440 pt): balance/split/expiry, redeem, history, Hall of Fame. Tests: 375 passed + 10 retention (new `tests/test_notas_cleanup.py`).

## 2026-09-27 — Claude — cleanup section 5 (Rechnungmaker)
- **Tax bug:** the country/tax select copied its value into hidden fields via an inline `onchange` — blocked by our CSP, so EVERY invoice was DE standard 19 % VAT (also for Kleinunternehmer/CH/AT). Now a named `tax_preset` select parsed server-side (`parse_tax_preset`); the Match draft remembers it (encrypted `EXTRA_FIELDS`).
- Forms were hardcoded Portuguese/German → shared translated macro `_invoice_fields.html` (37 `inv_*` keys × 9 langs); the invoice paper/PDF stays German by design. `.form-grid` never existed (labels ran inline) → defined; preview table no longer clipped (scroll wrapper, 480px pane); `.form-error` → `.error`; secondary buttons stay secondary in stacked forms.
- Standalone errors re-render the form with the typed values (stateless echo, never stored) and separate "invalid" / "no allowance" messages. Download name ASCII-safe (umlaut/quote in the number crashed/broke the header). `no-store` on Match form/preview/PDF. No invoice work on cancelled or already-invoiced Matches.
- Screenshot demo (Playwright + local Chrome, test DB): scratchpad `demo/01…07`. Tests: 371 passed + 10 retention (new `tests/test_rechnungmaker_cleanup.py`).

## 2026-09-27 — Claude — cleanup section 4 (Messenger & notifications)
- Clock times were printed in UTC (1–2 h off): `messenger.local_time()` (Europe/Berlin) for the chat page, chat-window JSON and the admin report list (Jinja filter `local_time`).
- `send_message`: a stale/tampered `listing_id` is dropped instead of an FK 500. Report redirect lookup scoped to the recipient; duplicate conversation lookup removed.
- New `app/safe_redirect.safe_path()` (same-site paths only): notification "open" link, "mark all read" (was the raw Referer), invitation `next`.
- Job-alert e-mails skip people across a block (either direction).
- a11y: chat thread + chat windows `aria-live="polite"`, window `aria-label` = other person, minimize button `aria-expanded`. messenger.js `?v=20260927-1`.
- Browser (1440 de + 375 zh): request → bubble → chat window → accept → reply; times local. Tests: 366 passed + 10 retention (new `tests/test_messenger_cleanup.py`).

## 2026-09-27 — Claude — cleanup section 3 (jobs & Matches)
- New `app/listings_service.py`: form validation + create/update with vacancies in ONE transaction (`set_vacancies(conn=)`); `listings_routes.py` 60→44 KB. Fixes: tampered type/voice, both fee+negotiable on self-ads, availability-trigger errors → form errors (were 500 / raw JSON); missing event date has its own message (`error_event_date_required`, 9 langs); vacancy rows + checkboxes survive a form error; `sheet_music_url` http(s) only; slots capped at 100; edit can't change the listing type; one report per person; deleting a listing expires its pending invitations.
- `create_invitation`: artist role must fit the vacancy, initiator verified, no block either way, no invitation born expired. `next` redirects same-site only (open redirect).
- Match history: fee from the matched vacancy (was legacy `listings.fee`, empty since #55; retention snapshot stores it too); evaluations/drafts batched per page; bad score → redirect, not JSON 400. Home highlights: one UPDATE.
- Browser (375px, ko): create (error path keeps rows) → my listings → detail/board/invitations/matches. Tests: 361 passed + 10 retention (new `tests/test_jobs_cleanup.py`; 3 fixtures now verify their contractor).

## 2026-09-27 — Claude — cleanup section 2 (profile & people search)
- New `app/profiles.py` (service; profile helpers moved out of `profile_routes.py`, 50→37 KB): `clean_profile_input` + `save_profile` in ONE transaction. Fixes: an invalid photo no longer skips bio/links/voice/repertoire (message said "rest saved"); bad `voice_type_id` / over-long city, fach, ensemble are form errors or truncated, not 500s; dead `social_whatsapp` param removed.
- Ratings (`save_rating`): refused across a block (either way) and for unverified raters (widget hidden too); stale `listing_id` no longer an FK 500.
- Share links: were hardcoded `vokalboard.de` and built `/u/users/ID` without a slug → `profile_public_url()` (SITE_BASE_URL, else request host); also used by the CV PDF.
- People search: badges batched in one query (`top_badges_for_users`, CLAUDE.md §4 N+1); non-numeric voice filter ignored; `%`/`_` in city are literal. CV + e-mail share `badge_label()`.
- Browser (375px, ko/zh): /profile, /users/{id}, /people — no overflow, translated. Tests: 353 passed + new `tests/test_profiles_cleanup.py`.

## 2026-09-27 — Claude — cleanup section 1 (account) + mascot size/duration
- New `app/accounts.py` (service): e-mail trimmed+lowercased everywhere; lookups by `lower(email)`; login lockout can no longer be dodged by changing letter case; sign-up validates e-mail/name and creates user+profile in ONE transaction (`app/database.transaction()`); timing-equalized login; 2-min cooldown on resend-verification / forgot-password e-mails; password reset burns every open link + clears lockout; change-password / delete-account share the login lockout. Session cleared on login. Data export now includes works, spoken languages, Notas ledger, invitations, matches, state/country/language.
- Forms: `autocomplete` hints (WCAG 1.3.5) + maxlength. New keys `register_error_invalid_email/_name` (9 languages; CJK fonts regenerated).
- Mascot (Daniel): fluid size tokens `--mascot-*` (rem + clamp, e.g. toast ~72px phone → ~105px 1440 → 136px max); bubble no longer wraps word-per-line; side toasts sit above the Report-bug button; every toast fully visible ≥3 s (`VB_MASCOT_MIN_MS`); link toast is now clickable + keyboard-focusable (was `pointer-events:none`). style.css/brand.css `?v=20260927-1`; brand contract baseline regenerated (attributes added only).
- Tests: 349 passed, 7 skipped + 10 retention (new `tests/test_accounts.py`).

## 2026-09-26 — Claude — zh/ko e-mails; last German-only e-mails localized
- `app/email_localization.py`: zh + ko copy in every function (`EMAIL_LANGUAGES` now 9); `_hello()` renders greetings (zh/ko name-first; other languages unchanged). New `listing_match_alert_email`, `urgent_listing_reminder_email`, `badge_unlocked_email` in all 9 languages.
- `app/notifications.py` (match alert + urgent reminder) and `app/badges.py` (badge unlocked) no longer send hardcoded German+EN; they use the recipient's `preferred_language` (English fallback). Badge names reuse the `badge_*_label` i18n keys.
- `app/email_layout.py`: zh/ko sign-off + footer.
- Tests: 340 passed, 7 skipped + 10 retention (new tests in `tests/test_email_localization.py`).

## 2026-09-26 — Claude — self-hosted CJK font (Noto Sans SC/KR)
- `app/static/fonts/noto-cjk/`: OFL subsets, wght 400–700 woff2 — "ui" (locale chars: SC 200 KB, KR 98 KB) + "common" (GB2312 L1 / KS X 1001 Hangul, fetched only via unicode-range). LICENSE + MANIFEST.
- `app/static/css/fonts-cjk.css` (generated by `scripts/subset_cjk_fonts.py`), linked in `base.html` only for zh/ko. Latin stays Manrope.
- Browser-checked zh home / ko login on a throwaway server (test DB): only the ui file loads; de loads none. Note: the local `web` dev container is a stale 2026-09-17 image with no code mount.
- Tests: 337 passed, 7 skipped + 10 retention (new `tests/test_cjk_fonts.py`).
- Next: zh/ko e-mail copy.

## 2026-09-26 — Claude — Korean UI translation (694/694)
- `app/locales/ko.json`: all public keys (해요체, fee 출연료, "Match"/Notas kept). zh done in 16f4fa2. `docs/I18N.md` phase 2 marks zh/ko done.
- Tests: `scripts/test_in_docker.sh` → 333 passed, 7 skipped + 10 retention; `i18n_tool.py check` clean.
- Next: CJK font (needs Daniel's OK to download Noto Sans SC/KR), then zh/ko e-mails.

## 2026-09-26 — Claude — e-mail footer per language + dependency cleanup (0 warnings)
- Footer/sign-off now in the recipient's language (`render_email(html, to)` looks up `users.preferred_language`): Daniel's "From Team VokalBoard.com" + translations for 7 languages. Old Portuguese seed and new English default count as built-in; custom admin text still goes to everyone. Admin form hint added.
- passlib → bcrypt directly (`app/auth.py`; same $2b$/12 rounds/72-byte truncation — proven compatible both ways); ReportLab 4.2.5 → 4.5.1; `httpx2` for TestClient. Suite now has 0 warnings; pip-audit clean.
- Found (backlog): badge + listing-alert e-mails are hardcoded German. Tests: 333 passed + 10 retention.

## 2026-09-26 — Claude — Romanian complete (UI 694/694 + e-mails)
- `app/locales/ro.json`: all public keys in 6 validated batches; informal "tu", comma-below ș/ț, glossary kept, fee = "onorariu", "negociabil". `ro` added to `EMAIL_LANGUAGES` with copy in all e-mail functions.
- Rendered /, /board, /login, /register in ro: no raw keys. Tests +1; 332 passed + 10 retention. AI draft — native review pending. Next languages: zh → ko (CJK font first).

## 2026-09-26 — Claude — Spanish e-mails (+ 2 e-mail bugs fixed)
- `app/email_localization.py`: "es" copy in all 15 e-mail functions; `es` in `EMAIL_LANGUAGES` (guard test covers every function/variant).
- Fixed: "vacancy filled" e-mail had hardcoded Portuguese ("A vaga em") for every language; verification/password-reset ended in English "N hours" for everyone ("Dieser Link ist 24 hours.") → one full sentence per language (`_VALID_FOR`).
- Found, NOT fixed (in HANDOFF backlog): the shared e-mail footer/signature is a single admin setting defaulting to Portuguese.
- Tests: +1; email/i18n tests pass.

## 2026-09-26 — Claude — #55 Match phase 2: one source for a listing's voice/fee
- Job listings keep voice/fee only in `listing_vacancies`; the copy on `listings` is cleared and blocked by constraint `listings_job_terms_live_in_vacancies`. Self-ads keep their own columns (moving them to vacancies would have pulled them into invitations/slots). View `listing_terms` merges both; `app/listing_terms.py` has the card summary join (same display rules as the old copy).
- Readers switched: card queries, fee ordering (`compatibility.py`), home matching, board voice filter, "search people for my listing", e-mail alerts + urgent reminder (now lists of voices). Behaviour fixes: multi-voice listings now match each voice (before: board filter never, home/alerts everyone); new-job alerts no longer go to every singer.
- Migration `2026-09-26_listing_terms.sql` (+ schema.sql, CONSOLIDATED) verified. Tests +3 (`test_listing_terms.py`); 330 passed + 10 retention.

## 2026-09-26 — Claude — Spanish UI complete (es 694/694)
- `app/locales/es.json`: all public keys, applied in 6 validated batches via `scripts/i18n_tool.py` (placeholders checked); informal "tú", glossary kept (Notas, Matches, Digital Pass, Rechnungmaker, Tangará), fee = "caché", negotiable = "a convenir". AI draft — native review pending; e-mails still fall back to English (phase 3).
- Also fixed "nota/Note" → "Nota" (currency name) in 5 core-language texts; Italian gender ("alla prossima Nota").
- Rendered /, /board, /login, /register in es: no raw keys. i18n tests pass. Next: #55 Match phase 2.

## 2026-09-26 — Claude — Messenger M6: daily e-mail limit + report queue — Messenger DONE
- `messenger.claim_daily_email()` (atomic UPDATE … RETURNING on `users.message_email_sent_at`): max 1 "new messages" e-mail per recipient per 24 h.
- Admin dashboard "Reported messages" (text snapshot, reporter, reported user); `POST /admin/message-reports/{id}/{dismiss|remove}` God Mode only + `audit_log`; remove deletes the message.
- `docs/specs/MESSENGER.md` marked IMPLEMENTED with final decisions + as-built notes. Tests +2; 327 passed + 10 retention; bandit clean on messenger code.

## 2026-09-26 — Claude — Messenger M5: desktop bubble + chat windows
- `messenger.js` dock: popup bubble on a new message → click opens a 320×420 chat window bottom-right (navy header: name, minimize, close), up to 3, restored across pages (sessionStorage) and when a window becomes wide; minimized windows only peek (`/since?peek=1`, nothing marked read). JSON send `POST /messages/c/{id}/post` (CSRF, same rules/side effects as the page). Dock not rendered on /messages pages; hidden < 1024 px. CSS cache `-4`, JS `-3`.
- Browser-verified (Chromium 1280 px): bubble → window → reply (accepts the request) → minimize → survives navigation → close; dock hidden at 390 px. Tests +2. Next: M6.

## 2026-09-26 — Claude — Messenger M4: live updates
- `messenger.poll_summary()` + `unread_messages_notification()` (synthetic, after 5 minutes unread); `render.py` uses them (header count = unread chats + requests). JSON `/messages/unread-count`, `/messages/c/{id}/since` (participants only). The immediate "new_message" bell entry is gone (Daniel: after 5 minutes).
- `app/static/js/messenger.js`: badge every 60 s, open thread every 5 s → 30 s when idle, paused in background tabs; textContent only. Red `.badge-alert` on Messages links and on ☰ (phones). CSS cache `20260926-3`.
- Tests: +2 route tests; 323 passed + 10 retention. Next: M5 desktop bubble.

## 2026-09-26 — Claude — Messenger M3: chat page
- `messages.html` rebuilt: conversation list (Inbox | Requests with highlight, All | Unread, "!" in the last 10 days) + thread (bubbles, listing context, accept/decline banner, pending note, hide, block, report per message, composer). `app/routers/messages_routes.py` rewritten thin; `/messages/sent|trash|{id}` redirect; `/messages/new?to=` opens an existing conversation. `message_detail.html` removed; brand-contract baseline refreshed for these two templates only (deliberate redesign). Style: `style.css` Messenger block (tokens only), cache `20260926-2`. 26 i18n keys (5 langs); retention warning = Daniel's wording.
- Tests: `tests/test_messenger_routes.py` (4). 321 passed + 10 retention. Next: M4.

## 2026-09-26 — Claude — Messenger M2: rules service
- New `app/messenger.py`: block > contact/Match > request (1 message until accepted; reply = accept; declined stays silent), accept/decline/hide, report (recipient only, text snapshot), list/thread/unread in single queries, never exposes read status. `/messages/send` now uses it (rate limits unchanged, 429 kept).
- Tests: `tests/test_messenger.py` (10); throttle test now seeds a contact pair (strangers are limited to 1 message anyway). Next: M3 chat page.

## 2026-09-26 — Claude — Messenger M1: schema (per-pair conversations, 60-day expiry)
- `db/migrations/2026-09-26_messenger.sql` (+ schema.sql, folded into CONSOLIDATED): `conversations` (request/active, per-side hide), `contact_pairs`, `message_reports`, `messages.conversation_id`, `users.message_email_sent_at`; backfill (both sides wrote → active + legacy contact; one-way → request). Verified idempotent + pg_dump-identical.
- Trigger files every message into its pair's conversation and drops an expired conversation's history before a new message; `visible_messages` = conversation active within 60 days; retention worker deletes conversations at 60 days (was ~30+60). `warning_days` → last 10 of 60 days.
- Tests: retention tests updated to the 60-day rule; 307 passed + 10 retention. Next: M2 (see HANDOFF §3).

## 2026-09-26 — Claude — Notas v2 implemented (N1–N5)
- **N1** `db/migrations/2026-09-26_notas_v2.sql` (+ schema.sql, folded into CONSOLIDATED): `credit_ledger.category/expires_at`, `credit_lot_usage`, backfill (existing = earned, 18 months from rollout). Verified idempotent + pg_dump-identical.
- **N2** `app/notas_wallet.py`: lots, purchased-first spend order, debts, lazy expiry, category-correct refunds; `credit_in_tx`/`debit_in_tx`. Urgency purchase + urgent-match reward now go through it (no direct ledger inserts left).
- **N3** `app/notas_expiry.py` in the retention worker: write-off + 30-day notice (notification + e-mail, 5 langs). **N4** `/notas` split/expiry/history tags; `/agb`, `/widerruf`, Stripe in `datenschutz`, footer links.
- **N5** `app/notas_purchase.py` + `/webhooks/stripe`: Checkout with server-side prices, waiver consent in PaymentIntent metadata, idempotent purchase/refund/dispute handling; gated by Stripe keys + Capitalism Mode. CSP `form-action` now allows checkout.stripe.com (redirect would have been blocked). `stripe==15.6.1`.
- Fixed: "Notas" translated as "Punkte/Noten" (de) / lower-cased (pt/en/fr/it) in 9 keys. Browser-checked /notas, buy page (320px), legal pages.
- Tests: +16 (`test_notas_v2.py`, `test_notas_purchase.py`); 307 passed + 10 retention, 0 failed; bandit clean on new code; pip-audit clean.

## 2026-09-26 — Claude — automatic account purge (6-month window)
- New `app/account_purge.py`, called by the hourly `retention_worker` (no extra Railway service): erases accounts deactivated > 6 months ago — user row + cascades, their Matches (→ evaluations, Match invoice drafts) and avatar file. Per-account savepoint; logs counts only.
- Bug found: the old manual script could never delete a user who had a Match (`job_matches` FKs are RESTRICT) and would abort the whole run there. `scripts/purge_deleted_accounts.py` is now a thin wrapper (`--dry-run`).
- Deletion notice (`delete_account_help`, 5 langs) now says Notas are kept for 6 months, then erased. `docs/specs/NOTAS_V2.md`: Kleinunternehmer (§ 19 UStG, Stripe Tax off, invoice footer, thresholds), no lawyer review.
- Tests: +3 (`tests/test_account_purge.py`). 291 passed + 10 retention, 0 failed.

## 2026-09-26 — Claude — Notas v2 + Messenger designed (docs only)
- Reviewed a Gemini proposal against the real repo (it assumed Alembic/JWT/UUID/ORM models/WebSockets — none exist) and designed both features with Daniel instead.
- New DRAFT specs: `docs/specs/NOTAS_V2.md` (purchased spent first + never expire; earned expire after 18 months per credit; 6-month reactivation then erasure; tax records kept by Stripe/accounting; Terms + withdrawal pages missing → prerequisite) and `docs/specs/MESSENGER.md` (per-pair chat, message requests, Match = consent, 60-day expiry with day-50 "!" tooltip, polling, desktop dock / mobile badge, never "seen").
- `CLAUDE.md` §3.B: `note_transactions` → real table `credit_ledger`. No code changed, no tests needed. Next: Daniel approves specs; tax status for Stripe.

## 2026-09-26 — Claude — language policy: es added, admin English-only for added languages
- Daniel's decisions: fr stays core; **es** added (with zh/ko/ro) for the **public site only**; admin stays English for added languages (core admin text untouched); moderators don't act on reports; German fee = "Honorar".
- `app/i18n_locales.py`: `page_language()` (used in `render()`: admin templates → English for non-core langs), `admin_only_keys()` scanner (0 today — admin is hardcoded English). `es` in `SUPPORTED_LANGUAGES`/`LANGUAGE_META`, `app/locales/es.json`. Tool scoped to public keys.
- Fixed hardcoded public text: Portuguese on the Match invoice pages + one English line on listing detail → 4 new keys (5 core langs). de fee label "Cachê*"→"Honorar*"; it "cachet"→"compenso" (3 strings). `permissions.py` docstring matches the moderator decision.
- `docs/I18N.md` rewritten as the per-language implementation route (phases 0–5, order es→ro→zh→ko, glossary incl. fee terms). `CLAUDE.md` §1 language line updated.
- Tests: +4 (admin scope unit + end-to-end, es registered, no admin keys in locale files). 288 passed + 10 retention, 0 failed.

## 2026-09-26 — Claude — a11y fixes, #52 bug, security scan, i18n groundwork, docs reorg
- **A11y/visual (Codex's 25/09 list, browser-verified at 320px):** labelled vacancy fields (`listing_form.html`, `listing-form.js`, 2 new i18n keys); help-text overlap after file inputs/buttons (`style.css`); invoice preview amounts no longer break (`brand.css`); mobile header 251→130px (`base.html` `.nav-dup`). Cache version `20260926-1`, style.css + listing-form.js now versioned too.
- **Bug (#52):** "publish anyway" did nothing — `requestSubmit()` inside the submit handler is ignored by browsers; now deferred. Verified 6 cases (de/en, job/self-ad, fee/no fee, OK/Cancel).
- **Security:** bandit 0 high (7 B608 reviewed = false positives); pip-audit prod clean; pytest → 9.0.3.
- **i18n groundwork:** `app/locales/{zh,ko,ro}.json` + `app/i18n_locales.py` loader (fallback to English), `scripts/i18n_tool.py` (status/todo/apply/check with placeholder validation), `docs/I18N.md`, `tests/test_i18n_locales.py` (6 tests incl. e-mail language guard).
- **Organized:** `VISUAL_ROLLOUT.md` → `docs/`; `preview4.html` + `Claude outputs/` → `docs/archive/` (moved, not deleted); `docs/README.md` index.
- Tests: 284 passed + 10 retention, 0 failed. Next: `HANDOFF.md` §3.

## 2026-09-26 — Claude — 18 failing tests fixed; suite green
- **Product bug:** `admin_routes.py` periodic-mail create/edit used `Form(...)`, so a blank field returned a raw 422 page instead of the friendly `error=dados_invalidos` redirect → now `Form("")`, service validation unchanged.
- **Stale tests after 19/09 changes (not product bugs):** vacancy rows are now required for job listings (new shared `job_vacancy_fields()` in `test_security.py`, used by report-moderation/punishments/urgency, 10 tests); level-2 admins may open `/admin`; `/notas` needs verified email; profile submenu (Digital Pass replaced the disabled placeholder) and profile form/fieldset counts; the logged-in home redirects to the wizard (post check now anonymous); the CV PDF privacy test now checks extracted text (the raw-byte check always hit the xref table; confirmed a public phone does appear).
- **Flaky test fix:** `_fake_ip()` pool 254 → ~131k addresses (random collisions hit the 5-registrations/IP/hour limit → intermittent 429).
- New `scripts/test_in_docker.sh`: isolated test DBs + throwaway container; also runs the retention tests, which were always skipped before.
- Tests: **278 passed + 10 retention, 0 failed**, 3 full runs. Next: `HANDOFF.md` §3.

## 2026-09-26 — Claude — token optimization pass 2 (docs/config only)
- `CLAUDE.md` §0: "Large files — never read whole" map (i18n.py ~170 KB, schema.sql, style.css, big routers…) + hygiene rules (grep→range reads, `git diff --stat`, short test tracebacks, plan read per P-section).
- New `.ignore` (ripgrep search-ignore, not gitignore): seed_cities.sql, brand_contract.json, `Claude outputs/`, preview4.html, icons.svg, fonts. Verified `rg --files` skips them.
- `AGENTS.md` 91→20 lines: migration rules/history moved verbatim to `docs/MIGRATIONS.md`, short summary kept. `CHANGELOG_2026-09-14.md` → `docs/changelog-archive/` (git mv).
- No code changed, no tests run. Next: 18 failing tests (`HANDOFF.md` §3).

## 2026-09-26 — Claude — document hierarchy + changelog split (docs only)
- New main hierarchy for all AIs (Daniel's decision): `CLAUDE.md`/`AGENTS.md` → **`HANDOFF.md`** → `AI_CHANGELOG.md` → `docs/changelog-archive/` (grep only). Added as `CLAUDE.md` §0 and at the top of `AGENTS.md`.
- New `HANDOFF.md`: current state (uncommitted visual batch, 18 failing tests, open a11y issues, open decisions, backlog, constraints).
- Entries up to 2026-09-19 moved verbatim to `docs/changelog-archive/AI_CHANGELOG_until_2026-09-19.md` (this file went from 5,973 to ~280 lines). New entry rules in this file's header (≤10 lines, rotation at ~300).
- `CLAUDE.md` §1 visual-identity paragraph condensed (points to the MANIFEST files + archive); fr-vs-es mismatch flagged inline.
- No code changed, no tests run (docs only). Next: Claude investigates the 18 failing tests (`HANDOFF.md` §3).

## 2026-09-25 — Codex — testes da revisão 20260925-1 e problemas NÃO corrigidos

Após a implementação sem testes, Daniel autorizou testar e encontrar problemas, expressamente SEM aplicar alterações. O limite de uso interrompeu o login de QA; na retomada foram concluídas somente as verificações internas pendentes, sem repetir a suíte completa. Esta entrada atualiza o estado de validação das entradas anteriores, preservadas abaixo.

### Execução e cobertura efetivas
- Versão atual de `app/` e `tests/` copiada somente ao contêiner local `vokalboard-brand-qa`; iniciado esse contêiner, com banco confirmado `vokalboard_brand_retention_test_20260924` e e-mails em backend console. Banco principal/produção não utilizados.
- Suíte completa: **267 passed, 18 failed, 3 warnings, 89,60s**. Mesmos 18 testes falhos anteriormente registrados; testes de marca passaram. Isso não prova que todas as falhas sejam bugs de produto ou que sejam causadas pelo visual; investigar expectativas/fixtures antes de corrigir.
- Navegador confirmou CSS `20260925-1`, fundo geral #F5F7FA, Manrope carregada e hero sem gradiente.
- **68 medições de largura** em 320/390/768/1440px: 7 páginas públicas × 4, 7 internas × 4 e 3 administrativas × 4; sem overflow horizontal da página. Isso NÃO certifica legibilidade interna dos componentes.
- Páginas internas: perfil privado/público fictício, formulário de anúncio, mensagens, Hall da Fama, Rechnungmaker avulso e Notas. Administrativas: e-mails, formulário de e-mail periódico e Red Zone. Editor do e-mail periódico confirmou monoespaçada 16px/24px; o editor de código da tela geral de e-mails não estava exposto nesse estado e não foi certificado.
- Menu móvel abriu (`aria-expanded=true`) e fechou com Escape (`false`). Botão Back desativado no wizard apresentou fundo #E3E7EF/texto #526176. Console observado sem warnings/errors. Viewport restaurado e aba temporária fechada.
- Fixtures sintéticas criadas após a suíte; uma conta fictícia foi promovida apenas no banco isolado para inspecionar Admin. Nenhuma mudança de privilégios em produção nem envio real de e-mail.

### Problemas encontrados — pendentes, nenhuma correção aplicada

| Prioridade | Problema / reprodução | Evidência |
|---|---|---|
| Alta (legibilidade) | `/rechnungmaker?tab=avulso`, viewport 320px: tabela e totais da prévia quebram textos/valores em muitas linhas. | Screenshot mostrou valores como `0.00 EUR` fragmentados nas células; papel com 273px de largura e totais restritos a cerca de 143px. Ausência de overflow da página não impediu a degradação. Rever layout da prévia sem alterar cálculo/emissão de PDF. |
| Média (sobreposição) | `/profile/wizard`, etapa foto, 320px: ajuda invade o campo de arquivo. | Borda inferior do input em y=694,19 e início da ajuda em y=686,19; `margin-top:-8px` computado. Sobreposição vertical de 8px confirmada na imagem. |
| Média (acessibilidade) | `/listings/new`: campos da linha de vagas sem rótulos adequados. | Voz e moeda apareceram como combobox sem nome, quantidade como spinbutton sem nome na árvore; voz/quantidade/cachê/moeda não possuem label associado nem aria-label na inspeção. Quantidade/cachê dependem de placeholder; não substitui rótulo visível persistente. |
| Baixa (usabilidade visual) | Cabeçalho autenticado muito alto no mobile. | Aproximadamente 251px em 320/390px e 233px em 768px, contra 92px em 1440px. Navegação ocupa espaço excessivo antes do conteúdo, embora sem overflow. É avaliação de usabilidade, não falha funcional confirmada. |

### Pendências e próximo passo
- Não verificados: celular físico, Safari/Firefox, zoom real 200%, leitor de tela, performance e todos os estados/idiomas. Fontes CJK empacotadas continuam pendentes.
- As 18 falhas da suíte mantêm a distribuição já documentada: moderação de denúncias (3), acesso financeiro (1), mascote (1), submenu de histórico (1), punições/estornos (4), privacidade no PDF de CV (1), e-mails periódicos (1), estrutura do perfil (2), AdminPosts (1), urgência (3). Correções funcionais ficam com Claude.
- Próximo passo verificável: somente após autorização, corrigir os problemas de apresentação/acessibilidade acima e repetir seus cenários; não marcar conformidade visual integral como concluída.
- Na tarefa de testes, nenhum arquivo do repositório foi alterado. **Nesta solicitação de registro, somente `AI_CHANGELOG.md` foi alterado**; mudanças preexistentes preservadas. Nenhum teste repetido agora, nenhuma correção, deploy ou migração executados.

### 2026-09-25 — Codex — fechamento das correções estéticas, SEM EXECUÇÃO
- `base.html`: versão do CSS `20260925-1` para invalidar cache. `tests/test_brand_visual.py`: apenas atualizadas as duas referências esperadas à versão; arquivo NÃO executado, critérios não removidos.
- `VISUAL_ROLLOUT.md`: nova revisão marcada como implementada mas não verificada; testes antigos não certificam estas mudanças. Exceções de editores monoespaçados e geometria circular documentadas.
- Entregue nesta sequência: correções de fundos/cores legadas, espaçamentos/raios identificados no audit, hierarquia de texto, estados hover e organização de fontes dos editores. Código funcional do Claude preservado.
- Pendência de implementação explícita: família CJK complementar empacotada/licenciada; nesta revisão só foi melhorada a seleção de fallbacks locais, sem prometer cobertura uniforme.
- Pendentes por solicitação de NÃO testar: navegador, celular físico, outros navegadores, zoom, leitor de tela, contraste renderizado, performance e regressões. As 18 falhas funcionais anteriores permanecem para Claude.
- Testes/build/site/browser/Docker: NENHUM executado nesta sessão. Sem publicação, deploy, migração ou acesso ao banco.
- Próximo passo verificável: quando autorizado, validar `20260925-1`, em especial navegação mobile maior e prévia da fatura; não declarar conformidade estrita antes disso.

### 2026-09-25 — Codex — lote visual: tipografia e exceção de editor (SEM TESTES)
- `brand.css`: navegação 16/24 (inclusive mobile), labels 14/20, títulos de cards do perfil 20/28 sem caixa alta, metadados 14/20, corpo da prévia de fatura 16/24 e títulos 24/32. Mantidos números tabulares; sem editar geração de PDF.
- `admin_emails.html` e `admin_periodic_mail_form.html`: fonte inline substituída pela classe `code-editor`, centralizada em brand.css. Monoespaçada preservada como exceção intencional para HTML cru, agora com entrada 16/24. Campos/validações/ações intactos.
- Fallbacks CJK agora específicos por idioma (`:lang(zh)`/`:lang(ko)`), incluindo opções locais Windows/macOS/Linux. NÃO há nova fonte CJK empacotada; cobertura consistente entre dispositivos continua pendente. Nenhum download/recurso remoto adicionado.
- Testes/site/build/navegador: NÃO executados. Próximo: atualizar cache e handoff, registrando implementação não verificada e pendência de fontes CJK locais licenciadas.

## 2026-09-25 — Codex — lote visual: fundos, espaçamento e raios (SEM TESTES)
- Autorização atual: implementar correções estéticas sem executar site, testes, build ou navegador. Alteração anterior do log preservada. Código funcional continua reservado ao Claude.
- `app/static/css/brand.css`: fundos sólidos Mineral para hero, convite e destaque de perfil; cores/bordas dos componentes reais de vagas normalizadas; espaçamento do perfil, formulários, mensagens, menus e hero alinhado à escala; raios de painéis/tags e bolha unificados; hover sem reduzir opacidade de texto.
- Nenhum campo, condição de exibição, ação, rota, regra ou banco alterado. Sem deploy.
- Testes executados: NENHUM, por solicitação expressa. Implementado, não validado em runtime; resultados de 24/09 não certificam esta revisão.
- Próximo: tipografia e exceções de fonte, versão de cache e documentação de pendências.

## 2026-09-25 — Codex — checagem estática de aderência estrita ao padrão visual

**Pedido:** apenas checar design e registrar; não implementar nem executar aplicação/testes. **Conclusão: aderência parcial, NÃO estrita.** A camada compartilhada usa a identidade correta, mas não normaliza todos os componentes. A entrega anterior de uma camada visual não equivale a conformidade integral com o manual.

**Método e escopo:** leitura de AGENTS, log recente, instruções de marca v0.4, Manual Visual v1.0, `style.css`, `brand.css` e referências nos templates. Conferida a ordem de inclusão (`base.html:54–55`: style antes de brand), especificidade e estilos inline. Git inicialmente limpo. Sem abrir navegador, iniciar Docker, executar testes/build/scripts da aplicação, acessar banco ou alterar o design. Achados abaixo são de código, não nova observação de renderização. Medidas numéricas do manual são referências técnicas propostas, não aprovações individuais do Daniel; divergências são registradas como tal.

### O que está alinhado no código
- Tokens centrais em `style.css:18–55`: canvas #F5F7FA, superfície #FFFFFF, navy #17283F, violeta #635BDE, hover #5148C5, cores semânticas e raios 16/8/6.
- `brand.css:3–4`: Manrope como fonte principal e fundo geral Mineral. Oito declarações locais de fonte em `style.css:69–132` cobrem pesos 400/500/600/700, latin/latin-ext; licença presente no projeto.
- Hierarquia global h1 32/40 desktop e 28/36 mobile, h2 24/32 e h3 20/28 em `style.css:273–282`; existem exceções locais listadas abaixo.
- `brand.css`: container com margens internas de 32px desktop/16px mobile, cards gerais 24px/16px, grid de anúncios com gap 16px, assinatura final navy e foco visível.
- Gradientes antigos de `.profile-hero`, `.notas-balance-box` e `.red-zone-hero` são sobrescritos por fundos sólidos em brand.css; não contá-los como desvios ativos apenas por aparecerem em busca textual. Mascote administrativo antigo e animação de patrulha também foram substituídos/desativados.

### Divergências e pendências sustentadas pela leitura

| Item | Evidência atual | Comparação com o manual / próxima revisão visual |
|---|---|---|
| Fundos com gradiente residual | `style.css:1084–1097` `.hero`; `:2973–2993` `.invite-friend-box`; `:2997–3008` `.profile-highlight-banner`. Referenciados por home, hall_da_fama e public_profile; sem sobrescrita correspondente em brand.css. | Manual §5: superfícies predominantemente branca/Mineral, não usar gradiente como decoração padrão. Estes componentes ainda usam gradiente e `--accent2`/`--accent2-light`, cores extras fora da tabela Mineral. Não considerar normalização concluída. |
| Fundos/bordas legados nas vagas | `style.css:1516–1560`: `.logistics-flag` #f0f5f0; `.listing-vacancies-box` #fbfcfc/#e5e7e7; `.vacancy-apply-status` #eef2ee. | Não correspondem aos tokens definidos. O adapter estiliza `.vacancy-card`/`.vacancy-row`, mas não estes componentes; revisar os seletores reais de listing_detail. Cores de `.vacancy-fee`/`.vacancy-slots`, por outro lado, já são sobrescritas. |
| Espaçamento não unificado | `.profile-edit-grid` gap 20px (`style.css:192–197`); `.stacked-form` gap 14px (`:940–943`); `.hero` padding 36px 28px, margem 28px, ações gap 10px/margem 18px (`:1084–1097`); `.message-row` padding 20px (`brand.css`). | Manual §6 enumera 4/8/12/16/24/32/48 e separação de cards 16px. Esses valores escapam da escala enumerada (mesmo quando múltiplos de 4). Margens/paddings adicionais permanecem em componentes específicos; o container global correto não os elimina. |
| Raios não unificados | `.profile-menu > .profile-menu-links` 10px (`style.css:138–145`); `.listing-vacancies-box` e `.invite-friend-box` 12px; `.profile-highlight-banner` pill; `.message-body-box` preserva canto de 4px (`:678`). | Referência §6: painel/card 16px, controle 8px, etiqueta 6px. Eventuais exceções de linguagem de chat/badge devem ser deliberadas e documentadas, não assumidas como aderência estrita. |
| Tamanhos de texto e hierarquia local | `.profile-hero .card h3` 0.78rem/caixa alta (`style.css:3114–3120`); `.hall-fame-meta` 0.78rem (`:2950` aproximadamente); `.invoice-paper` 0.82rem e kicker 0.7rem (`:3474–3516`); `.stacked-form label` 0.9rem (`:948–954`); navegação mobile 0.875rem (`brand.css`). | Manual §4: card 20/28, metadados/rótulos 14/20, campos/corpo/navegação 16/24. A regra global não vence todos estes seletores. Na fatura, algumas partes já sobem para 14px, mas o corpo e kicker continuam menores. Conferir papéis semânticos antes de ajustar; não aumentar textos indiscriminadamente. |
| Fontes fora de Manrope em editores | `admin_emails.html:85` e `admin_periodic_mail_form.html:46`: inline SF Mono/Consolas/Menlo e 13px. | Inline prevalece sobre o adapter; portanto fonte/tamanho não são uniformes em todo o site. Monoespaçada pode ser apropriada ao editor de HTML, mas é exceção funcional a documentar, não trocar cegamente. Conteúdo do iframe de e-mail não herda CSS do site e foi excluído da entrega visual anterior. |
| Cobertura CJK não garantida | Só `app/static/fonts/manrope` empacotada; `brand.css:3` cita Noto/CJK/YaHei/Malgun como alternativas do sistema, sem fornecer essas fontes. | Manual §4 exige planejar família complementar e validar glifos. A escolha efetiva pode variar por dispositivo; esta leitura não certifica aparência consistente em chinês/coreano. |
| Opacidade residual nos estados hover | `.button-primary:hover { opacity:0.95 }` (`style.css:1077–1080`) e `.invite-cta-summary:hover { opacity:0.95 }` (`:1585`) não têm override específico de opacity no hover em brand.css. | Manual §3 das instruções/§5 do manual: não reduzir opacidade de texto essencial. O background novo não remove essa propriedade; revisar estados hover, não apenas normal. |

### Como retomar, sem implementar nesta solicitação
1. Quando houver autorização para ajustes, normalizar primeiro os fundos/seletores reais, depois escala de espaçamento/raios e tipografia; manter funções, campos, permissões e trabalho do Claude.
2. Documentar exceções intencionais (editor de código, bolha de conversa) em vez de afirmar uniformidade absoluta.
3. Depois dos ajustes autorizados, conferir a cascata no navegador e repetir responsividade/zoom/acessibilidade. A checagem estática atual não certifica carregamento efetivo de fontes, contraste composto, recorte ou espaçamento renderizado.

**Arquivo alterado agora:** somente `AI_CHANGELOG.md`. **Testes executados:** nenhum, conforme pedido. **Próximo passo verificável:** revisar esta lista e, apenas sob autorização, aplicar correções estéticas por lote. Nenhuma implementação, deploy ou migração feita.


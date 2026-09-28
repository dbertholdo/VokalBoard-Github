# VokalBoard — Shared AI changelog (recent entries only)

**Read `HANDOFF.md` first** — it holds the current state. This file is history, not a briefing: read only the top entry unless you need more context. See the "Document hierarchy" section in `CLAUDE.md` / `AGENTS.md`.

**Entry rules (from 2026-09-26):**
- New entries go at the top, in English, **≤ 10 lines**: what changed (files), tests run + result, next safe step. No long caveat lists — put open items in `HANDOFF.md` instead.
- Record only verifiable facts. No tokens, passwords, database URLs or personal data.
- Never delete entries; correct them with a new entry.
- **Rotation:** when this file passes ~300 lines, move the oldest entries verbatim to `docs/changelog-archive/` (one file per period). Moving is not deleting.
- Older history: `docs/changelog-archive/` (`AI_CHANGELOG_until_2026-09-19.md`, `AI_CHANGELOG_2026-09-21_to_2026-09-24.md`) — grep it, never read it in full. Also see git history and `docs/changelog-archive/CHANGELOG_2026-09-14.md`.

## 2026-09-28 — Claude — 6c flags + 6 payment QR codes
- 6c: language menu uses SVG flags (flag-icons 7.2.3, MIT; `app/static/img/flags/` + MANIFEST/LICENSE) instead of emoji.
- 6: `app/invoice_qr.py` — Swiss QR-bill (qrbill → SVG → svglib drawing, own last page, doc language; skipped for QR-IBAN/unreadable address), GiroCode EPC QR (ReportLab widget) via new `girocode` checkbox; IBAN check with python-stdnum. New pinned deps in requirements.txt (pip-audit clean).
- 3 new texts × 9 langs (checkbox, "?", QR-bill note). Tests: tests/test_invoice_qr.py (5); full suite + bandit green.

## 2026-09-28 — Claude — 5b: cancel a confirmed Match, warnings, 30-day block, lift block
- `app/match_cancellation.py`: rules (7-day window, reason ≥ 50), cancel transaction (slot −1, listing active, invoice draft deleted, urgency reward debited), warn/dismiss, 3 warnings → `matches_blocked_until` +30 d, `lift_block` (Daniel's "unban").
- Blocked users can't apply/invite (`create_invitation`) or accept (`respond_invitation`) → `invitation_error_blocked`.
- UI: cancel box / "too late — contact {name}" on Matches cards; `/admin/cancellations` (+ blocked list, nav badge); e-mails `match_cancelled_email`, `match_warning_email` + bells (9 langs, 14 UI keys).
- Migration `2026-09-28_match_cancellations.sql` (tolerated missing). Tests: tests/test_match_cancellation.py (6); full suite 416 passed / 7 skipped + retention; bandit clean.

## 2026-09-28 — Claude — item 5: Rechnungmaker v2 phase 1 (+ Match fee pre-fill)
- Country (DE/AT/CH/Other) + invoice language (DE/EN/FR/IT) + 5 currencies; tax options/notes from `invoice_countries.py`; reverse charge needs client VAT ID.
- `invoice_pdf.py` + `_invoice_preview.html`/`invoice_preview.js` follow invoice language + country formats; footer "Rechnungmaker"; JS builds everything from embedded JSON (no duplicated tax rules).
- `app/invoice_form.py`: shared form→document, prefs (migration `2026-09-28_invoice_prefs.sql`, tolerated missing), Match pre-fill (fee, currency, event date, client, title); drafts store the v2 form, legacy drafts still build.
- "?" help on every field (site language, 9 langs); Daniel's "Invoice the person who posted the job" checkbox; no-JS Apply button. `invoice_tax_presets.py` removed.
- Tests: tests/test_rechnungmaker_v2.py (6) + updated cleanup/page tests; full suite 410 passed / 7 skipped + retention; bandit clean. Also added 5b (cancel a Match) to HANDOFF.

## 2026-09-28 — Claude — 4b SEO
- `app/seo.py`: canonical + hreflang per page (render context `seo`), JSON-LD WebSite/Organization (home) + JobPosting (active seeking_* listings), SITE_BASE_URL for public URLs, optional GOOGLE_SITE_VERIFICATION meta.
- base.html: pages' `{% block title %}` finally used (+ " — VokalBoard"); `meta_description` / `structured_data` blocks.
- Home/board keyword titles + descriptions + landing intro (`seo_*`, 9 langs); listing title "Title — City"; sitemap: xhtml:link alternates, /rechnungmaker, /agb.
- Tests: tests/test_seo.py (4); full suite 404 passed / 7 skipped + retention; bandit clean.

## 2026-09-28 — Claude — item 4: menu reorganization
- Top bar: Rechnungmaker · Jobs▾ (`_jobs_menu.html`) · People · Messages · Matches (badge = pending + evaluations) · bell · avatar▾ (`_profile_menu.html`: profile, Rewards, Admin, Log out) · language. Home link dropped (logo).
- ONE Matches page: `_matches_tabs.html` on /invitations (Open) and /profile/matches?view=confirmed|history; `/matches` entry redirect; admin ?user_id= still sees all.
- `match_service.count_pending_for_user` (render.py badge + /matches share it). Phone side menu = same order/partials. 8 new keys (9 langs).
- Tests: Matches entry + views split; menu test updated; brand contract regenerated; full suite 400 passed / 7 skipped + retention; bandit clean.
- Added 4b SEO to HANDOFF (Daniel's request).

## 2026-09-28 — Claude — 3b bots out of Analytics, 3c ticket spam
- 3b: `app/traffic.py` — human visits only via JS beacon (POST /visit, 1/session/12 h); bots/empty UA/headless + probe paths → `bot_traffic_daily` (per day+bot, no IP/URL); Red Zone → Bot traffic (`/financeiro/bots`, level 3). Migration `2026-09-28_bot_traffic.sql` (bots unrecorded until applied).
- 3c: bug report members-only (button + route); honeypot + 5 tickets/hour per IP and per account (`app/rate_limit.py`, in-memory); likely-spam heuristic (2 of: links, sales words, anonymous; computed live); single + bulk delete with password + audit_log.
- Fixed: bug-report errors were never shown on the page; `support_rate_limited` key (9 langs).
- Tests: tests/test_traffic.py + support ticket tests; full suite 398 passed / 7 skipped + retention; bandit clean.

## 2026-09-28 — Claude — item 3: referral rewards v2 + anti-fraud
- `app/referrals.py`: 1 Nota per referral after e-mail + real activity; limits 3/day 20/month; same-IP (3+) → flagged; admin approve/reject/reverse (`referral_admin_routes.py`, `/admin/referrals`, password + audit_log, nav badge).
- `app/email_identity.py`: identity (Gmail dots/+tags) + throwaway-domain list. Signup IP stored only as salted hash, referred users only.
- Migration `2026-09-28_referral_rewards.sql` (additive); code falls back to the old 1-per-10 rule until applied.
- Texts: `notas_how_it_works_v2`, `notas_referrals_pending_hint`, `notas_reason_referral_*` (9 langs); Terms 3.5 en+de.
- Tests: tests/test_referral_rewards.py (7); full suite 391 passed / 7 skipped + retention; bandit clean.

## 2026-09-28 — Claude — items 1+2: Rechnungmaker name translated, visitor gate
- `nav_rechnungmaker`/`invoice_go_to_rechnungmaker` translated in 8 langs (de unchanged); rechnungmaker.html h1/title use the key; `rechnungmaker_subtitle` → tagline.
- pt: 14 UI strings + 4 e-mails say "fatura" instead of "Rechnung". Invoice document/PDF stays German.
- Visitors/unconfirmed: blurred inert empty tool + card (`rechnungmaker_gate_*`, 9 langs), no redirect; `/login?next=` (safe_path, same-site only).
- Tests: test_rechnungmaker_page.py (gate, names, next); full suite 384 passed / 7 skipped + retention. Cache: style/fonts-cjk 20260928-2.

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


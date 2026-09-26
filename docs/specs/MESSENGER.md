# Spec — Messenger (backlog #53): per-pair chat, requests, 60-day expiry

**Status:** DRAFT — designed with Daniel 2026-09-26, not implemented.
Replaces Gemini's "Prompt 2" (it assumed JWT/WebSockets/UUID/ORM models/a `matches` table and permanent history — none of which fit this repo or the no-storage rule).

## Decisions (Daniel, 2026-09-26)

| # | Rule |
|---|---|
| D1 | **One conversation per pair of people** (like WhatsApp). Messages sent from a listing show a small context label ("About: *listing title*"). |
| D2 | **Everyone can message everyone**, but a first message from someone without prior contact lands in **Requests** (highlighted while unread). **Accept** → moves to the inbox and the pair counts as "had contact" permanently. **Decline** → hidden; the sender is not told. Until accepted, the sender can send **at most 1 message**. |
| D3 | No request needed when the pair **has had contact before** (accepted request, even if that chat was deleted since) **or has a Match** (a Match = consent from both sides). **Blocking always wins.** |
| D4 | **Each conversation is deleted 60 days after its last message** (any new message resets the timer). This applies to Match chats and pending requests too. |
| D5 | From **day 50 to 60**: a "!" icon with a hover tooltip: "In N days this chat will be deleted for inactivity." |
| D6 | Text + emoji only (existing: plain text, ≤ 2000 chars). **Never show "seen" or online status.** |
| D7 | **Desktop (by screen width):** floating chat windows (bottom right, minimize to a tab with unread count, close). **Mobile:** the Messages menu item shows a red dot with the unread number. |
| D8 | Both: a Notification Center entry when a message has been **unread for 5 minutes**. |
| D9 | Updates by **polling, only while the tab is visible**: unread badge every 60 s; open chat every 5 s, slowing to 30 s after 2 idle minutes; nothing in background tabs. No WebSockets (cost/complexity; revisit if traffic grows). |

## What exists today (reuse)

`messages` (sender → recipient, `body` ≤ 2000, `read_at`, per-side trash, `listing_id`), `/messages` inbox/sent/trash (`app/routers/messages_routes.py`), `blocked_users`, send rate limits, new-message e-mail, notification bell, unread count in the header. Retention today: archive 30 days after activity + delete 60 days later (≈ 90 days) — **changes to D4**.

## Data model (SQL migration, folded into the consolidated file)

- `conversations (id BIGSERIAL, user_low_id, user_high_id, status 'request'|'active', requested_by, declined_at NULL, created_at, last_activity_at, UNIQUE(user_low_id, user_high_id), CHECK(user_low_id < user_high_id))`. FKs `ON DELETE CASCADE`.
- `messages.conversation_id` (FK, cascade). Per-message trash columns are retired in the UI (a chat has no per-message trash); a per-user "hide conversation" flag replaces them.
- `contact_pairs (user_low_id, user_high_id, established_at, source 'accepted'|'legacy')` — the "had contact" marker that outlives deleted chats (D3). Erased with either account (cascade). Match pairs are checked live against `job_matches`, not copied here.
- Existing data: messages grouped into per-pair conversations; pairs where **both** sides have written → `active` + `contact_pairs(source='legacy')`; one-way history → `request`. `last_activity_at` = latest message.

## Rules in code (`app/messenger.py` service; routers stay thin)

- `can_message(sender, recipient)` → blocked (either way) → refuse; contact pair **or** Match → direct; else → request (1 message max until accepted).
- Retention worker: delete conversations (+ messages) where `last_activity_at + 60 days <= now()`; remove the old 30+60 archive logic for messages. Requests expire the same way.
- `read_at` stays internal only (unread counts, D8); never rendered to the other side.
- Account deactivated → the other side sees "Deactivated user"; account purged → its conversations are deleted (cascade), consistent with no-storage.
- Every UI string is an i18n key (5 core languages; added languages via `app/locales/`).

## UI

- `/messages` (all screens): left list with **Inbox | Requests (count, highlighted)** and **All | Unread** filters; right: the chat, text box, send. The "!" tooltip (D5) sits on the conversation in the list and in the chat header. Emoji: the operating system's emoji keyboard (Win + . / mobile keyboards) — no custom picker in v1.
- Desktop (≥ 1024 px): floating dock — up to 3 windows, minimize to a tab with an unread badge, close.
- Mobile: header/side-menu "Messages" with the red number badge.
- Notification Center: synthetic entry computed at page load ("unread message older than 5 minutes"), like the existing "profile incomplete" entry — no extra job.

## Endpoints (session auth + CSRF, same as the rest of the site)

`GET /messages/unread-count` (JSON, for the badge), `GET /messages/c/{id}` (page), `GET /messages/c/{id}/since?after=<id>` (JSON, polling), `POST /messages/c/{id}/send`, `POST /messages/c/{id}/accept`, `POST /messages/c/{id}/decline`, `POST /messages/c/{id}/hide`. Participants only (404 otherwise). Existing rate limits reused.

## Open (defaults proposed — Daniel can override)

- **New-message e-mail:** today one per message → with chat that becomes spam. Default: at most one e-mail per conversation per day, only if still unread after 30 minutes.
- **Desktop toast** on new messages (Gemini's idea): not in v1 unless wanted.
- **Report a message** to moderation: not in v1 (blocking covers the urgent case).

## Stages (each: code + tests + HANDOFF/changelog)

| Stage | Content | Tests |
|---|---|---|
| M1 | Schema + migration of existing messages | re-run on restored DB; pair grouping; legacy contact rules |
| M2 | `app/messenger.py` rules + send/accept/decline/hide routes | block > contact > Match > request; 1-message request limit; participant-only access |
| M3 | 60-day retention + "!" tooltip | timer reset on new message; day 50/60 boundaries; requests expire |
| M4 | `/messages` chat UI (list, Requests, filters) | render tests, i18n keys |
| M5 | Polling endpoints + mobile badge + 5-minute Notification Center entry | count correctness, hidden-tab pause (JS), no "seen" anywhere |
| M6 | Desktop floating dock | browser check 1024 px+ and 320 px (dock absent) |
| M7 | E-mail throttle | one e-mail/day/conversation |

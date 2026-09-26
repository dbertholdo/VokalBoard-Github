# Spec — Notas v2: purchased vs. earned, expiry, Stripe

**Status:** IMPLEMENTED 2026-09-26 (N1–N5, tested; migration pending like all others). N6 (go-live) needs Daniel: live keys, webhook, Capitalism Mode.

**As built — differences from the draft below:**
- Debits keep `category` NULL (a debit can span both categories); the split lives in `credit_lot_usage`. Only credits require a category (DB constraint).
- Stripe prices are set in code (`app/notas_purchase.BUNDLES`, `price_data`) — no Price IDs to create in the dashboard.
- Consent proof (Terms + waiver version and timestamp) is stored in the PaymentIntent **metadata at Stripe**, not via Stripe's `consent_collection` (which would need a ToS URL configured in the dashboard).
- Purchases require Stripe keys **and Capitalism Mode on**; God Mode can test while it's off.
- Purchase ledger key = `stripe_purchase:<payment_intent>`; refunds/disputes find the purchase by it — no Stripe API call and no extra table.
- Expiry job + 30-day notice (Notification Center + e-mail) run inside the hourly retention worker. "Already warned" is read from `notifications` (ledger stays append-only).
- Also fixed on the way: "Notas" was translated as "Punkte"/"Noten" (de) and lower-cased (pt/en/fr/it) in 9 keys — it's a name, never translated.
Replaces Gemini's "Prompt 1" (it assumed Alembic/JWT/UUID/ORM models and balance columns on `users` — none of which fit this repo).

## Decisions (Daniel, 2026-09-26)

| # | Rule |
|---|---|
| D1 | Two categories: **purchased** (paid with money) and **earned** (bonus: referrals, rewards, admin grants). |
| D2 | **Spend order: purchased first**, then earned (oldest-expiring first). Side effect accepted: earned Notas are more likely to expire. |
| D3 | **Purchased Notas never expire.** Inflation is controlled manually by changing platform prices. |
| D4 | **Earned Notas expire 18 months after the date each one was credited** (per credit, not per account). Stated explicitly in the Terms. |
| D5 | No cash-out, ever (existing rule). |
| D6 | Deleted account: reactivation possible for **6 months, balance included**; afterwards all data and Notas are erased. The user is told this when deleting. |
| D7 | After erasure VokalBoard keeps **no** personal/payment data; legally required bookkeeping records live in Stripe + the accountant's system (GDPR Art. 17(3)(b), §147 AO / §257 HGB). |
| D8 | Payment provider: **Stripe** (Daniel has an account). |
| D9 | Daniel is a freelancer under the **small-business VAT exemption (§ 19 UStG, Kleinunternehmer)** → no VAT charged, Stripe Tax **off**. |
| D10 | **No lawyer review** (Daniel's call) — legal texts are written from the drafts below. |

## What already exists (keep, don't rebuild)

`credit_ledger` (append-only; balance = SUM), `app/notas_wallet.py` (`credit_notas`, `debit_notas_atomic` with `SELECT … FOR UPDATE`, idempotency keys enforced by a unique partial index, server-side prices), admin refunds (`refund_ledger_entry`, `/financeiro/estornos`), shop, urgency purchases, referral/listing rewards. **`CLAUDE.md` §3.B's `note_transactions` = this `credit_ledger`.**

## Data model (SQL migration, folded into the consolidated file — see docs/MIGRATIONS.md)

- `credit_ledger.category VARCHAR(10) NOT NULL CHECK (category IN ('purchased','earned'))`.
- `credit_ledger.expires_at TIMESTAMPTZ NULL` — set only on earned **credits** (`created_at + 18 months`); NULL for purchased and for debits.
- New `credit_lot_usage (debit_id → credit_ledger, lot_id → credit_ledger, amount NUMERIC(10,2))` — records which credit "lots" each debit consumed. Needed for: correct spend order, expiring only the unspent remainder of a lot, category-correct refunds, audit. All FKs `ON DELETE CASCADE` (erased with the account).
- New reason codes: `purchase`, `earned_expired`, `stripe_refund`, `stripe_dispute`.

**Migrating existing data:** real purchases never existed (buy page is a stub) → every existing credit becomes **earned**. Existing debits are allocated oldest-first. Expiry for pre-existing credits = **18 months from the rollout date** (not retroactive — no one loses Notas on launch day); users get a notice.

## Rules in code (`app/notas_wallet.py`, one place)

- `debit_notas_atomic()` keeps its lock + idempotency and additionally allocates the amount across lots: purchased lots first (oldest first), then earned lots by `expires_at` ascending; writes `credit_lot_usage` rows in the same transaction.
- `get_balances(user_id)` → purchased, earned, and the next expiry (amount + date).
- Refund of a debit (`refund_ledger_entry`) returns the amount to the **same lots**. If an earned lot has already expired, it comes back as a fresh earned credit with a new 18-month expiry (goodwill default — Daniel may change).
- Worker `earned_expiry_worker` (daily, same pattern/advisory lock as the other workers): for each earned lot past `expires_at` with a remainder > 0 → one `earned_expired` debit for exactly that remainder.
- Notification Center (+ e-mail): 30 days before a lot expires — "X Notas expire on DD.MM.YYYY".
- Stripe refund/dispute debits purchased Notas; the balance may go negative → spending blocked until it's positive again.

## UI

`/notas`: total, "Purchased X · Earned Y", "Z earned Notas expire on …" (only if any), history column showing the category. Deletion flow (`/profile/delete-account`) and its confirmation e-mail state D6.

## Legal pages — prerequisite before selling anything

No Terms page exists yet (only Impressum, Datenschutz, Code of Conduct). Needed: **`/agb` (Terms)** and **`/widerruf` (withdrawal-rights notice)**, linked in the footer and in checkout, plus a Stripe section in the privacy policy. Per D10 there is no lawyer review; a lower-risk alternative is a legal-text subscription service (generated, maintained texts) — Daniel's choice. Draft clauses (EN; German version to be written from these):

1. Notas are platform credits without cash value; they cannot be paid out, exchanged for money or transferred.
2. Purchased Notas do not expire. Earned Notas (bonuses, rewards, referrals) expire 18 months after the date they were credited; you are notified 30 days in advance.
3. When you use Notas, purchased Notas are used first, then earned Notas starting with those that expire soonest.
4. VokalBoard may change the prices of platform services in Notas; changes are announced at least 4 weeks in advance and don't affect services already paid for.
5. If you delete your account, you can reactivate it — including your Notas — within 6 months. After that, your account data and all remaining Notas are permanently erased.
6. Right of withdrawal: 14 days. By ticking the checkbox at checkout you request immediate delivery and acknowledge that the right of withdrawal expires once the Notas are credited (§ 356 Abs. 5 BGB). *(Unreviewed — whether the waiver holds for prepaid credits is legally contested.)*

Legal pages stay out of scope for the added languages (es/zh/ko/ro) — see docs/I18N.md.

## Stripe (N5) — outline, details after the tax decision

- "Buy Notas" page (replaces `notas_comprar_stub.html`): fixed bundles (EUR/CHF), waiver checkbox (required) → server creates a **Checkout Session** (`mode=payment`, Price IDs from config, `metadata.user_id`, `consent_collection.terms_of_service=required` + waiver text in `custom_text`, `invoice_creation` on with the footer **"Gemäß § 19 UStG wird keine Umsatzsteuer berechnet."**, `automatic_tax` **off** (D9)) → redirect.
- `POST /webhooks/stripe`: verify signature with `STRIPE_WEBHOOK_SECRET`; `checkout.session.completed` → `credit_notas(category='purchased', reason='purchase', idempotency_key=<session id>)`; `charge.refunded` / `charge.dispute.created` → purchased debit. The waiver/ToS consent proof is stored by Stripe on the session (fits D7).
- Keys only as Railway env vars (`STRIPE_SECRET_KEY` = restricted key, `STRIPE_WEBHOOK_SECRET`). No card data ever touches VokalBoard.

### Kleinunternehmer limits to watch (D9)

- The exemption holds while total turnover (**all** freelance income, not just VokalBoard) stays ≤ €25,000 in the previous year and ≤ €100,000 in the current one. Crossing it → VAT applies; Stripe Tax gets switched on then.
- Selling digital services to consumers in **other EU countries**: above €10,000/year EU-wide, the customer country's VAT applies regardless of the German exemption (OSS registration). Until then, German rules apply.
- Selling platform credits is likely a **trade (Gewerbe)**, not freelance work — may need a Gewerbeanmeldung. Worth one question to the tax office.
- (Steuerklasse 5 is income tax only — unrelated to VAT.)

## Stages (each: code + tests + HANDOFF/changelog)

| Stage | Content | Tests |
|---|---|---|
| N1 | Schema (category, expires_at, lot usage) + data migration | migration re-run on a restored DB; balances unchanged |
| N2 | Spend order + lot allocation + refunds to lots | concurrency (two debits), purchased-first, FIFO earned, refund paths |
| N3 | Expiry worker + 30-day notice | lot partially spent then expired; idempotent re-run |
| N4 | `/notas` UI + `/agb` `/widerruf` pages + Stripe in the privacy policy | render tests, i18n keys (5 core langs) |
| N5 | Stripe in **test mode** (checkout + webhook) | signature rejection, duplicate webhook = one credit, refund/dispute |
| N6 | Go-live checklist (live keys, legal pages published, privacy policy) | manual, with Daniel |

**D6 purge — DONE 2026-09-26:** `app/account_purge.py`, run hourly by the retention worker (no extra Railway service); the deletion notice already mentions Notas.

# Notas Store — spec (Daniel + Claude, 2026-09-28)

**Status: DESIGN COMPLETE (Daniel, 2026-09-28) — ready to build when Daniel says go.**
Item 7 of the to-do list ("function catalogue" = the Notas store). Builds on the existing
catalogue (`app/shop_catalog.py`, table `shop_catalog_items`, Admin → Shop catalog) and the
Notas wallet (`app/notas_wallet.py`, append-only `credit_ledger`). 1 Nota = 1 EUR / 1 CHF.
Notas are never converted back into money (Terms §3).

## 1. Products (Daniel's prices, full price)

| Key | Product | Price | Duration | Effect in the site |
|---|---|---|---|---|
| `super_user_1y` | **Super User** | 5 | 365 days (buying again extends) | Light-purple frame around the person's card **everywhere** (profile, People search cards, listing cards by them, Matches, chat avatar) + small "Super User" label. **Replaces** "Profile highlight 7 days" (switched off, not deleted; running highlights keep running). |
| `featured_listing_30d` | **Featured listing** | 2 | 30 days, per listing | One chosen listing pinned at the top of the Jobs board with a "Featured" label. Bought from the listing (button "Feature this listing") or from the store (pick one of my active listings). |
| `people_top_30d` | **Top of People search** | 2 | 30 days (buying again extends) | Profile shown first in "Search people" results that match the person (country/city/voice type). Several buyers in the same results → ordered by purchase time, then normal order. |
| `invoice_single` | **1 invoice** | 0.50 | — | +1 invoice credit beyond the 5 free invoices/month (existing `purchased_invoice_credits`). |
| `invoice_pack_5` | **Invoice pack** | 2 | — | +5 invoice credits (= 0.40 each). |
| `verified_badge` | **Verified badge** | 5 | forever | Person submits a **public proof link** (opera house/choir roster, agency, conservatory, official website) + short note → admin approves/rejects. Badge shows on profile + cards. **Rejected = Notas refunded automatically.** Nothing uploaded or stored besides the link + note (Zero-Storage). |
| `supporter_badge` | **Supporter badge** | 5 | forever | Cosmetic "Supporter" badge on the profile — a thank-you for supporting VokalBoard. |
| — (existing) | **Urgent listing** | **1** (was 2) | until event | After the free weekly token; bought on the listing form as today (`app/urgency.py`, `URGENCY_PURCHASE_COST_NOTAS` 2 → 1). |
| `subscription_1y` | **1-year subscription** | 15 | 365 days (buying again extends) | **Only the subscription time — nothing else (Daniel: "Simple").** Writes a row in `subscriptions` (price recorded as Notas); same meaning as today's paid subscription (e.g. hides the "Subscribe now" banner when Capitalism Mode is on). No first-year discount. |

All prices stay editable in Admin → Shop catalog (the table above is the starting point).

## 2. Discounts

- **Welcome discount:** accounts **younger than 365 days (from registration)** pay **−50%** on
  every store item **except the 1-year subscription** (and urgent listings are included).
  Shown on each card: "Welcome price −50% until DD.MM.YYYY" (the date = registration + 365 days).
- **Admin discount per item:** % off, optional start/end date; the card shows a **"−XX% off!"**
  badge while it is active.
- **Both apply → the bigger one wins** (never added together).
- Price shown = what is charged; the ledger records the actual amount paid + which discount
  (`admin_note`, e.g. "welcome −50%").
- No launch offer for older members (Daniel).

## 3. Store page for users — `/store`

- Linked from the Notas page and the avatar menu → Rewards.
- Cards grouped: **Visibility** (Super User, Featured listing, Top of search) · **Tools & trust**
  (1 invoice, Invoice pack, Verified badge) · **Support** (Supporter badge, 1-year subscription).
- Each card: icon, title, one-line benefit, price (strike-through original + discounted price when
  a discount applies), discount badge, "Get it" button (confirm dialog with the final price),
  "Active until …" when the person already has it.
- Not enough Notas → "You're missing X Notas" + link to buy Notas (existing flow).
- All 10 languages (texts in `app/i18n.py` / `app/locales/*.json`); admin pages English.
- Replaces the catalogue section on `/notas` (which then links to `/store`).

## 4. Admin — Shop catalog (`/admin/loja`, extended)

- **Prices & discounts:** edit price, active/inactive, discount % + optional end date, with a
  live preview of the "−XX% off!" badge. Changes audit-logged.
- **Sales:** per item — times sold, Notas collected, unique buyers, last sale; **sortable** by
  most / least sold (and by Notas); period filter (30 days / 90 days / all time).
- **Verified badge requests:** queue with the proof link + note; Approve / Reject (reject =
  automatic refund); audit-logged. Nav badge with the number waiting.

## 5. Build notes

- Every product with an effect is code (`ITEM_EFFECTS` in `app/shop_catalog.py` → one small
  handler per effect); prices/active/discount live in `shop_catalog_items` (+ new columns
  `discount_percent`, `discount_until`).
- New state: `users.super_user_until`, `users.verified_at`, `users.supporter_since`,
  `listings.featured_until`, `users.people_top_until`, table `verification_requests`
  (link, note, status, reviewed_by/at). One migration, tolerated while missing (store hides
  the affected items).
- Frame + badges: one shared template macro used by every card type (no duplicated markup).
- Tests: prices + both discounts (bigger wins, subscription excluded, welcome window edges),
  each effect, refund on rejected verification, sales stats, no double charge on double click.

## 6. Decisions log

- Prices (Daniel, 2026-09-28): Super User 5 · Featured listing (30 d) 2 · Top of People search (30 d) 2 ·
  1 invoice 0.50 · Invoice pack (5) 2 · Verified (forever) 5 · Supporter 5 · Urgent listing 1 · 1-year subscription 15.
- Welcome −50% from registration, first 365 days, everything except the subscription; admin discount per item
  with "−XX% off!" badge; bigger discount wins; no launch offer for older members.
- Super User replaces "Profile highlight 7 days". Verified = public proof link, refund on reject.
- Subscription = only the subscription time. Top of People search = 30 days.
- Featured listings on the Jobs board: **max 3 at the top, rotating** (random 3 per page load when more are active).
- Admin: price/discount editor + sales table sortable most/least sold + verification queue.

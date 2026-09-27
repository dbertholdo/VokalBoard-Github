# Rechnungmaker v2 — spec (Daniel + Claude, 2026-09-27)

**Status: PLAN ONLY — not started. Build only after Daniel says "go".**
Builds on the 2026-09-27 cleanup (server-side tax preset, translated forms, `_invoice_fields.html`,
`app/invoice_tax_presets.py`). Zero-Storage rules (CLAUDE.md §2) apply unchanged.

## Decisions
- **Name:** "Rechnungmaker" is the official product name (one word, everywhere — the PDF footer's
  "Rechnung Maker" gets fixed). Each language adds a subtitle: de "Rechnungen erstellen", en "invoice maker",
  fr "créateur de factures", it "generatore di fatture", pt "Gerador de Faturas (NF)",
  es "generador de facturas", ro "generator de facturi", zh "发票生成器", ko "인보이스 생성기".
- **Country first:** a "Your country (where you pay taxes)" selector — 🇩🇪 Germany · 🇦🇹 Austria · 🇨🇭 Switzerland ·
  🌍 Other — preselected from the profile country. The issuer's country decides the rules.
- **Invoice language** (the document itself): DE / EN / FR / IT, defaulting from the country (Other → EN).
  Independent from the site language.
- **Reverse charge:** included for DE and AT (EU B2B clients).
- **"?" help on every field** (see Phase 1.9).
- **No Steuerberater review** (Daniel). A short "most common format — not tax advice" note stays on the page.
- **Phase 2 (QR codes): yes.**

## Phase 1 — country templates

1. **Country selector** at the top of both forms (standalone generator + Match invoice).
2. **Country profiles** in one new data file `app/invoice_countries.py` (adding a country = adding one entry):

   | | 🇩🇪 DE | 🇦🇹 AT | 🇨🇭 CH | 🌍 Other |
   |---|---|---|---|---|
   | Tax options | Kleinunternehmer (§19 UStG) · cultural exemption · 19 % · 7 % · reverse charge | Kleinunternehmer · cultural exemption · 20 % · 13 % · 10 % · reverse charge | not VAT-registered · 8.1 % · 2.6 % | own tax name + rate, or none |
   | Tax ID label | Steuernummer / USt-IdNr. | UID-Nummer | UID / MWST-Nr. | free label |
   | Currency | EUR | EUR | CHF (EUR allowed) | choose |
   | Invoice language | DE | DE | DE (FR/IT one click) | EN |
   | Number format | 1.234,56 | 1.234,56 | 1'234.56 | 1,234.56 |

   Legal notes (e.g. "Gemäß §19 UStG wird keine Umsatzsteuer berechnet") exist in all four invoice languages.
   **Reverse charge** shows 0 % + the fixed sentence ("Steuerschuldnerschaft des Leistungsempfängers /
   Reverse charge") and adds a required field for the client's VAT ID.
3. **Switching country never puts personal data in a URL.** It happens in the page via our own JS file
   (CSP-safe, no inline handlers — the 2026-09-27 tax bug came from one) and keeps what was typed. Without JS,
   an "Apply" button re-posts the form (POST, re-rendered; nothing stored, nothing in the address bar).
4. **PDF + live preview in the invoice language:** labels (Rechnung / Invoice / Facture / Fattura), legal
   notes, number and date formats.
5. **Match invoices:** country defaults to the issuer's profile country; country + invoice language are
   stored encrypted with the draft (like `tax_preset` today, `EXTRA_FIELDS`).
6. **Note on the page:** "Most common format for your country — not tax advice."
7. **Name + subtitle** under the page title and in the menu (small text), 9 languages.
8. **Tests:** rates, totals and legal notes per country; PDF labels per invoice language; reverse-charge
   requires the client VAT ID; no personal data ever in a URL.
9. **"?" help on every field:**
   - A small "?" button next to every label, both forms.
   - **Short:** one line — what the field is + an example format. No tutorials: people can google the
     details. E.g. DE tax ID: "Your tax number from the Finanzamt, e.g. 12/345/67890, or your VAT ID (DE…)."
   - **In the site language** the person uses (all 9: de, en, fr, it, pt, es, ro, zh, ko) — not the invoice
     language — so newcomers to the country understand it. Written for someone who has never made an invoice.
   - **Country-specific** where the rules differ (tax ID, tax options, rate, legal note, currency, date of
     performance, reverse charge); one shared text elsewhere. ~45 texts × 9 languages.
   - **Not hover-only:** hover or click on desktop, tap on phones, Tab + Enter on keyboard; linked to the field
     for screen readers (`aria-describedby`); Esc / tap outside closes.

## Phase 2 — payment QR codes
- **Swiss QR-bill** (official Swiss payment slip at the bottom of the invoice; bank apps scan it):
  automatic when the issuer is in CH or the IBAN is CH/LI and the currency is CHF/EUR. Open-source `qrbill`
  library (+ SVG-to-PDF helper) — **ask Daniel before installing new packages.**
- **GiroCode (EPC QR)**, optional checkbox for EUR invoices with a SEPA IBAN (DE, AT, …).
- **Daniel scans one of each with a real banking app before go-live.**

## Out of scope (for now)
- More invoice languages (ES/PT/RO…), more country profiles, e-invoicing formats (XRechnung/ZUGFeRD).

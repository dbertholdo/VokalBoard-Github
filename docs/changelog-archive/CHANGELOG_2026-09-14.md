# VokalBoard — Today's changelog (2026-09-14)

Everything below is already implemented, tested (33/33 tests passing),
and committed locally (commit `09f0c31`, branch `master`) in this
session's cloud environment. **It has not been pushed to your computer
yet** because the bridge to your PC was disconnected at the time — as
soon as it reconnects (just have the Claude app open), I'll sync the
files to your Google Drive folder automatically. After that, just
review and run `git push`.

## 🔴 Red Zone (everything hidden/off by default)

- **User levels** (`users.role_level`): 0 regular, 1 moderator (only
  sees the reports queue), 2 admin (everything that already existed:
  users, posts, data analysis), 3 god mode (everything above + the
  Red Zone). The old `is_admin` still exists and is kept
  automatically in sync — including via a trigger in the database
  itself, so as not to break the "becoming admin" flow already
  documented in the README.
- **Capitalism Mode**: turns billing on/off for the whole site. While
  off (default), nothing related to payment shows up anywhere — no
  banner, no price. Toggling the state requires **password
  re-authentication** (even while already logged in as god mode) and
  is logged in the audit trail, even when the password is wrong.
- **Subscription price** (EUR/CHF), editable in the Red Zone, with the
  same password lock.
- **Audit log** (`audit_log`): who, when, from which IP, for every
  sensitive action.

## 📖 Internal financial panel

- Expense entry (description, amount, currency, category, date)
- Recurring expenses (monthly/yearly)
- Receipt attachment (PDF or image) — stored separately, visible only
  to god mode (unlike the avatar, which is public)
- Expense export to CSV
- Manual bank statement upload: you create a column-mapping "profile"
  once per bank (which column is date/amount/description), and reuse
  that profile on every future import from that bank — OFX support is
  left for a later step
- Paid-plan adoption analytics by country (uses the existing `country`
  field + the new `subscriptions` table, ready for when billing is
  actually turned on)
- Chart toggle (bar / pie / line) on the financial panel, and
  retrofitted onto the existing Data Analysis view
- Monthly/yearly closing: freezes a summary of the period and exports
  it as **Excel, CSV, and PDF**

## Still pending (business decision, not technical)

- Country of taxation (Germany vs. Brazil) — the decision you said
  you'd make later
- Connection to a real payment processor (Paddle or another) — that's
  why `/assinar` is currently just a placeholder page, with no real
  checkout
- Confirmation that you've already put `.github/workflows/backup.yml`
  in the right place and created the `PRODUCTION_DATABASE_URL` secret

## How this was verified

- 33 automated tests passing (20 pre-existing + 13 new), including:
  wrong password changes nothing, each user level only accesses what
  it should, every sensitive action lands in the audit log, all three
  closing-export formats respond correctly
- Bandit (static security analysis) with no findings in the new files
- All new pages rendered end-to-end against a real Postgres database,
  with no errors

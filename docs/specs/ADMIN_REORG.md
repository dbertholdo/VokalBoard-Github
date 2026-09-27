# Admin reorganization — spec (Daniel + Claude, 2026-09-27)

**Status: PLAN — to be built as cleanup section 7, after Daniel's go.** Every existing URL keeps working;
only navigation, grouping and page layout change.

## Decisions (Daniel)
- **English everywhere in the admin** — translate the leftover Portuguese labels (Loja, Estornos,
  Extrato Geral, "Destaque de perfil", "Notas — extrato", Limpar, Assinaturas, …).
- **Moderators (level 1) see nothing** in the admin for now (Daniel decides later).
- **Admin must work well on a phone.**

## Problems today (2026-09-27 review)
- Flat sidebar of 9 ungrouped items; moderation (listing reports, reported messages, blocks) lives on the
  Dashboard instead of its own page.
- Red Zone tools (Refunds, General ledger, bank import, Grants) only reachable via links inside the Red
  Zone page; feature switches split between Dashboard (compatibility score) and Red Zone (Capitalism Mode).
- User detail page is one long page; redeemed shop vouchers (fulfilled by hand) have no "to deliver" list.

## New navigation (grouped sidebar)
```
🏠 Overview      Dashboard (what needs attention, with counts) · Analytics
🛡️ Community     Reports (listing reports · reported messages · blocks — tabs)
                 Users (list → user page in tabs: Account · Notas · Reviews · Moderation · Danger zone)
                 Support tickets
📣 Content       Announcements (Posts) · Banners · E-mails (send · periodic · design)
🎁 Shop          Shop catalog (was "Loja") · Vouchers to deliver (new)
🔴 Red Zone      Money: financial dashboard · general ledger · bank import · closings
 (God Mode,      Refunds · Grants (Notas / items)
  password       Settings: Capitalism Mode · prices · feature switches
  re-check)      Audit log (own page)
```
- Red count badges on menu items (open reports, tickets, vouchers to deliver).
- Admin-rights / God Mode switches move into the user page's "Danger zone" tab (password re-check).
- Phone: the sidebar collapses into the ☰ menu; tables scroll inside their card; no page-wide sideways scroll.

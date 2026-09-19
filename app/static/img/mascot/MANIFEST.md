# VokalBoard — Tangará mascot assets manifest

Nine poses approved 19/09/2026. Source (outside the repo, Daniel's
machine): `C:\Users\danie\.codex\generated_images\01a0b362-6841-7bc1-8f29-dc0e1ca62148\`.
Approval record and usage rules: `INSTRUCOES_MARCA_CODEX_CLAUDE.md` §2/§5
and `MANUAL_VISUAL_VOKALBOARD_V1.md` §7 (in the brand working folder,
outside the repo). Copied here with stable, descriptive names; originals
left untouched.

Tangará: navy/periwinkle, white chest, small crest, bright green eyes,
firm eyebrows — no strong pink cheeks. Do not recolor, regenerate, or
create a new pose per screen; reuse these nine.

| File here | Approved source filename | "Uso" | Approved context (manual §7) | Placed in this delivery? |
|---|---|---|---|---|
| `mascot-reference.png` | exec-171a006d-... | Referência mestre | Style/QA reference only, not itself a UI pose | No — kept as reference |
| `mascot-neutral.png` | exec-a9120c72-... | Neutro | General presentation/orientation; not on every card | Not yet — the only pose still unplaced |
| `mascot-welcoming.png` | exec-44341fc2-... | Acolhedor | Welcome / first access; must not interrupt recurring tasks | **Yes** — a "Welcome, {name}!" toast on every login (base.html, via app/mascot_moments.py) |
| `mascot-celebrating.png` | exec-30f085a7-... | Celebração | Match / a real confirmed conclusion; never before confirmation | **Yes** — `invitations.html`, `listing_candidates.html` (`responded=accepted`) |
| `mascot-attentive.png` | exec-d6195ee5-... | Atento | Reminder/pending item; no reproach or guilt | **Yes** — a "Hey, {name}! Don't forget to..." toast, one pending item, once per session (base.html) |
| `mascot-alert-zone.png` | exec-28fc8640-... | Zona de Alerta FINAL | Urgent-opportunity area — red glowing eyes ONLY, no lasers/!!!. **This is the "Zona de Alerta" urgent-listings feature, NOT the admin Red Zone (`zona_vermelha.html`) — the two are explicitly distinct, see manual §8.** Small, non-repeating. | **Yes** — `board.html` (`?urgent=1`) **and, by Daniel's own explicit call on 19/09/2026, also the 404 page** (`auth_message.html`, "lost bird" joke) — a deliberate one-off expansion of this pose's context, not a silent reinterpretation of the manual |
| `mascot-supportive.png` | exec-3a7f4234-... | Solidário | No results / difficulty; no jokes about the loss | **Yes** — `board.html` empty state |
| `mascot-thumbsup.png` | exec-9c847856-... | Joinha | Brief confirmation; must not replace the actual success message | **Yes** — `profile.html`, `notas.html`, `my_listings.html`, next to (not instead of) each existing success message |
| `mascot-wink.png` | exec-0432ae80-... | Piscadinha | Light aside; never in billing, security, or terms | **Yes** — `hall_da_fama.html`, one of four rotating incentive lines picked at random per page load |

## Neutro — still unplaced, on purpose

All eight other poses are now wired into a page (Part 2 backlog item 4,
19/09/2026 — see `AI_CHANGELOG.md` for the full writeup and
`app/mascot_moments.py` for the reminder-priority logic). Only Neutro
never got a clearly-matched moment during that pass — Daniel's answers
covered Acolhedor/Atento/Joinha/Piscadinha in detail but didn't call out
a spot for Neutro specifically, and the manual is explicit that overuse
is the failure mode ("não em todos os cards", "no máximo uma presença
dominante por bloco"), so it stayed out rather than being placed
speculatively. Open item for a future pass if Daniel wants it placed.

## Rules that apply to every placement (manual §7)

Decorative use: `alt=""` when the adjacent text already says what's
needed (all current placements qualify). No continuous/looping animation
— none is approved. At most one dominant mascot presence per visible
block. Keep at least 8px margin from surrounding content; never crop the
crest, wings, or feet. Sizes per the manual's own reference table: 80–96px
Zona de Alerta, 144–160px celebration, 120–200px welcome (Solidário/
Neutro/Atento/Joinha/Piscadinha sizes aren't in that table — pick something
modest and consistent when they're placed). No mascot on the invoice
(Rechnung) screens or in the data-review parts of any financial flow.

## Separately still open

`bird-flying.svg` (the periodic flying-bird easter egg referenced in
`base.html`) has no matching asset in this delivery — all nine approved
poses are static standing poses, and the manual explicitly says no
animation is approved yet ("Não há animação aprovada. Usar poses
estáticas"). Left as-is (already a broken reference before this change,
not something this delivery fixes or worsens) — needs its own decision
from Daniel before touching it.

`zona_vermelha.html`'s `red-zone-bird-police.png` (a "police guardian"
image, unrelated visual concept — not part of the approved Tangará set)
is also still a broken reference, and was deliberately NOT replaced with
`mascot-alert-zone.png` here — see the "Zona de Alerta vs. Red Zone"
distinction above. That's a separate open item for the actual Red Zone
admin page, not something this delivery covers.

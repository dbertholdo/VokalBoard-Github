# VokalBoard — brand assets manifest

Logo package delivered 19/09/2026. Source (outside the repo, Daniel's
machine): `C:\Users\danie\.codex\visualizations\2026\09\18\01a0b362-6841-7bc1-8f29-dc0e1ca62148\vokalboard-logo-v1\`
— see that folder's own `LEIA-ME.md`, plus `INSTRUCOES_MARCA_CODEX_CLAUDE.md`
and `MANUAL_VISUAL_VOKALBOARD_V1.md` in the parent folder for the full
approval record and usage rules. Copied here with stable names; originals
left untouched.

## Approved logo

"V/asas — Assinatura", option 03 (Daniel's approval, recorded in
`INSTRUCOES_MARCA_CODEX_CLAUDE.md` §2). Two mirrored wing shapes forming a
V, one small feather-cut notch per wing. Color `#17283F` (navy, primary use).

- `symbol-navy.svg` — full symbol, navy. Primary use, white/mineral
  backgrounds, width ≥ 48px.
- `symbol-white.svg` — full symbol, white. Dark/navy backgrounds only (no
  approved full dark theme — spot use, e.g. a solid-navy footer/banner).
- `icon-small-navy.svg` — optically-adjusted square variant (no fine
  cut-out detail) for anything under 48px wide: nav brand icon, favicon,
  footer icon. This is the one in active use across `base.html`.
- `icon-16.png` / `icon-32.png` / `icon-256.png` — raster fallbacks for
  favicon/apple-touch-icon where an SVG favicon isn't picked up.

Not copied here (available in the source folder if a future need arises):
`symbol-black.svg`, `icon-small-white.svg`, `icon-small-black.svg`,
`icon-24/48/64/128.png`, `prancha.svg/png` (the reference sheet), and the
`lockup-*-PROVISIONAL.*` files — those lockups use a placeholder font
(Segoe UI/Arial fallback), NOT the final Manrope lettering, and per the
handoff docs must not be adopted as the final signature. The site's
existing pattern (icon + live "VokalBoard" text set in Manrope, see
`base.html`'s `.brand`) already achieves a proper lockup without needing
a baked-in lettering file — do not introduce a lockup image until a real
Manrope-outlined one replaces the provisional ones.

## Protection / sizing rules (from the manual, §3)

At least H/4 clear space on every side (H = visible symbol height, not
counting transparent margin). Never stretch, rotate, outline, add a
shadow/glow, fill the gap between the wings, or substitute a generic
bird/emoji. Below 48px width, use `icon-small-navy.svg`, not the full
symbol. Full "symbol + wordmark" lockup: not finalized (needs the
Manrope-outlined lettering) — don't build one from these files.

## Font

Manrope was already self-hosted before this delivery — see
`app/static/fonts/manrope/` (OFL 1.1, `LICENSE.txt` present). Not part of
this manifest; nothing changed here.

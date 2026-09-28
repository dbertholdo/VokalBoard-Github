# Flags — MANIFEST

Small 4:3 country flags for the language menu (`app/templates/base.html`),
mapped per language in `LANGUAGE_META["…"]["flag_img"]` (`app/i18n.py`).

- **Source:** flag-icons v7.2.3 by Panayiotis Lipiridis — https://github.com/lipis/flag-icons
  (downloaded from cdn.jsdelivr.net/npm/flag-icons@7.2.3/flags/4x3/, 2026-09-28).
- **Licence:** MIT — see `LICENSE` in this folder (keep it next to the files).
- **Checked:** no scripts, no external references (`cn.svg`/`kr.svg` only use internal `#…` links).
- **Language → flag:** de→de, en→gb, fr→fr, it→it, pt→br, es→es, zh→cn, ko→kr, ro→ro, tr→tr.
  A flag stands for a language here, not a country (e.g. Portuguese uses Brazil's, the
  site's main Portuguese-speaking audience).
- **Why not emoji:** Windows doesn't render flag emoji (shows "DE", "GB"…).
- Adding a language: download `<code>.svg` from the same version, add it here, set `flag_img`.

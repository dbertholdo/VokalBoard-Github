# Noto Sans SC / KR — CJK fonts (self-hosted)

- **What:** subsets of Noto Sans SC (Simplified Chinese) and Noto Sans KR (Korean), variable weight 400–700, WOFF2.
- **Why:** Manrope has no CJK glyphs. These pair with it (same clean sans-serif, matching weights); Latin text still renders in Manrope.
- **Source:** github.com/notofonts/noto-cjk — `Sans/Variable/OTF/Subset/NotoSans{SC,KR}-VF.otf` (downloaded 2026-09-26).
- **License:** SIL Open Font License 1.1 — `LICENSE.txt` (must ship with the fonts).
- **Loaded by:** `app/static/css/fonts-cjk.css`, linked from `base.html` only when `lang` is `zh` or `ko`.

| File | Contents | Size |
|---|---|---|
| `notosanssc-ui-400-700.woff2` | every CJK char in `app/locales/zh.json` + CJK punctuation | ~200 KB |
| `notosanssc-common-400-700.woff2` | rest of GB2312 level 1 (3,755 most common hanzi) | ~750 KB, fetched only if a page uses one |
| `notosanskr-ui-400-700.woff2` | every Hangul char in `app/locales/ko.json` + punctuation | ~100 KB |
| `notosanskr-common-400-700.woff2` | rest of KS X 1001 Hangul (2,350 syllables) + jamo | ~185 KB, fetched only if a page uses one |

Rarer characters fall back to the system CJK font.

**After changing `zh.json` or `ko.json`:** rerun `python scripts/subset_cjk_fonts.py <dir with the two -VF.otf files>` (needs `pip install fonttools brotli`), then bump `fonts-cjk.css?v=` in `base.html`.

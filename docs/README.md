# docs/ — reference documentation

Start with `HANDOFF.md` at the repo root (current state), per the hierarchy in `CLAUDE.md` §0 / `AGENTS.md`.

| File | What it's for | Read when |
|---|---|---|
| `I18N.md` | Translation workflow, glossary, adding a language | Touching translations / languages |
| `MIGRATIONS.md` | Production migration rules + the consolidated pending migration | Touching `db/schema.sql` or `db/migrations/` |
| `specs/NOTAS_V2.md` | Notas v2 (implemented): purchased vs. earned, 18-month expiry, Stripe, Terms pages | Before any Notas/payment work |
| `specs/MESSENGER.md` | DRAFT spec: per-pair chat, requests, 60-day expiry, polling (#53) | Before any messaging work |
| `VISUAL_ROLLOUT.md` | Visual identity v1 rollout inventory (Codex) | Visual/CSS work |
| `changelog-archive/` | Old `AI_CHANGELOG` entries, verbatim | Grep only — never read whole |
| `archive/` | Obsolete deliverables: old screenshots, early migration drafts, a pre-rebrand mockup | Almost never (excluded from search by `.ignore`) |

Brand assets have their own manifests: `app/static/img/brand/MANIFEST.md`, `app/static/img/mascot/MANIFEST.md`.

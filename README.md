# VokalBoard

*"Dein Weg zu dem perfekten Auftritt!"* — a bulletin board connecting
singers (Sänger) and conductors (Dirigenten) in Germany, Austria and
Switzerland.

Read [`CLAUDE.md`](./CLAUDE.md) before making changes — it's the
authoritative architecture/business-rules/security guide for this project
(Zero-Storage policy, the Notas economy, the secret Match-evaluation
system, anti-spaghetti rules). Read [`AGENTS.md`](./AGENTS.md) for the
current production-deploy status and constraints. Check the top of
[`AI_CHANGELOG.md`](./AI_CHANGELOG.md) for what changed most recently.

## Stack

FastAPI (Python) + SQLAlchemy + PostgreSQL, Jinja2 templates, plain
CSS/JS (no frontend framework/build step).

## Local setup

1. **Database.** Either run Postgres via Docker (`docker compose up db`,
   which auto-loads `db/schema.sql` and `db/seed_sample_data.sql` on
   first start — see `docker-compose.yml`), or point `DATABASE_URL` at
   a Postgres instance you already have and load the schema yourself:
   ```
   psql "$DATABASE_URL" -f db/schema.sql
   ```
2. **Python deps.**
   ```
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt -r requirements-dev.txt
   ```
3. **Environment.** Copy `.env.example` to `.env` and fill in at least
   `DATABASE_URL` and `SECRET_KEY`. See the comments in `.env.example`
   for what each variable does — `EMAIL_BACKEND=console` and everything
   else can stay blank for local dev.
4. **Run.**
   ```
   uvicorn app.main:app --reload
   ```
   The site is then at http://localhost:8000.

Or skip steps 1–4 entirely and run the whole stack with
`docker compose up` (web + db together).

## Tests

```
pytest tests -q
```

Also useful: `bandit -r app` (security lint) and `pip-audit -r
requirements.txt` (dependency CVEs) — both in `requirements-dev.txt`.
Per CLAUDE.md §5.3, any code change should be validated with the test
suite before considering it done.

## Background workers

The app itself only serves HTTP requests — seven separate long-running
worker processes handle everything on a schedule (reminders, expiry,
retention, periodic reports, Notas rewards). Each lives in
`app/<name>_worker.py`, polls once an hour in a `while True: ...
time.sleep(3600)` loop, and takes `--once` (run one pass and exit) and
`--dry-run` (log what it *would* do, change nothing) flags — handy for
testing:

| Worker | What it does |
|---|---|
| `app.retention_worker` | Archives/purges old listings & messages per the retention policy |
| `app.invitation_expiry_worker` | Expires job invitations past their deadline |
| `app.match_evaluation_reminder_worker` | Reminds Match participants to leave their (secret) post-Match evaluation |
| `app.invoice_match_draft_expiry_worker` | Expires unconfirmed Rechnung drafts after 7 days |
| `app.urgent_listing_reminder_worker` | Reminds authors of urgent (Zona de Alerta) listings still unfilled |
| `app.periodic_mail_worker` | Sends the daily/weekly/monthly admin reports configured at `/admin/emails?tab=periodic` |
| `app.listing_reward_worker` | Credits the "publicar vaga" Notas reward (see `app/listing_rewards.py`) once a listing is old enough (or immediately if urgent), capped at 3/week per user |

Run one locally with e.g. `python -m app.periodic_mail_worker --once`,
or start all of them via Docker with `docker compose --profile workers
up` (each also has its own profile, e.g. `--profile retention`, if you
only want one).

**In production, each of these needs its own always-on process** —
`docker-compose.yml` is for local dev only; Railway doesn't build from
it. As of 19/09/2026 only `retention_worker` is known to have a Railway
service; the other six need one created the same way: Railway dashboard
→ New Service → same GitHub repo → Start Command
`python -m app.<worker_name>` → same environment variables as the `web`
service (at minimum `DATABASE_URL`). Without this, the admin screens for
these features (invitations, evaluations, invoices, urgent listings,
periodic mails, listing rewards) work fine, but nothing ever actually
fires on schedule.

## Email in production

`EMAIL_BACKEND` controls whether emails actually send (see
`app/email.py`):

- `console` (default) — prints the email to the server log. Fine for
  local dev; on Railway this means **no email ever reaches anyone**,
  because nobody reads the Railway log for that.
- `resend` — sends via the [Resend](https://resend.com) API. Requires
  `RESEND_API_KEY`.

Two easy-to-miss ways this silently doesn't work even with
`EMAIL_BACKEND=resend` set:

1. **`RESEND_API_KEY` missing/empty.** Until 19/09/2026 this silently
   fell back to the console backend with no warning at all. Fixed now —
   it logs `WARNING: EMAIL_BACKEND=resend but RESEND_API_KEY is empty`
   when this happens, so check the Railway logs for that line first.
2. **`EMAIL_FROM` still at its default**, `VokalBoard
   <onboarding@resend.dev>`. That's Resend's own shared *test* sender —
   it only ever delivers to the email address on your Resend account,
   never to anyone else. This is the most likely reason a real user
   (someone other than the Resend account owner) never received a
   confirmation or password-reset email. Fix: verify your own sending
   domain in the Resend dashboard, then set `EMAIL_FROM` to an address
   on it.

## Administering the site and viewing the database

Admin screens live under `/admin` (needs an account with `role_level >=
2`). To browse the database directly without writing SQL, start Adminer:
```
docker compose --profile admin up
```
then open http://localhost:8080. **Never expose port 8080 publicly**
without extra auth in front (SSH tunnel, or a proxy with login) — Adminer
alone only has the Postgres password protecting it.

## Database migrations

New schema changes go in `db/migrations/<date>_<name>.sql` and get
folded into `db/schema.sql` (kept as the current full schema, so a fresh
install never needs to replay migration history). See `AGENTS.md` for
the current status of pending migrations and the Railway-specific
gotcha with dollar-quoted (`DO $$...$$` / `CREATE FUNCTION ... $$...$$`)
blocks in the dashboard's web Query box — apply those with `psql`
instead, never pasted into that box.

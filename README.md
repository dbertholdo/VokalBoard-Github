# VokalBoard

Bulletin board for connecting singers and conductors in Germany —
inspired by ideas like Audition Oracle/Theapolis, but in the simple
format of a Craigslist: people post what they're looking for (or what
they're offering) and browse/filter other people's listings.

This project was built as a hands-on exercise in **SQL** and **web
development**. The technical decisions below were made on purpose to
maximize learning, not "maximum productivity."

## Stack

- **Backend:** Python + [FastAPI](https://fastapi.tiangolo.com/)
- **Database:** PostgreSQL, accessed with **raw SQL** via SQLAlchemy
  `text()` (no ORM) — see `app/database.py` and the files in
  `app/routers/`. The idea is that you read/write real SQL: `SELECT`,
  `JOIN`, dynamic `WHERE`, `INSERT ... RETURNING`.
- **Frontend:** server-side rendered HTML with Jinja2 (no JS
  framework) + plain CSS. Enough for the MVP, easy to swap later for
  React/Vue if you want to evolve it.
- **Authentication:** cookie-based session (Starlette's
  `SessionMiddleware`) + bcrypt password hashing.
- **Languages:** German and English, with a selector in the header.
  See `app/i18n.py` (translation dictionary) and `app/render.py`
  (injects the `t()` function and the current language into every
  template). The chosen language is saved in a cookie.
- **Deploy:** Docker + docker-compose to run locally; instructions for
  Railway/Render below.
- **CSRF:** manual protection via a "synchronizer token" — see the
  dedicated section further below.
- **Email:** signup confirmation and password recovery via email, with
  a pluggable email backend (`console` for development, `resend` for
  production) — see `app/email.py`.

## Project structure

```
vokalboard/
├── app/
│   ├── main.py                 # creates the FastAPI app, mounts routes
│   ├── database.py             # connection + raw SQL helpers
│   ├── auth.py                 # password hashing, user session
│   ├── i18n.py                  # DE/EN translation dictionary
│   ├── render.py                # Jinja2Templates wrapper with t()/lang
│   ├── routers/
│   │   ├── auth_routes.py      # /register, /login, /logout, email
│   │   │                       #   verification, forgot/reset password
│   │   ├── listings_routes.py  # /, /listings/..., search/filter
│   │   ├── profile_routes.py   # /profile (edit), /users/{id} (public)
│   │   └── messages_routes.py  # /messages, inbox/sent/trash
│   ├── csrf.py                  # CSRF protection (synchronizer token)
│   ├── email.py                  # email sending (console/Resend)
│   ├── templates/              # HTML (Jinja2)
│   └── static/css/style.css
├── db/
│   ├── schema.sql               # DDL: CREATE TABLE, indexes (already includes cities)
│   ├── seed_cities.sql          # DE/AT/CH cities (generated, see scripts/)
│   └── seed_sample_data.sql     # sample data (optional)
├── scripts/
│   └── generate_cities_seed.py  # regenerates db/seed_cities.sql from GeoNames
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Data model (schema)

- `voice_types` — support table, simplified to the 4 requested
  categories: Soprano, Alto, Tenor, Bass. At signup, the person picks
  directly one of these 4 options OR "Dirigent(in)" (conductor) — that
  single choice already sets both `role` and `voice_type_id`.
- `users` — singers and conductors in the same table, distinguished by
  `role`
- `singer_profiles` / `conductor_profiles` — extra 1:1 data tied to
  `users`, including `bio` (biography, capped at 1000 characters by a
  `CHECK` in the database — see `db/schema.sql`)
- `singer_composer_tags` — composer hashtags the singer has already
  sung (up to 10 per person, limit enforced at the application level).
  It's a separate table — not an array column — on purpose, so you can
  practice JOIN/GROUP BY (e.g. "which composers show up most on the
  platform?")
- `listings` — the bulletin board postings, with `listing_type`:
  - `seeking_singer` — conductor looking for a singer
  - `seeking_conductor` — singer looking for a conducting
    opportunity
  - `singer_available` — singer announcing availability
  - `conductor_available` — conductor announcing availability

- `singer_audio_links` — external links (YouTube, SoundCloud, etc.)
  for the singer's audio samples, up to 3 per person. **We don't store
  any audio files** — on purpose: storing media files would require
  object storage (S3/R2/Hetzner Object Storage) and more
  infrastructure, so the simpler solution (and more than enough for
  the use case) is for the person to paste a link to audio already
  hosted somewhere else.
- `email_verification_tokens` / `password_reset_tokens` — single-use,
  time-limited tokens for confirming email (48h) and resetting
  password (2h). See the "Email verification and password recovery"
  section.
- `messages` — internal messaging system between users (see the
  dedicated section below).
- `profile_views` — write-only log of profile visits (see the "Profile
  view counting" section).
- `cities` — real cities in Germany, Austria, and Switzerland (~1,270,
  sourced from GeoNames, population roughly ≥ 15,000), each already
  tied to its state/canton. Powers the cascading **Country > State >
  City** select used at signup, on the profile, and on the listing
  form — instead of city as free text, which used to let "München",
  "Munich", and "Muenchen" count as different places when matching
  singers and conductors in the same region. Not every small town is
  on the list; that's why there's always a "My city isn't listed"
  option that unlocks free text. The data comes from
  `db/seed_cities.sql`, generated by `scripts/generate_cities_seed.py`
  (run `pip install geonamescache --break-system-packages` and the
  script again only if you want to change the population cutoff or if
  the data goes stale — it's not a dependency of the app in
  production).

Each singer and conductor has a public profile page at `/users/{id}`
(name, city, voice type or choir/orchestra, biography, composer
hashtags, audio links, and active listings) and can edit their own
data at `/profile`.

## Role-based homepage (singer vs. conductor)

The homepage (`/`) changes behavior depending on who's logged in, so
singers don't see what's relevant to conductors and vice versa:

- **Logged-in singer:** sees by default only vacancies
  (`seeking_singer`) matching their own voice category — a tenor
  doesn't see alto vacancies, for example — but can adjust the filters
  (voice type, city, search) at any time.
- **Logged-in conductor:** sees by default available singers
  (`singer_available`), with filters by voice type, city, **and
  composer hashtag** (e.g. searching only for singers who have already
  sung Bach).
- **Anonymous visitor** (or any user with `?board=all`): sees the full
  bulletin board, with no role-based filter — useful before creating
  an account, or for anyone who wants to see everything.

Listings of type "seeking singer" (`seeking_singer`) — which both
conductors and other singers can post, since sometimes a singer is
also looking for colleagues for a gig — have extra required fields:
**Work**, **City**, **Fee**, and **Voice type** (with an explicit
"all voices" option); the **Venue/Ort** field (church, hall) is
optional. Whoever posted a listing can edit it later at
`/listings/{id}/edit`.

The full schema with comments is in `db/schema.sql` — it's worth
reading line by line, it's the best way to understand the "why" behind
each `FOREIGN KEY` and index.

## Running locally with Docker (recommended)

Prerequisite: [Docker](https://www.docker.com/) installed.

```bash
cd vokalboard
docker compose up --build
```

This spins up two containers:
1. `db` — PostgreSQL, already initialized with `schema.sql` + sample data
2. `web` — the FastAPI application, at http://localhost:8000

Sample users (password for all: `senha123`):
- `sofia.soprano@example.com` (singer, soprano)
- `tobias.tenor@example.com` (singer, tenor)
- `anna.dirigentin@example.com` (conductor, female)
- `markus.dirigent@example.com` (conductor, male)

To stop: `Ctrl+C` and then `docker compose down` (add `-v` to also
wipe the database data and start from scratch).

## Running without Docker (local Python + local Postgres)

```bash
# 1. Create a local PostgreSQL database called vokalboard
createdb vokalboard

# 2. Run the schema
psql vokalboard < db/schema.sql
psql vokalboard < db/seed_sample_data.sql   # optional

# 3. Configure the .env
cp .env.example .env
# edit .env with your local Postgres DATABASE_URL

# 4. Install dependencies
python -m venv venv
source venv/bin/activate  # on Windows: venv\Scripts\activate
pip install -r requirements.txt

# 5. Run the server
uvicorn app.main:app --reload
```

Go to http://localhost:8000

## Page structure (freemium)

- **`/`** — welcome screen. When logged in, shows "Welcome, {name}"
  and up to 5 listings matching the profile (singer: `seeking_singer`
  vacancies in their own voice category; conductor: `seeking_conductor`
  vacancies), prioritizing their own city. Without login, shows a
  teaser with the 5 most recent vacancies (title/city/type only, no
  description) and signup/login buttons.
- **`/board`** — the full bulletin board, with all filters (free-text
  search, city, country, voice type, listing type, composer hashtag).
  Open to any visitor, logged in or not.
- **`/listings/{id}`** and **`/users/{id}`** — **freemium model**:
  without login you can see that the listing/profile exists (title,
  city, badge, status dot), but the full description, contact details,
  biography, hashtags, and audio links only show up for people with an
  account. This is decided on the backend (`locked = user is None` in
  `listings_routes.py`/`profile_routes.py`), not just hidden via CSS —
  so there's no way to "view by hiding the JS."
- **`/profile`** — edit your own profile.
- **`/my-listings`** — post and edit your own listings.
- **`/messages`** — internal messenger.

## Country filter

Listings now have a `country` field (`DE`/`AT`/`CH`/`OTHER`), with
`DE` as the default. The country filter on `/board` exists because
singers and conductors in the German-speaking region circulate
between the three countries all the time — see the market analysis
section we discussed in chat.

## Date range filter (Zeitraum)

On `/board` you can filter by date range (`date_from`/`date_to`,
compared against `event_date`) — the use case is literally "I have
nothing booked in August, show me what exists between Aug 1 and Aug
31." Important behavior difference: choosing an explicit range
**replaces** the default "hide past events" filter — if you pick a
range that has already passed, listings from that range show up
anyway (the person is specifically asking for that period, so it makes
sense to show them even if it's in the past). Listings without an
`event_date` (e.g. "singer available," with no set date) can't match a
date range and are excluded while that filter is active.

## Event status indicator (colored dot)

Next to the title of any listing with an event date (`event_date`), a
colored dot appears:

- 🟢 **green** — event is still upcoming (more than 7 days away)
- 🟡 **yellow** — event happens within the next 7 days
- 🔴 **red** — event has already passed

This is calculated **at query time**, with a `CASE` in SQL comparing
`event_date` to `CURRENT_DATE` (see `EVENT_STATUS_SQL` in
`app/routers/listings_routes.py`) — it's not a column stored in the
database. This is a deliberate choice: since the status depends only
on today's date, calculating it at query time avoids needing a
nightly (cron) job to keep a "status" column always up to date.
Listings without an `event_date` show no dot at all.

## Email verification and password recovery

When signing up, the person receives an email with a confirmation link
(`/verify-email?token=...`), valid for 48 hours. While the email
hasn't been confirmed:

- A banner appears at the top of the site with a button to resend the
  confirmation email.
- The person **cannot post listings or send messages** (but can
  browse, filter, and edit their own profile normally).

Password recovery (`/forgot-password` → `/reset-password`) follows the
same single-use token pattern, valid for 2 hours. As a safeguard
against email enumeration, `/forgot-password` always shows the same
confirmation message, whether or not an account exists with that
email.

In development, emails aren't actually sent — they're just printed to
the server log (the `console` backend, the default). To send real
emails in production, configure this in `.env`:

```
EMAIL_BACKEND=resend
RESEND_API_KEY=your-key-here
EMAIL_FROM="VokalBoard <onboarding@resend.dev>"
```

The project uses the [Resend](https://resend.com/) API as an example
(generous free tier, simple HTTP-based API), but `app/email.py` was
written as a single function (`send_email`), so switching to another
provider (SendGrid, Mailgun, Amazon SES) is a matter of rewriting that
one function.

## What CSRF is and how this project protects against it

**CSRF (Cross-Site Request Forgery)** is an attack where a malicious
site makes the victim's browser send, without them noticing, a request
to *another* site (here, VokalBoard) by taking advantage of the fact
that the browser automatically sends that site's session cookies on
every request — including ones triggered from a different page.

Concrete example: you're logged in to VokalBoard. Without noticing,
you visit `malicious-site.com`, which has an invisible form pointing
to `POST vokalboard.de/listings/42/delete`. If the server only checked
"is there a valid session?", the browser would automatically send your
session cookie, and the attack would work — your listing would get
deleted without you having clicked anything on the real site.

The defense used here is the **"synchronizer token"** pattern (see
`app/csrf.py`):

1. When loading any page with a form, the server generates (or
   reuses) a random token and stores it in the user's session.
2. That same token is placed as a hidden field (`<input type="hidden"
   name="csrf_token">`) in every form.
3. On every `POST`, the server compares the token that came from the
   form with the one stored in the session. If they don't match (or
   it doesn't exist), the request is rejected with a 400 error.

A malicious site has no way to read the token from your session (it
doesn't run on your domain, and the token isn't a cookie — it's a
value inside the page's HTML), so it can't build a forged form that
passes this check. We tested this in practice: a `POST` with a wrong
or missing `csrf_token` is rejected with HTTP 400, even with a valid
session.

## Internal messaging system

Instead of exposing everyone's email publicly (which was already the
case before), you can now message someone directly through the
platform, via the "Send message" button on their public profile or
listing. The system has:

- **Inbox** (`/messages`) and **Sent** (`/messages/sent`).
- **Unread counter** in the menu, next to "Nachrichten/Messages".
- **Trash** (`/messages/trash`) and **"Empty trash"**.

Each message has **two status columns** (`sender_status` and
`recipient_status`, each `active` or `trashed`) — one for the sender,
one for the recipient — because trashing a message is a personal
action: if you delete a conversation from your trash, that shouldn't
affect what the other person sees on their end.

**Deliberate teaching simplification:** the "empty trash" button does
a real `DELETE` on the message row — which also removes the message
from the other person's side, even if they haven't trashed their own
copy. A "real" system would only delete the row once **both sides**
had status `trashed` (or would use a `deleted_at` column per side,
never doing an actual `DELETE`). I left this simplification in on
purpose as a next SQL exercise: you can change the `empty_trash` query
in `app/routers/messages_routes.py` to only delete when
`sender_status = 'trashed' AND recipient_status = 'trashed'`, and
create a separate keyword like "hide from my list" apart from "delete
for real."

## Profile view counting (private metric)

Every visit to a public profile (`/users/{id}`) writes a row to
`profile_views` (`profile_user_id`, `viewer_user_id` — null if
anonymous, `viewed_at`). **On purpose, this doesn't show up anywhere
in the UI** — not even for the profile owner — because it was
requested as a metric meant only for direct database queries, like a
simple, homegrown Google Analytics. Example query:

```sql
SELECT profile_user_id, COUNT(*) AS views
FROM profile_views
GROUP BY profile_user_id
ORDER BY views DESC;
```

## Practicing SQL with this project

Some suggested exercises using `psql` directly against the database
(`docker compose exec db psql -U vokalboard_user -d vokalboard`):

1. List all active listings with the name of who posted them (simple JOIN).
2. Count how many listings exist per `listing_type` (GROUP BY + COUNT).
3. List singers by voice type, including those who don't have any
   listing posted yet (LEFT JOIN).
4. Find the city with the most active listings in the last 30 days.
5. Using `singer_composer_tags`, find the 5 most-cited composers
   across all singers (JOIN + GROUP BY + COUNT + ORDER BY + LIMIT).
6. In `profile_views`, find the 5 most-visited profiles in the last 30
   days (GROUP BY + `WHERE viewed_at > now() - interval '30 days'`).
7. Fix the message trash simplification: rewrite the `empty_trash`
   query (`app/routers/messages_routes.py`) to only delete the row
   when **both sides** (`sender_status` and `recipient_status`) are
   `'trashed'`.
8. Find pairs of users who exchanged messages but never had contact
   through `listings` (JOIN between `messages` and `listings`,
   comparing `sender_id`/`recipient_id` with `author_id`).

## Deploy (Railway or Render)

Both support "deploy from a Dockerfile" in a fairly similar way.

### Railway

1. Create a new project → "Deploy from GitHub repo" (push this
   project to your own GitHub repository first).
2. Add a PostgreSQL service via the "New" → "Database" →
   "PostgreSQL" button. Railway generates a `DATABASE_URL`
   automatically.
3. In the application service (the one using the Dockerfile),
   configure the environment variables:
   - `DATABASE_URL`: copy from the "Variables" tab of the Postgres
     service, but swap the `postgresql://` prefix for
     `postgresql+psycopg2://`
   - `SECRET_KEY`: generate one with `python -c "import secrets; print(secrets.token_hex(32))"`
4. After the first deploy, run the schema against the Railway
   database. You can use the Postgres "Connect" button in the Railway
   dashboard to grab the connection string and run:
   ```bash
   psql "<railway-connection-string>" < db/schema.sql
   ```

### Render

1. "New +" → "Web Service" → connect your GitHub repository.
2. Render auto-detects the `Dockerfile`.
3. "New +" → "PostgreSQL" to create the managed database.
4. In the Web Service, under "Environment," add `DATABASE_URL` (with
   `postgresql+psycopg2://`) and `SECRET_KEY`.
5. Run the schema against the "External Database URL" shown on
   Render's database page:
   ```bash
   psql "<external-database-url>" < db/schema.sql
   ```

In both cases, the healthcheck at `/health` can be used by the
platform to check if the application is up.

## Domain and hosting (going beyond the free subdomain)

Railway/Render give you a subdomain like `your-app.up.railway.app` for
free — great for testing. For your own domain (`vokalboard.de`, for
example):

- **Registering the domain:** I recommend keeping "where I register
  the domain" separate from "where I host the app" — it gives you more
  freedom to switch hosting providers without losing the domain.
  - [INWX](https://www.inwx.com/) — a German registrar, a good option
    for `.de` domains (it does require some German contact details
    for `.de`, which can factor into the decision in the next point),
    fair pricing, panel in German/English.
  - [Porkbun](https://porkbun.com/) or [Namecheap](https://www.namecheap.com/) —
    good options for generic domains (`.com`, `.io`, `.app`),
    transparent pricing, no aggressive upselling.
- **Hosting:** you already have Railway/Render working with very
  little configuration (good for focusing on learning SQL/web, not
  DevOps). If down the line you want to learn more infrastructure
  (which pairs well with the Cloud/AWS track in your tech consultant
  course), it's worth considering [Hetzner Cloud](https://www.hetzner.com/cloud/) —
  a German provider, very cheap VPS, good latency for users in
  Germany, but requires you to configure the server yourself (Docker,
  HTTPS with Let's Encrypt/Caddy, backups).
  - Domain + Render/Railway = least effort.
  - Domain + Hetzner = more control and more ops learning, lower
    medium/long-term monthly cost.

## Site aimed at Germany, but eventually operated by someone in Brazil

You asked whether the site could keep serving a German audience while
being registered/administered in Brazil, with the idea of eventually
handing operations to your brother, who doesn't live in Germany. I'm
not a lawyer, so this is just a map of the terrain — it doesn't
replace real legal advice before launching something with real user
data:

- **Technically**, yes: nothing stops a site hosted or owned in Brazil
  from serving users in Germany — that's common.
- **Impressumspflicht (mandatory legal notice):** sites accessible in
  Germany with any commercial/professional character need an
  "Impressum" (identification of the person responsible, contact
  address, etc). This requirement currently lives in the
  *Digitale-Dienste-Gesetz* (DDG, which replaced the old TMG). It
  doesn't necessarily require the responsible person to live in
  Germany, but it needs to be a valid, reachable form of contact —
  worth confirming with a lawyer specialized in German digital law
  (*IT-Recht*) what counts as sufficient in your case.
- **GDPR/DSGVO:** since the platform collects personal data (name,
  email, phone, biography) from people in Germany/the EU, GDPR applies
  regardless of where the responsible company/person is based
  (extraterritorial effect, Art. 3). If whoever administers the site
  isn't established in the EU, GDPR Art. 27 generally requires
  appointing an **EU representative** — unless the data processing is
  occasional and low-risk, which hardly applies to an ongoing
  registration platform like this one.
- **In practice**, the most common paths for this kind of situation
  tend to be: (a) keeping you (a German resident) as the legal/
  Impressum responsible party while your brother handles day-to-day
  operations, or (b) hiring an EU GDPR representative service if/when
  formal responsibility actually shifts to Brazil. It's well worth
  validating this with a lawyer before moving from "study project" to
  "site with real users" — tools like [eRecht24](https://www.e-recht24.de/)
  or an *IT-Recht Kanzlei* generate Impressum/Datenschutzerklärung
  documents and also advise on this.

## Cascading location (Country > State), listing type, and filters

The listing form now asks for **State/Bundesland/Kanton**, in addition
to Country and City — required, along with the rest of the address
(follows the same "required in the app, optional in the schema"
pattern that City already used). The list of states (`STATE_OPTIONS`,
in `app/routers/listings_routes.py`) is a simple JavaScript cascade:
when the Country changes, the State `<select>` is repopulated (for
"Other country" it becomes free text). There's no third cascade level
for City — that would require a full geographic database (like
GeoNames), which was left out of scope for now; City remains free
text.

The listing also gained a **Solo / Choir / Both** field
(`ensemble_type`), meant for people looking for section reinforcement
vs. those looking for a solo singer vs. both. Both fields were added
as filters on `/board`.

## Social links on the profile

On `/profile`, each person can optionally add up to one link per
platform: Website, Facebook, Instagram, Twitter, WhatsApp — table
`user_social_links`, one row per platform (`UNIQUE(user_id,
platform)`). On the public profile (`/users/{id}`), instead of the raw
link, a button shows only the platform name ("Instagram", "Facebook"…)
to keep the page uncluttered — the full URL sits behind the `href`.
Only `http(s)://` links are accepted; anything else pasted there is
simply ignored on save.

## Star rating (private)

On `/users/{id}`, any logged-in person (except the profile owner
themselves) can give a rating from 0 to 5 stars + an optional comment.
**The requested rule was: only the person who received the rating can
see it — no one else.** This is guaranteed by *where* the query runs,
not by a permission check: `get_my_ratings()`/`get_rating_summary()`
(the only functions that fetch *received* ratings) are only called
from `/profile` — the person viewing what they themselves received.
The public route `/users/{id}` never calls those functions; it only
uses `get_rating_given()`, which is "the rating I have already given
this person" (to pre-fill the form in case I want to update it).
Re-rating the same person does an UPSERT (`ON CONFLICT (rater_id,
rated_id) DO UPDATE`) instead of piling up repeated ratings.

## Archiving past events

Listings with an `event_date` in the past disappear by default from
`/board` and from the Home suggestions (but stay in the database,
reachable by direct link and visible under "My listings"). Just like
the status dot, this is calculated **at query time**
(`WHERE event_date IS NULL OR event_date >= CURRENT_DATE`), with no
job/cron at all — the filter "hides/shows" listings on its own as days
go by. `/board?show_past=1` shows everything again, including past
events.

## Pagination

`/board` now paginates 20 at a time (`LIMIT`/`OFFSET` + a separate
`COUNT(*)` query to know the total number of pages) — before, the
whole page came as a single list, which would have become impractical
as the volume of listings grew.

## "Message already sent"

On `/listings/{id}`, if you've already sent at least one message about
that specific listing, a "Message already sent for this listing"
notice appears. This **doesn't block** you from sending another one —
it's just a reminder to avoid flooding the poster's inbox with the
same question multiple times.

## Change password and delete account (with recovery period)

- **`/profile/change-password`** — asks for the current password + a
  new one (minimum 6 characters), reuses `verify_password`/
  `hash_password` from `app/auth.py`.
- **Delete account** (the "Gefahrenzone" section on `/profile`) — asks
  for the password again for security. It's a **soft delete**: writes
  `deleted_at = now()` on the user's row instead of actually deleting
  it. From then on, `get_current_user()` and every author JOIN
  (`u.deleted_at IS NULL`) start ignoring that account — it disappears
  from the site as if it had been deleted, but the data stays in the
  database. If the person tries to log in again within 6 months, the
  login detects the deactivated account and sends them to
  `/reactivate-account`, which only requires confirming the password
  (no need for a new email/token flow). After 6 months, a separate
  script (`scripts/purge_deleted_accounts.py`, run via system cron or
  manually — **not** a job inside the app, following the same "no
  built-in cron" principle as the rest of the project) permanently
  deletes those accounts.

## Profile photo

Direct upload (no external service) on `/register` and `/profile` —
JPG/PNG/WebP, up to 3 MB, validated by Content-Type and size (see
`app/avatars.py`). The file is saved at
`app/static/avatars/{user_id}.{ext}`, which is already served publicly
by the same `StaticFiles` mount as the rest of the CSS/JS
(`/static/...`), with no need for a new mount. **Heads up:** on
platforms like Railway/Render (free tier), the container's disk is
ephemeral — a new deploy wipes these photos. Acceptable for a small
beta; if the project grows, the next step is migrating to object
storage (S3, Cloudflare R2, etc.).

## Matching listing alert

When someone posts a `seeking_singer` or `seeking_conductor` listing,
everyone with a matching profile (right voice, or conductor role) who
hasn't turned off alerts gets an email right away — not a daily
digest, it's actually immediate (`app/notifications.py`). It runs as a
FastAPI `BackgroundTask`: the listing gets posted and the person is
redirected right away, the emails go out afterward, in the background,
without delaying the response. Each person can toggle this on/off in
`/profile` (`users.notify_matches`, on by default).

## Favorite a listing

"☆ Favorite" button on `/listings/{id}` (for non-authors), listed at
`/my-favorites`. Simple `saved_listings` table with `UNIQUE(user_id,
listing_id)` — favoriting an already-favorited listing again does
nothing (`ON CONFLICT DO NOTHING`), and `/board` marks already
favorited listings with a ⭐ (computed with a correlated `EXISTS`
directly in the list query, no N+1).

## Export my data

`/profile/export` — downloads a `.json` with everything the person has
on record (profile, listings, messages sent/received, ratings
given/received, favorites). This is the GDPR data portability right
(Art. 20) — deliberately does NOT include `password_hash` (that's not
"your data" in the portability sense, it's an authentication secret).

## Profile completeness indicator

On `/profile`, a bar shows how much of the profile is filled in
(`compute_profile_completeness()` in
`app/routers/profile_routes.py`) — photo, city, phone, bio, social
link, and (for singers) voice type/hashtags/audio, or (for conductors)
ensemble name. Each item counts equally; the message reinforces that a
more complete profile builds more trust with visitors and improves the
automatic matches on the Home page (voice/city/hashtags feed into that
calculation).

## New look ("quiet luxury")

The CSS was redesigned (`app/static/css/style.css`) inspired by the
style (not the literal design — nothing was copied) of "premium beauty
studio" sites: ivory/cream as the background, burgundy as the accent
color, muted gold as a secondary color, a serif face (Playfair
Display, via Google Fonts) for headings and a sans-serif (Inter) for
body text. Since the rest of the site already used CSS variables
(`:root { --accent: ...; }`) instead of colors hardcoded into each
rule, swapping the entire palette was just a matter of changing those
variables — buttons, badges, cards, and forms adapted on their own.

## "Invite a friend" (referrals)

Each person has a short, unique code (`users.referral_code`, generated
the first time they visit `/profile` — `app/referrals.py`), used in a
link like `/register?ref=CODE`. Whoever signs up arriving through that
link has it saved in `users.referred_by_user_id`. On `/profile`, a
ready-to-copy link and how many people each user has referred both
appear.

There's no automatic reward/discount for referrals (the site doesn't
charge anything) — it's just a way for the community itself to bring
in more people, with the referral count serving as simple recognition
for whoever refers.

## Blocking people

On any public profile (`/users/{id}`) you can block the person
(optional reason), which does two things: (1) neither side can send
the other a message anymore (checked in both directions in
`POST /messages/send`), and (2) the blocked person's listings
disappear from `/board` and from the Home matches of whoever blocked
them (`NOT EXISTS` filter against `blocked_users`). The list of people
you've blocked, with an unblock button, lives on `/profile`. Blocking
is a one-way decision — blocking someone doesn't stop the other person
from still seeing your listings, unless they also block you.

## Report a listing

On every listing (except your own), a "Report listing" button opens a
form that requires a reason of at least 10 characters (also enforced
at the database level via a `CHECK` on `listing_reports.reason` — not
just form validation). There's no moderation screen on the site: the
reports are stored in `listing_reports` to be queried directly from
the database by whoever administers the site (same pattern already
used for `profile_views`, the profile view counter).

## Email on every new message

Besides the "matching listing" alert that already existed, each person
can now toggle on/off (`/profile`, `users.notify_messages`) an email
notification every time they receive a new message
(`POST /messages/send` in `messages_routes.py`, via `BackgroundTask` —
doesn't delay the send). On purpose, the email doesn't show the
message content, it just notifies that one arrived — this helps bring
the person back to the site to read it.

## Impressum

`/impressum` — required for any site operating in
Germany/Austria/Switzerland (Impressumspflicht, Art. 5 TMG), even when
administered from abroad. The page already makes clear that the site
is operated from Brazil, but the real details (legal name, address,
contact) still need to be filled in — see
`app/templates/impressum.html`, marked as `[PREENCHER: ...]` ("FILL
IN: ..."). **Do not publish the site with these fields still empty.**

## Code of conduct

`/code-of-conduct` — simple, straightforward rules of behavior on the
site (respect, honesty in listings, no spam, privacy, keeping a
professional tone, reporting instead of confronting). Doesn't depend
on any personal data, so it's already ready to use.

## Badges (light gamification)

On `/profile`, a section shows "achievements" computed on the fly from
what's already in the database (`app/badges.py`): referred a friend
(who verified their email — see "Referrals and abuse" below), posted a
listing, contacted someone, replied to a message within 24h at least
once, 100% complete profile, "gefragt/in demand" by visit volume
(100/500/1000), and "anniversary" by account age (1 year, 2 years…).
Only UNLOCKED badges show up on the public profile (`/users/{id}`); on
your own page (`/profile`) you see all of them, including the ones you
haven't unlocked yet.

On purpose, this is **not a ranking**: there's no screen that compares
one person against another, and the visit badge only shows "above X
visits," never the exact number — preserving the decision to keep
`profile_views` private.

**Email on every new badge**: a `user_badges` table (see
`db/schema.sql`) records when each badge/tier was first unlocked — it
doesn't store the RULE for any badge (that's still computed on the
fly), only the record of "already notified about this one." This
avoids sending the email again every time the page recomputes badges,
and lets multi-tier badges (visits, anniversary) send one email per
tier reached.

**When the check runs**: after actions that could plausibly unlock a
badge (posting a listing, sending a message, saving the profile) — and
also, "lazily," every time you open your own `/profile`. This covers
the anniversary and visit badges, which don't depend on a specific
action of yours: since the project doesn't use any internal cron, the
most natural and frequent visit (you opening your own profile) is
already enough to keep this up to date without needing any scheduled
job.

**Other light gamification ideas** (not implemented, but easy to slot
into the same `app/badges.py` pattern if you want):
- Badge for referral diversity — referred both singers and
  conductors.
- "Recently verified/active profile" badge (updated something in the
  last 30 days) — signals activity without exposing time online.
- A "monthly digest" email aggregating everything that happened in the
  week (new badges, messages, listing views) instead of one email per
  event — reduces email volume as the user base grows.
- "First reply in under 1h" badge (a tier above the 24h reply) — same
  pattern as `_has_fast_response`, just with a smaller window.

### Referrals and abuse (referral gaming)

One thing worth flagging: since there's no CAPTCHA or signup limit on
`/register`, nothing stopped (before this round) someone from
inflating their own referral count — and now the "Botschafter(in)"
badge — by creating several fake accounts through their own link. I
reduced (didn't eliminate) this: `get_referral_stats()` and the
referral badge only count referred people who **verified their
email** (`app/referrals.py`). This doesn't stop it 100% (you can still
verify disposable emails), but it's already a real barrier against the
simplest case. If this ever becomes a real problem, the next barriers
would be: CAPTCHA at signup, or a limit of X signups per IP/day.

## Blocking is invisible on both sides

Blocking someone (from `/users/{id}` or the list on `/profile`) now
makes each person's profile disappear from the other in both
directions — no matter who blocked whom, neither can see the other's
profile (`/users/{id}` just shows a generic notice, without revealing
the reason or who did the blocking), send messages, or see the other's
listings on `/board`/Home. Only the person who did the blocking sees
the other person in their own blocked list (with an unblock button) on
`/profile` — the blocked person never finds out they were blocked from
there.

## Spam folder notice on the Home page

Logged-in users see, on the Home page, a notice reminding them to
check their spam folder and mark the site's emails as "not spam" (so
they don't miss message/matching-listing alerts) — with a "✕" to
dismiss it. The choice is saved in the person's browser
(`localStorage`) **with a date**, not as "never show again": the
notice reappears automatically a week after being dismissed
(`app/templates/home.html`, `ONE_WEEK_MS`). This balances not being
annoying on every visit with not letting the notice disappear forever.

## Administrative access levels (`users.role_level`)

`users.role_level` (integer, 0 to 3 — see `db/schema.sql` and
`app/permissions.py`) is a scale, not a boolean:

- `0` — regular, no access to `/admin`
- `1` — moderator: only the `/admin` panel (read + reports/blocks)
- `2` — admin: everything `/admin` already did (users, posts, data
  analysis)
- `3` — god mode: everything above + the **Red Zone**
  (`/financeiro`) — Capitalism Mode, subscription pricing, internal
  financial panel

The old `is_admin BOOLEAN` column still exists, just for compatibility
with older screens/queries, and is kept automatically in sync with
`role_level >= 2` (both by the application —
`app/permissions.py:sync_is_admin_flag` — and by a trigger in the
database itself, `trg_sync_role_level`, in case someone edits
`is_admin` directly in Adminer/SQL without going through the
application).

**How to become god mode the first time**: there's no signup flow for
it through the UI (on purpose — it's a sensitive level). Directly in
the database:
```sql
UPDATE users SET role_level = 3 WHERE email = 'your-email@example.com';
```
(The trigger takes care of setting `is_admin = TRUE` too,
automatically.) After the first god mode account exists, promoting
other people can be done through the UI (`/admin/users/{id}`, "Make
admin" and "Grant god mode" buttons) — granting god mode to someone
can only be done by someone who is **already** god mode, never by a
regular admin.

Anyone trying to access `/admin` or `/financeiro` without the
required level is just redirected to the home page, with no message
revealing that the page exists. `require_level()` in
`app/permissions.py` is the single point that checks this — any future
admin route should call this same function at the start, instead of
reimplementing the check.

## Administering the site and viewing the database live

My recommendation stays the same: **it's not worth building a separate
admin API** — the `/admin` panel above already covers "take a quick
look without SQL," and Adminer covers "actually edit/query." For "view
and edit live" without writing any code, two ready-made options:

- **Adminer** — a single-file web interface, already included in this
  project as an optional service in `docker-compose.yml` (profile
  `admin`, doesn't start on its own). To use it locally:
  ```
  docker compose --profile admin up
  ```
  and open `http://localhost:8080` (server: `db`, user/password/
  database as in your `.env`). Lets you browse tables, run SQL, edit
  rows live — exactly what you asked for.
- **pgAdmin** — heavier than Adminer, but with more features (query
  charts, a more complete editor) if you ever miss something Adminer
  doesn't have.

**Important if you go beyond your own computer**: never expose
Adminer's port (8080), or `/admin`, publicly without extra protection
in front — an SSH tunnel (`ssh -L 8080:localhost:8080 your-server`) or
a reverse proxy with login (e.g. Caddy/nginx with basic auth) in
front. Adminer alone only has the Postgres password protecting it, and
`/admin` only has the site's normal login session (no 2FA) — which
isn't enough exposed directly on the internet.

## CAPTCHA (anti-bot protection)

Two layers, following the same "pluggable backend" pattern already
used for email (`app/email.py`):

1. **Honeypot** (`app/captcha.py`) — always on, zero configuration. An
   extra field (`website`) hidden off-screen via CSS on `/register`
   and `/forgot-password`: humans never see or fill it, generic bots
   fill everything in automatically. If it comes back filled in, we
   treat it as if the submission had succeeded (same redirect/message
   as always) except **without** creating the account or sending the
   email — no hint is given to the bot about why. Tested: a "bot" that
   fills the field doesn't create an account or receive a reset email;
   a normal submission (empty field) keeps working the same as always.
2. **Cloudflare Turnstile** (optional) — a genuinely "nearly
   invisible" challenge, without Google reCAPTCHA's privacy issues.
   Only turns on if you configure two keys in `.env`:
   ```
   TURNSTILE_SITE_KEY=...
   TURNSTILE_SECRET_KEY=...
   ```
   To get these keys (free): create an account at
   https://dash.cloudflare.com/ (no need to migrate your domain there)
   → **Turnstile** → **Add site** → copy the two keys. Without them
   configured, the site stays protected by the honeypot alone — which
   is already a real barrier against generic bots, just not against
   someone specifically trying to abuse your site.

The honeypot covers signup (which became more of a target after the
referral system) and "forgot password" (avoids reset-email spam).
Login has no CAPTCHA — there, the risk is password brute-forcing, not
signup bots, and the right defense for that is rate-limiting attempts
per account/IP, not a CAPTCHA; listed below as a next step, not
implemented yet.

## Datenschutzerklärung

`/datenschutz` — the "real" privacy policy (the Impressum identifies
WHO operates the site; this explains WHAT we do with the data).
Covers: what data we collect and why (account, listings, messages,
referrals, optional emails, profile visits, reports/blocks), cookies
(technical only — session and language, no tracking, so no cookie
banner is needed), who we share data with (hosting, Resend for email,
other users see only what you make public), how long we keep data
(tied to account deletion with a 6-month recovery window), your rights
(access, correction, deletion, portability — GDPR Art. 15–21), and
security (bcrypt, CSRF).

**One point is marked as `[NOCH MIT ANWALT/ANWÄLTIN ZU PRÜFEN]`
("still needs to be reviewed with a lawyer")**: section 4, on
international data transfer — since the site is operated from Brazil
but mainly serves Germany/Austria/Switzerland, there's a data transfer
between countries that technically requires a specific protection
mechanism (EU standard contractual clauses, for example). This depends
on details of your final hosting provider and is the kind of thing
worth confirming with a lawyer before accepting real user data — it's
not something that can be resolved just by writing the right text.

## Suggested next steps

- Add automated tests (pytest + test database).
- Switch authentication to JWT if a separate API is ever needed for a
  mobile app.
- Fill in the real Impressum details (name, address, contact) — see
  the "Impressum" section above. The Impressum and Datenschutz pages
  already exist and render normally with fields marked as
  `[PREENCHER: ...]`; nothing stops publishing the site with them like
  that, as long as the real text goes in as soon as possible
  afterward.
- Review the Datenschutzerklärung with a lawyer when you can —
  especially section 4 (international data transfer), marked as
  pending. Recommended to do this soon after launch, but not a
  technical blocker.
- Rate limiting on `/login` (password attempts per account/IP) — the
  CAPTCHA above covers signup bots and password-reset spam, but not
  login brute-forcing, which calls for a different defense (attempt
  counting, not a human/bot challenge).
- A daily message limit per account, if message spam becomes a real
  problem as the user base grows (mentioned, not implemented yet —
  left for if/when it makes sense).
- See the "Internal messaging system" section above for the pending
  trash simplification.
- Rating eligibility ("only someone who hired/worked with the person
  can rate them"), a "match found" flow (closes the listing, unlocks
  mutual rating), and an application system ("I'm interested" per
  listing) — three ideas discussed in chat, not implemented yet. See
  the detailed answer in chat about how each one could work.
- Rethink the "most active members ranking" idea — see the detailed
  answer in chat about why this is in tension with the decision to
  keep `profile_views` private, and the suggested retention
  alternatives.

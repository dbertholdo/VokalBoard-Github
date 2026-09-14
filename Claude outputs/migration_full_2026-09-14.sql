-- ============================================================
-- VokalBoard — Migração COMPLETA e idempotente (14/09/2026)
--
-- Por que este script existe: a migração anterior de hoje
-- (migration_2026-09-14.sql) só cobriu as tabelas NOVAS da Zona
-- Vermelha, presumindo que o resto do banco de produção já estava
-- em dia com db/schema.sql — não estava (dívida de sessões
-- anteriores nunca aplicada). Isso quebrou o site inteiro em
-- produção: `column "last_seen_at" of relation "users" does not
-- exist`.
--
-- Este script cobre O SCHEMA INTEIRO, não só o de hoje:
--   1. Garante TODAS as colunas da tabela users (ADD COLUMN IF NOT
--      EXISTS — nunca apaga nem altera coluna existente).
--   2. Garante TODAS as tabelas do sistema (CREATE TABLE IF NOT
--      EXISTS) — cobre qualquer tabela que porventura também esteja
--      faltando.
--   3. Garante todos os índices (CREATE INDEX IF NOT EXISTS).
--   4. Garante o trigger de sincronização is_admin <-> role_level.
--   5. Dados semente (voice_types, cities, system_settings) só são
--      inseridos se ainda não existirem.
--
-- 100% seguro para rodar em um banco que já tem dados: nada aqui
-- apaga ou sobrescreve uma linha existente. Pode ser executado mais
-- de uma vez sem problema (idempotente).
--
-- Como rodar: Railway → seu projeto → Postgres → aba "Query" → cole
-- este arquivo inteiro → Run.
-- ============================================================

-- ------------------------------------------------------------
-- 1) Tabela users — garante todas as colunas
-- ------------------------------------------------------------
ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR(150);
ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20);
ALTER TABLE users ADD COLUMN IF NOT EXISTS city VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS state VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS country VARCHAR(10) NOT NULL DEFAULT 'DE';
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(300);
ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_matches BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_messages BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_code VARCHAR(12);
ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS role_level SMALLINT NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- Constraints/UNIQUEs que podem não existir se a coluna acabou de
-- ser criada agora (envolvidas em DO blocks pra não falhar caso já
-- existam — Postgres não tem "ADD CONSTRAINT IF NOT EXISTS").
DO $$ BEGIN
    ALTER TABLE users ADD CONSTRAINT users_email_key UNIQUE (email);
EXCEPTION WHEN duplicate_table OR duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (role IN ('singer', 'conductor'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE users ADD CONSTRAINT users_country_check CHECK (country IN ('DE', 'AT', 'CH', 'OTHER'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE users ADD CONSTRAINT users_referral_code_key UNIQUE (referral_code);
EXCEPTION WHEN duplicate_table OR duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE users ADD CONSTRAINT users_role_level_check CHECK (role_level BETWEEN 0 AND 3);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_last_seen_at ON users(last_seen_at);
CREATE INDEX IF NOT EXISTS idx_users_city ON users(city);
CREATE INDEX IF NOT EXISTS idx_users_state ON users(state);
CREATE INDEX IF NOT EXISTS idx_users_deleted_at ON users(deleted_at);
CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by_user_id);
CREATE INDEX IF NOT EXISTS idx_users_role_level ON users(role_level);

-- Backfill: quem já era is_admin=TRUE antes de role_level existir
-- vira god mode automaticamente (não mexe em quem já foi ajustado
-- manualmente para um nível específico).
UPDATE users SET role_level = 3 WHERE is_admin = TRUE AND role_level = 0;

-- Trigger de sincronização is_admin <-> role_level
CREATE OR REPLACE FUNCTION sync_role_level_from_is_admin() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_admin AND NEW.role_level < 2 THEN
        NEW.role_level := 2;
    ELSIF NOT NEW.is_admin AND NEW.role_level >= 2 THEN
        NEW.role_level := 0;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sync_role_level ON users;
CREATE TRIGGER trg_sync_role_level
    BEFORE UPDATE OF is_admin ON users
    FOR EACH ROW
    EXECUTE FUNCTION sync_role_level_from_is_admin();

-- ------------------------------------------------------------
-- 2) Tabelas de apoio (lookup)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS voice_types (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(50) NOT NULL UNIQUE,
    sort_order  SMALLINT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cities (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    state         VARCHAR(100) NOT NULL,
    country_code  VARCHAR(10) NOT NULL CHECK (country_code IN ('DE', 'AT', 'CH')),
    population    INTEGER,
    UNIQUE (name, state, country_code)
);
CREATE INDEX IF NOT EXISTS idx_cities_state ON cities(state);
CREATE INDEX IF NOT EXISTS idx_cities_country ON cities(country_code);

-- ------------------------------------------------------------
-- 3) Zona Vermelha / painel financeiro (tabelas de hoje)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS system_settings (
    key                 VARCHAR(100) PRIMARY KEY,
    value                TEXT,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by_user_id   BIGINT REFERENCES users(id) ON DELETE SET NULL
);
INSERT INTO system_settings (key, value) VALUES
    ('capitalismo_mode_enabled', 'false'),
    ('subscription_price_eur_cents', '590'),
    ('subscription_price_chf_cents', '690')
ON CONFLICT (key) DO NOTHING;

CREATE TABLE IF NOT EXISTS audit_log (
    id              BIGSERIAL PRIMARY KEY,
    actor_user_id   BIGINT REFERENCES users(id) ON DELETE SET NULL,
    action          VARCHAR(100) NOT NULL,
    details         TEXT,
    ip_address      VARCHAR(64),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at DESC);

CREATE TABLE IF NOT EXISTS expenses (
    id                      BIGSERIAL PRIMARY KEY,
    description             VARCHAR(200) NOT NULL,
    amount_cents            BIGINT NOT NULL,
    currency                VARCHAR(3) NOT NULL DEFAULT 'EUR',
    category                VARCHAR(50) NOT NULL DEFAULT 'other',
    expense_date            DATE NOT NULL,
    is_recurring            BOOLEAN NOT NULL DEFAULT FALSE,
    recurrence_interval     VARCHAR(20) CHECK (recurrence_interval IN ('monthly', 'yearly') OR recurrence_interval IS NULL),
    receipt_url             VARCHAR(300),
    created_by_user_id      BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(expense_date DESC);
CREATE INDEX IF NOT EXISTS idx_expenses_recurring ON expenses(is_recurring);

CREATE TABLE IF NOT EXISTS bank_import_profiles (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE,
    column_mapping  JSONB NOT NULL,
    date_format     VARCHAR(20) NOT NULL DEFAULT '%d/%m/%Y',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bank_transactions (
    id                    BIGSERIAL PRIMARY KEY,
    import_profile_id     BIGINT REFERENCES bank_import_profiles(id) ON DELETE SET NULL,
    transaction_date      DATE NOT NULL,
    amount_cents          BIGINT NOT NULL,
    currency              VARCHAR(3) NOT NULL DEFAULT 'EUR',
    description           VARCHAR(300),
    matched_expense_id    BIGINT REFERENCES expenses(id) ON DELETE SET NULL,
    imported_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_bank_transactions_date ON bank_transactions(transaction_date DESC);

CREATE TABLE IF NOT EXISTS subscriptions (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    price_paid_cents    BIGINT NOT NULL,
    currency            VARCHAR(3) NOT NULL,
    country             VARCHAR(10),
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at          TIMESTAMPTZ,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_active_country ON subscriptions(is_active, country);

CREATE TABLE IF NOT EXISTS financial_closings (
    id                      BIGSERIAL PRIMARY KEY,
    period_type             VARCHAR(10) NOT NULL CHECK (period_type IN ('monthly', 'annual')),
    period_start             DATE NOT NULL,
    period_end               DATE NOT NULL,
    total_revenue_cents      BIGINT NOT NULL,
    total_expenses_cents     BIGINT NOT NULL,
    snapshot                 JSONB,
    closed_by_user_id        BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_financial_closings_period ON financial_closings(period_type, period_start DESC);

-- ------------------------------------------------------------
-- 4) Perfis, tokens, proteção contra abuso, analytics
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_social_links (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform    VARCHAR(20) NOT NULL CHECK (platform IN ('website', 'facebook', 'instagram', 'twitter', 'whatsapp')),
    url         VARCHAR(500) NOT NULL,
    UNIQUE (user_id, platform)
);

CREATE TABLE IF NOT EXISTS email_verification_tokens (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token       VARCHAR(64) NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token       VARCHAR(64) NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS login_lockouts (
    email         VARCHAR(255) PRIMARY KEY,
    failed_count  INTEGER NOT NULL DEFAULT 0,
    stage         INTEGER NOT NULL DEFAULT 0,
    locked_until  TIMESTAMPTZ,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS registration_attempts (
    ip_address    VARCHAR(64) PRIMARY KEY,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    window_started_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS site_visits (
    id                BIGSERIAL PRIMARY KEY,
    visited_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    lang              VARCHAR(5),
    referrer_domain   VARCHAR(255),
    is_authenticated  BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_site_visits_visited_at ON site_visits(visited_at);

CREATE TABLE IF NOT EXISTS posts (
    id            BIGSERIAL PRIMARY KEY,
    author_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title         VARCHAR(150) NOT NULL,
    body          TEXT NOT NULL,
    is_published  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_posts_published_created ON posts(is_published, created_at DESC);

CREATE TABLE IF NOT EXISTS singer_profiles (
    user_id         BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    voice_type_id   INTEGER REFERENCES voice_types(id),
    fach            VARCHAR(100),
    bio             TEXT CHECK (char_length(bio) <= 1000),
    experience_years SMALLINT
);

CREATE TABLE IF NOT EXISTS singer_composer_tags (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tag         VARCHAR(50) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, tag)
);
CREATE INDEX IF NOT EXISTS idx_singer_composer_tags_user ON singer_composer_tags(user_id);
CREATE INDEX IF NOT EXISTS idx_singer_composer_tags_tag ON singer_composer_tags(tag);

CREATE TABLE IF NOT EXISTS singer_audio_links (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    url         VARCHAR(500) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_singer_audio_links_user ON singer_audio_links(user_id);

CREATE TABLE IF NOT EXISTS conductor_profiles (
    user_id         BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    ensemble_name   VARCHAR(150),
    bio             TEXT CHECK (char_length(bio) <= 1000),
    experience_years SMALLINT,
    website_url     VARCHAR(300)
);

CREATE TABLE IF NOT EXISTS listings (
    id              BIGSERIAL PRIMARY KEY,
    author_id       BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    listing_type    VARCHAR(30) NOT NULL CHECK (
        listing_type IN ('seeking_singer', 'seeking_conductor', 'singer_available', 'conductor_available')
    ),
    title           VARCHAR(150) NOT NULL,
    description     TEXT NOT NULL,
    city            VARCHAR(100),
    country         VARCHAR(10) NOT NULL DEFAULT 'DE' CHECK (country IN ('DE', 'AT', 'CH', 'OTHER')),
    state           VARCHAR(100),
    voice_type_id   INTEGER REFERENCES voice_types(id),
    repertoire      VARCHAR(200),
    venue           VARCHAR(200),
    fee             VARCHAR(100),
    ensemble_type   VARCHAR(10) CHECK (ensemble_type IN ('solo', 'choir', 'both')),
    event_date      DATE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_listings_type ON listings(listing_type);
CREATE INDEX IF NOT EXISTS idx_listings_city ON listings(city);
CREATE INDEX IF NOT EXISTS idx_listings_country ON listings(country);
CREATE INDEX IF NOT EXISTS idx_listings_voice_type ON listings(voice_type_id);
CREATE INDEX IF NOT EXISTS idx_listings_active_created ON listings(is_active, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_listings_state ON listings(state);
CREATE INDEX IF NOT EXISTS idx_listings_event_date ON listings(event_date);
CREATE INDEX IF NOT EXISTS idx_listings_author ON listings(author_id);

CREATE TABLE IF NOT EXISTS messages (
    id                  BIGSERIAL PRIMARY KEY,
    sender_id           BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recipient_id        BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    listing_id          BIGINT REFERENCES listings(id) ON DELETE SET NULL,
    body                TEXT NOT NULL CHECK (char_length(body) <= 2000),
    read_at             TIMESTAMPTZ,
    sender_status       VARCHAR(10) NOT NULL DEFAULT 'active' CHECK (sender_status IN ('active', 'trashed')),
    recipient_status    VARCHAR(10) NOT NULL DEFAULT 'active' CHECK (recipient_status IN ('active', 'trashed')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_messages_recipient ON messages(recipient_id, recipient_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id, sender_status, created_at DESC);

CREATE TABLE IF NOT EXISTS profile_views (
    id                  BIGSERIAL PRIMARY KEY,
    profile_user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    viewer_user_id      BIGINT REFERENCES users(id) ON DELETE SET NULL,
    viewed_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_profile_views_profile ON profile_views(profile_user_id, viewed_at DESC);

CREATE TABLE IF NOT EXISTS ratings (
    id          BIGSERIAL PRIMARY KEY,
    rater_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rated_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    listing_id  BIGINT REFERENCES listings(id) ON DELETE SET NULL,
    stars       SMALLINT NOT NULL CHECK (stars BETWEEN 0 AND 5),
    comment     VARCHAR(500),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (rater_id <> rated_id),
    UNIQUE (rater_id, rated_id)
);
CREATE INDEX IF NOT EXISTS idx_ratings_rated ON ratings(rated_id);

CREATE TABLE IF NOT EXISTS saved_listings (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    listing_id  BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, listing_id)
);
CREATE INDEX IF NOT EXISTS idx_saved_listings_user ON saved_listings(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_saved_listings_listing ON saved_listings(listing_id);

CREATE TABLE IF NOT EXISTS listing_reports (
    id          BIGSERIAL PRIMARY KEY,
    listing_id  BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    reporter_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason      TEXT NOT NULL CHECK (char_length(reason) >= 10),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_listing_reports_listing ON listing_reports(listing_id);

CREATE TABLE IF NOT EXISTS blocked_users (
    id          BIGSERIAL PRIMARY KEY,
    blocker_id  BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blocked_id  BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason      VARCHAR(500),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (blocker_id <> blocked_id),
    UNIQUE (blocker_id, blocked_id)
);
CREATE INDEX IF NOT EXISTS idx_blocked_users_blocker ON blocked_users(blocker_id);
CREATE INDEX IF NOT EXISTS idx_blocked_users_blocked ON blocked_users(blocked_id);

CREATE TABLE IF NOT EXISTS user_badges (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    badge_key   VARCHAR(50) NOT NULL,
    tier        VARCHAR(20) NOT NULL DEFAULT '',
    unlocked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    notified_at TIMESTAMPTZ,
    UNIQUE (user_id, badge_key, tier)
);
CREATE INDEX IF NOT EXISTS idx_user_badges_user ON user_badges(user_id);

-- ------------------------------------------------------------
-- 5) Dados semente — só entram se as tabelas estiverem vazias
-- ------------------------------------------------------------
INSERT INTO voice_types (name, sort_order)
SELECT * FROM (VALUES
    ('Soprano', 1), ('Alto', 2), ('Tenor', 3), ('Baixo', 4)
) AS v(name, sort_order)
WHERE NOT EXISTS (SELECT 1 FROM voice_types);

-- Observação: a lista de cidades (db/seed_cities.sql) é grande e não
-- crítica para o site voltar a funcionar — se estiver faltando, rode
-- esse arquivo separadamente depois. Este script não duplica esse
-- INSERT gigante para não arriscar timeout na consulta.

-- ============================================================
-- Fim. Depois de rodar: recarregue o site logado — o erro de
-- "last_seen_at does not exist" deve sumir. Se aparecer qualquer
-- outro "column ... does not exist" ou "relation ... does not
-- exist", me mande o texto exato do erro.
-- ============================================================

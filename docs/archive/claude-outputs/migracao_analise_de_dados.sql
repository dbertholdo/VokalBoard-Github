-- Rode isso no Adminer/Railway (mesma tela onde você rodou o SQL do
-- login_lockouts) ANTES de fazer o deploy do código novo — senão o
-- site vai dar erro tentando gravar em tabelas/colunas que ainda não
-- existem no banco de produção.

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

ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_users_last_seen_at ON users(last_seen_at);

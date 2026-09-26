-- Rode isso no Adminer/Railway ANTES de fazer o deploy do código de
-- hoje (Zona Vermelha / painel financeiro) — senão o site vai dar
-- erro tentando ler colunas/tabelas que ainda não existem no banco
-- de produção. Seguro rodar mesmo se algo já existir (tudo usa
-- IF NOT EXISTS / é idempotente).

ALTER TABLE users ADD COLUMN IF NOT EXISTS role_level SMALLINT NOT NULL DEFAULT 0 CHECK (role_level BETWEEN 0 AND 3);
CREATE INDEX IF NOT EXISTS idx_users_role_level ON users(role_level);
UPDATE users SET role_level = 3 WHERE is_admin = TRUE AND role_level = 0;

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

-- Depois de rodar isso, você (dono da conta) precisa virar god mode
-- manualmente uma vez (troque pelo seu e-mail de verdade):
-- UPDATE users SET role_level = 3 WHERE email = 'seu-email@exemplo.com';

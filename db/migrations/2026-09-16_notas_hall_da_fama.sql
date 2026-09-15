-- ============================================================
-- VokalBoard — Migração (16/09/2026): Notas (banco de créditos) +
-- Hall da Fama
--
-- Cria:
--   - referral_events   (histórico antifraude permanente de indicações
--                          verificadas — hash do e-mail, nunca o
--                          e-mail em si)
--   - credit_ledger      (extrato de notas ganhas/resgatadas)
--   - users.profile_highlighted_until (efeito do resgate "destaque de
--                          perfil" do catálogo de recompensas)
--
-- 100% seguro para rodar em um banco que já tem dados: usa CREATE
-- TABLE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS, nunca apaga ou
-- sobrescreve nada. Pode ser executado mais de uma vez sem problema
-- (idempotente) — mesmo padrão das migrações anteriores.
--
-- Como rodar: Railway → seu projeto → Postgres → aba "Query" → cole
-- este arquivo inteiro → Run.
-- ============================================================

ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_highlighted_until TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS referral_events (
    id                   BIGSERIAL PRIMARY KEY,
    referrer_user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    referred_email_hash  CHAR(64) NOT NULL UNIQUE,
    referred_user_id     BIGINT REFERENCES users(id) ON DELETE SET NULL,
    credited_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_referral_events_referrer ON referral_events(referrer_user_id);

CREATE TABLE IF NOT EXISTS credit_ledger (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    delta        INTEGER NOT NULL,
    reason       VARCHAR(50) NOT NULL,
    reference_id BIGINT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_credit_ledger_user ON credit_ledger(user_id);

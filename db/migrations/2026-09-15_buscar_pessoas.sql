-- ============================================================
-- VokalBoard — Migração (15/09/2026): Buscar Pessoas
--
-- Adiciona à tabela users as colunas usadas pela nova busca de
-- pessoas (/people) e pelo link de perfil customizável (/u/{slug}):
--   - appear_in_search   (opt-in/opt-out de aparecer na busca)
--   - profile_slug       (link de perfil customizável, único)
--   - highlight_shown_count / last_highlighted_at (reservadas para
--     o próximo lote — "Destaques da semana" — já criadas agora
--     para não precisar rodar outra migração depois)
--
-- 100% seguro para rodar em um banco que já tem dados: usa ADD
-- COLUMN IF NOT EXISTS, nunca apaga ou sobrescreve nada. Pode ser
-- executado mais de uma vez sem problema (idempotente) — mesmo
-- padrão do migration_full_2026-09-14.sql de ontem.
--
-- Como rodar: Railway → seu projeto → Postgres → aba "Query" → cole
-- este arquivo inteiro → Run.
-- ============================================================

ALTER TABLE users ADD COLUMN IF NOT EXISTS appear_in_search BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_slug VARCHAR(60);
ALTER TABLE users ADD COLUMN IF NOT EXISTS highlight_shown_count SMALLINT NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_highlighted_at TIMESTAMPTZ;

-- profile_slug precisa ser único, mas ALTER TABLE ADD COLUMN não
-- aceita UNIQUE direto com segurança em bancos já populados — cria a
-- constraint separadamente, só se ainda não existir.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'users_profile_slug_key'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT users_profile_slug_key UNIQUE (profile_slug);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_users_appear_in_search ON users(appear_in_search);

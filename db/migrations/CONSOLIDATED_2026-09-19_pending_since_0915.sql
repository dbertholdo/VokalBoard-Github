-- ============================================================
-- VokalBoard — CONSOLIDATED pending migrations (built 19/09/2026)
--
-- Concatenates, in order, every migration from 2026-09-15_buscar_pessoas.sql
-- through 2026-09-19_notification_center.sql (28 files) — everything that has
-- piled up unapplied to Railway production since the migration freeze
-- described in AGENTS.md. Nothing here is destructive: every file was
-- audited before concatenation and none contains DROP TABLE, DROP COLUMN,
-- TRUNCATE, or an unguarded DELETE. Table/column/index creation uses
-- IF NOT EXISTS throughout (the handful of files that don't were only
-- ever meant to run once against a fresh, not-yet-migrated database,
-- which is exactly this situation).
--
-- ONE ordering fix vs. plain filename order: 2026-09-18_retention.sql runs
-- BEFORE 2026-09-18_p5_etapa2_urgencia.sql here (not after, despite sorting
-- after it alphabetically). p5_etapa2_urgencia.sql recreates the
-- visible_listings view referencing listings.archived_at/deleted_at, columns
-- that only 2026-09-18_retention.sql adds — applying in plain filename order
-- fails with "column archived_at does not exist". Confirmed by actually
-- running this consolidated file against a reconstructed pre-migration
-- baseline before handing it over; retention.sql has no dependency on
-- anything between rechnungmaker_foundation.sql and itself, so moving it
-- earlier is safe. Every other file was already dependency-order-safe.
--
-- UPDATE (19/09/2026, later same day): two more migrations were added
-- after this file was first built — 2026-09-19_unify_vacancies.sql (task
-- #46) and 2026-09-19_notification_center.sql (task #50) — appended at
-- the end, in that order. Neither depends on anything added here nor on
-- each other, so their position relative to one another doesn't matter;
-- they only need to run after the tables they touch (listing_vacancies,
-- users) already exist, which every earlier section in this file already
-- guarantees.
--
-- ============================================================
-- HOW TO APPLY — psql only, NOT the Railway dashboard "Query" box
-- ============================================================
-- The web Query box mis-splits statements inside dollar-quoted blocks
-- (DO $$...$$ / CREATE FUNCTION ... $$...$$) — that already broke
-- production once (missing appear_in_search column). This file keeps
-- five such blocks (2026-09-18_retention.sql defines five trigger
-- functions; they cannot be rewritten without dollar-quoting), so it
-- must be applied with the psql CLI, which parses $$ blocks correctly:
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f CONSOLIDATED_2026-09-19_pending_since_0915.sql
--
-- Get DATABASE_URL from Railway → Postgres service → "Connect" tab
-- (the external/public connection string). -v ON_ERROR_STOP=1 makes
-- psql abort immediately on the first error instead of plowing on with
-- a half-broken transaction.
--
-- The whole file runs as ONE transaction (BEGIN/COMMIT wrap everything
-- below) — either all 28 migrations land, or none do.
--
-- BEFORE RUNNING: confirm whether Railway production already has real
-- user registrations. If it's still empty test data, re-installing
-- fresh from db/schema.sql may be simpler than this incremental apply.
-- If it has real users, this consolidated file is the safe path — take
-- a Railway Postgres backup/snapshot first regardless.
-- ============================================================

BEGIN;

-- ---- 2026-09-15_buscar_pessoas.sql ---------------------
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
-- FIX (19/09/2026): a versão "simplificada" (bare ADD CONSTRAINT, sem
-- guarda) quebrou na prática — o Query box do Railway não roda o
-- script inteiro como uma única transação, e reaplicar o arquivo do
-- zero depois de um erro mais adiante tenta recriar esta constraint
-- que já tinha sido criada com sucesso na tentativa anterior. Restaurada
-- a guarda idempotente original (agora em todo o arquivo, não só aqui).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'users_profile_slug_key'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT users_profile_slug_key UNIQUE (profile_slug);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_users_appear_in_search ON users(appear_in_search);

-- ---- 2026-09-16_notas_hall_da_fama.sql -----------------
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

-- ---- 2026-09-17_admin_banners.sql ----------------------
CREATE TABLE IF NOT EXISTS site_banners (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    body VARCHAR(500) NOT NULL,
    link_url VARCHAR(500),
    audience VARCHAR(32) NOT NULL DEFAULT 'all' CHECK (audience IN ('all','singer','conductor','no_subscription')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---- 2026-09-17_banner_voice.sql -----------------------
ALTER TABLE site_banners ADD COLUMN IF NOT EXISTS voice_type_id INTEGER REFERENCES voice_types(id);

-- ---- 2026-09-17_phase1_email_language.sql --------------
-- Phase 1: transactional e-mails need an account-level language preference.
-- Existing accounts intentionally get English as the documented fallback.
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(8) NOT NULL DEFAULT 'en';

-- ---- 2026-09-17_profiles_and_matches.sql ---------------
-- P2/P3 foundation: a singer can have more than one voice type and a listing
-- can contain several voice-specific vacancies. Existing single-voice listings
-- and profiles remain valid while the UI is migrated incrementally.

CREATE TABLE IF NOT EXISTS singer_profile_voice_types (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    voice_type_id BIGINT NOT NULL REFERENCES voice_types(id) ON DELETE RESTRICT,
    PRIMARY KEY (user_id, voice_type_id)
);

INSERT INTO singer_profile_voice_types (user_id, voice_type_id)
SELECT user_id, voice_type_id
FROM singer_profiles
WHERE voice_type_id IS NOT NULL
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS listing_vacancies (
    id BIGSERIAL PRIMARY KEY,
    listing_id BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    voice_type_id BIGINT NOT NULL REFERENCES voice_types(id) ON DELETE RESTRICT,
    fee VARCHAR(100),
    total_slots SMALLINT NOT NULL DEFAULT 1 CHECK (total_slots > 0),
    filled_slots SMALLINT NOT NULL DEFAULT 0 CHECK (filled_slots >= 0 AND filled_slots <= total_slots),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (listing_id, voice_type_id)
);

INSERT INTO listing_vacancies (listing_id, voice_type_id)
SELECT id, voice_type_id
FROM listings
WHERE listing_type = 'seeking_singer' AND voice_type_id IS NOT NULL
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS job_invitations (
    id BIGSERIAL PRIMARY KEY,
    vacancy_id BIGINT NOT NULL REFERENCES listing_vacancies(id) ON DELETE CASCADE,
    artist_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    initiated_by_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(16) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'declined', 'expired')),
    expires_at TIMESTAMPTZ NOT NULL,
    responded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (artist_user_id <> initiated_by_user_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_pending_job_invitation
ON job_invitations (vacancy_id, artist_user_id)
WHERE status = 'pending';

CREATE TABLE IF NOT EXISTS job_matches (
    id BIGSERIAL PRIMARY KEY,
    listing_id BIGINT NOT NULL REFERENCES listings(id) ON DELETE RESTRICT,
    vacancy_id BIGINT NOT NULL REFERENCES listing_vacancies(id) ON DELETE RESTRICT,
    artist_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    contractor_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    invitation_id BIGINT UNIQUE REFERENCES job_invitations(id) ON DELETE SET NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'completed', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    CHECK (artist_user_id <> contractor_user_id)
);

CREATE INDEX IF NOT EXISTS idx_job_invitations_artist_pending
ON job_invitations (artist_user_id, status, expires_at);
CREATE INDEX IF NOT EXISTS idx_job_matches_user
ON job_matches (artist_user_id, contractor_user_id, status);

-- ---- 2026-09-17_rechnung_match_drafts.sql --------------
-- Rechnung por Match: o formulário transitório é cifrado em repouso e expira
-- em sete dias. Nenhum PDF é persistido pelo VokalBoard: após a confirmação,
-- ele é gerado em memória, enviado por e-mail às duas partes e o rascunho é
-- apagado. Os papéis são do Match, não da categoria do perfil.
-- A rota deve permitir INICIAR somente até CURRENT_DATE <=
-- listings.event_date + 7. Depois da iniciação, a outra parte recebe sete dias
-- completos para revisar; expires_at é criado_at + 7 dias, mesmo que esse
-- segundo prazo ultrapasse a janela original do evento.

CREATE TABLE IF NOT EXISTS invoice_match_drafts (
    id BIGSERIAL PRIMARY KEY,
    match_id BIGINT NOT NULL REFERENCES job_matches(id) ON DELETE CASCADE,
    requested_by_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    issuer_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    contractor_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    encrypted_payload BYTEA NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'awaiting_contractor'
        CHECK (status IN ('awaiting_issuer', 'awaiting_contractor', 'confirmed', 'expired', 'cancelled')),
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    confirmed_at TIMESTAMPTZ,
    CHECK (issuer_user_id <> contractor_user_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_open_invoice_match_draft
ON invoice_match_drafts (match_id)
WHERE status IN ('awaiting_issuer', 'awaiting_contractor');

CREATE INDEX IF NOT EXISTS idx_invoice_match_drafts_expiry
ON invoice_match_drafts (expires_at)
WHERE status IN ('awaiting_issuer', 'awaiting_contractor');

-- ---- 2026-09-17_rechnungmaker_foundation.sql -----------
-- Rechnungmaker: store only operational metadata. IBAN, BIC, tax ID,
-- residential address and invoice form contents must never be columns here.

CREATE TABLE IF NOT EXISTS invoice_number_sequences (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    invoice_year SMALLINT NOT NULL CHECK (invoice_year >= 2000),
    last_number INTEGER NOT NULL DEFAULT 0 CHECK (last_number >= 0),
    PRIMARY KEY (user_id, invoice_year)
);

-- Five free invoice generations per calendar month, per user. This resets
-- rather than carrying unused invoices forward.
CREATE TABLE IF NOT EXISTS invoice_monthly_usage (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    usage_month DATE NOT NULL CHECK (usage_month = date_trunc('month', usage_month)::date),
    free_used SMALLINT NOT NULL DEFAULT 0 CHECK (free_used BETWEEN 0 AND 5),
    PRIMARY KEY (user_id, usage_month)
);

-- Purchased credits are separate from the monthly allowance and never expire.
-- The future Notes purchase flow writes only delta/reason here, not financial
-- details from an invoice.
CREATE TABLE IF NOT EXISTS purchased_invoice_credits (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    delta SMALLINT NOT NULL CHECK (delta <> 0),
    reason VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_purchased_invoice_credits_user
ON purchased_invoice_credits (user_id, created_at DESC);

-- Match PDFs may exist privately for seven days. The table deliberately keeps
-- only a random filename, access relationship and expiry; no invoice content,
-- tax number, bank data or address is retained.
CREATE TABLE IF NOT EXISTS ephemeral_match_invoices (
    id BIGSERIAL PRIMARY KEY,
    match_id BIGINT NOT NULL REFERENCES job_matches(id) ON DELETE CASCADE,
    created_by_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    stored_filename VARCHAR(100) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ephemeral_match_invoices_expiry
ON ephemeral_match_invoices (expires_at);

-- ---- 2026-09-18_p3_logistics_and_vacancies.sql ---------
-- P3.A: campos de logística opcionais no anúncio (Fahrkosten/Partitur
-- vorhanden/Probenplan vorhanden — checkboxes simples, decisão do
-- usuário em 18/09/2026) + link de partitura (Zero-Storage: só link
-- externo, nunca upload — decisão de 17/09/2026, confirmada de novo).
-- As vagas múltiplas por naipe em si já tinham fundação
-- (listing_vacancies, migração de 17/09) — nada novo nelas aqui.

ALTER TABLE listings
    ADD COLUMN IF NOT EXISTS travel_cost_covered BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS sheet_music_available BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS sheet_music_url VARCHAR(500),
    ADD COLUMN IF NOT EXISTS rehearsal_schedule_available BOOLEAN NOT NULL DEFAULT FALSE;

-- ---- 2026-09-18_p3f_match_evaluations.sql --------------
-- P3.F: avaliação pós-Match (5 categorias) + selos de qualidade privados.
--
-- Decisões do Daniel em 18/09/2026 (ver AI_CHANGELOG.md e
-- PLANO_EXECUTIVO_ORGANIZADO.md, bullet "Após Match concluído (P3.F)"):
--   - Sistema NOVO, em paralelo ao `ratings` livre já existente (não
--     mexido por esta migração).
--   - 5 categorias, cada uma de 1 a 5 estrelas: Pünktlichkeit,
--     Vorbereitung, Musikalität, Professionelle Kommunikation,
--     Angenehme Zusammenarbeit. Mútuo — cada lado do Match avalia o
--     outro, uma linha por (match, quem avalia).
--   - Progressão Bronze/Prata/Ouro/Platina "estilo Uber": UMA por
--     categoria, calculada em tempo real (AVG) a partir desta tabela —
--     por isso não há coluna de "tier" armazenada aqui, o tier nunca é
--     persistido, só computado (ver app/match_evaluations.py).
--   - Nota e selos ficam só internos (dono do perfil + Admin) — isso é
--     regra de exibição na aplicação, não precisa de coluna aqui.
--   - SECRETO: "igual Uber, ninguém vê quem avaliou e como" — nenhuma
--     rota deve expor uma linha desta tabela individualmente pra
--     ninguém (nem pro avaliado, nem pro Admin pela UI normal); só a
--     média agregada por categoria é lida.
--
-- job_matches ganha 2 colunas para o worker de lembrete não reenviar
-- e-mail toda hora durante os 14 dias da janela (uma por lado do Match,
-- já que cada lado só recebe o lembrete referente à SUA avaliação
-- pendente).

CREATE TABLE IF NOT EXISTS match_evaluations (
    id                       BIGSERIAL PRIMARY KEY,
    match_id                 BIGINT NOT NULL REFERENCES job_matches(id) ON DELETE CASCADE,
    rater_id                 BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rated_id                 BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    punctuality              SMALLINT NOT NULL CHECK (punctuality BETWEEN 1 AND 5),
    preparation              SMALLINT NOT NULL CHECK (preparation BETWEEN 1 AND 5),
    musicality               SMALLINT NOT NULL CHECK (musicality BETWEEN 1 AND 5),
    communication             SMALLINT NOT NULL CHECK (communication BETWEEN 1 AND 5),
    collaboration            SMALLINT NOT NULL CHECK (collaboration BETWEEN 1 AND 5),
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (rater_id <> rated_id),
    UNIQUE (match_id, rater_id)
);
CREATE INDEX IF NOT EXISTS idx_match_evaluations_rated ON match_evaluations (rated_id);

ALTER TABLE job_matches
    ADD COLUMN IF NOT EXISTS artist_eval_reminder_sent_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS contractor_eval_reminder_sent_at TIMESTAMPTZ;

-- ---- 2026-09-18_p4_etapa3_feature_usage.sql ------------
-- P4 Etapa 3 (18/09/2026): contador genérico de uso de ferramentas do
-- site, pedido pelo Daniel junto com o badge de pendência do
-- Rechnungmaker — "quero que haja uma forma de trackear quais
-- ferramentas do site são mais usadas. E isso inclui Rechnung maker."
-- Ver app/feature_usage.py — deliberadamente genérico, não é específico
-- do Rechnungmaker, só é o primeiro consumidor.
CREATE TABLE IF NOT EXISTS feature_usage_monthly (
    feature_key VARCHAR(64) NOT NULL,
    usage_month DATE NOT NULL,
    count BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (feature_key, usage_month)
);

-- ---- 2026-09-18_p4_match_invoice_marker.sql ------------
-- P4: marcador NÃO-sensível de que uma Rechnung já foi confirmada e
-- enviada por e-mail para este Match — nunca guarda o PDF nem os
-- dados do formulário (Zero-Storage, CLAUDE.md Seção 2). Serve só
-- pra UI (esconder os botões de pedir/gerar depois de já enviada).
ALTER TABLE job_matches ADD COLUMN IF NOT EXISTS invoice_sent_at TIMESTAMPTZ;

-- ---- 2026-09-18_p5_etapa1_notas_wallet_foundation.sql --
-- P5 Etapa 1 (18/09/2026) — fundação antifraude do sistema de Notas +
-- recompensa por publicar vaga (0,50 Nota, teto de 3/semana).
--
-- Duas mudanças em credit_ledger:
--   1. delta vira NUMERIC(10,2) em vez de INTEGER — precisa suportar
--      valores fracionados como 0,50 (recompensa por vaga postada).
--      Valores já existentes (sempre inteiros: +1 bônus de indicação,
--      -3 resgate de destaque de perfil) migram sem perda nenhuma.
--   2. idempotency_key (opcional) — protege créditos automáticos
--      (recompensa por vaga postada, e futuras: recompensa por login
--      diário, perfil 100%, etc.) contra duplicidade por retry de
--      rede/duplo clique: nunca duas linhas com a mesma
--      (user_id, idempotency_key). NULL nunca conflita (uso normal,
--      manual, como o resgate de itens da loja, que não precisa de
--      chave).
ALTER TABLE credit_ledger ALTER COLUMN delta TYPE NUMERIC(10,2);
ALTER TABLE credit_ledger ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(100);
CREATE UNIQUE INDEX IF NOT EXISTS idx_credit_ledger_user_idempotency
    ON credit_ledger (user_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

-- ---- 2026-09-18_retention.sql --------------------------
-- Apply transactionally before deploying the corresponding application code.
ALTER TABLE listings ADD COLUMN IF NOT EXISTS available_from date;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS available_until date;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS archived_at timestamptz;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
ALTER TABLE listings ALTER COLUMN country DROP NOT NULL;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS archived_at timestamptz;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS activity_at timestamptz;
UPDATE messages SET activity_at=created_at WHERE activity_at IS NULL;
-- A conversation is the pair of participants, irrespective of listing.
WITH activity AS (
 SELECT least(sender_id,recipient_id) a, greatest(sender_id,recipient_id) b, max(created_at) latest
 FROM messages WHERE archived_at IS NULL GROUP BY 1,2
)
UPDATE messages m SET activity_at=a.latest FROM activity a
WHERE least(m.sender_id,m.recipient_id)=a.a AND greatest(m.sender_id,m.recipient_id)=a.b
  AND m.archived_at IS NULL;
ALTER TABLE messages ALTER COLUMN activity_at SET DEFAULT now();
ALTER TABLE messages ALTER COLUMN activity_at SET NOT NULL;

CREATE TABLE IF NOT EXISTS content_lifecycle_log (
 id bigserial PRIMARY KEY, entity_type text NOT NULL, entity_id bigint NOT NULL,
 action text NOT NULL, actor_id bigint, occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_lifecycle_entity ON content_lifecycle_log(entity_type,entity_id);
CREATE INDEX IF NOT EXISTS idx_messages_pair_activity ON messages(least(sender_id,recipient_id),greatest(sender_id,recipient_id),activity_at);

ALTER TABLE job_matches ADD COLUMN IF NOT EXISTS listing_snapshot jsonb;
UPDATE job_matches m SET listing_snapshot=jsonb_build_object('title',l.title,'event_date',l.event_date,'fee',l.fee)
FROM listings l WHERE l.id=m.listing_id AND m.listing_snapshot IS NULL;
ALTER TABLE job_matches ALTER COLUMN listing_id DROP NOT NULL;
ALTER TABLE job_matches ALTER COLUMN vacancy_id DROP NOT NULL;
ALTER TABLE job_matches DROP CONSTRAINT IF EXISTS job_matches_listing_id_fkey;
ALTER TABLE job_matches ADD CONSTRAINT job_matches_listing_id_fkey FOREIGN KEY(listing_id) REFERENCES listings(id) ON DELETE SET NULL;
ALTER TABLE job_matches DROP CONSTRAINT IF EXISTS job_matches_vacancy_id_fkey;
ALTER TABLE job_matches ADD CONSTRAINT job_matches_vacancy_id_fkey FOREIGN KEY(vacancy_id) REFERENCES listing_vacancies(id) ON DELETE SET NULL;

CREATE OR REPLACE FUNCTION snapshot_match_listing() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 SELECT jsonb_build_object('title',title,'event_date',event_date,'fee',fee)
 INTO NEW.listing_snapshot FROM listings WHERE id=NEW.listing_id;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS match_snapshot ON job_matches;
CREATE TRIGGER match_snapshot BEFORE INSERT ON job_matches FOR EACH ROW EXECUTE FUNCTION snapshot_match_listing();

CREATE OR REPLACE VIEW visible_listings AS
 SELECT * FROM listings WHERE archived_at IS NULL AND deleted_at IS NULL
 AND (COALESCE(available_until,event_date) IS NULL OR COALESCE(available_until,event_date)+30 > CURRENT_DATE);
CREATE OR REPLACE VIEW visible_messages AS
 SELECT * FROM messages WHERE archived_at IS NULL AND activity_at+interval '30 days' > now();

CREATE OR REPLACE FUNCTION validate_availability() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.archived_at IS NOT NULL OR NEW.deleted_at IS NOT NULL THEN RETURN NEW; END IF;
 IF NEW.listing_type='singer_available' THEN
   IF NEW.available_from IS NULL OR NEW.available_until IS NULL OR
      NEW.available_until < NEW.available_from OR NEW.available_until-NEW.available_from > 29 THEN
     RAISE EXCEPTION 'availability_invalid' USING ERRCODE='23514';
   END IF;
   -- Per-owner transaction lock protects the quota even under concurrent requests.
   PERFORM pg_advisory_xact_lock(8201, (NEW.author_id % 2147483647)::integer);
   IF NEW.is_active AND NEW.available_until >= CURRENT_DATE AND
      (SELECT count(*) FROM listings WHERE author_id=NEW.author_id AND id<>NEW.id
        AND listing_type='singer_available' AND is_active AND archived_at IS NULL
        AND deleted_at IS NULL AND available_until>=CURRENT_DATE) >= 2 THEN
     RAISE EXCEPTION 'availability_limit' USING ERRCODE='23514';
   END IF;
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS availability_guard ON listings;
CREATE TRIGGER availability_guard BEFORE INSERT OR UPDATE ON listings FOR EACH ROW EXECUTE FUNCTION validate_availability();

CREATE OR REPLACE FUNCTION message_activity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 PERFORM pg_advisory_xact_lock((least(NEW.sender_id,NEW.recipient_id)%2147483647)::integer,
                              (greatest(NEW.sender_id,NEW.recipient_id)%2147483647)::integer);
 -- Expired history never returns when a new conversation starts.
 UPDATE messages SET archived_at=activity_at+interval '30 days'
 WHERE archived_at IS NULL AND activity_at+interval '30 days'<=now()
 AND least(sender_id,recipient_id)=least(NEW.sender_id,NEW.recipient_id)
 AND greatest(sender_id,recipient_id)=greatest(NEW.sender_id,NEW.recipient_id);
 UPDATE messages SET activity_at=NEW.created_at
 WHERE archived_at IS NULL AND least(sender_id,recipient_id)=least(NEW.sender_id,NEW.recipient_id)
 AND greatest(sender_id,recipient_id)=greatest(NEW.sender_id,NEW.recipient_id);
 NEW.activity_at=NEW.created_at;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS conversation_activity ON messages;
CREATE TRIGGER conversation_activity BEFORE INSERT ON messages FOR EACH ROW EXECUTE FUNCTION message_activity();

CREATE OR REPLACE FUNCTION audit_content_lifecycle() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actor bigint; event text;
BEGIN
 IF TG_OP='DELETE' THEN
   INSERT INTO content_lifecycle_log(entity_type,entity_id,action) VALUES(TG_TABLE_NAME,OLD.id,'purged');
   RETURN OLD;
 END IF;
 actor=COALESCE((to_jsonb(NEW)->>'author_id')::bigint,(to_jsonb(NEW)->>'sender_id')::bigint);
 IF TG_OP='INSERT' THEN event='posted';
 ELSIF OLD.deleted_at IS DISTINCT FROM NEW.deleted_at THEN event='deleted';
 ELSE RETURN NEW;
 END IF;
 INSERT INTO content_lifecycle_log(entity_type,entity_id,action,actor_id) VALUES(TG_TABLE_NAME,NEW.id,event,actor);
 RETURN NEW;
END $$;
-- Separate UPDATE logic works for messages (which have no deleted_at).
CREATE OR REPLACE FUNCTION audit_content_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (to_jsonb(OLD)->>'deleted_at') IS NULL AND (to_jsonb(NEW)->>'deleted_at') IS NOT NULL THEN
   INSERT INTO content_lifecycle_log(entity_type,entity_id,action) VALUES(TG_TABLE_NAME,NEW.id,'deleted');
 END IF;
 IF OLD.archived_at IS NULL AND NEW.archived_at IS NOT NULL THEN
   INSERT INTO content_lifecycle_log(entity_type,entity_id,action) VALUES(TG_TABLE_NAME,NEW.id,'archived');
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS listing_audit ON listings;
CREATE TRIGGER listing_audit AFTER INSERT OR DELETE ON listings FOR EACH ROW EXECUTE FUNCTION audit_content_lifecycle();
DROP TRIGGER IF EXISTS listing_change_audit ON listings;
CREATE TRIGGER listing_change_audit AFTER UPDATE ON listings FOR EACH ROW EXECUTE FUNCTION audit_content_change();
DROP TRIGGER IF EXISTS message_audit ON messages;
CREATE TRIGGER message_audit AFTER INSERT OR DELETE ON messages FOR EACH ROW EXECUTE FUNCTION audit_content_lifecycle();
DROP TRIGGER IF EXISTS message_change_audit ON messages;
CREATE TRIGGER message_change_audit AFTER UPDATE ON messages FOR EACH ROW EXECUTE FUNCTION audit_content_change();

-- ---- 2026-09-18_p5_etapa2_urgencia.sql -----------------
-- P5 Etapa 2 (18/09/2026) — Sistema de Urgência.
--
-- Decisões confirmadas com o Daniel (17/09 e 18/09/2026): 1 token de
-- urgência grátis por semana por pessoa, não acumula; com 0 tokens,
-- compra-se por 2 Notas (equivalente a 2 Euros); marcar uma vaga como
-- urgente pode acontecer no formulário de criação OU depois, via
-- botão; vale só pra quem procura preencher vaga (seeking_singer /
-- seeking_conductor); recompensa de 0,50 Nota (metade do "preço
-- cheio" de 1 Nota) pra quem publicou quando o Match acontece pela
-- plataforma; lembrete extra 6h depois se a vaga urgente continuar
-- sem Match.

ALTER TABLE listings ADD COLUMN IF NOT EXISTS is_urgent BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS urgent_marked_at TIMESTAMPTZ;
-- NULL até o worker de lembrete de 6h mandar o aviso extra (garante
-- que o lembrete só é enviado uma vez por vaga — ver
-- app/urgent_listing_reminder_worker.py).
ALTER TABLE listings ADD COLUMN IF NOT EXISTS urgent_reminder_sent_at TIMESTAMPTZ;

-- Acelera tanto o filtro "?urgent=1" do /board quanto a query do
-- worker de lembrete (que só olha vagas urgentes sem lembrete ainda).
CREATE INDEX IF NOT EXISTS idx_listings_urgent ON listings (is_urgent) WHERE is_urgent = TRUE;

-- Controla o token semanal grátis por pessoa. "Não acumula" = cada
-- semana (segunda-feira, ISO week) é sua própria linha, free_used
-- nunca passa de 1 — não existe "banco" de tokens sobrando.
CREATE TABLE IF NOT EXISTS urgency_weekly_usage (
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    usage_week DATE NOT NULL,
    free_used  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, usage_week)
);

-- IMPORTANTE: visible_listings é uma VIEW com "SELECT * FROM listings
-- ...", e no Postgres um "SELECT *" numa view fica CONGELADO na lista
-- de colunas que existia no momento em que a view foi criada — os tres
-- ALTER TABLE ADD COLUMN acima não aparecem sozinhos nela. Precisa
-- recriar a view (CREATE OR REPLACE, mesma query de sempre) pra ela
-- passar a incluir is_urgent/urgent_marked_at/urgent_reminder_sent_at.
CREATE OR REPLACE VIEW visible_listings AS
 SELECT * FROM listings WHERE archived_at IS NULL AND deleted_at IS NULL
 AND (COALESCE(available_until,event_date) IS NULL OR COALESCE(available_until,event_date)+30 > CURRENT_DATE);

-- ---- 2026-09-18_p5_loja_admin_catalog.sql --------------
-- P5 Loja — painel de Admin (18/09/2026).
--
-- Pedido do Daniel: um menu dedicado em Admin pra controlar a loja —
-- ativar/desativar produto individualmente (ex.: bug num item, sem
-- tirar a loja inteira do ar), histórico geral das transações da
-- loja, busca por usuário + extrato individual. Decisões confirmadas
-- via AskUserQuestion: (a) começar pelo painel de Admin, ainda sem
-- itens novos (selo de confiança / Rechnungen extra ficam pra depois);
-- (b) o catálogo (hoje fixo no Python) passa a viver no banco, pra dar
-- controle de fato ao Admin sem precisar de deploy a cada mudança;
-- (c) "histórico geral" mostra só transações da loja (resgates de
-- catálogo + compra de urgência), não o credit_ledger inteiro de todo
-- mundo; (d) desativar um item só bloqueia NOVOS resgates — quem já
-- resgatou antes mantém o benefício normalmente.

-- shop_catalog_items: preço e estado (ativo/inativo) de cada item da
-- loja, controláveis pelo Admin sem precisar mexer em código. O
-- EFEITO de cada item (o que exatamente ele faz ao ser resgatado)
-- continua no Python (app/shop_catalog.py, ITEM_EFFECTS) — só preço e
-- ativo/inativo são administráveis nesta etapa.
CREATE TABLE IF NOT EXISTS shop_catalog_items (
    id         BIGSERIAL PRIMARY KEY,
    item_key   VARCHAR(50) NOT NULL UNIQUE,
    cost       NUMERIC(10,2) NOT NULL,
    active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Migra o único item que já existia (fixo antes em
-- app/routers/notas_routes.py: REDEMPTION_CATALOG), pra não perder o
-- catálogo atual ao trocar de fonte.
INSERT INTO shop_catalog_items (item_key, cost, active)
VALUES ('profile_highlight_7d', 3, TRUE)
ON CONFLICT (item_key) DO NOTHING;

-- ---- 2026-09-18_p5_loja_catalog_crud.sql ---------------
-- P5 Loja — CRUD de itens pelo Admin + comprar Notas que faltam
-- (18/09/2026).
--
-- Pedido do Daniel: "colocar forma de adicionar itens à loja, mudar
-- descrição e título de itens, como uma loja normal" + oferecer
-- comprar a diferença de Notas quando o saldo não é suficiente pra
-- um item. Decisões confirmadas via AskUserQuestion: (a) item NOVO
-- criado pelo Admin é um "voucher genérico" — só debita Notas e
-- registra no histórico, sem efeito automático no sistema (o único
-- efeito programado hoje, "estender destaque de perfil", continua só
-- pro item que já existia); (b) título/descrição editados pelo Admin
-- ficam em UM idioma só, guardado no banco — mostra igual pra todo
-- mundo, sem exigir tradução; (c) "comprar Notas que faltam" é só a
-- interface por enquanto (tela "em breve", mesmo padrão do /assinar
-- hoje) — nenhuma cobrança real ainda, sem gateway de pagamento
-- integrado.

-- title/description NULL = item ainda usa o texto de app/i18n.py
-- (é o caso do único item que já existia, profile_highlight_7d, até
-- o Admin editar e sobrescrever). Item NOVO criado pelo Admin sempre
-- tem os dois preenchidos (não tem entrada no i18n pra cair como
-- fallback).
ALTER TABLE shop_catalog_items ADD COLUMN IF NOT EXISTS title VARCHAR(150);
ALTER TABLE shop_catalog_items ADD COLUMN IF NOT EXISTS description VARCHAR(500);

-- icon: antes vinha só do dicionário Python ITEM_EFFECTS (só cobria o
-- item que já existia) — agora vem do banco pra qualquer item,
-- inclusive os novos criados pelo Admin (ver ALLOWED_ICONS em
-- app/shop_catalog.py, uma lista fechada validada no servidor).
ALTER TABLE shop_catalog_items ADD COLUMN IF NOT EXISTS icon VARCHAR(50) NOT NULL DEFAULT 'icon-gift';

-- O item que já existia usava "icon-sparkle" (era o valor fixo em
-- ITEM_EFFECTS antes desta migration) — preserva o ícone atual.
UPDATE shop_catalog_items SET icon = 'icon-sparkle' WHERE item_key = 'profile_highlight_7d';

-- ---- 2026-09-18_p6_admin_report_moderation.sql ---------
-- P6 — fechar o loop de denúncias (18/09/2026): "resposta a denúncias e
-- notificação ao usuário quando denúncia for aceita" (pedido do Daniel,
-- painel de Admin). Antes, listing_reports só armazenava a denúncia —
-- sem status, sem quem revisou, sem notificação. Ver app/moderation.py.
ALTER TABLE listing_reports
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'accepted', 'rejected')),
    ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS resolved_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_listing_reports_status ON listing_reports(status);

-- ---- 2026-09-18_p6_email_layout.sql --------------------
-- P6 — Layout compartilhado de e-mails (18/09/2026).
--
-- Pedido do Daniel: editar o layout (ícones, logo, texto/fontes,
-- assinatura e rodapé) de TODOS os e-mails automáticos num lugar só,
-- pra mudar tudo de uma vez sem mexer em cada e-mail individual. Ver
-- app/email_layout.py (render_email(), chamado automaticamente por
-- app/email.py's send_email()) e a tela /admin/emails.
--
-- Reaproveita system_settings (mesma tabela genérica de chave/valor
-- já usada por Capitalism Mode e preço de assinatura) — sem tabela
-- nova. Valor NULL/ausente cai pro padrão em app/email_layout.py
-- (_DEFAULTS), então estas linhas são só pra deixar os registros já
-- existentes desde o início (facilita ver/editar no Admin).
INSERT INTO system_settings (key, value) VALUES
    ('email_layout_logo_url', ''),
    ('email_layout_accent_color', '#12a488'),
    ('email_layout_header_emoji', '🎵'),
    ('email_layout_signature', 'Equipe VokalBoard'),
    ('email_layout_footer', 'Você recebeu este e-mail porque tem uma conta no VokalBoard.')
ON CONFLICT (key) DO NOTHING;

-- ---- 2026-09-18_p6_financeiro_estornos.sql -------------
-- P6 — estorno de compras, Loja e dinheiro (18/09/2026): "adicionar um
-- botão ou submenu para estornar compra, tanto da loja quanto com
-- dinheiro, em algum submenu do financeiro" (pedido do Daniel). O lado
-- Loja/Notas reaproveita credit_ledger (já existia, sem mudança de
-- schema). O lado dinheiro precisa marcar uma assinatura como
-- estornada — hoje `subscriptions` nunca é preenchida de verdade (sem
-- gateway/Capitalism Mode desligado), mas a tabela já existe (mesmo
-- motivo do comentário original: "para o dashboard já funcionar no
-- dia que o billing for ligado").
ALTER TABLE subscriptions
    ADD COLUMN IF NOT EXISTS refunded_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS refunded_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL;

-- ---- 2026-09-18_p6_moderation_punishments.sql ----------
-- P6 — punição ao aceitar uma denúncia (18/09/2026): "no botão de
-- denúncia precisamos definir alguma forma de warning/punição/
-- banimento" (pedido do Daniel). 3 níveis: aviso (sem efeito na
-- conta), suspensão (reaproveita o deleted_at/"Deactivate" que já
-- existe — o próprio usuário pode reverter fazendo login de novo) e
-- banimento (definitivo — ver app/moderation.py).
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS banned_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS banned_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL;

-- Histórico de punições — permite ver quantos avisos/suspensões/bans
-- uma conta já recebeu (ex.: no mini card do Admin), sem precisar
-- adivinhar a partir do texto solto de audit_log.
CREATE TABLE IF NOT EXISTS moderation_actions (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    report_id    BIGINT REFERENCES listing_reports(id) ON DELETE SET NULL,
    action_type  VARCHAR(20) NOT NULL CHECK (action_type IN ('warning', 'suspend', 'ban')),
    admin_id     BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_moderation_actions_user ON moderation_actions(user_id);

-- ---- 2026-09-18_phone_visibility.sql -------------------
-- P2.C: telefone obrigatório para publicar anúncio (validado na
-- aplicação, não precisa de constraint de banco — contas antigas sem
-- telefone continuam existindo, só não conseguem publicar até
-- preencher) + escolha de visibilidade no perfil público.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS phone_visibility VARCHAR(10) NOT NULL DEFAULT 'private';

-- FIX (19/09/2026): restored idempotency guard — see the note by
-- users_profile_slug_key above for why the "safe since applies once"
-- assumption didn't hold in practice.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'users_phone_visibility_check'
    ) THEN
        ALTER TABLE users
            ADD CONSTRAINT users_phone_visibility_check CHECK (phone_visibility IN ('private', 'public'));
    END IF;
END $$;

-- ---- 2026-09-18_spoken_languages.sql -------------------
-- P2.B: idiomas falados no perfil (qualquer role, não só cantor).
-- Lista fixa (10 mais faladas na Europa incluindo Português) + "Outra" com
-- nome livre + até 3 campos extras + remoção — controlado na aplicação
-- (app/languages.py), aqui só a tabela que guarda o que a pessoa escolheu.

CREATE TABLE IF NOT EXISTS user_spoken_languages (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- código da lista fixa (app/languages.py: SPOKEN_LANGUAGE_OPTIONS) ou
    -- 'other' quando a pessoa escolheu "Outra" e digitou um nome livre.
    language_code VARCHAR(20) NOT NULL,
    -- só usado quando language_code = 'other'; nulo nos demais casos.
    custom_name VARCHAR(100),
    sort_order SMALLINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_spoken_languages_user
ON user_spoken_languages (user_id);

-- Evita repetir o mesmo idioma fixo duas vezes para a mesma pessoa
-- (não se aplica a 'other', que pode ter nomes livres diferentes).
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_spoken_language_fixed
ON user_spoken_languages (user_id, language_code)
WHERE language_code <> 'other';

-- ---- 2026-09-19_p3b_invitations_and_applications.sql ---
-- P3.B — candidatura espontânea + convite pelo diretório both write to
-- job_invitations, differentiated by initiated_by_user_id: when it equals
-- artist_user_id, the ARTIST started it (a candidatura) and the
-- contractor (the listing's author) is the one who must accept/decline;
-- when it's someone else, that someone is the contractor inviting the
-- artist, who then accepts/declines. The original CHECK forbade the
-- self-initiated case entirely — drop it, app logic (app/match_service.py)
-- now owns this rule.
ALTER TABLE job_invitations DROP CONSTRAINT IF EXISTS job_invitations_check;

-- ---- 2026-09-19_p3e_structured_fees.sql ----------------
-- P3.E: Cachê estruturado (valor numérico + moeda) em vez de texto
-- livre, e infraestrutura de compatibilidade/score.
--
-- Decisão do Daniel em 18/09/2026: o campo `fee` (VARCHAR texto livre)
-- não deixa comparar/ordenar por valor de forma confiável ("250€" vs "a
-- combinar" vs "200-300€"). Novos campos: fee_amount (numérico),
-- fee_currency (EUR/CHF/USD/GBP — multi-moeda pré-implementada pensando
-- em expansão futura pra outros países, mesmo hoje operando só em
-- DE/AT/CH) e fee_negotiable (booleano, "a negociar").
--
-- O campo antigo `fee` (texto livre) é MANTIDO nas duas tabelas — dados
-- antigos continuam lá, só não é mais escrito/lido pelo formulário e
-- exibição novos. Sem migração/backfill de dados existentes até o
-- Daniel autorizar (mesma regra de sempre: nada roda contra o Postgres
-- do Railway sem liberação explícita).
--
-- NÃO comparamos valores em moedas diferentes (sem conversão de câmbio)
-- — ordenar por fee_amount desc compara o valor numérico bruto entre
-- moedas diferentes, o que é impreciso quando há mistura de moedas.
-- Aceitável por ora: hoje o site é DE/AT/CH (majoritariamente EUR/CHF,
-- valores parecidos); registrado como limitação conhecida.

-- FIX (19/09/2026): added IF NOT EXISTS to every ADD COLUMN below, and
-- split each ADD CONSTRAINT out into its own idempotency-guarded block
-- — same reasoning as users_profile_slug_key above.
ALTER TABLE listings
    ADD COLUMN IF NOT EXISTS fee_amount NUMERIC(10, 2) CHECK (fee_amount IS NULL OR fee_amount >= 0),
    ADD COLUMN IF NOT EXISTS fee_currency VARCHAR(3) NOT NULL DEFAULT 'EUR' CHECK (fee_currency IN ('EUR', 'CHF', 'USD', 'GBP')),
    ADD COLUMN IF NOT EXISTS fee_negotiable BOOLEAN NOT NULL DEFAULT FALSE;

-- Defesa em profundidade: nunca os dois ao mesmo tempo (valor E "a
-- negociar" marcados) — a regra "exatamente um dos dois" pra
-- listing_type que exige cachê é validada na aplicação
-- (_fee_valid em listings_routes.py), isto aqui só impede o caso
-- claramente inconsistente de ambos juntos.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'listings_fee_not_both'
    ) THEN
        ALTER TABLE listings
            ADD CONSTRAINT listings_fee_not_both CHECK (NOT (fee_amount IS NOT NULL AND fee_negotiable));
    END IF;
END $$;

ALTER TABLE listing_vacancies
    ADD COLUMN IF NOT EXISTS fee_amount NUMERIC(10, 2) CHECK (fee_amount IS NULL OR fee_amount >= 0),
    ADD COLUMN IF NOT EXISTS fee_currency VARCHAR(3) NOT NULL DEFAULT 'EUR' CHECK (fee_currency IN ('EUR', 'CHF', 'USD', 'GBP')),
    ADD COLUMN IF NOT EXISTS fee_negotiable BOOLEAN NOT NULL DEFAULT FALSE;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'listing_vacancies_fee_not_both'
    ) THEN
        ALTER TABLE listing_vacancies
            ADD CONSTRAINT listing_vacancies_fee_not_both CHECK (NOT (fee_amount IS NOT NULL AND fee_negotiable));
    END IF;
END $$;

-- Toggle de Admin (Red Zone-lite — não é uma ação financeira/destrutiva
-- como o Capitalism Mode, então fica em /admin, não em /financeiro) pra
-- controlar se o score/critério de compatibilidade aparece pro usuário
-- final. Implantado desligado por padrão — Daniel quer discutir depois
-- se/como mostrar.
INSERT INTO system_settings (key, value) VALUES
    ('compatibility_score_visible', 'false')
ON CONFLICT (key) DO NOTHING;

-- ---- 2026-09-19_p6_support_and_grants.sql --------------
-- P6 close-out (19/09/2026) — two of the three remaining P6 items,
-- scoped with Daniel via AskUserQuestion (the third, segmented email
-- sending, stays explicitly out of scope: it depends on a real
-- Subscription/payment gateway that doesn't exist in this codebase
-- yet — see PLANO_EXECUTIVO_ORGANIZADO.md and AI_CHANGELOG.md).
--
-- 1. Ad-hoc admin grant (God Mode only, /financeiro/conceder): an
--    Admin can credit/debit a specific user's Notas balance, or issue
--    a shop_catalog_items entry to them directly (bypassing
--    self-purchase), each with a mandatory free-text justification.
--    Reuses credit_ledger/app/notas_wallet.py for the actual
--    crediting/debiting — this new column just holds the admin's own
--    typed words, since `reason` itself stays a short machine label
--    ("admin_grant_credit" / "admin_grant_debit" / "redeem_<item_key>"
--    for a granted item), same shape as every other credit_ledger
--    reason in this codebase.
ALTER TABLE credit_ledger ADD COLUMN IF NOT EXISTS admin_note TEXT;

-- 2. "Fale conosco" (contact) + "Reportar erro" (bug report) — one
--    unified ticket inbox for both, distinguished by `type`, mirroring
--    the shape of listing_reports/moderation_actions (open ->
--    answered/resolved, resolved_by/resolved_at). A bug report
--    auto-captures page_url/page_name from the page the button was
--    clicked on (see app/templates/base.html); user_id is nullable
--    (SET NULL, never blocks account deletion) since a report can, in
--    principle, come off a page a logged-out visitor can still see.
--    `email` only matters for a logged-out submission (the contact
--    form itself requires login — see app/routers/support_routes.py)
--    so there's a way to reply.
CREATE TABLE IF NOT EXISTS support_tickets (
    id                   BIGSERIAL PRIMARY KEY,
    type                 VARCHAR(20) NOT NULL CHECK (type IN ('contact', 'bug_report')),
    user_id              BIGINT REFERENCES users(id) ON DELETE SET NULL,
    email                VARCHAR(255),
    subject              VARCHAR(200),
    description          TEXT NOT NULL CHECK (char_length(description) >= 10),
    page_url             TEXT,
    page_name            VARCHAR(200),
    status               VARCHAR(20) NOT NULL DEFAULT 'open'
                             CHECK (status IN ('open', 'answered', 'resolved')),
    admin_response       TEXT,
    resolved_by_user_id  BIGINT REFERENCES users(id) ON DELETE SET NULL,
    resolved_at          TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status);
CREATE INDEX IF NOT EXISTS idx_support_tickets_user ON support_tickets(user_id);

-- ---- 2026-09-19_periodic_mails.sql ---------------------
-- Periodic mails (P0 backlog item: "define daily/weekly/monthly
-- reports") — Daniel's follow-up request (19/09/2026): a screen to
-- build, list, edit, pause and delete recurring admin emails. Each
-- mail's body is plain HTML, wrapped automatically by the existing
-- shared email layout (app/email_layout.py) — same envelope as every
-- other automatic email on the site, only the body is per-mail.
--
-- Recipients are fixed to the admin team (role_level >= 2) for this
-- delivery — see app/periodic_mails.py's module docstring for why
-- (deliberately NOT a general segmented-broadcast tool; that's the
-- "segmented email sending" item Daniel already deferred elsewhere,
-- blocked on a real Subscription system). recipient_scope is still a
-- column, not a hardcoded constant, so a second scope can be added
-- later without another migration.
CREATE TABLE IF NOT EXISTS periodic_mails (
    id                  BIGSERIAL PRIMARY KEY,
    name                VARCHAR(200) NOT NULL,
    subject             VARCHAR(300) NOT NULL,
    body_html           TEXT NOT NULL,
    frequency           VARCHAR(10) NOT NULL CHECK (frequency IN ('daily', 'weekly', 'monthly')),
    recipient_scope     VARCHAR(20) NOT NULL DEFAULT 'admins' CHECK (recipient_scope IN ('admins')),
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    last_sent_at        TIMESTAMPTZ,
    next_send_at        TIMESTAMPTZ NOT NULL,
    created_by_user_id  BIGINT REFERENCES users(id) ON DELETE SET NULL,
    updated_by_user_id  BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Worker query is "active mails due now" — partial index keeps it
-- cheap even once paused/old mails pile up.
CREATE INDEX IF NOT EXISTS idx_periodic_mails_due ON periodic_mails(next_send_at) WHERE is_active = TRUE;


-- ---- 2026-09-19_unify_vacancies.sql ---------------------
-- ============================================================
-- Unify voice-type/vaga entry into a single UI (19/09/2026)
--
-- Daniel: "Hoje temos duas formas de adicionar voz e eu quero que elas
-- se fundam em uma só... com duas formas de adicionar vagas, fica
-- confuso, inclusive para o código e db."
--
-- From now on, listing_vacancies is the ONLY place a seeking_singer/
-- seeking_conductor listing's voice type and fee are entered — the
-- standalone listings.voice_type_id/fee_amount/fee_currency/
-- fee_negotiable fields are still WRITTEN for these two listing_types
-- (kept in sync, derived from the vacancy rows — see
-- _derive_listing_fields_from_vacancies() in
-- app/routers/listings_routes.py) so every other query that still
-- reads those columns directly (home page matching, board filtering,
-- e-mail alerts, banner targeting, the "Buscar pessoas" directory)
-- keeps working unchanged. Also gives seeking_conductor listings
-- convite/candidatura/Match for the first time (previously hardcoded
-- to seeking_singer only in app/match_service.py) — a conductor
-- vacancy has voice_type_id = NULL, since conductors have no naipe.
--
-- Not destructive: relaxes one NOT NULL constraint and adds rows,
-- never removes or drops anything. Safe to run standalone or folded
-- into a future consolidation alongside the other pending migrations
-- (see AGENTS.md's "migration freeze" section — this is NOT applied
-- to production yet, same as every dated migration since 2026-09-15).
-- ============================================================


-- 1) A conductor vacancy has no naipe.
ALTER TABLE listing_vacancies ALTER COLUMN voice_type_id DROP NOT NULL;

-- 2) Backfill: every currently-active seeking_singer/seeking_conductor
--    listing that has ZERO vacancy rows today gets exactly one,
--    mirroring its own (until-now standalone) voice_type_id/fee
--    columns — so every existing listing becomes invite-able
--    immediately, with nothing lost. total_slots=1 matches the
--    single-implicit-vacancy assumption the old single-field UI
--    always had.
INSERT INTO listing_vacancies (listing_id, voice_type_id, fee_amount, fee_currency, fee_negotiable, total_slots)
SELECT l.id, l.voice_type_id, l.fee_amount, l.fee_currency, l.fee_negotiable, 1
FROM listings l
WHERE l.listing_type IN ('seeking_singer', 'seeking_conductor')
  AND l.is_active = TRUE
  AND NOT EXISTS (SELECT 1 FROM listing_vacancies lv WHERE lv.listing_id = l.id);

-- ---- 2026-09-19_notification_center.sql ---------------------
-- ============================================================
-- Central de Notificações (19/09/2026)
--
-- Designed together with Daniel via AskUserQuestion before coding —
-- see app/notification_center.py's module docstring and
-- AI_CHANGELOG.md for the full design conversation. A real list of
-- discrete, individually-readable events, additive on top of the
-- live pending-count nav badges already on the site (unread messages,
-- pending invitations/evaluations/invoice actions — app/render.py),
-- which are untouched by this migration.
--
-- Not destructive: only creates a new table + indexes. Safe to run
-- standalone or folded into a future consolidation alongside the
-- other pending migrations (see AGENTS.md's "migration freeze"
-- section — this is NOT applied to production yet, same as every
-- dated migration since 2026-09-15).
-- ============================================================


CREATE TABLE IF NOT EXISTS notifications (
    id            BIGSERIAL PRIMARY KEY,
    user_id       BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type          VARCHAR(40) NOT NULL,
    title_key     VARCHAR(80) NOT NULL,
    title_params  JSONB,
    link_url      VARCHAR(300),
    icon          VARCHAR(40) NOT NULL DEFAULT 'icon-bell',
    read_at       TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_created ON notifications(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_user_unread ON notifications(user_id) WHERE read_at IS NULL;

-- ============================================================
-- ---- 2026-09-26_notas_v2.sql ----------------------------------
-- Folded in 2026-09-26. Verified on its own: applied twice to a DB built
-- from the previous schema.sql (idempotent) → pg_dump identical to the
-- current schema.sql. It only touches credit_ledger / credit_lot_usage,
-- which exist earlier in this file, so its position at the end is safe.
-- ============================================================
-- category: set on every CREDIT (delta > 0). NULL on debits (a debit can
-- span both categories — credit_lot_usage records the exact split) and on
-- zero-delta rows (shop grants).
ALTER TABLE credit_ledger ADD COLUMN IF NOT EXISTS category VARCHAR(10);
-- expires_at: only on earned credits (created_at + 18 months).
ALTER TABLE credit_ledger ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

-- One-time backfill: purchases never existed before v2 (the buy page was a
-- stub), so every existing credit is EARNED. Its 18 months start at rollout,
-- not retroactively — nobody loses Notas on launch day.
UPDATE credit_ledger
SET category = 'earned', expires_at = now() + interval '18 months'
WHERE delta > 0 AND category IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'credit_ledger_category_valid') THEN
        ALTER TABLE credit_ledger ADD CONSTRAINT credit_ledger_category_valid
            CHECK (category IS NULL OR category IN ('purchased', 'earned'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'credit_ledger_credit_has_category') THEN
        ALTER TABLE credit_ledger ADD CONSTRAINT credit_ledger_credit_has_category
            CHECK (delta <= 0 OR category IS NOT NULL);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'credit_ledger_expiry_only_earned') THEN
        ALTER TABLE credit_ledger ADD CONSTRAINT credit_ledger_expiry_only_earned
            CHECK (expires_at IS NULL OR category = 'earned');
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_credit_ledger_earned_expiry
    ON credit_ledger (expires_at) WHERE category = 'earned';

-- Which credit "lots" each debit consumed. Needed for the spend order
-- (purchased first, then earned by expiry), for expiring only the unspent
-- remainder of an earned lot, and for category-correct refunds.
CREATE TABLE IF NOT EXISTS credit_lot_usage (
    id        BIGSERIAL PRIMARY KEY,
    debit_id  BIGINT NOT NULL REFERENCES credit_ledger(id) ON DELETE CASCADE,
    lot_id    BIGINT NOT NULL REFERENCES credit_ledger(id) ON DELETE CASCADE,
    amount    NUMERIC(10,2) NOT NULL CHECK (amount > 0)
);
CREATE INDEX IF NOT EXISTS idx_credit_lot_usage_lot ON credit_lot_usage(lot_id);
CREATE INDEX IF NOT EXISTS idx_credit_lot_usage_debit ON credit_lot_usage(debit_id);

-- Backfill: allocate every historical debit to that user's credits,
-- oldest first. A debit larger than all credits keeps an uncovered
-- remainder (a "debt"), which the app settles from the next credit.
DO $$
DECLARE
    d RECORD;
    lot RECORD;
    need NUMERIC(10,2);
    take NUMERIC(10,2);
BEGIN
    FOR d IN
        SELECT c.id, c.user_id, -c.delta AS amount
        FROM credit_ledger c
        WHERE c.delta < 0
          AND NOT EXISTS (SELECT 1 FROM credit_lot_usage u WHERE u.debit_id = c.id)
        ORDER BY c.created_at, c.id
    LOOP
        need := d.amount;
        FOR lot IN
            SELECT l.id,
                   l.delta - COALESCE((SELECT SUM(u.amount) FROM credit_lot_usage u WHERE u.lot_id = l.id), 0) AS remaining
            FROM credit_ledger l
            WHERE l.user_id = d.user_id AND l.delta > 0
            ORDER BY l.created_at, l.id
        LOOP
            EXIT WHEN need <= 0;
            CONTINUE WHEN lot.remaining <= 0;
            take := LEAST(need, lot.remaining);
            INSERT INTO credit_lot_usage (debit_id, lot_id, amount) VALUES (d.id, lot.id, take);
            need := need - take;
        END LOOP;
    END LOOP;
END $$;

-- ============================================================
-- ---- 2026-09-26_messenger.sql ---------------------------------
-- Folded in 2026-09-26. Verified on its own: applied twice to a DB built
-- from the previous schema.sql with sample messages (idempotent) →
-- pg_dump identical to the current schema.sql. Depends only on messages,
-- users and the retention functions/view defined earlier in this file.
-- ============================================================
CREATE TABLE IF NOT EXISTS conversations (
    id                BIGSERIAL PRIMARY KEY,
    user_low_id       BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_high_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- 'request' = first contact not yet accepted (lands in the recipient's
    -- Requests folder); 'active' = normal chat.
    status            VARCHAR(10) NOT NULL DEFAULT 'active' CHECK (status IN ('request', 'active')),
    requested_by      BIGINT REFERENCES users(id) ON DELETE CASCADE,
    declined_at       TIMESTAMPTZ,   -- recipient declined the request (sender is never told)
    low_hidden_at     TIMESTAMPTZ,   -- per-side "hide conversation"; cleared by any new message
    high_hidden_at    TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_activity_at  TIMESTAMPTZ NOT NULL DEFAULT now(),  -- 60-day expiry clock
    CHECK (user_low_id < user_high_id),
    UNIQUE (user_low_id, user_high_id)
);
CREATE INDEX IF NOT EXISTS idx_conversations_activity ON conversations(last_activity_at);
CREATE INDEX IF NOT EXISTS idx_conversations_high ON conversations(user_high_id);

-- "These two have had contact" — outlives deleted chats, so they never need
-- a request again. Erased with either account. Matches are checked live
-- against job_matches, not copied here.
CREATE TABLE IF NOT EXISTS contact_pairs (
    user_low_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_high_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    established_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    source          VARCHAR(10) NOT NULL CHECK (source IN ('accepted', 'legacy')),
    PRIMARY KEY (user_low_id, user_high_id),
    CHECK (user_low_id < user_high_id)
);

ALTER TABLE messages ADD COLUMN IF NOT EXISTS conversation_id BIGINT REFERENCES conversations(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, id);

-- Reports keep a snapshot of the text: the message itself may expire
-- (60 days) before moderation looks at it. Resolved reports are purged
-- 60 days after resolution by the retention worker.
CREATE TABLE IF NOT EXISTS message_reports (
    id                BIGSERIAL PRIMARY KEY,
    message_id        BIGINT REFERENCES messages(id) ON DELETE SET NULL,
    reporter_id       BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reported_user_id  BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason            VARCHAR(500) NOT NULL,
    body_snapshot     TEXT NOT NULL,
    status            VARCHAR(10) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'dismissed', 'removed')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at       TIMESTAMPTZ,
    resolved_by       BIGINT REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE (message_id, reporter_id)
);
CREATE INDEX IF NOT EXISTS idx_message_reports_open ON message_reports(created_at) WHERE status = 'open';

-- At most one "new messages" e-mail per recipient per day (M6).
ALTER TABLE users ADD COLUMN IF NOT EXISTS message_email_sent_at TIMESTAMPTZ;

-- Backfill: every still-visible message joins its pair's conversation.
-- Both sides have written → active + legacy contact pair; one-way → request.
-- Already-archived messages stay without a conversation and are purged by
-- the retention worker (they were hidden already).
INSERT INTO conversations (user_low_id, user_high_id, status, requested_by, created_at, last_activity_at)
SELECT lo, hi,
       CASE WHEN bool_or(sender_id = lo) AND bool_or(sender_id = hi) THEN 'active' ELSE 'request' END,
       CASE WHEN bool_or(sender_id = lo) AND bool_or(sender_id = hi) THEN NULL ELSE min(sender_id) END,
       min(created_at), max(created_at)
FROM (
    SELECT least(sender_id, recipient_id) AS lo, greatest(sender_id, recipient_id) AS hi, sender_id, created_at
    FROM messages WHERE archived_at IS NULL AND conversation_id IS NULL
) t
GROUP BY lo, hi
ON CONFLICT (user_low_id, user_high_id) DO NOTHING;

UPDATE messages m SET conversation_id = c.id
FROM conversations c
WHERE m.conversation_id IS NULL AND m.archived_at IS NULL
  AND c.user_low_id = least(m.sender_id, m.recipient_id)
  AND c.user_high_id = greatest(m.sender_id, m.recipient_id);

INSERT INTO contact_pairs (user_low_id, user_high_id, established_at, source)
SELECT user_low_id, user_high_id, created_at, 'legacy' FROM conversations WHERE status = 'active'
ON CONFLICT DO NOTHING;

-- Every inserted message belongs to its pair's conversation (created here
-- if the app didn't pass one — e.g. direct inserts), and an expired
-- conversation's old messages never come back (they're dropped first).
CREATE OR REPLACE FUNCTION message_activity() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    lo BIGINT := least(NEW.sender_id, NEW.recipient_id);
    hi BIGINT := greatest(NEW.sender_id, NEW.recipient_id);
BEGIN
    PERFORM pg_advisory_xact_lock((lo % 2147483647)::integer, (hi % 2147483647)::integer);
    IF NEW.conversation_id IS NULL THEN
        INSERT INTO conversations (user_low_id, user_high_id, status, created_at, last_activity_at)
        VALUES (lo, hi, 'active', NEW.created_at, NEW.created_at)
        ON CONFLICT (user_low_id, user_high_id) DO NOTHING;
        SELECT id INTO NEW.conversation_id FROM conversations WHERE user_low_id = lo AND user_high_id = hi;
    END IF;
    DELETE FROM messages
    WHERE conversation_id = NEW.conversation_id
      AND EXISTS (SELECT 1 FROM conversations c WHERE c.id = NEW.conversation_id
                  AND c.last_activity_at + interval '60 days' <= now());
    UPDATE conversations
    SET last_activity_at = GREATEST(last_activity_at, NEW.created_at), low_hidden_at = NULL, high_hidden_at = NULL
    WHERE id = NEW.conversation_id;
    NEW.activity_at := NEW.created_at;
    RETURN NEW;
END $$;

CREATE OR REPLACE VIEW visible_messages AS
 SELECT m.* FROM messages m JOIN conversations c ON c.id = m.conversation_id
 WHERE c.last_activity_at + interval '60 days' > now();

-- ============================================================
-- ---- 2026-09-26_listing_terms.sql (#55) -----------------------
-- Folded in 2026-09-26. Verified on its own: applied twice to a DB built
-- from the previous schema.sql with a job listing + self-ad (idempotent,
-- constraint rejects re-copying) → pg_dump identical to schema.sql.
-- Depends on listings/listing_vacancies (created earlier in this file).
-- ============================================================
UPDATE listings
SET voice_type_id = NULL, fee_amount = NULL, fee_negotiable = FALSE
WHERE listing_type IN ('seeking_singer', 'seeking_conductor')
  AND (voice_type_id IS NOT NULL OR fee_amount IS NOT NULL OR fee_negotiable);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'listings_job_terms_live_in_vacancies') THEN
        ALTER TABLE listings ADD CONSTRAINT listings_job_terms_live_in_vacancies
            CHECK (listing_type NOT IN ('seeking_singer', 'seeking_conductor')
                   OR (voice_type_id IS NULL AND fee_amount IS NULL AND NOT fee_negotiable));
    END IF;
END $$;

CREATE OR REPLACE VIEW listing_terms AS
 SELECT lv.listing_id, lv.voice_type_id, lv.fee_amount, lv.fee_currency, lv.fee_negotiable
 FROM listing_vacancies lv
 JOIN listings l ON l.id = lv.listing_id AND l.listing_type IN ('seeking_singer', 'seeking_conductor')
 UNION ALL
 SELECT l.id, l.voice_type_id, l.fee_amount, l.fee_currency, l.fee_negotiable
 FROM listings l
 WHERE l.listing_type IN ('singer_available', 'conductor_available');

COMMIT;

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

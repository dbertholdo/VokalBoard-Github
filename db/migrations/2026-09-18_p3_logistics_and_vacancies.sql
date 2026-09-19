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

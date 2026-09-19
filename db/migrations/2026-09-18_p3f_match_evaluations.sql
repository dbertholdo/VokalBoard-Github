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

CREATE TABLE match_evaluations (
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
CREATE INDEX idx_match_evaluations_rated ON match_evaluations (rated_id);

ALTER TABLE job_matches
    ADD COLUMN artist_eval_reminder_sent_at TIMESTAMPTZ,
    ADD COLUMN contractor_eval_reminder_sent_at TIMESTAMPTZ;

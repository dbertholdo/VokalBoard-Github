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

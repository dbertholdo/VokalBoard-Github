-- P6 — fechar o loop de denúncias (18/09/2026): "resposta a denúncias e
-- notificação ao usuário quando denúncia for aceita" (pedido do Daniel,
-- painel de Admin). Antes, listing_reports só armazenava a denúncia —
-- sem status, sem quem revisou, sem notificação. Ver app/moderation.py.
ALTER TABLE listing_reports
    ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'accepted', 'rejected')),
    ADD COLUMN resolved_at TIMESTAMPTZ,
    ADD COLUMN resolved_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX idx_listing_reports_status ON listing_reports(status);

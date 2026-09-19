-- P6 — punição ao aceitar uma denúncia (18/09/2026): "no botão de
-- denúncia precisamos definir alguma forma de warning/punição/
-- banimento" (pedido do Daniel). 3 níveis: aviso (sem efeito na
-- conta), suspensão (reaproveita o deleted_at/"Deactivate" que já
-- existe — o próprio usuário pode reverter fazendo login de novo) e
-- banimento (definitivo — ver app/moderation.py).
ALTER TABLE users
    ADD COLUMN banned_at TIMESTAMPTZ,
    ADD COLUMN banned_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL;

-- Histórico de punições — permite ver quantos avisos/suspensões/bans
-- uma conta já recebeu (ex.: no mini card do Admin), sem precisar
-- adivinhar a partir do texto solto de audit_log.
CREATE TABLE moderation_actions (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    report_id    BIGINT REFERENCES listing_reports(id) ON DELETE SET NULL,
    action_type  VARCHAR(20) NOT NULL CHECK (action_type IN ('warning', 'suspend', 'ban')),
    admin_id     BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_moderation_actions_user ON moderation_actions(user_id);

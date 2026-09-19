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
    ADD COLUMN refunded_at TIMESTAMPTZ,
    ADD COLUMN refunded_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL;

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

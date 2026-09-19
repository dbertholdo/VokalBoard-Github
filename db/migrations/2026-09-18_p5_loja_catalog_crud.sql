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

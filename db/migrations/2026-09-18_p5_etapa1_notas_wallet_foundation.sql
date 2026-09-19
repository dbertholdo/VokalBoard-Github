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

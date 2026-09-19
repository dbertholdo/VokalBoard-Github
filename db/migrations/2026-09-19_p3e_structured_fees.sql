-- P3.E: Cachê estruturado (valor numérico + moeda) em vez de texto
-- livre, e infraestrutura de compatibilidade/score.
--
-- Decisão do Daniel em 18/09/2026: o campo `fee` (VARCHAR texto livre)
-- não deixa comparar/ordenar por valor de forma confiável ("250€" vs "a
-- combinar" vs "200-300€"). Novos campos: fee_amount (numérico),
-- fee_currency (EUR/CHF/USD/GBP — multi-moeda pré-implementada pensando
-- em expansão futura pra outros países, mesmo hoje operando só em
-- DE/AT/CH) e fee_negotiable (booleano, "a negociar").
--
-- O campo antigo `fee` (texto livre) é MANTIDO nas duas tabelas — dados
-- antigos continuam lá, só não é mais escrito/lido pelo formulário e
-- exibição novos. Sem migração/backfill de dados existentes até o
-- Daniel autorizar (mesma regra de sempre: nada roda contra o Postgres
-- do Railway sem liberação explícita).
--
-- NÃO comparamos valores em moedas diferentes (sem conversão de câmbio)
-- — ordenar por fee_amount desc compara o valor numérico bruto entre
-- moedas diferentes, o que é impreciso quando há mistura de moedas.
-- Aceitável por ora: hoje o site é DE/AT/CH (majoritariamente EUR/CHF,
-- valores parecidos); registrado como limitação conhecida.

ALTER TABLE listings
    ADD COLUMN fee_amount NUMERIC(10, 2) CHECK (fee_amount IS NULL OR fee_amount >= 0),
    ADD COLUMN fee_currency VARCHAR(3) NOT NULL DEFAULT 'EUR' CHECK (fee_currency IN ('EUR', 'CHF', 'USD', 'GBP')),
    ADD COLUMN fee_negotiable BOOLEAN NOT NULL DEFAULT FALSE,
    -- Defesa em profundidade: nunca os dois ao mesmo tempo (valor E "a
    -- negociar" marcados) — a regra "exatamente um dos dois" pra
    -- listing_type que exige cachê é validada na aplicação
    -- (_fee_valid em listings_routes.py), isto aqui só impede o caso
    -- claramente inconsistente de ambos juntos.
    ADD CONSTRAINT listings_fee_not_both CHECK (NOT (fee_amount IS NOT NULL AND fee_negotiable));

ALTER TABLE listing_vacancies
    ADD COLUMN fee_amount NUMERIC(10, 2) CHECK (fee_amount IS NULL OR fee_amount >= 0),
    ADD COLUMN fee_currency VARCHAR(3) NOT NULL DEFAULT 'EUR' CHECK (fee_currency IN ('EUR', 'CHF', 'USD', 'GBP')),
    ADD COLUMN fee_negotiable BOOLEAN NOT NULL DEFAULT FALSE,
    ADD CONSTRAINT listing_vacancies_fee_not_both CHECK (NOT (fee_amount IS NOT NULL AND fee_negotiable));

-- Toggle de Admin (Red Zone-lite — não é uma ação financeira/destrutiva
-- como o Capitalism Mode, então fica em /admin, não em /financeiro) pra
-- controlar se o score/critério de compatibilidade aparece pro usuário
-- final. Implantado desligado por padrão — Daniel quer discutir depois
-- se/como mostrar.
INSERT INTO system_settings (key, value) VALUES
    ('compatibility_score_visible', 'false')
ON CONFLICT (key) DO NOTHING;

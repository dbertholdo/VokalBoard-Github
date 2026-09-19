-- P4 Etapa 3 (18/09/2026): contador genérico de uso de ferramentas do
-- site, pedido pelo Daniel junto com o badge de pendência do
-- Rechnungmaker — "quero que haja uma forma de trackear quais
-- ferramentas do site são mais usadas. E isso inclui Rechnung maker."
-- Ver app/feature_usage.py — deliberadamente genérico, não é específico
-- do Rechnungmaker, só é o primeiro consumidor.
CREATE TABLE IF NOT EXISTS feature_usage_monthly (
    feature_key VARCHAR(64) NOT NULL,
    usage_month DATE NOT NULL,
    count BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (feature_key, usage_month)
);

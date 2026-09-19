-- P2.B: idiomas falados no perfil (qualquer role, não só cantor).
-- Lista fixa (10 mais faladas na Europa incluindo Português) + "Outra" com
-- nome livre + até 3 campos extras + remoção — controlado na aplicação
-- (app/languages.py), aqui só a tabela que guarda o que a pessoa escolheu.

CREATE TABLE IF NOT EXISTS user_spoken_languages (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- código da lista fixa (app/languages.py: SPOKEN_LANGUAGE_OPTIONS) ou
    -- 'other' quando a pessoa escolheu "Outra" e digitou um nome livre.
    language_code VARCHAR(20) NOT NULL,
    -- só usado quando language_code = 'other'; nulo nos demais casos.
    custom_name VARCHAR(100),
    sort_order SMALLINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_spoken_languages_user
ON user_spoken_languages (user_id);

-- Evita repetir o mesmo idioma fixo duas vezes para a mesma pessoa
-- (não se aplica a 'other', que pode ter nomes livres diferentes).
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_spoken_language_fixed
ON user_spoken_languages (user_id, language_code)
WHERE language_code <> 'other';

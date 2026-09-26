-- Rode isso no Adminer/Railway ANTES de fazer o deploy do código novo —
-- senão o site vai dar erro tentando gravar na tabela posts, que ainda
-- não existe no banco de produção.

CREATE TABLE IF NOT EXISTS posts (
    id            BIGSERIAL PRIMARY KEY,
    author_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title         VARCHAR(150) NOT NULL,
    body          TEXT NOT NULL,
    is_published  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_posts_published_created ON posts(is_published, created_at DESC);

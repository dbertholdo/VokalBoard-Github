CREATE TABLE IF NOT EXISTS site_banners (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    body VARCHAR(500) NOT NULL,
    link_url VARCHAR(500),
    audience VARCHAR(32) NOT NULL DEFAULT 'all' CHECK (audience IN ('all','singer','conductor','no_subscription')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

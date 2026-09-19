-- P2.C: telefone obrigatório para publicar anúncio (validado na
-- aplicação, não precisa de constraint de banco — contas antigas sem
-- telefone continuam existindo, só não conseguem publicar até
-- preencher) + escolha de visibilidade no perfil público.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS phone_visibility VARCHAR(10) NOT NULL DEFAULT 'private';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'users_phone_visibility_check'
    ) THEN
        ALTER TABLE users
            ADD CONSTRAINT users_phone_visibility_check CHECK (phone_visibility IN ('private', 'public'));
    END IF;
END $$;

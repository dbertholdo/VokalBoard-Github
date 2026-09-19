-- P4: marcador NÃO-sensível de que uma Rechnung já foi confirmada e
-- enviada por e-mail para este Match — nunca guarda o PDF nem os
-- dados do formulário (Zero-Storage, CLAUDE.md Seção 2). Serve só
-- pra UI (esconder os botões de pedir/gerar depois de já enviada).
ALTER TABLE job_matches ADD COLUMN IF NOT EXISTS invoice_sent_at TIMESTAMPTZ;

-- P6 — Layout compartilhado de e-mails (18/09/2026).
--
-- Pedido do Daniel: editar o layout (ícones, logo, texto/fontes,
-- assinatura e rodapé) de TODOS os e-mails automáticos num lugar só,
-- pra mudar tudo de uma vez sem mexer em cada e-mail individual. Ver
-- app/email_layout.py (render_email(), chamado automaticamente por
-- app/email.py's send_email()) e a tela /admin/emails.
--
-- Reaproveita system_settings (mesma tabela genérica de chave/valor
-- já usada por Capitalism Mode e preço de assinatura) — sem tabela
-- nova. Valor NULL/ausente cai pro padrão em app/email_layout.py
-- (_DEFAULTS), então estas linhas são só pra deixar os registros já
-- existentes desde o início (facilita ver/editar no Admin).
INSERT INTO system_settings (key, value) VALUES
    ('email_layout_logo_url', ''),
    ('email_layout_accent_color', '#12a488'),
    ('email_layout_header_emoji', '🎵'),
    ('email_layout_signature', 'Equipe VokalBoard'),
    ('email_layout_footer', 'Você recebeu este e-mail porque tem uma conta no VokalBoard.')
ON CONFLICT (key) DO NOTHING;

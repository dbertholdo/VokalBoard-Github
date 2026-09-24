# Brand kit v1 — inventário e verificação (24/09/2026)

Referência: `vokalboard-brand-kit-v1`, manual e instruções versão 0.4.
Escopo exclusivamente visual. Sem deploy, migração, mudança de cobrança ou permissões.
Estado inicial: Claude já integrou tokens Mineral, Manrope local, mascotes e novos fluxos.
Preservar as quatro alterações iniciais: AI_CHANGELOG, i18n, listing-form.js e listing_form.html.

## Inventário completo de templates

| Lote | Telas / componentes | Trabalho visual |
|---|---|---|
| 1 — Fundação | base; cabeçalho, rodapé, menus, notificações, banners, diálogo de suporte | Assinatura final, navegação, superfícies, foco, toque, responsividade |
| 2 — Oportunidades | home, board, listing_detail, listing_form, my_listings, my_favorites, listing_candidates, invitations, match_history | Cards, filtros, vagas, estados, Zona de Alerta e Match |
| 3 — Pessoas e comunicação | profile, public_profile, profile_wizard, search_people, messages, message_detail, message_compose, hall_da_fama, contato | Perfil, diretório, conversa, formulários, feedback e mascote contextual |
| 4 — Conta e documentos | login, register, forgot_password, reset_password, change_password, reactivate_account, auth_message, digital_pass_stub, assinar_stub, notas_comprar_stub, notas, rechnungmaker, invoice_match_form, invoice_match_preview | Campos, erros, revisão financeira sóbria, números legíveis, estados indisponíveis |
| 5 — Administração | admin, admin_users, admin_user_detail, admin_posts, admin_analytics, admin_banners, admin_emails, admin_periodic_mail_form, admin_tickets, admin_loja, zona_vermelha, financial_dashboard, financial_import, financeiro_conceder, financeiro_extrato_geral, financeiro_estornos | Tabelas, métricas, editores, filtros, permissões preservadas; Red Zone administrativa distinta |
| 6 — Legal e parciais | impressum, datenschutz, code_of_conduct; _captcha_fields, _location_fields, _profile_menu, _retention_warning, _search_error, _invoice_preview | Leitura, links, labels e estados compartilhados |

PDFs e e-mails efetivamente enviados não são páginas do site: manter conteúdo, fontes
incorporadas e regras atuais. A prévia de Rechnung recebe somente estilo de tela.
Não transformar os stubs existentes em funcionalidades nem ocultá-los.

## Critérios de validação

- Assets do pacote conferidos por SHA-256; nenhuma regeneração de mascote.
- Contrato de campos/ações/links preservado por template, inclusive trabalho não commitado do Claude.
- Testes existentes em banco Docker novo e isolado, sem tocar Railway ou banco local principal.
- Navegador real: 320, 390, 768 e 1440px; reflow equivalente a zoom 200%; teclado,
  foco, menu, dismiss, paginação, formulário condicional, aviso de cachê, prévia financeira.
- Conferir font-loading, contraste dos tokens, ausência de overflow e console.
- Estado de cada lote e resultados reais registrados no AI_CHANGELOG; esta lista não declara aprovação.

## Separação obrigatória

Zona de Alerta = urgências. Red Zone = administração. God Mode = poderes.
Não renomear rotas, enums, permissões ou áreas por substituição global.

## Resultado da revisão local (24/09/2026)

- Camada compartilhada aplicada aos seis lotes; 59 templates preservam o contrato de campos/ações/links capturado antes do trabalho.
- 11 testes de marca aprovados: assets, contraste de oito pares, herança de base e smoke autenticado de 40 rotas. Isso não equivale a auditoria integral de acessibilidade.
- Navegador: 9 famílias públicas/autenticadas × 4 larguras e 12 administrativas × 4 larguras = 84 medições sem overflow horizontal de página, em 320/390/768/1440px.
- Inspeção por imagem de homepage, perfil, wizard, formulário, Rechnungmaker, Admin/Red Zone e diálogo de suporte. Contraste ativo Red Zone corrigido; alinhamento de checkboxes corrigido; nome acessível do botão de suporte conservado no mobile.
- Verificados: Manrope carregada, foco por Tab (navy 2px), menu móvel/ Escape, Dismiss da homepage, alternância dos campos de disponibilidade, paginação para página 2, prévia de fatura reagindo a nome/valor fictícios, abrir/cancelar suporte sem enviar.
- Console observado sem warnings/errors. Perfil em 720px sem overflow (reflow de largura equivalente a 1440/200%; não foi zoom real).
- Suíte geral: 267 aprovados / 18 falhas; detalhes por grupo no AI_CHANGELOG. Não corrigidas: trabalho funcional reservado ao Claude, causa não atribuída ao visual sem evidência.

### Limites reais de verificação / handoff

- Não testado em aparelho físico nem Safari/Firefox; teste móvel foi viewport do navegador integrado.
- Zoom real 200%, leitor de tela, performance e todos os estados de dados/idiomas não foram certificados.
- Não executados nesta revisão: submissão de anúncio com confirmação de cachê, emissão/envio de PDF, pagamentos, campanhas de e-mail ou ações administrativas destrutivas. Campos e ações preservados pelo contrato, mas isso não substitui testes ponta a ponta destes fluxos.
- Base/skin cobrem todos os templates inventariados; não se declara que todos os estados possíveis de cada tela foram visualmente inspecionados.
- Nenhum deploy, alteração de backend, migração em produção ou worker de produção executado. Contêiner `vokalboard-brand-qa` / porta local 8002 e banco isolado mantidos para reprodução.

# Archived AI changelog entries (2026-09-25, moved 2026-09-28)

## 2026-09-25 — Codex — testes da revisão 20260925-1 e problemas NÃO corrigidos

Após a implementação sem testes, Daniel autorizou testar e encontrar problemas, expressamente SEM aplicar alterações. O limite de uso interrompeu o login de QA; na retomada foram concluídas somente as verificações internas pendentes, sem repetir a suíte completa. Esta entrada atualiza o estado de validação das entradas anteriores, preservadas abaixo.

### Execução e cobertura efetivas
- Versão atual de `app/` e `tests/` copiada somente ao contêiner local `vokalboard-brand-qa`; iniciado esse contêiner, com banco confirmado `vokalboard_brand_retention_test_20260924` e e-mails em backend console. Banco principal/produção não utilizados.
- Suíte completa: **267 passed, 18 failed, 3 warnings, 89,60s**. Mesmos 18 testes falhos anteriormente registrados; testes de marca passaram. Isso não prova que todas as falhas sejam bugs de produto ou que sejam causadas pelo visual; investigar expectativas/fixtures antes de corrigir.
- Navegador confirmou CSS `20260925-1`, fundo geral #F5F7FA, Manrope carregada e hero sem gradiente.
- **68 medições de largura** em 320/390/768/1440px: 7 páginas públicas × 4, 7 internas × 4 e 3 administrativas × 4; sem overflow horizontal da página. Isso NÃO certifica legibilidade interna dos componentes.
- Páginas internas: perfil privado/público fictício, formulário de anúncio, mensagens, Hall da Fama, Rechnungmaker avulso e Notas. Administrativas: e-mails, formulário de e-mail periódico e Red Zone. Editor do e-mail periódico confirmou monoespaçada 16px/24px; o editor de código da tela geral de e-mails não estava exposto nesse estado e não foi certificado.
- Menu móvel abriu (`aria-expanded=true`) e fechou com Escape (`false`). Botão Back desativado no wizard apresentou fundo #E3E7EF/texto #526176. Console observado sem warnings/errors. Viewport restaurado e aba temporária fechada.
- Fixtures sintéticas criadas após a suíte; uma conta fictícia foi promovida apenas no banco isolado para inspecionar Admin. Nenhuma mudança de privilégios em produção nem envio real de e-mail.

### Problemas encontrados — pendentes, nenhuma correção aplicada

| Prioridade | Problema / reprodução | Evidência |
|---|---|---|
| Alta (legibilidade) | `/rechnungmaker?tab=avulso`, viewport 320px: tabela e totais da prévia quebram textos/valores em muitas linhas. | Screenshot mostrou valores como `0.00 EUR` fragmentados nas células; papel com 273px de largura e totais restritos a cerca de 143px. Ausência de overflow da página não impediu a degradação. Rever layout da prévia sem alterar cálculo/emissão de PDF. |
| Média (sobreposição) | `/profile/wizard`, etapa foto, 320px: ajuda invade o campo de arquivo. | Borda inferior do input em y=694,19 e início da ajuda em y=686,19; `margin-top:-8px` computado. Sobreposição vertical de 8px confirmada na imagem. |
| Média (acessibilidade) | `/listings/new`: campos da linha de vagas sem rótulos adequados. | Voz e moeda apareceram como combobox sem nome, quantidade como spinbutton sem nome na árvore; voz/quantidade/cachê/moeda não possuem label associado nem aria-label na inspeção. Quantidade/cachê dependem de placeholder; não substitui rótulo visível persistente. |
| Baixa (usabilidade visual) | Cabeçalho autenticado muito alto no mobile. | Aproximadamente 251px em 320/390px e 233px em 768px, contra 92px em 1440px. Navegação ocupa espaço excessivo antes do conteúdo, embora sem overflow. É avaliação de usabilidade, não falha funcional confirmada. |

### Pendências e próximo passo
- Não verificados: celular físico, Safari/Firefox, zoom real 200%, leitor de tela, performance e todos os estados/idiomas. Fontes CJK empacotadas continuam pendentes.
- As 18 falhas da suíte mantêm a distribuição já documentada: moderação de denúncias (3), acesso financeiro (1), mascote (1), submenu de histórico (1), punições/estornos (4), privacidade no PDF de CV (1), e-mails periódicos (1), estrutura do perfil (2), AdminPosts (1), urgência (3). Correções funcionais ficam com Claude.
- Próximo passo verificável: somente após autorização, corrigir os problemas de apresentação/acessibilidade acima e repetir seus cenários; não marcar conformidade visual integral como concluída.
- Na tarefa de testes, nenhum arquivo do repositório foi alterado. **Nesta solicitação de registro, somente `AI_CHANGELOG.md` foi alterado**; mudanças preexistentes preservadas. Nenhum teste repetido agora, nenhuma correção, deploy ou migração executados.

### 2026-09-25 — Codex — fechamento das correções estéticas, SEM EXECUÇÃO
- `base.html`: versão do CSS `20260925-1` para invalidar cache. `tests/test_brand_visual.py`: apenas atualizadas as duas referências esperadas à versão; arquivo NÃO executado, critérios não removidos.
- `VISUAL_ROLLOUT.md`: nova revisão marcada como implementada mas não verificada; testes antigos não certificam estas mudanças. Exceções de editores monoespaçados e geometria circular documentadas.
- Entregue nesta sequência: correções de fundos/cores legadas, espaçamentos/raios identificados no audit, hierarquia de texto, estados hover e organização de fontes dos editores. Código funcional do Claude preservado.
- Pendência de implementação explícita: família CJK complementar empacotada/licenciada; nesta revisão só foi melhorada a seleção de fallbacks locais, sem prometer cobertura uniforme.
- Pendentes por solicitação de NÃO testar: navegador, celular físico, outros navegadores, zoom, leitor de tela, contraste renderizado, performance e regressões. As 18 falhas funcionais anteriores permanecem para Claude.
- Testes/build/site/browser/Docker: NENHUM executado nesta sessão. Sem publicação, deploy, migração ou acesso ao banco.
- Próximo passo verificável: quando autorizado, validar `20260925-1`, em especial navegação mobile maior e prévia da fatura; não declarar conformidade estrita antes disso.

### 2026-09-25 — Codex — lote visual: tipografia e exceção de editor (SEM TESTES)
- `brand.css`: navegação 16/24 (inclusive mobile), labels 14/20, títulos de cards do perfil 20/28 sem caixa alta, metadados 14/20, corpo da prévia de fatura 16/24 e títulos 24/32. Mantidos números tabulares; sem editar geração de PDF.
- `admin_emails.html` e `admin_periodic_mail_form.html`: fonte inline substituída pela classe `code-editor`, centralizada em brand.css. Monoespaçada preservada como exceção intencional para HTML cru, agora com entrada 16/24. Campos/validações/ações intactos.
- Fallbacks CJK agora específicos por idioma (`:lang(zh)`/`:lang(ko)`), incluindo opções locais Windows/macOS/Linux. NÃO há nova fonte CJK empacotada; cobertura consistente entre dispositivos continua pendente. Nenhum download/recurso remoto adicionado.
- Testes/site/build/navegador: NÃO executados. Próximo: atualizar cache e handoff, registrando implementação não verificada e pendência de fontes CJK locais licenciadas.

## 2026-09-25 — Codex — lote visual: fundos, espaçamento e raios (SEM TESTES)
- Autorização atual: implementar correções estéticas sem executar site, testes, build ou navegador. Alteração anterior do log preservada. Código funcional continua reservado ao Claude.
- `app/static/css/brand.css`: fundos sólidos Mineral para hero, convite e destaque de perfil; cores/bordas dos componentes reais de vagas normalizadas; espaçamento do perfil, formulários, mensagens, menus e hero alinhado à escala; raios de painéis/tags e bolha unificados; hover sem reduzir opacidade de texto.
- Nenhum campo, condição de exibição, ação, rota, regra ou banco alterado. Sem deploy.
- Testes executados: NENHUM, por solicitação expressa. Implementado, não validado em runtime; resultados de 24/09 não certificam esta revisão.
- Próximo: tipografia e exceções de fonte, versão de cache e documentação de pendências.

## 2026-09-25 — Codex — checagem estática de aderência estrita ao padrão visual

**Pedido:** apenas checar design e registrar; não implementar nem executar aplicação/testes. **Conclusão: aderência parcial, NÃO estrita.** A camada compartilhada usa a identidade correta, mas não normaliza todos os componentes. A entrega anterior de uma camada visual não equivale a conformidade integral com o manual.

**Método e escopo:** leitura de AGENTS, log recente, instruções de marca v0.4, Manual Visual v1.0, `style.css`, `brand.css` e referências nos templates. Conferida a ordem de inclusão (`base.html:54–55`: style antes de brand), especificidade e estilos inline. Git inicialmente limpo. Sem abrir navegador, iniciar Docker, executar testes/build/scripts da aplicação, acessar banco ou alterar o design. Achados abaixo são de código, não nova observação de renderização. Medidas numéricas do manual são referências técnicas propostas, não aprovações individuais do Daniel; divergências são registradas como tal.

### O que está alinhado no código
- Tokens centrais em `style.css:18–55`: canvas #F5F7FA, superfície #FFFFFF, navy #17283F, violeta #635BDE, hover #5148C5, cores semânticas e raios 16/8/6.
- `brand.css:3–4`: Manrope como fonte principal e fundo geral Mineral. Oito declarações locais de fonte em `style.css:69–132` cobrem pesos 400/500/600/700, latin/latin-ext; licença presente no projeto.
- Hierarquia global h1 32/40 desktop e 28/36 mobile, h2 24/32 e h3 20/28 em `style.css:273–282`; existem exceções locais listadas abaixo.
- `brand.css`: container com margens internas de 32px desktop/16px mobile, cards gerais 24px/16px, grid de anúncios com gap 16px, assinatura final navy e foco visível.
- Gradientes antigos de `.profile-hero`, `.notas-balance-box` e `.red-zone-hero` são sobrescritos por fundos sólidos em brand.css; não contá-los como desvios ativos apenas por aparecerem em busca textual. Mascote administrativo antigo e animação de patrulha também foram substituídos/desativados.

### Divergências e pendências sustentadas pela leitura

| Item | Evidência atual | Comparação com o manual / próxima revisão visual |
|---|---|---|
| Fundos com gradiente residual | `style.css:1084–1097` `.hero`; `:2973–2993` `.invite-friend-box`; `:2997–3008` `.profile-highlight-banner`. Referenciados por home, hall_da_fama e public_profile; sem sobrescrita correspondente em brand.css. | Manual §5: superfícies predominantemente branca/Mineral, não usar gradiente como decoração padrão. Estes componentes ainda usam gradiente e `--accent2`/`--accent2-light`, cores extras fora da tabela Mineral. Não considerar normalização concluída. |
| Fundos/bordas legados nas vagas | `style.css:1516–1560`: `.logistics-flag` #f0f5f0; `.listing-vacancies-box` #fbfcfc/#e5e7e7; `.vacancy-apply-status` #eef2ee. | Não correspondem aos tokens definidos. O adapter estiliza `.vacancy-card`/`.vacancy-row`, mas não estes componentes; revisar os seletores reais de listing_detail. Cores de `.vacancy-fee`/`.vacancy-slots`, por outro lado, já são sobrescritas. |
| Espaçamento não unificado | `.profile-edit-grid` gap 20px (`style.css:192–197`); `.stacked-form` gap 14px (`:940–943`); `.hero` padding 36px 28px, margem 28px, ações gap 10px/margem 18px (`:1084–1097`); `.message-row` padding 20px (`brand.css`). | Manual §6 enumera 4/8/12/16/24/32/48 e separação de cards 16px. Esses valores escapam da escala enumerada (mesmo quando múltiplos de 4). Margens/paddings adicionais permanecem em componentes específicos; o container global correto não os elimina. |
| Raios não unificados | `.profile-menu > .profile-menu-links` 10px (`style.css:138–145`); `.listing-vacancies-box` e `.invite-friend-box` 12px; `.profile-highlight-banner` pill; `.message-body-box` preserva canto de 4px (`:678`). | Referência §6: painel/card 16px, controle 8px, etiqueta 6px. Eventuais exceções de linguagem de chat/badge devem ser deliberadas e documentadas, não assumidas como aderência estrita. |
| Tamanhos de texto e hierarquia local | `.profile-hero .card h3` 0.78rem/caixa alta (`style.css:3114–3120`); `.hall-fame-meta` 0.78rem (`:2950` aproximadamente); `.invoice-paper` 0.82rem e kicker 0.7rem (`:3474–3516`); `.stacked-form label` 0.9rem (`:948–954`); navegação mobile 0.875rem (`brand.css`). | Manual §4: card 20/28, metadados/rótulos 14/20, campos/corpo/navegação 16/24. A regra global não vence todos estes seletores. Na fatura, algumas partes já sobem para 14px, mas o corpo e kicker continuam menores. Conferir papéis semânticos antes de ajustar; não aumentar textos indiscriminadamente. |
| Fontes fora de Manrope em editores | `admin_emails.html:85` e `admin_periodic_mail_form.html:46`: inline SF Mono/Consolas/Menlo e 13px. | Inline prevalece sobre o adapter; portanto fonte/tamanho não são uniformes em todo o site. Monoespaçada pode ser apropriada ao editor de HTML, mas é exceção funcional a documentar, não trocar cegamente. Conteúdo do iframe de e-mail não herda CSS do site e foi excluído da entrega visual anterior. |
| Cobertura CJK não garantida | Só `app/static/fonts/manrope` empacotada; `brand.css:3` cita Noto/CJK/YaHei/Malgun como alternativas do sistema, sem fornecer essas fontes. | Manual §4 exige planejar família complementar e validar glifos. A escolha efetiva pode variar por dispositivo; esta leitura não certifica aparência consistente em chinês/coreano. |
| Opacidade residual nos estados hover | `.button-primary:hover { opacity:0.95 }` (`style.css:1077–1080`) e `.invite-cta-summary:hover { opacity:0.95 }` (`:1585`) não têm override específico de opacity no hover em brand.css. | Manual §3 das instruções/§5 do manual: não reduzir opacidade de texto essencial. O background novo não remove essa propriedade; revisar estados hover, não apenas normal. |

### Como retomar, sem implementar nesta solicitação
1. Quando houver autorização para ajustes, normalizar primeiro os fundos/seletores reais, depois escala de espaçamento/raios e tipografia; manter funções, campos, permissões e trabalho do Claude.
2. Documentar exceções intencionais (editor de código, bolha de conversa) em vez de afirmar uniformidade absoluta.
3. Depois dos ajustes autorizados, conferir a cascata no navegador e repetir responsividade/zoom/acessibilidade. A checagem estática atual não certifica carregamento efetivo de fontes, contraste composto, recorte ou espaçamento renderizado.

**Arquivo alterado agora:** somente `AI_CHANGELOG.md`. **Testes executados:** nenhum, conforme pedido. **Próximo passo verificável:** revisar esta lista e, apenas sob autorização, aplicar correções estéticas por lote. Nenhuma implementação, deploy ou migração feita.


# VokalBoard — Shared AI changelog (recent entries only)

**Read `HANDOFF.md` first** — it holds the current state. This file is history, not a briefing: read only the top entry unless you need more context. See the "Document hierarchy" section in `CLAUDE.md` / `AGENTS.md`.

**Entry rules (from 2026-09-26):**
- New entries go at the top, in English, **≤ 10 lines**: what changed (files), tests run + result, next safe step. No long caveat lists — put open items in `HANDOFF.md` instead.
- Record only verifiable facts. No tokens, passwords, database URLs or personal data.
- Never delete entries; correct them with a new entry.
- **Rotation:** when this file passes ~300 lines, move the oldest entries verbatim to `docs/changelog-archive/` (one file per period). Moving is not deleting.
- Older history (2026-09-14 → 2026-09-19): `docs/changelog-archive/AI_CHANGELOG_until_2026-09-19.md` — grep it, never read it in full. Also see git history and `docs/changelog-archive/CHANGELOG_2026-09-14.md`.

## 2026-09-26 — Claude — 18 failing tests fixed; suite green
- **Product bug:** `admin_routes.py` periodic-mail create/edit used `Form(...)`, so a blank field returned a raw 422 page instead of the friendly `error=dados_invalidos` redirect → now `Form("")`, service validation unchanged.
- **Stale tests after 19/09 changes (not product bugs):** vacancy rows are now required for job listings (new shared `job_vacancy_fields()` in `test_security.py`, used by report-moderation/punishments/urgency, 10 tests); level-2 admins may open `/admin`; `/notas` needs verified email; profile submenu (Digital Pass replaced the disabled placeholder) and profile form/fieldset counts; the logged-in home redirects to the wizard (post check now anonymous); the CV PDF privacy test now checks extracted text (the raw-byte check always hit the xref table; confirmed a public phone does appear).
- **Flaky test fix:** `_fake_ip()` pool 254 → ~131k addresses (random collisions hit the 5-registrations/IP/hour limit → intermittent 429).
- New `scripts/test_in_docker.sh`: isolated test DBs + throwaway container; also runs the retention tests, which were always skipped before.
- Tests: **278 passed + 10 retention, 0 failed**, 3 full runs. Next: `HANDOFF.md` §3.

## 2026-09-26 — Claude — token optimization pass 2 (docs/config only)
- `CLAUDE.md` §0: "Large files — never read whole" map (i18n.py ~170 KB, schema.sql, style.css, big routers…) + hygiene rules (grep→range reads, `git diff --stat`, short test tracebacks, plan read per P-section).
- New `.ignore` (ripgrep search-ignore, not gitignore): seed_cities.sql, brand_contract.json, `Claude outputs/`, preview4.html, icons.svg, fonts. Verified `rg --files` skips them.
- `AGENTS.md` 91→20 lines: migration rules/history moved verbatim to `docs/MIGRATIONS.md`, short summary kept. `CHANGELOG_2026-09-14.md` → `docs/changelog-archive/` (git mv).
- No code changed, no tests run. Next: 18 failing tests (`HANDOFF.md` §3).

## 2026-09-26 — Claude — document hierarchy + changelog split (docs only)
- New main hierarchy for all AIs (Daniel's decision): `CLAUDE.md`/`AGENTS.md` → **`HANDOFF.md`** → `AI_CHANGELOG.md` → `docs/changelog-archive/` (grep only). Added as `CLAUDE.md` §0 and at the top of `AGENTS.md`.
- New `HANDOFF.md`: current state (uncommitted visual batch, 18 failing tests, open a11y issues, open decisions, backlog, constraints).
- Entries up to 2026-09-19 moved verbatim to `docs/changelog-archive/AI_CHANGELOG_until_2026-09-19.md` (this file went from 5,973 to ~280 lines). New entry rules in this file's header (≤10 lines, rotation at ~300).
- `CLAUDE.md` §1 visual-identity paragraph condensed (points to the MANIFEST files + archive); fr-vs-es mismatch flagged inline.
- No code changed, no tests run (docs only). Next: Claude investigates the 18 failing tests (`HANDOFF.md` §3).

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

## 2026-09-24 — Codex — pendências consolidadas após a sessão visual

Registro solicitado por Daniel. Esta entrada consolida o ponto de retomada e substitui os próximos passos intermediários desta sessão, sem apagar o histórico. Não é uma nova auditoria de todo o Plano Executivo.

### 1. Validação visual ainda pendente
- [ ] Testar em celular físico e em Safari/Firefox, incluindo menu, fechamento de avisos, formulários e tabelas.
- [ ] Testar zoom real de 200%; a medição de largura equivalente não certifica zoom real.
- [ ] Completar acessibilidade com leitor de tela, navegação integral por teclado, nomes dos campos dinâmicos e contraste dos estados efetivamente renderizados. Os oito pares de cores aprovados não cobrem todos os estados.
- [ ] Inspecionar os estados ainda não exercitados dos templates inventariados em `VISUAL_ROLLOUT.md`: dados extensos, erros, vazios, diferentes idiomas e conteúdo dinâmico; corrigir apenas eventuais problemas visuais encontrados.
- [ ] Medir performance de carregamento/renderização; não foi certificada nesta sessão.

### 2. Investigação funcional — responsabilidade do Claude
Não corrigida por Codex, conforme divisão expressa do Daniel. Reproduzir e distinguir defeito real de fixture/expectativa desatualizada antes de alterar código ou testes. Não atribuir as falhas ao redesign sem evidência.

| Grupo de testes | Falhas | Evidência a investigar |
|---|---:|---|
| `test_admin_report_moderation.py` | 3 | Preparação do anúncio retornou None antes de testar moderação |
| `test_financial.py` | 1 | Acesso nível 2 recebeu 200 onde teste esperava 303 |
| `test_mascot_moments.py` | 1 | Momento joinha após resgate não encontrou asset esperado |
| `test_match_history_access.py` | 1 | Quantidade de itens do submenu diverge da expectativa |
| `test_moderation_punishments_and_estornos.py` | 4 | Preparação do anúncio retornou None |
| `test_p2_wizard_cv_works.py` | 1 | Asserção de telefone privado nos bytes do PDF falhou; verificar conteúdo extraído, não concluir vazamento apenas pela sequência de bytes |
| `test_periodic_mails.py` | 1 | Campos em branco retornaram 422 onde teste esperava 303 |
| `test_profile_layout.py` | 2 | Contagens de campos/cards diferentes das expectativas |
| `test_security.py` / AdminPosts | 1 | Post esperado não encontrado no HTML retornado |
| `test_urgency_routes.py` | 3 | Criação urgente retornou 400; botão e anúncio urgente esperados ausentes |

- [ ] Reexecutar a suíte completa após investigação; último resultado foi **267 aprovados, 18 falhas, 3 avisos**. Não declarar suíte verde.
- [ ] Verificar ponta a ponta os fluxos não exercitados nesta revisão: publicar anúncio com confirmação de cachê, emitir/enviar PDF, pagamentos, campanhas e controles administrativos. Usar dados/serviços isolados; não disparar e-mails reais, cobrar ou realizar ações destrutivas em produção.
- [ ] Avaliar os avisos de dependências (Starlette/httpx, passlib/crypt, ReportLab/ast); nenhuma atualização de dependência foi feita aqui.

### 3. Ponto de retomada e salvaguardas
- Já verificado, não refazer sem motivo: contrato dos 59 templates; 11 testes de marca aprovados na execução final (1,25s); 84 medições de largura; interações e limitações detalhadas no inventário. `git diff --check` sem erros.
- Ambiente usado: contêiner `vokalboard-brand-qa`, localhost:8002, banco `vokalboard_brand_retention_test_20260924`. Confirmar disponibilidade e isolamento antes de executar testes; não presumir que continua ativo.
- A suíte limpa usuários `sectest`: executá-la antes de criar fixtures para navegador, nunca simultaneamente. A execução final dos testes ocorreu depois da última inspeção; recriar fixtures se necessário. Não registrar credenciais aqui.
- Preservar regras/campos/ações e mudanças do Claude. Zona de Alerta = urgência; Red Zone = administração; God Mode = poderes.
- Nenhum deploy/publicação/migração de produção autorizado. Codex permanece no visual; programação funcional fica com Claude.
- Arquivo alterado nesta solicitação: somente `AI_CHANGELOG.md`. Verificação: conferência do log/inventário e estado Git antes da edição; sem executar novamente testes de aplicação por ser alteração documental.
- Próximo passo verificável: Claude reproduzir os grupos falhos no banco isolado; revisão visual prosseguir pelos itens da seção 1, sem certificar antecipadamente os resultados.

### 2026-09-24 — Codex — entrega da camada visual e handoff de QA
- `VISUAL_ROLLOUT.md`: cobertura efetiva, evidências e limites registrados; não certificar estados não testados.
- Verificação final: contrato dos 59 templates aprovado; botão Report a bug com nome acessível em 320px, diálogo abre e Cancel fecha sem envio; foco visível por teclado. Viewport restaurado, aba final de QA fechada.
- Marca aplicada via CSS compartilhado, assinatura final em contornos, Manrope existente, componentes Mineral e separação de Red Zone administrativa/urgência. Regras funcionais e mudanças prévias do Claude preservadas.
- Próximo verificável para Claude: investigar as 18 falhas funcionais registradas abaixo e testar fluxos de negócio. Limites de QA visual: aparelho físico, zoom real, outros navegadores/leitor de tela e estados não exercitados descritos no inventário. Não tratar a suíte geral como verde.
- Sem publicar/deploy/migrar produção. Ambiente local de QA mantido em 8002 para reprodução; banco principal não modificado por esta tarefa.

### 2026-09-24 — Codex — acessibilidade do controle flutuante
- `base.html`: adiciona nome acessível traduzido ao botão Report a bug, cujo texto fica oculto no celular. Ação, diálogo e envio intactos.
- Revisão CSS -3 no navegador: checkboxes alinhados em linha; foco por Tab navy 2px; sem overflow em 320px. Aviso Dismiss ocultou banner; menu abriu e fechou por Escape. Paginação mostrou Page 2 / 2. Perfil em 720px (reflow equivalente de largura para 1440/200%) sem overflow; NÃO é teste de zoom real do navegador.
- Próximo: confirmar nome acessível e contrato final, registrar cobertura/limites para Claude.

### 2026-09-24 — Codex — versão final de cache e testes focados
- `base.html`/`test_brand_visual.py`: asset revision `20260924-3` inclui ajuste de checkbox e danger, evitando CSS anterior em cache.
- Testes de marca após ajustes: **11 passed**, três avisos de dependências; `git diff --check` sem erros (avisos normais LF/CRLF).
- A limpeza automática dos testes remove contas sectest; fixture recriada somente no banco isolado para inspeção final. Não executar suíte simultaneamente com navegador autenticado.
- Próximo: conferir última revisão no navegador e registrar limitações reais, sem corrigir backend.

### 2026-09-24 — Codex — alinhamento de opções e estados de perigo
- `brand.css`: labels de checkbox/radio mantêm texto ao lado do controle, em vez de empilhamento centralizado observado no celular; respeita `[hidden]`. Botões danger da Red Zone mantêm cor semântica vermelha, sem alterar ações.
- Verificado: Red Zone ativo agora navy sobre branco, regra nova carregada; alternância Singer available exibe início/fim e oculta event_date, sem overflow.
- Próximo: repetir inspeção destes estados e testes de marca; funções não visuais ficam para Claude.

### 2026-09-24 — Codex — atualização de cache visual
- `base.html` e teste de marca: versão do CSS passa a `20260924-2`, pois o navegador ainda carregava a cópia anterior após reload (regra nova ausente em document.styleSheets).
- Mudança somente de referência ao asset; próximo: verificar regra efetivamente carregada e contraste Red Zone.

### 2026-09-24 — Codex — contraste administrativo observado no navegador
- `brand.css`: corrige Red Zone ativo branco-sobre-branco no submenu; padroniza somente aparência dos controles de `.red-zone-box`.
- Evidência anterior: 36 medições de páginas principais + 48 de páginas administrativas, nas larguras 320/390/768/1440, sem overflow horizontal de página. Menu móvel aberto com aria-expanded=true; prévia avulsa atualizou nome e valor fictícios (100 + 19 = 119), sem emitir PDF.
- Próximo: recarregar CSS local e verificar contraste ativo, demais estados e contrato. Nenhuma rota, validação ou permissão alterada.

### 2026-09-24 — Codex — suíte completa e fronteira com Claude
- Por confirmação expressa do Daniel: Codex trabalha SOMENTE no visual; programação funcional fica com Claude. Nenhuma correção funcional será feita nesta etapa.
- Suíte no contêiner `vokalboard-brand-qa`, banco isolado: **267 passed, 18 failed, 3 warnings**, 90,43s. Testes novos de marca passaram (controles de 59 templates, assets, contraste e rotas).
- Falhas para investigação do Claude, SEM atribuição confirmada de causa: admin_report_moderation (3), financial (1), mascot_moments (1), match_history_access (1), moderation_punishments_and_estornos (4), p2_wizard_cv_works (1), periodic_mails (1), profile_layout (2), security/AdminPosts (1), urgency_routes (3). Saída resumida não prova regressão; testes/expectativas também podem estar desatualizados.
- Navegador: homepage anônima inspecionada em desktop e 320px, sem overflow horizontal; Manrope presente no estilo computado. Ainda faltam páginas internas/interações e demais larguras.
- Próximo verificável: fixtures locais para inspecionar páginas autenticadas e completar responsividade. Sem deploy, sem produção.

### 2026-09-24 — Codex — retomada da validação visual
- `tests/test_brand_visual.py`: reconhece aspas simples e duplas válidas no extends Jinja; nenhum template/controle alterado.
- Execução interrompida em cinco falhas: 70 testes passaram; três falhas na preparação de anúncios para denúncias, uma em acesso financeiro e uma no teste visual (aspas). Ainda não atribuídas a regressões.
- Próximo: repetir teste corrigido, finalizar suíte e verificar telas no navegador; ambiente exclusivamente local isolado, sem deploy/migrações em produção.

### Marca — acabamento contextual e regressões
- Contrato de controles executado: 59 templates preservados.
- `brand.css`: remove verde/gradiente residual do perfil, normaliza estados de vagas/convites.
- `zona_vermelha.html`: região administrativa usa símbolo branco sobre navy, NÃO o mascote de urgência;
  rótulos Red Zone/God Mode e permissões intactos. `brand/MANIFEST.md` atualizado para assinatura final.
- `tests/test_brand_visual.py`: cobertura do template-base, contraste de oito pares e 40 rotas reais.
- Banco novo `vokalboard_brand_retention_test_20260924` criado e schema carregado; nenhum banco existente alterado.
- Próximo: executar suíte e navegador com fixtures descartáveis. Não declarar aprovação antes disso.

### Marca — lotes 1–5: skin compartilhada
- `base.html`: logo final e stylesheet `brand.css`; menus e ações preservados.
- `brand.css`: navegação, controles 44px, cards/filtros, perfis/mensagens, Notas, Admin,
  urgência localizada e prévia de Rechnung; layout estreito e redução de movimento.
- Ainda não validado no navegador. Próximo: contrato de campos e execução em banco isolado.

### Marca — assets finais importados
- `app/static/img/brand/vokalboard-lockup-{navy,white}.svg`: assinatura final em contornos
  copiada sem edição do kit; todos os hashes do MANIFEST conferidos com sucesso.
- Origens preservadas; nada gerado/recolorido. Próximo: conectar assinatura e estilos.

### Marca — baseline capturada
- `tests/brand_contract.json`: contrato do HTML funcional atual antes de qualquer mudança de telas.
- Gerador executado com sucesso; próximo: conferir assets e aplicar lote 1.

### Marca — contrato de preservação antes do redesign
- `tests/brand_contract.py`: inventaria campos, ações, links, IDs e atributos de validação
  antes da mudança visual, incluindo alterações ainda não commitadas do Claude.
- Teste ainda não executado; próximo: capturar baseline e aplicar assinatura/CSS compartilhado.

## 2026-09-24 — Codex — identidade visual v1: inventário e escopo
- Lidos AGENTS, entrada Claude 21/09 (cachê opcional + confirmação), manuais/instruções
  e COMECE_AQUI/VERIFICACAO do pacote final. Nenhuma regra funcional antiga será restaurada.
- `VISUAL_ROLLOUT.md`: inventário dos 59 templates, seis lotes, limites e critérios de teste.
- Git inicial: quatro arquivos já modificados (este log, i18n, listing-form.js, listing_form.html), preservados.
- Testes ainda não executados nesta etapa; Docker disponível após início pelo usuário.
- Próximo: assets finais e camada visual compartilhada; regressões em banco isolado.
- Sem deploy, sem SQL em produção, sem ativar workers de produção/local principal.

## 2026-09-21 — Agent: Claude — Task #52: warn when publishing a listing without a fee or "negotiable"

Backlog item #52 from `PLANO_EXECUTIVO_ORGANIZADO.md` P5: "Aviso ao
publicar anúncio sem Cachê/A negociar." Picked as the next package
after delivering a SWOT/PESTLE/RACI/NFR/Gap Analysis report — chosen
by Daniel from a short list of ready backlog items because it's small
and self-contained.

**Scope, deliberately soft.** Fee has been fully optional server-side
since 19/09/2026 (`app/fees.py`/`app/vacancies.py`: "a vaga's fee isn't
validated as strictly required... it can be added/edited later") — this
task does NOT change that. It only adds a client-side confirmation
nudge, in `app/static/js/listing-form.js`, so nobody accidentally
publishes an anúncio with zero fee information without realizing it —
listings with a visible cachê get more applications.

**Behavior:** on submit, if the listing type is a job listing
(`seeking_singer`/`seeking_conductor`) and NO visible vacancy row has
either a fee amount typed or "A negociar" checked, OR the listing is a
self-ad (`singer_available`/`conductor_available`) and the top-level
fee section is in the same empty state, a `window.confirm()` shows a
translated warning ("Você não preencheu o cachê nem marcou 'A
negociar'... Publicar mesmo assim?"). Cancel keeps editing; OK
resubmits the form once (a local flag prevents asking twice on the
same submit).

**Files changed:**
- `app/i18n.py` — new key `listing_form_fee_warning_confirm` (de/en/fr/it/pt).
- `app/templates/listing_form.html` — form now carries `id="listing-form"`
  and `data-fee-warning="{{ t(...) }}"` so the JS reads the already-
  translated message instead of hardcoding English (the page is
  user-facing, not Admin, so it must follow the viewer's own language —
  unlike the Admin/God Mode `t_en()` fix from two days ago).
- `app/static/js/listing-form.js` — new submit listener, added at the
  end of the existing IIFE; reuses the same `typeSelect`/
  `feeAmountInput`/`feeNegotiableCheckbox` references already declared
  above it in the file, no new globals.

**Testing:** `node --check` on the JS file and an `ast.parse` on
`i18n.py` both pass (syntax-only — this sandbox has no live Postgres or
browser). No Python backend logic changed, so no new pytest test was
needed; grepped `tests/` first to confirm nothing already asserts on
`listing_form.html`'s exact markup around the fee section (nothing
does). Per the project's own testing note, this still needs a real
browser check (including confirming the dialog text renders correctly
in a non-English site language) before being called fully verified —
left as the next safe step for whoever has browser/device access next.

**Next safe step:** browser-verify this in at least German and
English, on both `seeking_singer` (multi-row case) and
`singer_available` (top-level fee case), then move to whichever backlog
item Daniel prioritizes next.


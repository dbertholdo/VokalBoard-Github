# VokalBoard — Shared AI changelog (recent entries only)

**Read `HANDOFF.md` first** — it holds the current state. This file is history, not a briefing: read only the top entry unless you need more context. See the "Document hierarchy" section in `CLAUDE.md` / `AGENTS.md`.

**Entry rules (from 2026-09-26):**
- New entries go at the top, in English, **≤ 10 lines**: what changed (files), tests run + result, next safe step. No long caveat lists — put open items in `HANDOFF.md` instead.
- Record only verifiable facts. No tokens, passwords, database URLs or personal data.
- Never delete entries; correct them with a new entry.
- **Rotation:** when this file passes ~300 lines, move the oldest entries verbatim to `docs/changelog-archive/` (one file per period). Moving is not deleting.
- Older history: `docs/changelog-archive/` (`AI_CHANGELOG_until_2026-09-19.md`, `AI_CHANGELOG_2026-09-21_to_2026-09-24.md`) — grep it, never read it in full. Also see git history and `docs/changelog-archive/CHANGELOG_2026-09-14.md`.

## 2026-09-26 — Claude — Messenger M6: daily e-mail limit + report queue — Messenger DONE
- `messenger.claim_daily_email()` (atomic UPDATE … RETURNING on `users.message_email_sent_at`): max 1 "new messages" e-mail per recipient per 24 h.
- Admin dashboard "Reported messages" (text snapshot, reporter, reported user); `POST /admin/message-reports/{id}/{dismiss|remove}` God Mode only + `audit_log`; remove deletes the message.
- `docs/specs/MESSENGER.md` marked IMPLEMENTED with final decisions + as-built notes. Tests +2; 327 passed + 10 retention; bandit clean on messenger code.

## 2026-09-26 — Claude — Messenger M5: desktop bubble + chat windows
- `messenger.js` dock: popup bubble on a new message → click opens a 320×420 chat window bottom-right (navy header: name, minimize, close), up to 3, restored across pages (sessionStorage) and when a window becomes wide; minimized windows only peek (`/since?peek=1`, nothing marked read). JSON send `POST /messages/c/{id}/post` (CSRF, same rules/side effects as the page). Dock not rendered on /messages pages; hidden < 1024 px. CSS cache `-4`, JS `-3`.
- Browser-verified (Chromium 1280 px): bubble → window → reply (accepts the request) → minimize → survives navigation → close; dock hidden at 390 px. Tests +2. Next: M6.

## 2026-09-26 — Claude — Messenger M4: live updates
- `messenger.poll_summary()` + `unread_messages_notification()` (synthetic, after 5 minutes unread); `render.py` uses them (header count = unread chats + requests). JSON `/messages/unread-count`, `/messages/c/{id}/since` (participants only). The immediate "new_message" bell entry is gone (Daniel: after 5 minutes).
- `app/static/js/messenger.js`: badge every 60 s, open thread every 5 s → 30 s when idle, paused in background tabs; textContent only. Red `.badge-alert` on Messages links and on ☰ (phones). CSS cache `20260926-3`.
- Tests: +2 route tests; 323 passed + 10 retention. Next: M5 desktop bubble.

## 2026-09-26 — Claude — Messenger M3: chat page
- `messages.html` rebuilt: conversation list (Inbox | Requests with highlight, All | Unread, "!" in the last 10 days) + thread (bubbles, listing context, accept/decline banner, pending note, hide, block, report per message, composer). `app/routers/messages_routes.py` rewritten thin; `/messages/sent|trash|{id}` redirect; `/messages/new?to=` opens an existing conversation. `message_detail.html` removed; brand-contract baseline refreshed for these two templates only (deliberate redesign). Style: `style.css` Messenger block (tokens only), cache `20260926-2`. 26 i18n keys (5 langs); retention warning = Daniel's wording.
- Tests: `tests/test_messenger_routes.py` (4). 321 passed + 10 retention. Next: M4.

## 2026-09-26 — Claude — Messenger M2: rules service
- New `app/messenger.py`: block > contact/Match > request (1 message until accepted; reply = accept; declined stays silent), accept/decline/hide, report (recipient only, text snapshot), list/thread/unread in single queries, never exposes read status. `/messages/send` now uses it (rate limits unchanged, 429 kept).
- Tests: `tests/test_messenger.py` (10); throttle test now seeds a contact pair (strangers are limited to 1 message anyway). Next: M3 chat page.

## 2026-09-26 — Claude — Messenger M1: schema (per-pair conversations, 60-day expiry)
- `db/migrations/2026-09-26_messenger.sql` (+ schema.sql, folded into CONSOLIDATED): `conversations` (request/active, per-side hide), `contact_pairs`, `message_reports`, `messages.conversation_id`, `users.message_email_sent_at`; backfill (both sides wrote → active + legacy contact; one-way → request). Verified idempotent + pg_dump-identical.
- Trigger files every message into its pair's conversation and drops an expired conversation's history before a new message; `visible_messages` = conversation active within 60 days; retention worker deletes conversations at 60 days (was ~30+60). `warning_days` → last 10 of 60 days.
- Tests: retention tests updated to the 60-day rule; 307 passed + 10 retention. Next: M2 (see HANDOFF §3).

## 2026-09-26 — Claude — Notas v2 implemented (N1–N5)
- **N1** `db/migrations/2026-09-26_notas_v2.sql` (+ schema.sql, folded into CONSOLIDATED): `credit_ledger.category/expires_at`, `credit_lot_usage`, backfill (existing = earned, 18 months from rollout). Verified idempotent + pg_dump-identical.
- **N2** `app/notas_wallet.py`: lots, purchased-first spend order, debts, lazy expiry, category-correct refunds; `credit_in_tx`/`debit_in_tx`. Urgency purchase + urgent-match reward now go through it (no direct ledger inserts left).
- **N3** `app/notas_expiry.py` in the retention worker: write-off + 30-day notice (notification + e-mail, 5 langs). **N4** `/notas` split/expiry/history tags; `/agb`, `/widerruf`, Stripe in `datenschutz`, footer links.
- **N5** `app/notas_purchase.py` + `/webhooks/stripe`: Checkout with server-side prices, waiver consent in PaymentIntent metadata, idempotent purchase/refund/dispute handling; gated by Stripe keys + Capitalism Mode. CSP `form-action` now allows checkout.stripe.com (redirect would have been blocked). `stripe==15.6.1`.
- Fixed: "Notas" translated as "Punkte/Noten" (de) / lower-cased (pt/en/fr/it) in 9 keys. Browser-checked /notas, buy page (320px), legal pages.
- Tests: +16 (`test_notas_v2.py`, `test_notas_purchase.py`); 307 passed + 10 retention, 0 failed; bandit clean on new code; pip-audit clean.

## 2026-09-26 — Claude — automatic account purge (6-month window)
- New `app/account_purge.py`, called by the hourly `retention_worker` (no extra Railway service): erases accounts deactivated > 6 months ago — user row + cascades, their Matches (→ evaluations, Match invoice drafts) and avatar file. Per-account savepoint; logs counts only.
- Bug found: the old manual script could never delete a user who had a Match (`job_matches` FKs are RESTRICT) and would abort the whole run there. `scripts/purge_deleted_accounts.py` is now a thin wrapper (`--dry-run`).
- Deletion notice (`delete_account_help`, 5 langs) now says Notas are kept for 6 months, then erased. `docs/specs/NOTAS_V2.md`: Kleinunternehmer (§ 19 UStG, Stripe Tax off, invoice footer, thresholds), no lawyer review.
- Tests: +3 (`tests/test_account_purge.py`). 291 passed + 10 retention, 0 failed.

## 2026-09-26 — Claude — Notas v2 + Messenger designed (docs only)
- Reviewed a Gemini proposal against the real repo (it assumed Alembic/JWT/UUID/ORM models/WebSockets — none exist) and designed both features with Daniel instead.
- New DRAFT specs: `docs/specs/NOTAS_V2.md` (purchased spent first + never expire; earned expire after 18 months per credit; 6-month reactivation then erasure; tax records kept by Stripe/accounting; Terms + withdrawal pages missing → prerequisite) and `docs/specs/MESSENGER.md` (per-pair chat, message requests, Match = consent, 60-day expiry with day-50 "!" tooltip, polling, desktop dock / mobile badge, never "seen").
- `CLAUDE.md` §3.B: `note_transactions` → real table `credit_ledger`. No code changed, no tests needed. Next: Daniel approves specs; tax status for Stripe.

## 2026-09-26 — Claude — language policy: es added, admin English-only for added languages
- Daniel's decisions: fr stays core; **es** added (with zh/ko/ro) for the **public site only**; admin stays English for added languages (core admin text untouched); moderators don't act on reports; German fee = "Honorar".
- `app/i18n_locales.py`: `page_language()` (used in `render()`: admin templates → English for non-core langs), `admin_only_keys()` scanner (0 today — admin is hardcoded English). `es` in `SUPPORTED_LANGUAGES`/`LANGUAGE_META`, `app/locales/es.json`. Tool scoped to public keys.
- Fixed hardcoded public text: Portuguese on the Match invoice pages + one English line on listing detail → 4 new keys (5 core langs). de fee label "Cachê*"→"Honorar*"; it "cachet"→"compenso" (3 strings). `permissions.py` docstring matches the moderator decision.
- `docs/I18N.md` rewritten as the per-language implementation route (phases 0–5, order es→ro→zh→ko, glossary incl. fee terms). `CLAUDE.md` §1 language line updated.
- Tests: +4 (admin scope unit + end-to-end, es registered, no admin keys in locale files). 288 passed + 10 retention, 0 failed.

## 2026-09-26 — Claude — a11y fixes, #52 bug, security scan, i18n groundwork, docs reorg
- **A11y/visual (Codex's 25/09 list, browser-verified at 320px):** labelled vacancy fields (`listing_form.html`, `listing-form.js`, 2 new i18n keys); help-text overlap after file inputs/buttons (`style.css`); invoice preview amounts no longer break (`brand.css`); mobile header 251→130px (`base.html` `.nav-dup`). Cache version `20260926-1`, style.css + listing-form.js now versioned too.
- **Bug (#52):** "publish anyway" did nothing — `requestSubmit()` inside the submit handler is ignored by browsers; now deferred. Verified 6 cases (de/en, job/self-ad, fee/no fee, OK/Cancel).
- **Security:** bandit 0 high (7 B608 reviewed = false positives); pip-audit prod clean; pytest → 9.0.3.
- **i18n groundwork:** `app/locales/{zh,ko,ro}.json` + `app/i18n_locales.py` loader (fallback to English), `scripts/i18n_tool.py` (status/todo/apply/check with placeholder validation), `docs/I18N.md`, `tests/test_i18n_locales.py` (6 tests incl. e-mail language guard).
- **Organized:** `VISUAL_ROLLOUT.md` → `docs/`; `preview4.html` + `Claude outputs/` → `docs/archive/` (moved, not deleted); `docs/README.md` index.
- Tests: 284 passed + 10 retention, 0 failed. Next: `HANDOFF.md` §3.

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


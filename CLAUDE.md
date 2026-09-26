# CLAUDE.md — Diretrizes de Desenvolvimento do VokalBoard

Este arquivo é o guia oficial de arquitetura, regras de negócio e restrições de segurança para o desenvolvimento do **VokalBoard** ("Dein Weg zu dem perfekten Auftritt!"). Todos os agentes de IA (Claude/Codex) devem ler este documento e o `HANDOFF.md` antes de iniciar qualquer alteração — see §0 (main document hierarchy).

---

## 0. Document hierarchy — MAIN HIERARCHY FOR ALL AIs (Daniel's decision, 2026-09-26)

Read in this order, and **stop as soon as you have enough context**. This saves tokens and applies to Claude, Codex and any other agent.

| # | File | Role | When to read |
|---|---|---|---|
| 1 | `CLAUDE.md` (Claude) / `AGENTS.md` (Codex) | Stable rules | Always (auto-loaded) |
| 2 | **`HANDOFF.md`** | **Current state**: repo/test status, next step, open issues, open decisions, constraints | **Always, first**; usually enough |
| 3 | `AI_CHANGELOG.md` | Recent history (≤ ~300 lines) | Only the top entry, or when HANDOFF points there |
| 4 | `docs/changelog-archive/` | Old history | **Grep only**, never read in full |
| 5 | `PLANO_EXECUTIVO_ORGANIZADO.md` (grep `^### P` for the package, read only that range), `docs/VISUAL_ROLLOUT.md`, `docs/MIGRATIONS.md`, `docs/I18N.md`, `MANIFEST.md` files (index: `docs/README.md`) | Roadmap / visual inventory / migration rules / translations / brand assets | Only when the task touches them |

**At the end of every task:** (a) **rewrite** `HANDOFF.md` so it reflects the new current state (≤ ~80 lines; remove resolved items); (b) add a **≤10-line** entry at the top of `AI_CHANGELOG.md`; (c) if the changelog passes ~300 lines, move the oldest entries verbatim to `docs/changelog-archive/`.
**Token hygiene:** read files by range/grep rather than whole; run tests with **`scripts/test_in_docker.sh`** (isolated test DBs in a throwaway container — never the dev or production DB; pass a file path to run one file, `--recreate` after schema changes). Don't re-read a file you just edited; don't dump whole `git diff`s — use `git diff --stat` then diff single files.
**Large files — NEVER read whole** (grep for the symbol, then read only that line range): `app/i18n.py` (~170 KB — grep the key), `db/schema.sql` (~135 KB — grep `CREATE TABLE <name>`), `app/static/css/style.css` (~100 KB — grep the selector), `app/routers/{listings,admin,profile,financial}_routes.py` (50–60 KB each — grep `def <name>`), `db/migrations/CONSOLIDATED_*.sql` (~55 KB), `app/templates/base.html` (~38 KB), `app/static/img/icons.svg`. Never open `db/seed_cities.sql` (city data), `tests/brand_contract.json` (generated baseline) or `docs/archive/` (old one-off deliverables, screenshots, obsolete mockups).

---

## 1. Stack Tecnológica e Padrões do Projeto
- **Backend:** Python (FastAPI), SQLAlchemy, PostgreSQL.
- **Frontend / UI:** Jinja2 templates, HTML5, CSS customizado (`style.css`), JavaScript puro (sem frameworks pesados).
- **Idioma Padrão do Sistema:** Alemão (com suporte a i18n para inglês, português, espanhol, italiano, chinês simplificado, coreano e romeno — ⚠️ the code actually ships **fr**, not es; open decision in `HANDOFF.md` §5). A moeda oficial do site é a **Nota** (1 Nota = 1 Euro/CHF dependendo da região).
- **Estilo Visual Obrigatório:** Todos os cards, blocos e painéis devem seguir o padrão de bordas arredondadas/suavizadas e sombreamento leve, com separação evidente e restrita para a **Red Zone**.
- **Visual identity v1.0 (Mineral palette):** navy `#17283F`, background `#F5F7FA`, violet action `#635BDE`/hover `#5148C5`, white surfaces; Manrope self-hosted in `app/static/fonts/manrope/`. Tokens live in `:root` of `app/static/css/style.css`; the shared brand layer is `app/static/css/brand.css` (loaded after `style.css`). New rules must use `var(--token)`, never raw hex. Logo: `app/static/img/brand/`; Tangará mascot poses: `app/static/img/mascot/` (+ `app/mascot_moments.py`). **Read each folder's `MANIFEST.md` before using the logo or mascot.** The 404 page's Zona de Alerta pose is an approved exception. Zona de Alerta (urgency) ≠ Red Zone (admin). Full history: `docs/changelog-archive/` (2026-09-19 entries).

---

## 2. Regras Críticas de Segurança e Privacidade (Zero-Storage)
1. **Dados Sensíveis e Fiscais:** Endereço residencial completo, dados bancários (IBAN, BIC) e números fiscais (Steuernummer / USt-IdNr) **NUNCA** são armazenados no banco de dados ou salvos permanentemente em disco após o uso. Eles entram de forma temporária/stateless apenas no momento de gerar documentos (como a Rechnung).
2. **Rechnungmaker (Zero-Storage Policy):** 
   - O PDF da fatura é gerado estritamente em memória RAM e armazenado em diretório privado temporário por no máximo **7 dias**, sendo apagado automaticamente por rotinas de limpeza (cron/worker).
   - O sistema de faturas possui duas vertentes:
     - *Sub-aba 1: Match-Rechnungen [N]* (Vinculada a contratos confirmados, com contadores e expiração).
     - *Sub-aba 2: Gerador Avulso* (Stateless, 100% manual, sem retenção de dados).
3. **Sessões e Autenticação:** Sessões de usuário expiram após **24 horas de inatividade**.
4. **Isolamento da Red Zone:** Ações destrutivas, ligar/desligar o *Capitalism Mode*, gerenciar tokens de urgência globais ou manipular privilégios exigem **re-autenticação por senha** (mesmo já estando logado) e são auditados na tabela `audit_log`.

---

## 3. Lógica de Negócio e Funcionalidades Principais

### A. Sistema de Vagas, Múltiplos Naipes e Matches
- **Anúncios Múltiplos:** Um anúncio pai pode conter várias vagas por naipe (Soprano, Tenor, Baixo, etc.), com cotas individuais e cachês específicos.
- **Filtro de Fach:** No diretório de artistas, selecionar um anúncio ativo aplica um filtro rígido que exibe apenas perfis compatíveis com a voz exigida.
- **Convites e Candidaturas:** O envio de convite não reserva vaga imediatamente. O artista tem prazo para aceitar. A vaga só incrementa o contador quando o status muda para **Aceito**, criando um **Match** formal.
- **Pausa Automática:** O anúncio só muda para "Pausado" quando 100% das cotas de todos os naipes forem preenchidas.

### B. Sistema de Notas e Economia Interna
- As transações de Notas devem obrigatoriamente registrar histórico na tabela `note_transactions` (evitando simples alterações em um campo numérico isolado de saldo), garantindo auditoria de origem e destino (ex: bônus de perfil 100%, indicações, compra de urgências, selo de verificação).
- **Regra de Conversão:** Notas compradas ou ganhas **NÃO** podem ser convertidas em dinheiro real (explicitado nos termos de uso).

### C. Avaliações, Badges e Gamificação (360°)
- **Avaliação pós-Match (P3.F):** fica ativa por **14 dias** a partir do `event_date` do anúncio, na sub-aba "Meus Matches" (`/profile/matches`), enquanto o Match não estiver `cancelled`. É mútua: cada lado avalia o outro em **5 categorias fixas** (1-5 estrelas cada): Pünktlichkeit, Vorbereitung, Musikalität, Professionelle Kommunikation, Angenehme Zusammenarbeit.
- **Selo por categoria, "estilo Uber":** o tier (Bronze ➔ Prata ➔ Ouro ➔ Platina) de cada categoria **NUNCA é armazenado** — é sempre calculado ao vivo como a **média corrente** de todas as avaliações recebidas naquela categoria, podendo **subir ou descer** com o tempo (diferente dos badges de marco/visualizações/indicações, que só sobem). Só aparece um tier depois de um mínimo de avaliações recebidas (evita expor selo com 1 nota só). Ver `app/match_evaluations.py` (cortes em `TIER_CUTOFFS`/`MIN_EVALUATIONS_FOR_TIER`).
- **SECRETO (regra fixa, decisão do Daniel 18/09/2026):** igual Uber — ninguém vê quem avaliou nem a nota individual de um Match específico, nem o próprio avaliado. Só a **média agregada por categoria** é visível, e só para o **próprio dono do perfil** e para o **Admin** (`/admin/users/{id}`) — nunca em `public_profile.html` nem em nenhuma outra rota pública. Nenhuma rota pode fazer `SELECT` direto na tabela `match_evaluations` fora de `app/match_evaluations.py`.
- Existe também um sistema de `ratings` (estrelas + comentário) mais antigo e **separado**, exibido publicamente com o nome de quem avaliou (visível em `/admin/users/{id}` e no perfil) — não confundir com as avaliações secretas de Match acima; são tabelas e regras de visibilidade diferentes.

---

## 4. Regras Anti-Spaghetti e Arquitetura Limpa (Obrigatório)
Para evitar o inchaço do código e manter a manutenibilidade, os agentes devem seguir estritamente estes princípios:
1. **Fat Routers Proibidos:** Os arquivos de rotas (`*_routes.py`) devem conter apenas a recepção de parâmetros, chamadas de serviços e retorno de templates/JSON. Toda lógica de negócio, regras condicionais pesadas e validações complexas devem residir na camada de serviços (`services/`).
2. **Prevenção ao Padrão N+1:** Em consultas a listagens (como diretório de artistas ou painel de matches), é **proibido** chamar funções de banco de dados dentro de loops para buscar dados relacionados (ex: buscar badges um a um para cada card). Utilize joins, `joinedload` do SQLAlchemy ou agregações em lote.
3. **Isolamento de Responsabilidades:** 
   - Estilos globais e componentes devem respeitar o escopo; evite inflar o `style.css` com regras duplicadas.
   - Funções utilitárias de formatação, i18n e segurança devem ser centralizadas em módulos dedicados, nunca duplicadas dentro de rotas.

---

## 5. Instruções para os Agentes de IA (Claude / Codex)
1. **Consulte o Estado Atual:** Leia `HANDOFF.md` antes de codificar (ver §0). Abra o `AI_CHANGELOG.md` só quando precisar de mais histórico.
2. **Modularidade:** Mantenha as rotas limpas conforme a Seção 4.
3. **Testes Automatizados:** Toda alteração de código deve ser validada executando a suíte de testes (`pytest tests -q`) para garantir que as regras de segurança e fluxos continuem íntegros.
4. **Atualize o Handoff e o Changelog:** Ao concluir qualquer tarefa, reescreva `HANDOFF.md` (estado atual) e adicione uma entrada curta (≤10 linhas) no topo de `AI_CHANGELOG.md`: o que mudou, testes rodados, próximo passo seguro. See §0.
5. **Idioma da documentação e dos comentários (decisão do Daniel, 18/09/2026): a partir de agora, EM INGLÊS.** Isso vale pra `AI_CHANGELOG.md`, `PLANO_EXECUTIVO_ORGANIZADO.md`, comentários de código (docstrings, comentários inline, mensagens de commit) e este próprio `CLAUDE.md` daqui pra frente. Não é retroativo — não é pra reescrever/traduzir o que já existe em português (mudanças anteriores a 18/09/2026 ficam como estão); "no final do projeto vamos voltar pra tradução" cobre isso depois, de uma vez só. Textos voltados ao USUÁRIO final (i18n em `app/i18n.py`, `app/email_localization.py`, conteúdo de e-mail, UI) não mudam — continuam multilíngues (`de`/`en`/`fr`/`it`/`pt`) como sempre foram; essa regra é só pra documentação/comentários/código, não pra conteúdo do produto.
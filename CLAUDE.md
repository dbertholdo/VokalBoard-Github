# CLAUDE.md — Diretrizes de Desenvolvimento do VokalBoard

Este arquivo é o guia oficial de arquitetura, regras de negócio e restrições de segurança para o desenvolvimento do **VokalBoard** ("Dein Weg zu dem perfekten Auftritt!"). Todos os agentes de IA (Claude/Codex) devem ler este documento e o `AI_CHANGELOG.md` antes de iniciar qualquer alteração.

---

## 1. Stack Tecnológica e Padrões do Projeto
- **Backend:** Python (FastAPI), SQLAlchemy, PostgreSQL.
- **Frontend / UI:** Jinja2 templates, HTML5, CSS customizado (`style.css`), JavaScript puro (sem frameworks pesados).
- **Idioma Padrão do Sistema:** Alemão (com suporte a i18n para inglês, português, espanhol, italiano, chinês simplificado, coreano e romeno). A moeda oficial do site é a **Nota** (1 Nota = 1 Euro/CHF dependendo da região).
- **Estilo Visual Obrigatório:** Todos os cards, blocos e painéis devem seguir o padrão de bordas arredondadas/suavizadas e sombreamento leve, com separação evidente e restrita para a **Red Zone**.
- **Identidade visual v1.0 (19/09/2026, paleta Mineral — substituiu o esquema verde anterior):** navy `#17283F` (marca/texto), fundo `#F5F7FA`, ação violeta `#635BDE`/hover `#5148C5`, superfícies brancas. Tipografia Manrope (Google Fonts, SIL OFL 1.1), self-hosted em `app/static/fonts/manrope/` — ver `@font-face` no topo de `style.css`. Tokens (cor, espaçamento 4/8/12/16/24/32/48px, raio de card/controle/tag) ficam em `:root` de `app/static/css/style.css`, sob os MESMOS nomes de variável de antes (`--accent`, `--ink`, `--bg`, etc.) — qualquer regra nova deve usar `var(--token)`, nunca hex direto, pra herdar automaticamente de futuros ajustes de marca. **Logo e mascote implementados em 19/09/2026** (além do sistema cor/tipografia/espaçamento/raio-base já aplicado antes): símbolo "V/asas — Assinatura" (`app/static/img/brand/`, ver `MANIFEST.md` na pasta) substituindo a referência quebrada a `bird-logo.svg` em favicon/nav/footer. Das oito poses aprovadas do Tangará (`app/static/img/mascot/`, ver `MANIFEST.md` na pasta), sete já em uso (a última leva, Part 2 backlog item 4, adicionou Acolhedor/Atento/Joinha/Piscadinha ao Zona de Alerta/Solidário/Celebração já existentes — ver `app/mascot_moments.py` pra lógica de prioridade do lembrete Atento). Só Neutro segue sem tela definida — ver o manifesto pra não espalhar o mascote sem critério. **Atenção:** a página 404 usa a pose Zona de Alerta (olhos vermelhos) como piada de "pássaro perdido" — uma exceção pontual explicitamente aprovada pelo Daniel, documentada no manifesto, ao invés de restringir essa pose só à Zona de Alerta como o manual original definia. Pendências que **não** fazem parte desta entrega: a assinatura completa símbolo+nome em Manrope (os lockups da pasta de origem são PROVISIONAL, fonte antiga, não usar), o `bird-flying.svg` (easter egg do pássaro voando — nenhuma pose aprovada é animada) e o `red-zone-bird-police.png` da Red Zone administrativa (conceito visual antigo, não faz parte do pacote Tangará — "Zona de Alerta" ≠ "Red Zone", ver `INSTRUCOES_MARCA_CODEX_CLAUDE.md` §1). Ver `AI_CHANGELOG.md` de 19/09/2026 para o detalhe completo.

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
1. **Consulte o Histórico:** Leia sempre os últimos registros do `AI_CHANGELOG.md` antes de codificar para entender o que foi alterado recentemente.
2. **Modularidade:** Mantenha as rotas limpas conforme a Seção 4.
3. **Testes Automatizados:** Toda alteração de código deve ser validada executando a suíte de testes (`pytest tests -q`) para garantir que as regras de segurança e fluxos continuem íntegros.
4. **Atualize o Changelog:** Ao concluir qualquer tarefa ou etapa de desenvolvimento, adicione obrigatoriamente uma entrada clara no topo de `AI_CHANGELOG.md` detalhando o que foi alterado, os testes rodados e o próximo passo seguro.
5. **Idioma da documentação e dos comentários (decisão do Daniel, 18/09/2026): a partir de agora, EM INGLÊS.** Isso vale pra `AI_CHANGELOG.md`, `PLANO_EXECUTIVO_ORGANIZADO.md`, comentários de código (docstrings, comentários inline, mensagens de commit) e este próprio `CLAUDE.md` daqui pra frente. Não é retroativo — não é pra reescrever/traduzir o que já existe em português (mudanças anteriores a 18/09/2026 ficam como estão); "no final do projeto vamos voltar pra tradução" cobre isso depois, de uma vez só. Textos voltados ao USUÁRIO final (i18n em `app/i18n.py`, `app/email_localization.py`, conteúdo de e-mail, UI) não mudam — continuam multilíngues (`de`/`en`/`fr`/`it`/`pt`) como sempre foram; essa regra é só pra documentação/comentários/código, não pra conteúdo do produto.
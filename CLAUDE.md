# CLAUDE.md — Diretrizes de Desenvolvimento do VokalBoard

Este arquivo é o guia oficial de arquitetura, regras de negócio e restrições de segurança para o desenvolvimento do **VokalBoard** ("Dein Weg zu dem perfekten Auftritt!"). Todos os agentes de IA (Claude/Codex) devem ler este documento e o `AI_CHANGELOG.md` antes de iniciar qualquer alteração.

---

## 1. Stack Tecnológica e Padrões do Projeto
- **Backend:** Python (FastAPI), SQLAlchemy, PostgreSQL.
- **Frontend / UI:** Jinja2 templates, HTML5, CSS customizado (`style.css`), JavaScript puro (sem frameworks pesados).
- **Idioma Padrão do Sistema:** Alemão (com suporte a i18n para inglês, português, espanhol, italiano, chinês simplificado, coreano e romeno). A moeda oficial do site é a **Nota** (1 Nota = 1 Euro/CHF dependendo da região).
- **Estilo Visual Obrigatório:** Todos os cards, blocos e painéis devem seguir o padrão de bordas arredondadas/suavizadas e sombreamento leve. Cores consistentes com a identidade visual (tons de verde para perfis/cards e separação evidente e restrita para a **Red Zone**).

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
- O sistema de avaliação pós-match fica ativo por **14 dias** na sub-aba de "Matches".
- Permite classificar por estrelas e depositar *Badges* de qualidades (Pünktlichkeit, Vorbildliche Vorbereitung, Musikalität, etc.).
- O acúmulo evolui o perfil do artista/maestro de Bronze ➔ Prata ➔ Ouro ➔ Platina.

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
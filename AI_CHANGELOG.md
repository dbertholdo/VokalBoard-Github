# VokalBoard — Registro compartilhado de IA

### Item 2 — regressões de servidor adicionadas
- `tests/test_pagination.py`: 21 anúncios/pessoas sintéticos, páginas sem sobreposição,
  preservação de filtros nos links, limites, vazio, acesso e cards dentro do contêiner.
- Fixtures removem somente dados sintéticos criados. Docker reconstruído com sucesso.
- Próximo: executar suíte, testes JS de concorrência/erros e navegação real.

### Item 2 — limites e desempate
- Rotas `listings_routes.py`/`search_people_routes.py`: limitar página à última
  existente e usar ID como desempate, evitando ordem indefinida em datas iguais.
- Próximo: regressões automatizadas e navegador. Nenhum teste novo executado ainda.

### Item 2 — templates integrados
- `board.html`, `search_people.html`: contêiner abrange contador/cards/vazio/paginação;
  componente compartilhado conectado, restauração de país/estado/cidade no histórico.
- `_search_error.html` e `i18n.py`: erro recuperável em DE/EN/FR/IT/PT.
- Removido script antigo incompleto do board. Próximo: verificar ordenação/limites e testes.

### Item 2 — componente compartilhado criado
- `app/static/js/search-pagination.js`: atualização só dos resultados, filtros/limpar,
  histórico, cancelamento de requisições antigas, timeout, erro com link de tentativa
  convencional, foco acessível e preservação de cliques modificados/nova aba.
- Ainda não conectado/testado; próximo: integrar templates e traduções.

## P1 — item 2 iniciado: paginação board e diretório
- Diagnóstico: `board-results` fecha antes dos cards/paginação; diretório sem atualização parcial.
- Plano: componente compartilhado, filtros/limpar, histórico e restauração dos filtros,
  cancelamento de respostas antigas, erros recuperáveis e funcionamento sem JavaScript.
- Nenhuma implementação desta etapa testada ainda. Registrar cada mudança antes de continuar.

## P1 — item 1 Banners: implementação e testes concluídos; validação visual pendente

- Entregue `/admin/banners`: criar/editar, ativar/desativar, excluir/restaurar,
  filtros ativos/inativos/excluídos/todos e paginação de 20 registros.
- Públicos: todos (inclui visitantes), cantores com voz opcional, regentes,
  usuários sem assinatura ativa. Banners excluídos/inativos não aparecem no site.
- Links no submenu e menu lateral só para God Mode. Mutações exigem CSRF;
  cada alteração grava auditoria na mesma transação. Restauração fica inativa.
- Avisos existentes revisados: confirmação de e-mail, assinatura e dica semanal
  continuam automáticos, separados das campanhas administráveis.
- Docker reconstruído; suíte atual: **58 passed, 4 warnings, 17,64 s**.
  `git diff --check` sem erros (avisos de conversão de fim de linha do Windows).
- Teste visual tentado: navegador integrado não conseguiu criar aba localhost,
  retornando que a aba não pertence à sessão. Inventário posterior continua vazio.
  Não declarar validação visual concluída: continua no item 7.

### Tabela de continuidade (não omitir itens)
| Nº | Item | Estado / próximo trabalho |
|---|---|---|
| 1 | Banners | Implementado e testes aprovados; conferir visual quando navegador estiver disponível. |
| 2 | Paginação | Corrigir contêiner do board, implementar diretório, histórico/erros e testar. |
| 3 | Perfil | Concluir seções em cards e separação de controles de conta. |
| 4 | Formulários | Corrigir classificação de campos condicionais e validar. |
| 5 | Títulos/navegação | Preservar títulos individuais e conferir cards faltantes. |
| 6 | Red Zone | Movimento reduzido e validação do ativo/layout/efeito. |
| 7 | Validação visual final | Desktop/celular, console, inclusive Banners; depende de navegador funcional. |

### Item 1 — banco local atualizado
- Migração `banner_voice` aplicada com ON_ERROR_STOP; coluna de voz criada.
- Próximo: reconstrução do serviço e testes.

### Item 1 — ajuste do cenário de teste
- Assinatura sintética agora informa valor e moeda exigidos pelo esquema.
- Próximo: aplicar migração de voz e executar suíte.

### Item 1 — alteração: testes de banners
- `tests/test_banners.py` cobre ciclo completo, auditoria, texto escapado,
  CSRF, bloqueio de níveis 0/1/2, URLs perigosas, voz secundária e assinatura.
- Próximo: executar testes no Docker; ainda não declarar aprovação.

### Item 1 — alteração: integração
- Rotas registradas em main; render seleciona banners por usuário fora do Admin.
- Submenu e menu lateral mostram Banners só para God Mode; base exibe texto
  escapado e links validados. Próximo: migração local e testes funcionais.

### Item 1 — alteração: tela Banners
- `admin_banners.html`: formulário completo, público/voz, filtros de estado,
  edição, ações e confirmação de exclusão. Avisos de sistema distinguidos das
  campanhas. Próximo: conectar rotas/menu/exibição e validar.

### Item 1 — alteração: rotas administrativas
- `banner_routes.py`: CRUD, ativar/desativar, exclusão lógica e restauração
  inativa; consulta paginada por estado. God Mode e CSRF em todas as mutações.
- Auditoria e alteração do banner usam a mesma transação. Validação de links,
  tamanho e voz no servidor. Próximo: tela e integração; não testado ainda.

### Item 1 — alteração: serviço de banners
- `app/banners.py`: seleção de ativos por público e voz, respeitando validade
  da assinatura independentemente do Capitalism Mode; visitantes recebem só todos.
- Links aceitam caminho interno ou HTTPS, rejeitando protocolos executáveis.
- Próximo: rotas God Mode e auditoria transacional; testes ainda pendentes.

### Item 1 — alteração: segmentação por voz
- Esquema e nova migração `2026-09-17_banner_voice.sql` incluem voz opcional.
- Revisão automática rejeitou uma tentativa de acrescentar DROP TABLE ao esquema;
  a alternativa aplicada apenas adiciona a coluna, sem remover dados.
- Próximo: serviço e rotas; migração de voz ainda não aplicada.

## P1 — checklist numerado e retomada: item 1 Banners

1. Banners: concluir CRUD, restauração, públicos incluindo voz, exibição, menu, God Mode/CSRF/auditoria e testes.
2. Paginação: corrigir contêiner do board, implementar no diretório e validar navegação.
3. Perfil: concluir cartões por seção e separar controles de conta.
4. Formulários: corrigir agrupamento dos campos condicionais e validar no navegador.
5. Títulos/navegação: preservar títulos individuais e conferir todos os cards previstos.
6. Red Zone: validar layout/ativo, efeito periódico e movimento reduzido.
7. Validação final: testes atuais, desktop/celular e console.

Correção dos registros anteriores: mudanças de código não equivalem a validação.
A suíte de 55 testes é anterior às últimas mudanças de P1. Item 1 em andamento;
itens 2 a 7 pendentes. Registrar cada alteração antes de continuar.

## 2026-09-17 — Agente: Codex — P1, migração de banners aplicada

**Validado:**
- A migração `2026-09-17_admin_banners.sql` foi aplicada com sucesso ao
  PostgreSQL Docker local.

**Próximo passo:**
- Criar rotas e tela do Admin com proteção God Mode, CSRF e auditoria.

## 2026-09-17 — Agente: Codex — P1, esquema e público de banners

**Alterado:**
- `db/schema.sql` e migração de banners: bancos novos e existentes passam a
  suportar público `todos`, `cantores`, `regentes` ou `sem assinatura`, estado
  ativo e exclusão lógica para consulta posterior de banners excluídos.

**Próximo passo:**
- Aplicar a migração local antes de criar a interface administrativa.

## 2026-09-17 — Agente: Codex — P1, fundação de banners

**Alterado:**
- `db/migrations/2026-09-17_admin_banners.sql`: criada a tabela de banners
  administráveis, com texto, link opcional e chave global de ativação.

**Próximo passo:**
- Atualizar o esquema limpo, aplicar a migração local e criar as rotas/telas
  do Admin; registrar cada alteração antes de continuar.

## 2026-09-17 — Agente: Codex — P1, paginação parcial do board

**Alterado:**
- `app/templates/board.html`: resultados e paginação receberam contêiner com
  atualização parcial. Com JavaScript, filtros e links de página buscam a
  página e substituem só a área de resultados; sem JavaScript, o formulário e
  os links continuam funcionando por recarga normal.

**Próximo passo:**
- Validar no navegador o filtro e a paginação parcial; revisar console e
  registrar o resultado antes de iniciar qualquer nova alteração.

## 2026-09-17 — Agente: Codex — P1, links de cards em nova aba

**Alterado:**
- `board.html`, `search_people.html`, `home.html` e `my_favorites.html`:
  cards de anúncios e perfis agora abrem em nova aba, protegidos por
  `rel="noopener noreferrer"`.

**Próximo passo:**
- Validar em navegador que os links abrem corretamente e seguir para paginação
  ou gestão de banners, registrando cada modificação antes de continuar.

## 2026-09-17 — Agente: Codex — P1, traduções do formulário

**Alterado:**
- `app/i18n.py` e `app/templates/listing_form.html`: os títulos de cartões do
  formulário agora usam chaves traduzidas para DE/EN/FR/IT/PT em vez de texto
  fixo em inglês.

**Próximo passo:**
- Reconstruir a aplicação e validar no navegador os estados condicionais de
  vaga (venue/fee/repertoire) e a apresentação das duas seções.

## 2026-09-17 — Agente: Codex — P1, perfil em cards

**Alterado:**
- `app/templates/profile.html`: badges continuam acima do editor; o formulário
  de perfil foi colocado em cartão próprio, com contexto de edição separado da
  área pública e de conquistas.
- `app/static/css/style.css`: grupos do editor, preferências e campos comuns
  passaram a ter cartões/áreas visuais distintas, mantendo os mesmos campos e
  regras de envio.

**Próximo passo:**
- Testar a tela em desktop/celular; depois traduzir os subtítulos do formulário
  de anúncios, registrando cada alteração antes de avançar.

## 2026-09-17 — Agente: Codex — P1, Red Zone integrada

**Alterado:**
- `app/templates/zona_vermelha.html`: incluído cabeçalho próprio da Red Zone
  com o pássaro policial e indicação explícita de God Mode.
- `app/static/css/style.css`: aplicado tema vermelho, layout responsivo e uma
  animação discreta de patrulha a cada 10 minutos; não há giroflex por decisão
  do usuário.

**Próximo passo:**
- Reorganizar o perfil em cartões e, imediatamente depois dessa alteração,
  registrar antes de continuar.

## 2026-09-17 — Agente: Codex — P1, ativo da Red Zone copiado

**Alterado:**
- `app/static/img/red-zone-bird-police.png`: adicionado o pássaro policial
  transparente aprovado pelo usuário. Não substitui nenhum ativo existente.

**Próximo passo:**
- Integrar o ativo somente na Red Zone e registrar a alteração antes de seguir.

## 2026-09-17 — Agente: Codex — P1, ativo visual pronto para inclusão

**Criado, ainda não inserido no projeto:**
- Versão PNG do pássaro policial fornecido pelo usuário, com fundo transparente
  e sem giroflex, gerada como ativo da Red Zone. Origem temporária do gerador:
  `C:\\Users\\danie\\.codex\\generated_images\\01a0abc4-c79e-72c0-b114-9bb3f5f3bad2\\exec-20099536-cec1-4f5d-9429-75ebadca7d6f.png`.

**Próximo passo:**
- Copiar o ativo para `app/static/img/` com nome novo, integrá-lo à Red Zone e
  registrar imediatamente essa alteração antes de continuar.

## 2026-09-17 — Agente: Codex — P1, alteração 2 registrada antes de continuar

**Alterado:**
- `app/templates/listing_form.html`: formulário de anúncio foi separado em
  cartões de “Required information” e “Optional details”, usando a base visual
  criada na alteração anterior. Os campos condicionais de vaga permanecem no
  cartão opcional e o JavaScript existente continua responsável por sua regra.

**Ponto de continuidade:**
- Validar a estrutura e os estados condicionais do formulário no navegador.
  As traduções dos dois subtítulos ainda devem ser incluídas antes de fechar
  P1, assim como as demais exigências de perfil, banners e Red Zone.

## 2026-09-17 — Agente: Codex — P1, alteração 1 registrada antes de continuar

**Alterado:**
- `app/templates/base.html` e `app/i18n.py`: título-base agora é “Vokal
  Board — [tagline traduzida]”, mantendo cada página livre para acrescentar
  seu próprio complemento quando a migração dos títulos individuais ocorrer.
- `app/routers/profile_routes.py`: WhatsApp removido das opções de rede social
  do perfil; links já gravados não são apagados nesta alteração.
- `app/static/css/style.css`: criada a base visual reutilizável de cartão para
  grupos de formulário de anúncio; o HTML será agrupado em alteração própria.

**Ponto de continuidade:**
- Ainda falta aplicar as classes aos grupos obrigatório/opcional do formulário,
  validar no navegador e realizar os demais itens de P1. Esta entrada foi
  escrita imediatamente após a alteração, conforme regra do usuário.

## 2026-09-17 — Agente: Codex — Fase 1 em validação final

**Concluído nesta sessão:**
- Contato direto de e-mail e telefone em anúncios agora só é visível ao dono
  do anúncio ou às duas partes de um Match confirmado/concluído daquele
  anúncio. O mensageiro interno continua disponível para usuários verificados.
- O filtro de oportunidades e os avisos de novas vagas consideram as múltiplas
  vozes do perfil, mantendo o campo antigo como compatibilidade temporária.
- A moeda de produto é sempre exibida como `Notas`.
- O indicador de mensagens não lidas passou a usar vermelho e as telas de
  conversa receberam apresentação em formato de mensageiro.
- Relatórios e concessão/remoção de privilégios foram restringidos ao God
  Mode. Um admin comum não pode mais promover outro usuário.
- Idioma preferido de e-mails transacionais foi adicionado à conta; cadastro,
  confirmação, recuperação de senha e nova mensagem usam esse idioma quando
  há tradução, com fallback documentado em inglês.
- Criadas a migração `2026-09-17_phase1_email_language.sql` e a regra raiz
  `AGENTS.md`, tornando a leitura e atualização deste changelog obrigatória
  antes/depois de trabalho material por Codex ou Claude.

**Validado:**
- Migração aplicada no PostgreSQL Docker local.
- Suíte completa: `55 passed` em 16,67 s.
- Um defeito de limpeza de dados de teste para Matches foi encontrado e
  corrigido; a suíte agora remove somente os Matches de contas descartáveis
  antes de apagá-las.

**Ainda pendente desta mesma Fase 1 (não declarar concluída antes disso):**
- Fazer teste real autenticado em viewport móvel do botão de menu lateral e
  confirmar abertura/fechamento; o teste anônimo não contém menu por projeto.
- Acionar e confirmar o botão X de um aviso efetivamente visível na página
  inicial.
- Configurar e testar entrega real de e-mail. O ambiente local permanece em
  `EMAIL_BACKEND=console`; para entrega em caixas reais será necessário um
  remetente/domínio verificado e uma chave do provedor, que não devem ser
  gravados no repositório.

**Próximo passo seguro:**
- Concluir os dois testes visuais autenticados e, se as credenciais forem
  disponibilizadas pelo responsável, validar um envio real sem expor segredo.

## 2026-09-17 — Agente: Codex

**Objetivo:** iniciar P4 com a fundação segura do Rechnungmaker, depois das
decisões do usuário sobre numeração, retenção, recibos, franquia e país.

**Alterado:**
- `db/migrations/2026-09-17_rechnungmaker_foundation.sql`: criada a estrutura
  de sequência anual, franquia mensal, créditos comprados e metadados legados
  de PDFs temporários de Match.
- `db/migrations/2026-09-17_rechnung_match_drafts.sql`: criado o rascunho de
  Match criptografado, com expiração de sete dias e sem retenção de PDF.
- `db/schema.sql`: atualizado para bancos novos terem a mesma estrutura.

**Decidido:**
- Número sugerido: `YYYY-0001`, incrementado por usuário e reiniciado no ano;
  a pessoa pode editar o número.
- Cinco Rechnungen grátis por usuário a cada mês; não cumulativas.
- Créditos comprados por 0,50 Nota ficam em registro separado e acumulam.
- Rechnung por Match é opcional; qualquer parte do Match pode iniciar o pedido.
  O contratado é o emissor e quem publicou o anúncio é o contratante, sem
  depender de a pessoa ser cantora, regente ou outra categoria.
- O rascunho de Match pode ficar criptografado por sete dias. Ao confirmar, o
  PDF é enviado por e-mail para as duas partes e não fica armazenado.
- A ação específica do Match só pode ser iniciada até sete dias após a data do
  evento. Depois que alguém inicia, a outra parte recebe sete dias completos
  para revisar e confirmar; se não fizer, a opção desaparece para ambas.
- Recibos de reembolso não serão armazenados pelo VokalBoard; o destino é o
  contratante diretamente.
- O país é escolhido pela pessoa e pré-carrega padrões que ela pode alterar.

**Segurança:**
- As novas tabelas não possuem colunas de IBAN, BIC, número fiscal, endereço
  residencial ou conteúdo da Rechnung em texto aberto. Elas guardam somente
  contadores, sequência, estado do fluxo, conteúdo cifrado e expiração. A
  chave de cifra não pertence ao banco nem ao repositório.
- A migração foi aplicada e validada no banco Docker local.

**Gancho para a próxima parte:**
- Criar o Gerador Avulso stateless com preview e PDF em memória; depois ligar
  o mesmo gerador aos `job_matches` com solicitação opcional, revisão da outra
  parte, envio por e-mail e exclusão do rascunho após sucesso.

## 2026-09-17 — Agente: Codex

**Alterado:**
- `docker-compose.yml`: removida a montagem de desenvolvimento que o Docker
  Desktop expunha vazia nesta pasta sincronizada; a aplicação passa a iniciar
  a partir da imagem construída.
- `app/main.py`: sessão autenticada agora expira após 24 h de inatividade.
- `app/i18n.py`: adicionados Chinês simplificado, Coreano e Romeno, com
  fallback temporário em inglês até a tradução completa de cada tela.

**Validado:**
- Docker Compose iniciado com sucesso e suíte completa: 44 testes aprovados.

## 2026-09-17 — Agente: Codex

**Alterado:**
- `app/invoice_service.py`: centralizadas as regras atômicas de numeração
  `YYYY-0001`, franquia mensal de cinco e créditos comprados acumuláveis.

**Regra preservada:**
- A contagem só deve ser consumida depois que a entrega do PDF tiver êxito;
  isso evita cobrar uma Rechnung cuja entrega por e-mail falhou.

## 2026-09-17 — Agente: Codex

**Segurança de dependências:**
- A auditoria identificou vulnerabilidades conhecidas em `python-multipart`
  e `starlette`, transitivas da pilha anterior.
- `requirements.txt` foi atualizado para `python-multipart==0.0.31` e
  `fastapi==0.141.1`, que traz uma linha atual de Starlette. A alteração será
  aceita somente se a suíte completa e a auditoria voltarem a passar.
- `app/render.py`: adaptado o ponto central de renderização à assinatura do
  Starlette 1.x; nenhuma rota precisou de alteração individual.


## 2026-09-17 — Agente: Codex

**Objetivo:** iniciar P2/P3 pela fundação compatível de perfil multi-voz,
vagas múltiplas, convites e Matches.

**Alterado:**
- `db/migrations/2026-09-17_profiles_and_matches.sql`: adicionada migração
  compatível para perfis com múltiplas vozes, vagas por naipe, convites e
  Matches; dados de voz existentes são copiados sem apagar os campos antigos.
- `db/schema.sql`: atualizado o esquema para bancos criados do zero terem a
  mesma estrutura.

**Gancho para a próxima parte:**
- P2 deve gravar/ler `singer_profile_voice_types` no perfil e no diretório,
  mantendo `singer_profiles.voice_type_id` como voz principal durante a
  transição.
- P3 deve usar `listing_vacancies`, `job_invitations` e `job_matches` para
  criar a interface de vagas, convite, expiração e aceite atômico.

**Atenção:**
- A migração precisa ser aplicada explicitamente em bancos existentes; o
  Docker não aplica automaticamente novos arquivos em um volume já criado.


## 2026-09-17 — Agente: Codex

**Objetivo:** iniciar P1 com uma base visual reutilizável para o detalhe de
anúncio, deixando extensão segura para convites e Matches futuros.

**Alterado:**
- `app/templates/listing_detail.html`: adicionadas classes semânticas ao título,
  metadados, descrição e cartão de contato.
- `app/static/css/style.css`: criado o estilo específico do detalhe de anúncio,
  coerente com os cards arredondados e suavemente elevados do perfil.

**Verificado:**
- Sintaxe Python aprovada e `git diff --check` sem problemas de espaço.

**Gancho para a próxima parte:**
- Usar as classes `listing-detail-*` para incluir, em P3, as ações de convite,
  candidatura e Match sem alterar o estilo de cards do restante do site.
- P1 ainda inclui base visual de perfil, Red Zone, banners e testes de navegador;
  não considerar P1 completa nesta etapa.


## 2026-09-17 — Agente: Codex

**Objetivo:** executar o primeiro lote do P0: correções de estabilidade,
privacidade e interface confirmadas na revisão.

**Alterado:**
- `app/templates/base.html`: o menu lateral móvel passa a registrar seus
  eventos após o HTML do cabeçalho e da barra lateral existirem.
- `app/templates/home.html`: removido o `onclick` bloqueado por CSP do botão X;
  o fechamento usa somente o listener com nonce.
- `app/routers/profile_routes.py`: perfil de conta desativada é filtrado e
  retorna 404.
- `app/routers/notas_routes.py`: o débito de Notas e o destaque de perfil agora
  ocorrem em uma única transação com bloqueio da conta, evitando gasto duplo
  por pedidos simultâneos.
- `tests/test_security.py`: adicionados testes para conta desativada e ausência
  de manipulador de clique inline no aviso.
- `PLANO_EXECUTIVO_ORGANIZADO.md`: definido que o On/Off de campanhas de
  e-mail é global.

**Verificado:**
- Imagem Docker reconstruída com o código atual.
- `pytest tests -q`: 38 testes aprovados.
- Página inicial abriu no navegador isolado pela aplicação reconstruída.

**Estado / próximo passo:**
- O primeiro lote do P0 está concluído. Permanecem no P0 a investigação do
  filtro de anúncios por voz e a configuração de envio real de e-mails.
- O código de e-mail está em modo `console` no ambiente local; envio real exige
  configurar o provedor e credenciais, que não foram alterados.


## 2026-09-17 — Agente: Codex

**Objetivo:** incorporar a extensão do Menu de E-mails e das campanhas de
renovação ao plano de execução.

**Alterado:**
- `PLANO_EXECUTIVO_ORGANIZADO.md`: incluídas campanha para pessoas sem
  assinatura ativa, links personalizados, editor de e-mails e assinatura
  padrão salva.
- `AI_CHANGELOG.md`: registrada esta etapa.

**Solicitado pelo usuário:**
- Botão “Notificação por Email: On/Off”.
- Disparo de promoção para todas as pessoas sem assinatura ativa, com campos
  para desconto e validade do link personalizado.
- Após compra, o link personalizado é desativado e redireciona à página
  inicial, para evitar compartilhamento.
- Editor de e-mails como o de posts e uma assinatura padrão salva.

**Atenção / próximo passo:**
- Antes de implementar, confirmar o alcance do botão On/Off: global, por
  campanha ou por destinatário. Não assumir essa regra.


## 2026-09-17 — Agente: Codex

**Objetivo:** fechar a regra de renovação de assinatura e registrar a proposta
de administração dessas regras.

**Alterado:**
- `PLANO_EXECUTIVO_ORGANIZADO.md`: definida a linha do tempo de descontos e
  notificações de renovação; incluída a sugestão de seção “Assinaturas” no
  Admin como item a desenhar.
- `AI_CHANGELOG.md`: registrada esta decisão.

**Decidido:**
- Com 120 dias restantes, a renovação tem 20% de desconto.
- A partir de 100 dias, enviar e-mail e notificação push no site no máximo uma
  vez por semana, para evitar spam.
- Ao chegar a 60 dias restantes, encerra-se o desconto de 20% e passa a valer
  10% até a expiração.
- Depois da expiração, aplicar preço normal. Após 30 dias sem renovar, enviar
  link exclusivo com 20% de desconto.

**Estado / próximo passo:**
- A regra comercial de renovação está fechada. Ao implementar P5, desenhar a
  área Admin > Assinaturas com proteção para alterações em assinaturas ativas.
- P0 continua sendo o próximo pacote seguro de implementação.


## 2026-09-17 — Agente: Codex

**Objetivo:** registrar as decisões do usuário sobre convites, Rechnung,
urgência, renovação e partitura, para remover ambiguidades do plano.

**Alterado:**
- `PLANO_EXECUTIVO_ORGANIZADO.md`: substituídas as cinco divergências pela
  decisão registrada do usuário e atualizados os pacotes P3, P4 e P5.
- `AI_CHANGELOG.md`: registrada esta continuação.

**Decidido:**
- Convite: 48 h, com e-mail; expira antes se faltarem 6 h para o evento.
- Rechnung grátis: 5 por mês.
- Urgência: 1 token semanal; se o saldo for 0, compra por Notas equivalente a
  2 Euros.
- Partitura: apenas link externo, sem upload ou armazenamento.
- Renovação: 20% com a regra “antes de 60 dias”; aviso semanal desde 100 dias
  e link exclusivo de renovação com 20% quando a pessoa não renovar.

**Atenção / próximo passo:**
- Falta somente precisar o sentido de “antes de 60 dias”: mais de 60 dias de
  antecedência ou até 60 dias de antecedência. Não implementar a condição de
  desconto até essa fronteira estar confirmada.
- P0 continua sendo o próximo pacote seguro de implementação.


## 2026-09-17 — Agente: Codex

**Objetivo:** organizar as anotações do Plano Executivo para uma execução
coordenada entre Codex e Claude, sem reinterpretar requisitos.

**Alterado:**
- `PLANO_EXECUTIVO_ORGANIZADO.md`: criado o mapa de execução, agrupado por
  pacote e com referência aos parágrafos do documento-fonte.
- `AI_CHANGELOG.md`: registrada esta etapa de planejamento.

**Verificado:**
- O documento `Plano Executivo - 16 de Setembro.docx` foi lido duas vezes:
  uma pela estrutura do Word e outra pelo XML interno. Ambas têm 277
  parágrafos; as diferenças encontradas foram somente de tabulação/quebra de
  linha, não de conteúdo.
- Repetições literais e sobreposições foram preservadas como referências, não
  apagadas. Foram isoladas cinco divergências que precisam de decisão humana:
  prazo do convite, franquia mensal de Rechnung, preço/regra da urgência,
  janela de desconto de renovação e o formato de partitura sem armazenamento.

**Estado / próximo passo:**
- Antes de implementar P3, P4 ou P5, pedir ao usuário as cinco decisões
  registradas em `PLANO_EXECUTIVO_ORGANIZADO.md`.
- O próximo pacote seguro é P0, depois das decisões que ele exigir. Todo agente
  deve consultar o novo plano e este changelog antes de alterar o projeto.


## 2026-09-17 — Agente: Codex

**Objetivo:** mapear o estado deixado pela última etapa com Claude, revisar o
projeto inteiro em busca de acoplamento excessivo e riscos de manutenção, e
validar a aplicação sem alterar o comportamento funcional.

**Alterado:**
- `AI_CHANGELOG.md`: incluído este registro de continuidade e de resultados.
- Nenhum arquivo de aplicação, banco, interface ou dependência foi modificado.

**Verificado:**
- A árvore de trabalho contém somente este arquivo novo, ainda não versionado.
- Revisados os módulos Python, rotas, templates, JavaScript, CSS, esquema SQL,
  configuração Docker, documentação e automações do GitHub.
- Sintaxe: 34 módulos Python analisados, sem erro de sintaxe.
- Testes automatizados: `36 passed` (14,58 s), executados no contêiner Python
  3.12 com PostgreSQL configurado.
- Análise estática de segurança: Bandit não encontrou problema de gravidade
  média ou alta; há 3 avisos de baixa gravidade para avaliar em mudança futura.
- Auditoria de dependências: 26 avisos conhecidos concentrados em
  `python-multipart==0.0.20` e `starlette==0.38.6`. Atualizar Starlette exige
  atualizar FastAPI de forma compatível, não apenas trocar um número isolado.
- A imagem Docker é construída com sucesso. Neste computador, porém, o Docker
  Desktop não monta corretamente a pasta sincronizada `G:`: dentro do
  contêiner, `app/` fica vazio e o `schema.sql` aparece como diretório. Assim,
  `docker compose up` reinicia o serviço web apesar de a imagem conter o
  aplicativo. O caminho mais confiável para desenvolvimento local é uma pasta
  não sincronizada (por exemplo, `C:\dev\VokalBoard`) usando o Git para sincronizar.

**Problemas confirmados / ordem sugerida:**
1. Corrigir o menu lateral móvel em `app/templates/base.html`: o script procura
   os elementos antes de eles existirem no HTML e encerra sem registrar o clique.
2. Corrigir o botão X do aviso da página inicial em `app/templates/home.html`:
   ele mantém um `onclick` que a política de segurança bloqueia; há um segundo
   manipulador por JavaScript, mas o atributo inválido deve ser removido e o
   fluxo coberto por teste de navegador.
3. Corrigir a consulta de perfil público em `app/routers/profile_routes.py`:
   ela não filtra `deleted_at IS NULL`, diferentemente dos demais acessos a
   usuários. Uma conta desativada pode continuar acessível pela URL numérica.
4. Tornar o resgate de Notas em `app/routers/notas_routes.py` atômico. Hoje o
   saldo é lido e só depois debitado; dois pedidos simultâneos podem gastar mais
   créditos que o disponível.
5. Atualizar as dependências vulneráveis em uma mudança própria, com testes de
   regressão e versões compatíveis de FastAPI/Starlette.

**Qualidade / prevenção de "spaghetti":**
- O projeto ainda é compreensível e os domínios estão nomeados de modo claro,
  mas as rotas estão acumulando regras de negócio e SQL. Os maiores pontos de
  pressão são `listings_routes.py`, `profile_routes.py`, `admin_routes.py` e
  `financial_routes.py`.
- Há acoplamento entre rotas: autenticação reutiliza funções de perfil,
  administração reutiliza envio de e-mail da rota de autenticação e badges
  depende de perfil. Antes de novas funcionalidades, mover essas regras para
  serviços neutros por domínio, mantendo as rotas finas.
- A busca de pessoas chama `top_badges()` para cada cartão; cada chamada faz
  diversas consultas. Para uma página cheia, isso cria o padrão N+1. Substituir
  por uma consulta/agregação em lote antes de aumentar a escala.
- `render()` e os destaques semanais fazem trabalho de banco em toda página;
  destaques também atualizam contadores em uma requisição GET. Centralizar e
  tornar essa seleção transacional ou cacheada reduzirá carga e efeitos
  colaterais inesperados.
- `style.css` (2.338 linhas), `i18n.py` (1.036 linhas) e algumas rotas grandes
  devem ser divididos por área funcional gradualmente, sempre com teste antes
  e depois; não fazer uma reescrita geral.
- A suíte atual cobre bem permissões, CSRF e painel financeiro, mas não cobre
  o JavaScript nem a experiência móvel — exatamente onde os dois bugs visuais
  passaram. Incluir testes reais de navegador e testes de tradução/rotas novas.
- Os testes dependem de um banco já criado e de uma variável `DATABASE_URL`;
  sem ela tentam nomes antigos de banco local. Documentar ou automatizar esse
  preparo para tornar a execução repetível.
- `backup.yml` e `main.yml` aparentam duplicar a automação de backup; decidir
  qual é a fonte oficial para não manter dois fluxos semelhantes.
- Migrações SQL não são aplicadas automaticamente quando já existe um volume
  PostgreSQL. Adotar um executor de migrações/versionamento antes de evoluir o
  banco em produção.

**Estado / próximo passo:**
- Revisão e validação concluídas sem alteração funcional. O próximo trabalho
  recomendado é um pequeno pacote de correções (itens 1 a 4), com teste de
  navegador para celular e testes de regressão para conta desativada e Notas.
- Codex e Claude devem ler esta entrada antes de continuar e acrescentar uma
  entrada nova ao encerrar qualquer mudança.

Este arquivo é o ponto de passagem entre Codex e Claude. Antes de alterar o
projeto, leia a entrada mais recente. Depois de concluir, interromper ou
entregar uma tarefa, acrescente uma nova entrada no topo, usando o modelo
abaixo.

## Regras de uso

- Registre somente fatos verificáveis: arquivos, comportamento, testes e
  pendências. Não inclua tokens, senhas, URLs de banco ou dados pessoais.
- Não apague entradas antigas; corrija-as em uma entrada nova.
- Se a tarefa não foi concluída, deixe explícito o ponto de parada e o próximo
  passo seguro.
- Antes de editar algo que outro agente possa estar mudando, confira o estado
  atual do Git e registre qualquer conflito ou dúvida.
- Este arquivo complementa, mas não substitui, o histórico do Git e
  `CHANGELOG_2026-09-14.md`.

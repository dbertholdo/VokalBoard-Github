# Plano executivo organizado do VokalBoard

## Fonte e uso deste plano

Fonte única das ideias: `G:\My Drive\Coursera\VokalBoard\DOCS\Plano Executivo - 16 de Setembro.docx`.

O documento-fonte foi lido duas vezes: pela estrutura do Word e diretamente
pelo XML interno. Foram encontrados 277 parágrafos nas duas leituras. As
diferenças foram somente quebras de linha e tabulações, não conteúdo.

Este arquivo organiza, mas não substitui nem reescreve a fonte. Cada pacote
abaixo aponta os parágrafos de origem. Antes de implementar qualquer pacote,
Codex ou Claude deve reler os trechos correspondentes no Word. Quando dois
trechos parecerem repetir uma ideia, os dois continuam registrados aqui para
que nenhuma condição seja perdida.

## Regras de trabalho

- **[18/09/2026] Sem migração em produção até o usuário liberar de novo.**
  Continuar criando/atualizando `db/schema.sql` e `db/migrations/*.sql`
  normalmente a cada mudança de schema, mas não instruir a rodar nem assumir
  que foi rodado nada no Postgres do Railway. Ver detalhe e motivo em
  `AGENTS.md`. Quando o usuário pedir, o trabalho vira: consolidar tudo numa
  migração única e aplicar via `psql` (não pela caixa "Query" do Railway).
  **[19/09/2026] Já preparado, ainda NÃO aplicado:**
  `db/migrations/CONSOLIDATED_2026-09-19_pending_since_0915.sql` — os 26
  arquivos concatenados, testados de ponta a ponta (achou e corrigiu um bug
  real de ordem entre `p5_etapa2_urgencia.sql` e `retention.sql` — ver
  `AGENTS.md`). Falta só o Daniel decidir quando aplicar.
- Não iniciar código para um pacote com decisão pendente.
- Trabalhar em apenas um pacote por vez. Correções de produção podem ser um
  pacote próprio e curto.
- Antes de começar: ler este arquivo, `AI_CHANGELOG.md`, os trechos-fonte e o
  estado atual do Git.
- Antes de encerrar: testar o pacote, atualizar `AI_CHANGELOG.md` com arquivos,
  testes, decisões e próximo passo seguro.
- Não misturar refatoração ampla com funcionalidade. Se houver repetição de
  código, extrair somente o necessário para o pacote atual.
- Todo fluxo novo que mova dinheiro, Notas, acesso, convite, Match ou dados
  privados deve ter teste de regra de negócio e teste de permissão.
- Toda mudança visual ou JavaScript precisa de teste em navegador, inclusive em
  largura de celular — mas o teste em **largura de celular** só precisa rodar
  quando a funcionalidade for especificamente sobre mobile (ex: menu lateral),
  ou consolidado no fechamento do pacote inteiro; não repetir a cada tarefa
  isolada. Ver detalhe em `AGENTS.md` → "Estratégia de teste mobile".

## Itens repetidos, complementares e divergentes

### Duplicado literal

- **E-mail de confirmação e recuperação atrasado/não enviado:** parágrafos 34
  e 41 repetem exatamente a mesma anotação. O parágrafo 19 amplia o problema
  para confirmações, senha e relatórios diários, semanais e mensais.

### Complementares - devem virar um único fluxo

- **Urgência em anúncios:** 24, 25, 114, 261 e 262. Incluem quadro de vagas
  urgentes, filtro por voz, envio após 6 h, token semanal, não acumular tokens,
  compra de urgência e recompensa por conclusão.
- **Convites, candidaturas e Matches:** 11, 23, 118-185, 189, 195, 235, 240 e
  242. O texto descreve tanto a interface quanto o modelo de vagas, estados,
  permissões, prazos, avaliação e Rechnung vinculada.
- **Rechnungmaker:** 32, 43-109, 111-113, 147, 152-153, 170-184, 254 e 263.
  Há um gerador avulso sem retenção, Rechnungen ligadas a Matches com PDF por
  7 dias e Rechnungen da plataforma/financeiro que precisam ficar disponíveis
  permanentemente. Tratar como tipos distintos de documento, sem misturar
  dados e prazo de retenção.
- **Perfil, áudio, CV e cartão de visita:** 13, 27, 29-31, 36, 113, 193-194 e
  225-229. Incluem perfil editável em cards, línguas, telefone, áudio/links,
  CV PDF, QR Code e cartão de visita.
- **Avaliação e badges pós-Match:** 5, 111, 189, 209-217, 237, 248, 252, 258 e
  264. A regra-base é avaliação somente após Match concluído, por tempo
  limitado, com estrelas, badges e progressão.
- **Vouchers e regras comerciais:** 21, 236 e 266. A criação e a análise de
  uso pertencem ao God Mode e Data Analytics.
- **Administração, analytics e suporte:** 9, 15, 17, 38, 191-192, 230-232,
  238, 241, 243-247, 251, 265 e 268-270. Toda entidade nova deve aparecer em
  controle administrativo e analytics conforme o documento.

### Decisões confirmadas em 17 de setembro de 2026

1. **Convite:** vale por 48 h e deve notificar a pessoa por e-mail. Quando o
   evento ocorrer antes desse prazo, o convite some ao faltarem 6 h para o
   evento. Na implementação, a expiração será o primeiro instante entre “48 h
   após o convite” e “6 h antes do evento”.
2. **Rechnung grátis:** são 5 por mês.
3. **Urgência:** cada pessoa recebe 1 token de urgência por semana. Se estiver
   com 0 token, pode comprar urgência com Notas; o custo é equivalente a 2
   Euros.
4. **Renovação:** com 120 dias restantes, ativar desconto de 20%. A partir de
   100 dias, notificar por e-mail e notificação push no site apenas 1 vez por
   semana, para evitar spam, mostrando: “Você X dias para renovar com 20% de
   desconto. Renove agora. Sua assinatura acaba em Y dias.” Ao chegar a 60 dias,
   termina a promoção de 20% e passa a valer 10% de desconto até a data de
   expiração. Após a data, aplica-se o preço normal. Se não renovar em 30 dias
   após a expiração, enviar um link exclusivo com 20% de desconto.
5. **Partitura:** campo para colar link externo, sem upload e sem armazenamento,
   para evitar problemas com copyright.

**Sugestão registrada, ainda não uma decisão de desenho:** criar no Admin a
seção “Assinaturas”, com sub-menu para editar essas regras. Antes de criar,
definir quais limites podem ser editados por administradores e quais devem ser
fixos para evitar alterações acidentais em assinaturas ativas.

## Backlog por pacote executável

### P0 - Estabilidade, acesso e correções já observadas

**Fonte:** 2, 6-9, 14-15, 17-20, 22, 34, 37-38, 41 e 249.

- “menu lateral não funciona mobile”.
- E-mail de mensagem, aviso visual de mensagem recebida e visual de mensageiro.
- Apenas God Mode pode colocar ou retirar privilégios; denúncias precisam
  permitir ações administrativas sobre o Post.
- Verificar o filtro de anúncios por voz, visibilidade de contatos e acesso de
  não cadastrados aos posts.
- Envio imediato de confirmação/recuperação: já corrigido (Fase 1,
  18/09/2026 — e-mails transacionais na língua preferencial, ver mais
  abaixo).
- **Relatórios diário/semanal/mensal: ENTREGUE em 19/09/2026** —
  "Periodic mails", `/admin/emails?tab=periodic`. Escopo confirmado via
  AskUserQuestion: vão só pro time Admin (nível 2+), não é a ferramenta
  de envio segmentado pra usuários que o Daniel já pediu pra pular (P6,
  bloqueada por falta de sistema real de Assinatura). Admin cria/edita/
  pausa/exclui cada e-mail periódico (nome, assunto, corpo HTML,
  frequência); o envelope ao redor é o mesmo layout compartilhado já
  existente (`/admin/emails`, aba Formulário/Código) — só o corpo muda
  por e-mail. Worker novo `app/periodic_mail_worker.py` (mesmo formato
  dos outros 5 workers do site) manda os e-mails vencidos a cada hora e
  reagenda pro próximo ciclo. Ver `AI_CHANGELOG.md` de 19/09/2026 pro
  detalhe completo (tabela nova `periodic_mails`, rotas, testes).
- “Notas” não deve ser traduzido como moeda do site.
- E-mails devem usar a língua preferencial da pessoa; se for complexo, inglês.
- O Changelog compartilhado já existe em `AI_CHANGELOG.md`; manter a regra de
  consulta antes de trabalhar.

**Pronto quando:** os bugs têm teste de regressão, o celular foi testado em
navegador e os fluxos de e-mail foram verificados sem dados reais.

### P1 - Navegação, interface e consistência visual

**Fonte:** 10, 12-13, 15, 18, 116, 192, 196, 238, 250-251, 269 e 277.

- Redesenhar detalhe de anúncio seguindo o perfil e modernizar botões.
- Organizar “Mein Profil” em cards no padrão do perfil público; badges em cima;
  informações fora do perfil em cards de verde mais escuro.
- Separar visualmente a Red Zone e usar o tema descrito: pássaro de óculos e
  giroflex a cada 10 min. A imagem-base deve ser solicitada antes dessa parte.
- Trocar o título por “Vokal Board - Dein Weg zu dem perfekten Auftritt!” com
  a segunda parte traduzida para cada língua.
- Links de cards/ofertas/perfis em nova aba ou janela; máximo de 20 resultados;
  paginação que recarrega só a área de pesquisa/board.
- Cards obrigatórios e opcionais no formulário de anúncio devem ser separados,
  arredondados e com sombra leve, como padrão de todos os cards.
- Remover WhatsApp de perfil e cadastro em “Sozial Netzwerk”.
- Criar gestão administrativa de banners e conferir os banners existentes.

### P2 - Perfil, diretório, áudio e exportações

**Fonte:** 3-5, 16, 27-31, 36, 113, 119-135, 193-194, 225-229, 240 e 267.

- Adicionar Chinês simplificado, Coreano e Romeno; investigar conexão com conta
  Google sem assumir que ela será implementada.
- Permitir mais de um tipo de voz e criar a seleção de línguas exatamente como
  descrita: 10 mais faladas na Europa incluindo Português, “Outra”, até três
  outros campos e remoção.
- Telefone obrigatório, com escolha de visibilidade; e-mail e telefone passam
  a ser obrigatórios para publicar anúncio e só aparecem quando ocorre Match.
- Criar Wizard de perfil para chegar a um CV completo.
- Perfil público: obras solo e coralista em cards diferentes, player minimalista,
  embeds de vídeo abaixo dos cards e campos definidos para exportação.
- Exportar CV PDF e cartão de visita com as opções, QR Code e “Audiobeispiele /
  Listen to me” descritos na fonte. Criar miniatura personalizada para o link
  do perfil, com foto, pássaro e primeiro nome.
- Diretório: selecionar anúncio ativo, aplicar compatibilidade de voz/Fach e
  mostrar convite apenas nas condições de compatibilidade citadas.
- **Decisão do usuário (18/09/2026):** no diretório "Buscar pessoas", o
  filtro por tipo de voz continua amplo — buscar "Soprano" deve trazer todas
  as pessoas com essa voz (principal ou adicional), de todos os subtipos/
  Fächer; Fach **nunca** é critério de busca ali. Fach é um dado opcional,
  exibido só no perfil da própria pessoa, com opção de ocultá-lo ("Não
  mostrar"). A "compatibilidade de voz/Fach" citada no item acima é
  específica do contexto de uma vaga (P3 — quando a vaga exigir um Fach
  específico), não do diretório geral de busca.

### P3 - Anúncios, urgência, convites e Matches

**Fonte:** 11, 23-25, 114, 118-185, 187-190, 198-224, 235, 240 e 242.

- Modelar anúncio pai, vagas por naipe, candidaturas/convites e Matches como a
  fonte descreve; vagas múltiplas têm quantidade e cachê por voz.
- Implementar estados pendente, recusado e aceito. Somente aceite incrementa a
  vaga de forma atômica; anúncio pausa apenas quando todos os naipes estiverem
  preenchidos.
- Aplicação espontânea, lista de candidaturas, sugestões compatíveis, convite
  pelo diretório, convite express e prevenção de convite duplicado pertencem ao
  mesmo fluxo.
- **Convite express — decisão confirmada em 18/09/2026 (Opção 2):** qualquer
  pessoa, mesmo sem conta, pode compartilhar o link de uma vaga
  (`/listings/{id}`) para aumentar o alcance. O **cartão de preview** (Open
  Graph/Twitter Card) que aparece quando o link é colado no WhatsApp/
  Telegram/etc. mostra apenas Obra (repertório) e Cidade, escondendo cachê,
  data exata e o resto, como isca para criar conta. Título do cartão, no
  formato exato pedido: "Veja essa oportunidade: {Obra}, {Cidade}. Vi e
  pensei em você!" (traduzido nas demais línguas do site). Só se aplica a
  anúncios do tipo vaga (`seeking_singer`/`seeking_conductor`, os únicos
  com repertório e cidade obrigatórios); anúncios de "disponível"
  (`singer_available`/`conductor_available`) mantêm o cartão genérico do
  site.
- **Ajuste confirmado em 18/09/2026:** a página `/listings/{id}` em si
  também passou a esconder o Cachê (e venue/data/tipo de voz/Estado) de
  quem não está logado, não só o cartão de preview — pedido do Daniel
  porque o cachê visível "chama muito para o registro" e reduzia o
  incentivo de criar conta. Anônimo numa vaga vê só Nome (título),
  Obra (repertório) e Cidade, com uma frase convidando a criar conta pra
  ver o resto — mesmos três campos do cartão de preview, agora também na
  página. Continua só para vaga (`seeking_singer`/`seeking_conductor`);
  anúncios de "disponível" não foram tocados, e a descrição
  completa/contato continuam gerenciados pelo `lock_reason` que já existia
  antes do P3.D. **Implementado**
  em `app/templates/base.html` (blocos `og_title`/`og_description`/
  `twitter_title`/`twitter_description` agora sobrescrevíveis),
  `app/templates/listing_detail.html`, `app/routers/listings_routes.py`
  (contexto `anon_teaser`) e `app/i18n.py` — ver
  `AI_CHANGELOG.md` de 18/09/2026 para detalhes e testes.
- Implementar convite com validade de 48 h, e-mail de notificação e expiração
  antecipada quando faltarem 6 h para o evento.
- Implementar logística do anúncio: Fahrkosten, Partitur vorhanden e Probenplan
  vorhanden, todos opcionais como descritos.
- **Sugestões compatíveis (P3.E) — decisões confirmadas em 18/09/2026:**
  - **Cachê vira valor numérico com moeda**, em vez do texto livre atual.
    Campos novos em `listings` e `listing_vacancies`: `fee_amount`
    (numérico, 2 casas decimais), `fee_currency` (EUR/CHF/USD/GBP, EUR por
    padrão) e `fee_negotiable` (booleano). No formulário: uma caixa de
    moeda (ordem no dropdown: Euro, CHF, Dólar, Libra) ao lado do valor, e
    um checkbox "A negociar" que trava a caixa de valor quando marcado.
    Obrigatório preencher OU o valor OU marcar "a negociar" (nunca os
    dois, nunca nenhum). Multi-moeda é pré-implementado de propósito —
    hoje o site só opera DE/AT/CH (EUR/CHF), mas a ideia é lançar em
    outros países depois. O campo antigo `fee` (texto livre) permanece no
    schema por enquanto (dados antigos), só não é mais usado por
    formulário/exibição novos — sem migração de dados até o Daniel
    autorizar.
  - **Home (`/`) reordenado por Cachê, do maior pro menor.** Anônimo: 5
    anúncios genéricos/mistos (não mais só os mais recentes), ordenados por
    valor pago, maior primeiro. Logado: continua mostrando as 5 vagas que
    batem com o perfil (como já era), só que agora ordenadas por Cachê
    decrescente em vez de por cidade. Anúncios marcados "a negociar" vão
    pro final da lista (não dá pra comparar valor), e **dentro** do grupo
    "a negociar" a ordem passa a ser por % de compatibilidade.
  - **Filtro de tipo de voz continua binário** (bate ou não bate) — não
    vira parte de um score. Fach fica de fora do critério de busca (já era
    regra antiga do P2, confirmada de novo aqui — muito subjetivo).
  - **Peso dos critérios de compatibilidade, do mais pro menos
    importante:** tipo de voz (filtro binário, obrigatório) > cidade, em
    camadas — cidade igual primeiro, se não tiver ninguém/nada disponível
    olha o mesmo Estado, se não tiver olha o mesmo país (sem cálculo de
    distância real em km — o banco não tem latitude/longitude hoje) >
    nota média (`ratings`), usada só como critério de desempate interno,
    **nunca exibida publicamente** — nota é dado privado, só o próprio
    dono do perfil vê a própria nota, ou o Admin ao abrir o card de
    "Manage" do usuário (reforça regra que já existia).
  - **Toggle de Admin para a visibilidade da pontuação/critério**, a ser
    implantado desde já mesmo que comece desligado — o Daniel quer
    discutir depois se/como o score aparece pro usuário final, mas quer a
    infraestrutura pronta (mesmo padrão do Capitalism Mode em
    `app/financial_settings.py`).
  - **E-mail de alerta de vaga nova continua binário e amplo** (não vira
    filtrado por score) — decisão deliberada pra maximizar visitas ao
    site.
  - Hashtags de compositor: limite de 10 por pessoa já é a regra atual,
    confirmado que não muda.
  - **Implementado em 18/09/2026** — schema (`fee_amount`/`fee_currency`/
    `fee_negotiable` em `listings` e `listing_vacancies`, `app/fees.py`),
    formulário (valor+moeda+"a negociar", com JS desabilitando o campo de
    valor), exibição em todo lugar que mostrava `fee` (`format_fee()` via
    global de template), reordenação da Home (`app/compatibility.py`) e o
    toggle de Admin (`compatibility_score_visible`, desligado por padrão).
    Testado com `pytest` (71 passed, 7 skipped) + smoke test manual; ainda
    NÃO rodado contra o Postgres do Railway. Ver `AI_CHANGELOG.md` para o
    detalhe completo dos arquivos alterados. Único ponto deixado pra
    depois: `/board` (lista pública sem login) continua mostrando o Cachê
    normalmente — só `/listings/{id}` esconde pra anônimo (`anon_teaser`,
    ajuste de mais cedo); não foi pedido explicitamente pro board nesta
    rodada.
- **Após Match concluído (P3.F) — decisões confirmadas em 18/09/2026:**
  - **Sistema NOVO, em paralelo ao `ratings` já existente** (livre, sem
    Match, uma vez por pessoa — esse continua do jeito que está, não é
    tocado). O documento-fonte original descrevia algo mais simples (1
    nota geral 1-5 + badges soltos tipo tag); ficou decidido em conversa
    anterior nesta sessão construir algo mais elaborado — registrado
    aqui porque diverge do texto original do Word.
  - **5 categorias, cada uma avaliada de 1 a 5 estrelas:** Pünktlichkeit,
    Vorbereitung, Musikalität, Professionelle Kommunikation e Angenehme
    Zusammenarbeit. Soma das 5 dividida por 5 = nota daquela avaliação.
    (Nomes finais confirmados em 18/09/2026 — substituem uma tentativa
    anterior com nomes em português/alemão misturados.)
  - **Mútuo:** cada lado do Match (artista e contratante) pode avaliar o
    outro, mesmas 5 categorias, formulários independentes. Avaliação é
    opcional, só lembrada (não bloqueia nada).
  - **Liberação e janela:** só para Match não cancelado (`confirmed` ou
    `completed`), a partir da data do evento (`listings.event_date`) já
    ter passado, e fica disponível por exatamente 14 dias depois disso —
    sub-aba em "Meus Matches" (`/profile/matches`). Lembrete automático
    na central de notificações: "Wie war deine Erfahrung? Bewerte
    {Primeiro nome}!" (traduzido nas línguas do site).
  - **Progressão Bronze→Prata→Ouro→Platina — modelo "estilo Uber",
    confirmado em 18/09/2026:** UMA progressão **por categoria** (5
    selos independentes, não 1 selo geral). Cada tier é a **média
    corrente** (não permanente) de todas as avaliações recebidas
    naquela categoria — pode subir OU descer com o tempo, diferente dos
    outros badges do site (que só sobem, uma vez desbloqueados). Corte:
    média ≥4.5 = Platina, ≥4.0 = Ouro, ≥3.5 = Prata, abaixo disso mas
    com avaliações suficientes = Bronze. Mínimo de avaliações antes de
    mostrar qualquer tier: 3 (evita expor selo com 1 nota só) — número
    minha sugestão, não foi confirmado número a número pelo Daniel, só
    o modelo geral (avisar se quiser outro mínimo).
  - **Visibilidade: só interna.** A nota final e os selos de qualidade
    NÃO aparecem no perfil público (`public_profile.html`) — só o
    próprio dono (na própria `/profile`) e o Admin (card de "Manage" do
    usuário) veem. Diferente dos badges de marco que já existem hoje
    (indicação, visualizações etc.), que continuam públicos — só os
    novos selos de qualidade ficam privados.
  - **Addendum confirmado em 18/09/2026 (depois do bloco acima já
    registrado):** (a) o modelo "estilo Uber" acima é o modelo FINAL —
    superseeds uma resposta anterior, já descartada, de cortes fixos
    por contagem de avaliações (3/10/25/50 avaliações, média
    ≥3.5/4.0/4.3/4.5); (b) **secreto igual Uber — "ninguém vê quem
    avaliou e como"**: isso vai além de "só interna" — nem o próprio
    avaliado, nem o Admin, nem NINGUÉM vê a nota individual de um Match
    específico nem quem avaliou quem, em lugar nenhum do site. Só a
    MÉDIA AGREGADA por categoria (`get_quality_tiers()` em
    `app/match_evaluations.py`) pode ser exibida, e só pro próprio dono
    e pro Admin — nenhuma rota pode expor uma linha individual de
    `match_evaluations`. Implementado em `app/match_evaluations.py`.
- Material de ensaio deve seguir Zero-Storage: somente link externo ou
  referência bibliográfica, com aviso de direitos autorais, após confirmação.

### P4 - Rechnungmaker e documentos financeiros

**Fonte:** 32, 43-109, 111-112, 147, 152-153, 170-184, 254 e 263.

- Aplicar a franquia de 5 Rechnungen grátis por mês e separar os três fluxos:
  avulso stateless, Match com rascunho temporário criptografado e documento financeiro permanente
  da plataforma.
- Implementar requisitos alemães listados: dados obrigatórios, opções de USt,
  moeda EUR/CHF, despesas, pagamento, preview e confirmação.
- Dados bancários e fiscais nunca podem ir ao perfil público, log, sessão ou
  disco em texto aberto. No Match, o contratado pode pedir Rechnung de forma
  opcional; o rascunho fica criptografado por até 7 dias para revisão do
  contratante. Após confirmação, o PDF é gerado em memória e enviado por
  e-mail às duas partes, sem retenção pelo VokalBoard.
- A opção de iniciar a Rechnung de um Match desaparece após sete dias da data
  do evento. Uma vez iniciado o pedido, a outra parte tem sete dias completos
  para revisar e confirmar; depois disso o pedido desaparece para ambas.
- Criar badges de pendência, Match-Rechnungen, Gerador Avulso, pedidos entre as
  partes e contador gamificado de Rechnungen conforme os parágrafos 80-112.

**Status em 18/09/2026 — dividido em etapas menores, a pedido do Daniel.
P4 COMPLETO** (Etapas 1-3 + to-do list, ver abaixo — único item restante,
o "documento financeiro permanente da plataforma", foi movido pro P99
por decisão do próprio Daniel, não é mais parte do P4):

- **Já pronto antes desta rodada (Codex, 17/09):** fundação de banco
  (`invoice_number_sequences`, `invoice_monthly_usage`,
  `purchased_invoice_credits`, `invoice_match_drafts`), franquia atômica de
  5 grátis/mês + créditos comprados (`app/invoice_service.py`), numeração
  `YYYY-NNNN` editável, e o Gerador Avulso básico (`/rechnungen`).
- **Etapa 1 (esta rodada) — Match-Rechunungen: pedir/gerar + preview + e-mail:**
  botões no card do Match (`/profile/matches`) — "Solicitar Rechnung"
  (contratante pede) e "Gerar/Editar Rechnung" (emissor preenche);
  formulário pré-preenchido com dados públicos do Match; tela de preview
  (as duas partes veem, só o contratante confirma); ao confirmar, PDF em
  memória + e-mail com anexo pras duas partes + rascunho apagado
  (Zero-Storage real, sem cópia nenhuma). Emissor = `job_matches.artist_user_id`
  (quem presta o serviço), contratante = `job_matches.contractor_user_id`.
  **Ainda NÃO nesta etapa** (ficam pras próximas, por decisão explícita do
  Daniel de ir "em partes menores"): worker de expiração automática dos 7
  dias, badges de pendência no menu/sub-aba, contador gamificado
  (1/10/50/100 Rechnungen).
- **Decisões confirmadas em 18/09/2026 (tributação e despesas, valem pros
  dois fluxos — Avulso e Match):**
  - USt/MWST: radios fixos por país — Alemanha (Kleinunternehmer §19 UStG /
    Isenção cultural §4 Nr.20 UStG / Padrão) com as frases exatas do
    documento-fonte; Áustria e Suíça têm as mesmas 3 categorias mas com
    frase GENÉRICA (o Claude não tem a citação de parágrafo austríaca/suíça
    verificada — fica marcado no código pra confirmar com um
    Steuerberater/Treuhandstelle antes de produção); "Outro" com texto
    livre pra qualquer outro país (EUA, resto da UE). Ver
    `app/invoice_tax_presets.py`.
  - Despesas (Fahrkosten/Übernachtungskosten): só o VALOR entra como linha
    extra no PDF — SEM upload/anexo de comprovante no site. Decisão do
    Daniel: "a pessoa resolve os comprovantes direto com o empregador...
    ela já tem que imprimir e entregar a Rechnung, ela faz tudo privado."
  - O terceiro fluxo do bullet original ("documento financeiro permanente
    da plataforma") foi movido para o **P99** em 18/09/2026 — perguntado
    de novo ao Daniel, ele não lembra mais o que essa ideia queria dizer
    ("Mande isso para P99 pq não lembro"). Ver P99 abaixo.
- **Etapa 2 (18/09/2026) — worker de expiração dos 7 dias: ENTREGUE.**
  Decisões confirmadas com o Daniel: (a) rascunho vencido é **apagado
  direto** (mesmo padrão Zero-Storage de `confirm_and_send`/
  `cancel_draft` — nunca fica em status `expired` primeiro); (b) **as
  duas partes recebem e-mail** avisando que expirou, convidando a pedir
  de novo se ainda for necessário. Implementado em
  `app/invoice_match_draft_expiry_worker.py` (mesmo formato de
  `app/invitation_expiry_worker.py`/`app/match_evaluation_reminder_worker.py`
  — lock consultivo próprio id 8303, `--once`/`--dry-run`). Nova função
  `match_invoice_expired_email()` em `app/email_localization.py` (5
  idiomas). 4 testes novos em
  `tests/test_invoice_match_draft_expiry_worker.py`. Ver
  `AI_CHANGELOG.md` de 18/09/2026 para detalhe completo.
  - **Ainda NÃO registrado em `docker-compose.yml`** — mesmo padrão dos
    outros workers do site hoje (nenhum tem serviço lá, só o
    `retention_worker` atrás de profile opt-in); avisar se o Daniel
    quiser todos os workers registrados numa rodada futura.
- **Etapa 3 (18/09/2026) — badge de pendência + página dedicada
  `/rechnungmaker` + contador pessoal gamificado + tracking geral de uso
  de ferramentas: ENTREGUE.** Decisões confirmadas com o Daniel: (a) o
  badge de pendência no menu conta **os dois** — pedido novo recebido E
  rascunho aguardando minha ação (contagem única, `count_pending_actions()`
  em `app/invoice_match_drafts.py`, uma única query com JOIN, sem N+1);
  (b) nasceu a página própria `/rechnungmaker` com 2 abas (Match-Rechnungen
  / Gerador Avulso), substituindo os botões que ficavam embutidos em
  `/profile/matches` — UI intencionalmente simples (abas grandes tipo
  botão, `.tool-tabs`/`.tool-tab`) por pedido explícito do Daniel ("as
  pessoas... provavelmente não tem muitos conhecimentos de informática");
  `/rechnungen` antigo agora só redireciona (303) pra
  `/rechnungmaker?tab=avulso`; (c) contador pessoal (bronze/prata/ouro/
  platina em 1/10/50/100 Rechnungen) soma Avulso + Match juntos (tanto
  faz pro Daniel), é **privado** (só o dono vê, no topo da própria página
  `/rechnungmaker`), calculado ao vivo a partir das tabelas de accounting
  já existentes (`invoice_monthly_usage` + `purchased_invoice_credits`) —
  ver `get_personal_invoice_badge()`/`get_lifetime_invoice_count()` em
  `app/invoice_service.py`; é badge de **marco** (só sobe), não "estilo
  Uber". (d) Novo mecanismo **genérico** de tracking de uso por
  ferramenta do site (pedido explícito: "quero que haja uma forma de
  trackear quais ferramentas do site são mais usadas... isso inclui
  Rechnung maker") — tabela `feature_usage_monthly` +
  `app/feature_usage.py` (`record_feature_usage()`/
  `get_feature_usage_totals()`), reaproveitável por qualquer feature
  futura, hoje só chamado por `consume_invoice_generation()` (cobre
  Avulso + Match); visível em Admin (`/admin`, seção "Most-used tools").
  16 testes novos (`tests/test_rechnungmaker_page.py`,
  `tests/test_feature_usage.py`, +3 em `tests/test_invoice_service.py`).
  Ver `AI_CHANGELOG.md` de 18/09/2026 para detalhe completo.

**To-do list do Rechnungmaker — adicionado em 18/09/2026: ENTREGUE na
mesma data (Daniel pediu pra terminar o P4 até o final).**

- **Assinatura no rodapé do PDF: ENTREGUE.** Rodapé centralizado com
  "Made with assistance of VokalBoard - Rechnung Maker -
  www.vokalboard.com/rechnungmaker" — nos dois fluxos (Avulso e Match),
  já que os dois passam pela mesma `render_invoice_pdf()` em
  `app/invoice_pdf.py` (um `Paragraph` centralizado no fim do `story`,
  fonte 7pt cinza-esverdeada discreta). Teste novo em
  `tests/test_invoice_pdf.py` extrai o texto do PDF com `pypdf` (dep.
  nova, só em `requirements-dev.txt` — nunca importada fora dos testes)
  pra confirmar que o rodapé realmente aparece no PDF gerado.
- **Menu suspenso de tributação por país DACH: ENTREGUE.** Os radios de
  status por baixo do país viraram um único `<select>` que já mostra o
  par completo ("Deutschland — Kleinunternehmer (§19 UStG)", "Österreich
  — Kleinunternehmerregelung", "Schweiz — Von der Mehrwertsteuer
  befreit", etc.) + "Outro país" no fim — `TAX_PRESET_OPTIONS` em
  `app/invoice_tax_presets.py` (valor `"PAIS:status"`, ex. `"DE:standard"`,
  default `"DE:standard"` — mesmo padrão que já era o default antes). Um
  JS inline mínimo (sem biblioteca) faz o split do valor selecionado em
  dois `<input type="hidden">` (`tax_country`/`tax_status`) — os mesmos
  nomes de campo que o backend já esperava, então `resolve_tax()` e as
  rotas em `app/routers/invoice_routes.py` não precisaram mudar nada,
  só passar `tax_preset_options` no contexto. Aplicado nos dois
  formulários (`rechnungmaker.html` aba Avulso, `invoice_match_form.html`
  do Match). Decisão de UX tomada sem checar com o Daniel de novo (era só
  uma nota antiga apontando pra uma seção que nunca chegou a existir no
  documento): optei por **substituir** os radios (não manter os dois),
  já que o texto-fonte dizia "ao invés dos radios atuais".

### P5 - Notas, loja, assinatura e economia

**Fonte:** 20-21, 25-28, 35, 111, 236-237, 239, 252, 255-266, 268, 270-274.

**Status em 18/09/2026 — pacote grande demais pra uma rodada só, dividido
em etapas menores a pedido do Daniel (mesmo estilo do P4):**

- **Etapa 1 (18/09/2026) — fundação antifraude + recompensa por vaga
  postada: ENTREGUE.** Decisões confirmadas com o Daniel (perguntadas
  via AskUserQuestion): (a) começar pelo menor pedaço, de baixo risco
  (fundação + recompensa), deixando Urgência/Assinatura/Loja expandida
  pra próximas rodadas; (b) por enquanto **sem cobrança de dinheiro
  real** — tudo fica em Notas/estrutura pronta, Capitalism Mode
  continua desligado (mesmo padrão já documentado em
  `app/financial_settings.py`); (c) recompensa por vaga postada usa
  **teto fixo de 3 vagas recompensadas por semana** (não "tempo mínimo
  ativo") — mais simples, ao custo aceito de uma corrida bem
  improvável poder passar 1 acima do teto; (d) "comprar urgência"
  (fora de escopo NESTA etapa, mas já esclarecido pro futuro) marca a
  vaga como "urgente" com destaque visual + aparece num quadro
  dedicado de vagas urgentes.
  - **Achado técnico durante a implementação:** `credit_ledger.delta`
    era `INTEGER` — não cabia "0,50 Nota por vaga postada" sem migrar
    o schema. Perguntado ao Daniel, decisão: migrar pra
    `NUMERIC(10,2)` (não simplificar pra 1 Nota inteira, não creditar
    só a cada 2 vagas) — ver
    `db/migrations/2026-09-18_p5_etapa1_notas_wallet_foundation.sql`.
    Valores antigos (sempre inteiros) migraram sem perda.
  - **Fundação nova, reaproveitável por loja/urgência/assinatura**
    quando chegar a vez: `app/notas_wallet.py` — `credit_notas()` e
    `debit_notas_atomic()` (as 3 regras fixas do plano: saldo nunca
    negativo por corrida via `SELECT ... FOR UPDATE`, idempotência via
    `idempotency_key` + índice único parcial no banco
    `idx_credit_ledger_user_idempotency`, preço sempre calculado pelo
    chamador nunca aceito do cliente), `format_notas()` (exibição:
    inteiro sem decimais, fração com vírgula), `count_credits_since()`
    (base pra qualquer teto semanal/diário futuro).
  - **Recompensa em si:** `app/listing_rewards.py` —
    `award_listing_posted_reward()`, chamada via `background_tasks`
    depois de qualquer anúncio publicado (`create_listing` em
    `listings_routes.py`) — nunca atrasa nem quebra a publicação da
    vaga em si mesmo se falhar. Vale pra qualquer `listing_type`
    (vaga ou autoanúncio de disponibilidade), não só vaga procurando
    artista.
  - `app/referrals.py`/`app/routers/notas_routes.py` refatorados pra
    usar o módulo novo em vez de duplicar a query de saldo
    (`get_credit_balance` centralizado em `notas_wallet.py`) — o
    bônus de indicação também passou a usar `credit_notas()`.
    **Deliberadamente NÃO tocado:** `redeem_notas()` (resgate de
    itens da loja) continua com sua própria trava de linha inline —
    tem um efeito colateral (estender `profile_highlighted_until`) na
    MESMA transação do débito, e reescrever isso não era o escopo
    desta etapa; fica pra quando a loja crescer.
  - 11 testes novos (`tests/test_notas_wallet.py`,
    `tests/test_listing_rewards.py`). Ver `AI_CHANGELOG.md` de
    18/09/2026 para detalhe completo.
- **Etapa 2 (18/09/2026) — Sistema de Urgência: ENTREGUE.** Decisões
  confirmadas com o Daniel via AskUserQuestion: (a) marcar como
  urgente vale **das duas formas** — checkbox na criação do anúncio E
  botão "marcar como urgente" depois, em `/my-listings`; (b) vale só
  pra quem está **procurando preencher vaga**
  (`seeking_singer`/`seeking_conductor`), não pra autoanúncio de
  disponibilidade; (c) o "envio após 6h" do texto-fonte é um
  **lembrete extra pros perfis compatíveis**, 6h depois de marcada
  urgente, só se ainda não tiver Match; (d) recompensa de conclusão
  (confirmada em duas rodadas, a primeira resposta livre foi
  ambígua): **0,50 Nota** pro publicador quando o Match acontece pela
  plataforma numa vaga urgente (metade do "preço cheio" de 1 Nota).
  Token semanal grátis (1/semana, não acumula) + compra por 2 Notas a
  partir do segundo uso — já estava decidido desde a Etapa 1.
  - `app/urgency.py` (novo) — `mark_listing_urgent()` atômico (trava
    a vaga, valida elegibilidade, decide grátis vs. pago, debita via
    `debit_notas_atomic()` da Etapa 1); `get_urgency_status()`.
  - `app/match_service.py` — recompensa de 0,50 Nota creditada na
    MESMA transação da criação do Match (`respond_invitation`),
    idempotente por `match_id`.
  - Rotas novas em `listings_routes.py`, worker de lembrete de 6h
    (`app/urgent_listing_reminder_worker.py`, lock id 8304), badges
    âmbar/laranja em `/board` e `/my-listings`, ~12 chaves i18n novas.
  - **Gotcha do Postgres descoberto e agora documentado**: a view
    `visible_listings` (`SELECT * FROM listings WHERE ...`) congela a
    lista de colunas no momento da criação — `ALTER TABLE listings
    ADD COLUMN` não propaga sozinho; é preciso `CREATE OR REPLACE
    VIEW` de novo. Causou 17 falhas em testes sem relação com
    urgência até ser corrigido — atenção pra qualquer coluna nova
    futura em `listings`.
  - 18 testes novos. Suíte completa: **137 passed, 7 skipped**. Ver
    `AI_CHANGELOG.md` de 18/09/2026 (entrada "P5 Etapa 2") para
    detalhe completo.
- **Loja — painel de Admin (18/09/2026): ENTREGUE.** Primeira parte da
  Loja expandida, escolhida (via AskUserQuestion) pra começar pelo
  painel de Admin antes de qualquer item novo. Funções entregues,
  todas confirmadas com o Daniel antes de codar:
  - **Ativar/desativar produto individualmente** — catálogo migrou de
    lista fixa no Python pra tabela `shop_catalog_items` (preço +
    ativo/inativo), controlável em `/admin/loja` sem deploy. Desativar
    só bloqueia NOVOS resgates — quem já resgatou antes mantém o
    benefício normalmente.
  - **Histórico geral da loja** — `/admin/loja`, paginado, só
    transações da loja (resgates de catálogo + compra de urgência),
    não mistura com bônus/recompensas de outras origens.
  - **Busca por usuário + extrato** — reaproveitou a busca que já
    existia em `/admin/users`; o extrato de Notas (completo, qualquer
    origem) foi adicionado à página `/admin/users/{id}`.
  - Ver `AI_CHANGELOG.md` de 18/09/2026 ("P5 Loja: painel de Admin")
    pra detalhe completo. 8 testes novos, suíte completa **145
    passed, 7 skipped**.
- **Loja — CRUD de itens + "comprar Notas que faltam" (18/09/2026,
  mesmo dia): ENTREGUE.** Pedido do Daniel: "colocar forma de
  adicionar itens à loja, mudar descrição e título de itens, como uma
  loja normal" + oferecer comprar a diferença de Notas quando o saldo
  não é suficiente (ex.: tem 3, precisa de 11). Decisões confirmadas
  via AskUserQuestion:
  - Item **novo** criado pelo Admin é um **voucher genérico** — só
    debita Notas e registra no histórico, sem efeito automático (quem
    cumpre é o Admin, manualmente). O único efeito programado em
    código continua sendo o do item que já existia (destaque de
    perfil).
  - Título/descrição editados pelo Admin ficam em **um idioma só**,
    guardado no banco — mostra igual pra todo mundo.
  - "Comprar as Notas que faltam" é **só a interface por enquanto**
    (tela "em breve", mesmo padrão do `/assinar` hoje) — **nenhuma
    cobrança real ainda**, não existe gateway de pagamento integrado
    no site. Liga o dinheiro real quando um gateway for escolhido,
    provavelmente junto com a Assinatura (mesma pendência).
  - `shop_catalog_items` ganhou `title`/`description`/`icon` (todos
    administráveis); `ALLOWED_ICONS` é uma lista fechada validada no
    servidor. `/notas` mostra "Faltam X Notas" + link pra comprar a
    diferença em vez de um botão simplesmente desabilitado.
  - Ver `AI_CHANGELOG.md` de 18/09/2026 pra detalhe completo. 14
    testes novos, suíte completa **159 passed, 7 skipped**.
- **Ainda NÃO iniciado (próximas etapas, ordem sugerida):** os itens
  específicos da Loja (selo de confiança, Rechnungen extra) — o CRUD
  genérico já permite cadastrá-los como vouchers manuais quando o
  Daniel quiser, sem esperar por código dedicado a cada um; cobrança
  real de Notas (gateway de pagamento) — junto com a Assinatura, que
  tem a mesma pendência; Assinatura (desconto escalonado 20%/10%,
  e-mails/push, link exclusivo pós-30-dias, Admin "Assinaturas");
  Hall da Fama (foto de quem convida no link, botão "Convidar um
  amigo!").

- Definir o preço dos demais serviços. A urgência está decidida: 1 token
  semanal e compra por Notas equivalente a 2 Euros quando o saldo de tokens é 0.
  A fonte usa “1 Nota = 1 Euro/Franco” e também pede equivalência pela
  localização da conta.
- Notas nunca podem ser convertidas em dinheiro real; registrar essa regra nos
  termos de compra e uso.
- Reunir recompensas: login diário após 5 min, perfil 100% completo, referral,
  aceite de urgência, gasto da primeira Nota, impulso de perfil e demais badges.
- **Recompensa por publicar vaga (nova regra, adicionada em 18/09/2026):**
  creditar Notas automaticamente toda vez que um anúncio (vaga) for publicado,
  como incentivo para aumentar o volume de postagens — valor de exemplo: 0,50
  Nota por anúncio postado. Como toda transação de Notas (Seção 3.B do
  CLAUDE.md), deve registrar histórico em `note_transactions` com origem
  identificável (ex: "vaga_postada", referenciando o `listing_id`). Avaliar
  antifraude antes de implementar: limite diário/semanal de recompensas por
  usuário, ou exigir que o anúncio permaneça ativo por um tempo mínimo, para
  evitar postar e apagar em massa só para acumular Notas. Ainda não
  implementado — apenas planejado aqui; a lógica real entra em
  `create_listing` (`listings_routes.py`) quando for priorizado.
- Loja de Notas, vouchers, selo confiável, urgências pagas e Rechnungen extras
  precisam de extrato global, extrato por usuário e controles no Admin.
- **Antifraude na loja e na assinatura (nova regra, adicionada em
  18/09/2026):** pedido do Daniel para prevenir glitches/exploits, cobrindo
  toda ação que credita, debita ou desconta Notas — compra, recompensa,
  voucher, urgência paga, assinatura e desconto por link.
  - **Saldo nunca fica negativo por corrida (race condition):** todo débito de
    Notas é um `UPDATE` atômico com `WHERE saldo >= :custo` (mesmo padrão já
    usado em `listing_vacancies.filled_slots` no P3.B) — nunca ler o saldo
    numa consulta e decidir/gravar numa segunda, senão duas compras
    simultâneas no mesmo saldo baixo podem ambas passar.
  - **Preço nunca vem do cliente:** todo valor de compra (Notas, urgência,
    assinatura, extra de Rechnung) é recalculado no servidor a partir da
    tabela/config de preços; o back-end nunca confia em preço, desconto ou
    total enviado pelo formulário/JS.
  - **Idempotência:** toda compra ou resgate de voucher usa uma chave de
    idempotência (ex: id do pedido gerado no primeiro clique) para que um
    duplo clique, um F5 ou um retry de rede não gerem duas transações — sem
    isso, `note_transactions` (Seção 3.B do CLAUDE.md) fica sujeita a débito
    ou crédito duplicado.
  - **Vouchers e links de desconto:** códigos de voucher e o link exclusivo
    de 20% (regra de 30 dias sem renovar, já descrita abaixo) precisam de uso
    único por conta, rate limit contra força bruta de código e desativação
    imediata após o primeiro uso — consistente com a regra já registrada de
    desativar o link após a compra.
  - **Recompensas automáticas (login diário, perfil 100%, referral, vaga
    postada etc.) precisam de limite/antifraude próprio**, já anotado bullet
    acima para o caso de "vaga postada"; aplicar o mesmo raciocínio (limite
    diário/semanal, condição mínima de tempo/qualidade) a qualquer nova
    recompensa automática que for adicionada aqui no P5.
  - **Auditoria:** toda transação de Notas, ação de God Mode sobre saldo
    alheio e resgate de voucher/link ficam no `audit_log` (Seção 2.4 do
    CLAUDE.md), com ator, IP e timestamp, para investigação de abuso.
  - Ainda não implementado — apenas planejado aqui; entra junto com a
    implementação real da loja/assinatura (P5), não antes.
- Assinatura: desconto de 20% de 120 até 60 dias restantes; e-mail e
  notificação push no site, no máximo uma vez por semana a partir de 100 dias;
  10% até expirar; preço normal após expirar; e link exclusivo de 20% após 30
  dias sem renovar. Avaliar a seção “Assinaturas” no Admin para editar regras,
  registros gratuitos ligados/desligados e anuidade após pagamento.
- No novo Menu de E-mails, avaliar um botão “Notificação por Email: On/Off” e
  uma campanha para todas as pessoas sem assinatura ativa, com promoção. Os
  campos pedidos são: quanto de desconto e por quanto tempo o link
  personalizado vale. O link deve ser desativado e redirecionar à página
  inicial somente após a compra, para evitar compartilhamento.
- **E-mail de vagas pro naipe de quem deixou a assinatura vencer (pedido do
  Daniel, 18/09/2026) — especificação completa, ainda NÃO implementada:**
  registrado aqui de propósito, sem codar ainda, porque hoje ninguém tem
  assinatura de verdade (Capitalism Mode desligado, sem gateway de pagamento
  — a tabela `subscriptions` existe mas está vazia). Entra junto com a
  implementação real da Assinatura (P5), quando o pagamento estiver ligado.
  Decisões já confirmadas via AskUserQuestion, pra não perguntar de novo
  quando chegar a vez:
  - **Público-alvo:** só quem JÁ teve assinatura ativa e deixou vencer (não
    quem nunca assinou — isso é a campanha genérica de conversão, separada,
    já registrada acima).
  - **Frequência:** configurável por um sub-menu no Admin (não fixa no
    código) — mesma seção “Assinaturas”/Menu de E-mails já prevista acima,
    com um campo de "a cada X dias".
  - **Conteúdo:** tom “Estão buscando por você!” + só a CONTAGEM de vagas
    abertas que batem com o naipe/voz da pessoa (ex.: “3 vagas pra Soprano
    estão abertas perto de você”) — SEM nenhum detalhe da vaga em si (sem
    cidade, cachê, título ou quem publicou), só o número. Termina oferecendo
    os planos de assinatura (mensal/anual, ver decisão de preço ainda em
    aberto acima) pra desbloquear os detalhes.
  - Reaproveita o `On/Off` global de notificação por e-mail já planejado
    pro Menu de E-mails (P6, abaixo) — desativa a campanha inteira por
    toggle, sem precisar tocar em código.
- Hall da Fama deve mostrar link de convite, botão “Convidar um amigo!” e foto
  de quem convida no link, se viável.

### P6 - Administração, suporte, segurança e dados

**Fonte:** 9, 17, 21-22, 38, 191-192, 230-232, 236, 238, 241, 243-247,
251, 265, 268-270, 274, 276-277.

- God Mode: privilégios, vouchers, envio segmentado de e-mails, loja de Notas,
  registros grátis e Capitalism Mode como último botão da página.
  Estorno de compra (Loja + dinheiro), ver bullet "Admin" abaixo:
  **ENTREGUE** em `/financeiro/estornos`.
  - **Concessão avulsa — vouchers/registros grátis (19/09/2026):
    ENTREGUE** — "Make p6 done", escopo confirmado via AskUserQuestion
    ("Notas + shop vouchers"). Nova tela `/financeiro/conceder` (God
    Mode): credita/debita Notas de um usuário específico, ou concede
    um item do catálogo da Loja diretamente (sem passar pelo
    autorresgate) — cada ação exige justificativa escrita, reauth de
    senha e fica no `audit_log`, mesmo cuidado das outras ações
    financeiras do Red Zone. A concessão de item NUNCA debita o saldo
    do usuário (é um presente, não uma compra) — ver
    `grant_catalog_item_to_user()` em `app/shop_catalog.py`. Ver
    `AI_CHANGELOG.md` de 19/09/2026 pra detalhe completo. 7 testes
    novos, suíte completa **225 passed, 7 skipped** (nesse ponto,
    antes dos testes de tickets abaixo).
  - **Envio segmentado de e-mails: continua FORA de escopo**, decisão
    confirmada com o Daniel via AskUserQuestion ("Skip for now") —
    depende de Assinatura real (gateway de pagamento), que não existe
    nesse código ainda. Revisitar quando esse sistema existir.
- Novo Menu de E-mails: incluir disparo para pessoas sem assinatura ativa com
  promoção, botão “Notificação por Email: On/Off”, desconto e validade de link
  personalizado. Criar editor de e-mails no mesmo espírito do editor de posts
  e manter uma assinatura padrão salva. O On/Off é global, para que a campanha
  possa ser desativada por toggle.
  - **Layout compartilhado (18/09/2026): ENTREGUE** — `/admin/emails`
    (logo, cor de destaque, emoji de cabeçalho, assinatura, rodapé),
    aplicado automaticamente a TODOS os ~16 pontos de envio de e-mail
    do site (`send_email()` embrulha tudo com `render_email()` — ver
    `app/email_layout.py`). Formulário simples (não editor rich-text
    livre — decisão do Daniel via AskUserQuestion, e-mail tem
    limitação real de renderização) + pré-visualização ao vivo.
    Ícones no e-mail são emoji (o sprite `icons.svg` do site não
    funciona em cliente de e-mail). Ver `AI_CHANGELOG.md` de
    18/09/2026 pra detalhe completo. 7 testes novos, suíte completa
    **166 passed, 7 skipped**.
  - **Aba "Código" (18/09/2026): ENTREGUE** — segunda aba em
    `/admin/emails` (`?tab=code`), mostrando/editando o HTML cru do
    molde por trás do formulário simples (pedido seguinte do Daniel:
    "uma aba onde mostra o Code do e-mail pra eu editar coisas
    menores"). 6 placeholders documentados na própria página
    (`{{BODY}}`, `{{LOGO}}`, `{{ACCENT}}`, `{{EMOJI}}`,
    `{{SIGNATURE}}`, `{{FOOTER}}`), validação bloqueia salvar sem
    `{{BODY}}` (senão o corpo sumiria de todo e-mail), botão
    "Restaurar padrão", `<script>` removido por precaução. HTML cru
    sem o sanitizador de posts (incompatível com tabela/estilo
    inline que e-mail exige) — aceitável por ser Admin-only, mesmo
    patamar do Adminer. Ver `app/email_layout.py` e `AI_CHANGELOG.md`
    de 18/09/2026 pra detalhe completo. 10 testes novos (17 no total
    do arquivo), suíte completa **176 passed, 7 skipped**.
  - **Ainda faltam**, dependendo da Assinatura com pagamento real: o
    disparo em si pra quem não tem assinatura ativa (com promoção),
    o botão global "Notificação por Email: On/Off", o desconto e
    validade de link personalizado, e a campanha de "vagas pro seu
    naipe" de quem deixou vencer — essa última já com um campo de
    **frequência ("a cada X dias")** configurável aqui no Admin
    (decisão do Daniel, 18/09/2026), especificação completa na seção
    P5 (Assinatura), acima.
- **Admin (18/09/2026): ENTREGUE** — mini card ao gerenciar perfil
  (`/admin/users/{id}`: status/e-mail verificado/saldo de Notas/destaque,
  tudo num olhar só), lista de usuários ativos filtrável
  (`/admin/users?active_only=1`), adicionar/remover dias de destaque
  manualmente (`app/highlights.py`, `adjust_highlight_days()`,
  reembolso de uma linha específica do extrato de Notas
  (`POST /admin/users/{id}/refund-notas/{ledger_id}`, idempotente), e
  resposta a denúncias (aceitar/rejeitar em `/admin`, só God Mode) com
  notificação por e-mail a quem denunciou nos dois casos (não só
  aceita) — `app/moderation.py` + `report_resolved_email()` em
  `app/email_localization.py`. Ver `AI_CHANGELOG.md` de 18/09/2026
  pra detalhe completo. 16 testes novos, suíte completa
  **192 passed, 7 skipped**.
  - **Punição na denúncia (18/09/2026): ENTREGUE** — "no botão de
    denúncia precisamos definir alguma forma de warning/punição/
    banimento". Aceitar uma denúncia agora tem um `<select>` opcional
    de punição pro autor do anúncio: `warning` (só notifica, não
    mexe na conta), `suspend` (reaproveita o mesmo `deleted_at` de
    "Deactivate account" — o autor reverte sozinho fazendo login de
    novo) ou `ban` (DIFERENTE de suspender — definitivo: bloqueia
    login e a oferta de reativação, só um Admin reverte via "Unban",
    e-mail fica banido de recadastro pra sempre). Histórico em
    `moderation_actions`, visível em `/admin/users/{id}` junto com
    badge "Banned" e o botão de unban (só God Mode). Ver
    `app/moderation.py`.
  - **Estornos — Loja + dinheiro (18/09/2026): ENTREGUE** — "um botão
    ou submenu para estornar compra, tanto da loja quanto com
    dinheiro, em algum submenu do financeiro". Nova tela
    `/financeiro/estornos` (God Mode): lado Loja/Notas lista os
    últimos 50 débitos de QUALQUER usuário com botão de estorno
    (reaproveitando a mesma função usada pelo botão que já existia em
    `/admin/users/{id}`, extraída pra `refund_ledger_entry()` em
    `app/notas_wallet.py`); lado dinheiro lista assinaturas pagas
    (hoje sempre vazio — sem gateway/Capitalism Mode desligado — mas
    construído já, pronto pro dia que existir), com reauth de senha
    igual as outras ações financeiras do Red Zone. Estornar uma
    assinatura tira ela da receita de fechamentos futuros
    (`create_closing()` corrigido pra isso). Ver `AI_CHANGELOG.md` de
    18/09/2026 pra detalhe completo de ambos. 16 testes novos, suíte
    completa **208 passed, 7 skipped**.
  - **Filter transactions by period (18/09/2026): DELIVERED** — "We
    gotta have a way to see also transactions by period to facilitate
    the whole operation at Financeiro." Added an optional `start`/`end`
    date-range filter (query params) to the two existing screens:
    `/financeiro/painel` (expenses list, total, "by category" chart —
    the monthly-trend and country-adoption charts stay unfiltered on
    purpose, they're whole-history overviews) and `/financeiro/estornos`
    (Notas-debits list and refundable-subscriptions list, each filtered
    by its own date column). Same fixed-literal-SQL-clause security
    pattern used elsewhere in the codebase. Along the way, fixed a
    pre-existing bug where `_cents_to_amount()` crashed the "by
    category" chart whenever it had real data (a SQL `SUM()` returns
    `Decimal`, which isn't JSON-serializable). See `AI_CHANGELOG.md` of
    18/09/2026 for full detail. 3 new tests, full suite **211 passed, 7
    skipped**.
  - **Extrato Geral — whole-platform statement (18/09/2026):
    DELIVERED** — "have an Extrato of the whole Finances of the
    platform... what's going out, what's coming in... like a normal
    bank... choose what to see and what to export." New screen
    `/financeiro/extrato-geral` (God Mode): merges expenses (out) and
    non-refunded subscription revenue (in) into one chronological
    statement with a running balance, filterable by period + type
    (in/out) + expense category, with CSV/Excel/PDF export that always
    matches the on-screen filters (`_build_extrato_geral()` is the
    single shared source for the page and all three exports). See
    `AI_CHANGELOG.md` of 18/09/2026 for the full scope decisions. 6 new
    tests, full suite **217 passed, 7 skipped**.
- **"Fale conosco" + "Reportar erro" (19/09/2026): ENTREGUE** — escopo
  confirmado via AskUserQuestion ("Auto-context + Admin inbox"). Um
  inbox único (`support_tickets`, `type` contact/bug_report) pra
  ambos: `/contato` (formulário normal, exige login) e um botão
  flutuante "Reportar erro" em TODA página (`base.html`) que
  autopreenche URL/nome da página via JS no momento do clique — só a
  descrição é digitada. Admin responde em `/admin/tickets` (nível
  Admin, não precisa ser God Mode — é ler/responder mensagem, não
  mexer em dinheiro/privilégio), com e-mail de volta pra quem abriu
  quando há endereço pra alcançar. `page_url` client-supplied nunca
  vira open-redirect (só o PATH é reaproveitado no redirect de volta
  — ver `_safe_redirect_target()` em `app/routers/support_routes.py`).
  Ver `AI_CHANGELOG.md` de 19/09/2026 pra detalhe completo. 9 testes
  novos, suíte completa **231 passed, 7 skipped**.
- Toda entidade nova precisa expor dados anonimizados ao Data
  Analytics — **não verificado nesta rodada** (não é uma tela nova pra
  construir, é uma auditoria contra `/admin/analytics`; ficou de fora
  do escopo confirmado com o Daniel em 19/09/2026, que priorizou os
  dois itens acima).
- Sessão expira após 24 h de inatividade — **já implementado**
  (`CLAUDE.md` §2.3); não reverificado nesta rodada.

### P7 - Ideias deliberadamente futuras

**Fonte:** 190 e 253.

- “Implementar um encontro por ano? Quando tivermos 1000 inscritos pagantes?”
- “Adicionar uma área no perfil.”

Estes itens não têm especificação suficiente. Manter como descoberta/decisão,
sem iniciar implementação.

### P99 - Revisão final de código (só depois de terminar TODA a to-do list)

**Fonte:** decisão do Daniel em 18/09/2026, ao lado da discussão do P3.E.

- **Bloqueio de anúncio para não cadastrado, com camada borrada por cima
  (blur) + pop-up de login/registro.** Ideia: em vez do anônimo conseguir
  abrir o anúncio normalmente (mesmo com campos escondidos, como está hoje
  — ver P3 "Ajuste confirmado em 18/09/2026"), a página mostra os detalhes
  do anúncio por trás de uma camada semitransparente/borrada (CSS
  `backdrop-filter: blur(...)` ou overlay), com um pop-up na frente:
  "Registre-se ou faça login para ver!" e os links correspondentes. Serve
  pra quando a pessoa recebe o link (ex: pelo WhatsApp via convite
  express) e precisa logar ou se cadastrar pra ver de verdade — reforça a
  função de aquisição do convite express.
  - **ENTREGUE em 19/09/2026.** Daniel escolheu "P99 final review pass"
    como próximo passo; escopo confirmado via AskUserQuestion antes de
    qualquer código (blur+pop-up só pra vaga listings, unificando
    `anon_teaser` + o ramo "anon" do `lock_reason` num gate só). Ver
    `app/templates/listing_detail.html` (bloco `{% if anon_teaser %}`
    dentro de `{% if lock_reason %}`) e as regras `.anon-gate*` em
    `app/static/css/style.css`. Importante: o blur em si é decorativo — só
    o trecho de descrição já público (120 caracteres) mais duas barras
    falsas, nenhum dado novo é enviado ao anônimo; os campos que já eram
    omitidos no servidor (Cachê/venue/data/tipo de voz/Estado/Ensemble)
    continuam omitidos, o contato continua gated por
    `can_view_direct_contact` (que já exige `user` logado). Self-ad
    listings e o caso "unverified" mantêm o `.locked-box` antigo, sem
    mudança. Detalhe técnico: `anon_teaser` e `lock_reason == "anon"` já
    eram logicamente idênticos (ambos `user is None`, um só restrito ao
    tipo vaga) — não foi preciso criar variável nova, só ramificar o
    template existente. Ver `AI_CHANGELOG.md` de 19/09/2026 pro detalhe
    completo.
  - Ainda em aberto (não fazia parte do escopo confirmado com Daniel):
    espalhar esse mesmo padrão de pop-up de login pra outras funções que
    hoje só checam `if not user: redirect /login` sem camada visual —
    o Daniel mencionou que pode valer pra "toda função que necessite de
    login", não só anúncios. Maior que este item; avaliar como tarefa
    própria se/quando o Daniel quiser retomar.

- **Critério FIXO confirmado em 18/09/2026 — esconder informação "de
  assinante" em TODO lugar, não só na página do anúncio.** Correção sobre
  o P3.E: eu tinha deixado o Cachê visível pra anônimo em `/board` (lista
  pública) porque só tinha sido pedido explicitamente esconder em
  `/listings/{id}`. Daniel corrigiu: a regra é geral — **qualquer
  informação que hoje é escondida de quem não tem conta (Cachê, venue,
  data exata, tipo de voz, Estado — a mesma lista do `anon_teaser` do P3)
  deve ficar escondida em TODOS os lugares onde ela aparece**, não só na
  página individual do anúncio. Isso inclui pelo menos `/board` (lista
  pública, hoje mostra Cachê/tipo de voz/repertório sem gate nenhum) e
  qualquer card/listagem futura que mostre anúncio pra visitante sem
  login. **Tratar isso como critério fixo daqui em diante** — todo pacote
  novo que exibir dado de anúncio já precisa nascer respeitando essa
  regra, não só o board existente.
  - **ENTREGUE em 19/09/2026, junto com o P99.10 acima.** Escopo
    confirmado via AskUserQuestion: "esconder leve, como antes" —
    `/board` agora omite tipo de voz e Cachê (server-side, sem
    renderizar) pra visitante anônimo num card de vaga listing, igual
    já fazia `anon_teaser` na página de detalhe; repertório continua
    visível (nunca esteve na lista de campos escondidos). Sem overlay
    por card — foi a opção deliberadamente mais simples que a versão
    blur+pop-up da página de detalhe. Ver `app/templates/board.html`.
    Não sobrou nenhum outro lugar mostrando dado de vaga pra anônimo
    além de board e listing_detail nesta revisão.

- **"Documento financeiro permanente da plataforma" (movido do P4 em
  18/09/2026).** O bullet-fonte original do Rechnungmaker mencionava um
  terceiro fluxo além do Avulso e do Match-Rechnungen, chamado
  "documento financeiro permanente da plataforma" — nunca ficou claro o
  que isso queria dizer (não é o PDF Avulso stateless, nem o rascunho
  criptografado do Match). Perguntado de novo ao Daniel na Etapa 3, ele
  respondeu que não lembra mais o que a ideia original significava
  ("Mande isso para P99 pq não lembro"). Fica registrado aqui só pra não
  se perder: se algum dia isso voltar à cabeça do Daniel (ou aparecer de
  novo no documento-fonte), essa é a pendência que faltou esclarecer.
  Contradiz a política de Zero-Storage (Seção 2 do `CLAUDE.md`) manter
  qualquer documento financeiro "permanente" salvo em disco/banco, então
  antes de implementar qualquer coisa aqui é preciso alinhar com o
  Daniel se ele quer abrir exceção à regra ou se é outra coisa
  (ex: só um histórico de metadados, sem o PDF em si).

## Fluxo operacional para Codex e Claude

1. **Escolher:** selecionar um único pacote e registrar no topo de
   `AI_CHANGELOG.md` o objetivo e os parágrafos-fonte.
2. **Especificar:** para itens sem divergência, transformar somente aquele
   pacote em checklist de aceitação. Para divergências, parar e pedir decisão.
3. **Mapear impacto:** listar rotas, dados, telas, permissões, traduções,
   Admin/Red Zone, analytics e testes afetados antes de editar.
4. **Implementar pequeno:** uma mudança coerente por vez; sem aproveitar para
   refatorar áreas não relacionadas.
5. **Validar:** testes existentes, novos testes da regra e navegador em desktop
   e celular quando houver interface.
6. **Registrar:** atualizar `AI_CHANGELOG.md` com resultado verificável,
   arquivos alterados, migração se houver, testes e próxima etapa.
7. **Revisar:** o outro agente começa pelo changelog e por este plano, revisa o
   pacote concluído e só então escolhe o próximo.

## Ordem recomendada de execução

1. P0: correções que impedem uso, e-mails e acesso.
2. P1: testes de navegador e base visual consistente.
3. P2: dados de perfil/diretório que P3 usa.
4. P3: vagas múltiplas, convites e Matches.
5. P4: Rechnungmaker, porque depende do Match estável.
6. P5: economia, vouchers e assinatura, depois que as ações geradoras de Notas
   estiverem definidas.
8. P6: controles completos, analytics e suporte em paralelo apenas quando as
   entidades correspondentes existirem.

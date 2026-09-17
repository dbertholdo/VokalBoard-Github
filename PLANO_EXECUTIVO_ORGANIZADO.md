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
  largura de celular.

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
- Corrigir envio imediato de confirmação/recuperação e definir os relatórios
  diário, semanal e mensal mencionados.
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
- Implementar convite com validade de 48 h, e-mail de notificação e expiração
  antecipada quando faltarem 6 h para o evento.
- Implementar logística do anúncio: Fahrkosten, Partitur vorhanden e Probenplan
  vorhanden, todos opcionais como descritos.
- Após Match concluído: avaliação de 1 a 5 estrelas, badges qualitativas,
  lembrete e janela de 14 dias.
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

### P5 - Notas, loja, assinatura e economia

**Fonte:** 20-21, 25-28, 35, 111, 236-237, 239, 252, 255-266, 268, 270-274.

- Definir o preço dos demais serviços. A urgência está decidida: 1 token
  semanal e compra por Notas equivalente a 2 Euros quando o saldo de tokens é 0.
  A fonte usa “1 Nota = 1 Euro/Franco” e também pede equivalência pela
  localização da conta.
- Notas nunca podem ser convertidas em dinheiro real; registrar essa regra nos
  termos de compra e uso.
- Reunir recompensas: login diário após 5 min, perfil 100% completo, referral,
  aceite de urgência, gasto da primeira Nota, impulso de perfil e demais badges.
- Loja de Notas, vouchers, selo confiável, urgências pagas e Rechnungen extras
  precisam de extrato global, extrato por usuário e controles no Admin.
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
- Hall da Fama deve mostrar link de convite, botão “Convidar um amigo!” e foto
  de quem convida no link, se viável.

### P6 - Administração, suporte, segurança e dados

**Fonte:** 9, 17, 21-22, 38, 191-192, 230-232, 236, 238, 241, 243-247,
251, 265, 268-270, 274, 276-277.

- God Mode: privilégios, vouchers, envio segmentado de e-mails, loja de Notas,
  registros grátis e Capitalism Mode como último botão da página.
- Novo Menu de E-mails: incluir disparo para pessoas sem assinatura ativa com
  promoção, botão “Notificação por Email: On/Off”, desconto e validade de link
  personalizado. Criar editor de e-mails no mesmo espírito do editor de posts
  e manter uma assinatura padrão salva. O On/Off é global, para que a campanha
  possa ser desativada por toggle.
- Admin: mini card ao gerenciar perfil, lista de usuários ativos filtrável,
  adicionar/remover dias, reembolso, resposta a denúncias e notificação ao
  usuário quando denúncia for aceita.
- Criar “Fale conosco” como ticket por inbox e “Reportar erro” em todas as
  páginas com dados da página e descrição obrigatória.
- Toda entidade nova precisa expor dados anonimizados ao Data Analytics.
- Sessão expira após 24 h de inatividade.

### P7 - Ideias deliberadamente futuras

**Fonte:** 190 e 253.

- “Implementar um encontro por ano? Quando tivermos 1000 inscritos pagantes?”
- “Adicionar uma área no perfil.”

Estes itens não têm especificação suficiente. Manter como descoberta/decisão,
sem iniciar implementação.

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

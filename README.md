# Maestro & Cantor

Quadro de avisos (bulletin board) para conectar cantores e maestros na
Alemanha — inspirado em ideias como Audition Oracle/Theapolis, mas no
formato simples de um Craigslist: as pessoas publicam o que procuram
(ou o que oferecem) e navegam/filtram os anúncios de outras pessoas.

Este projeto foi montado como um exercício prático de **SQL** e
**desenvolvimento web**. As decisões técnicas abaixo foram feitas de
propósito para maximizar aprendizado, não "produtividade máxima".

## Stack

- **Backend:** Python + [FastAPI](https://fastapi.tiangolo.com/)
- **Banco de dados:** PostgreSQL, acessado com **SQL puro** via
  SQLAlchemy `text()` (sem ORM) — veja `app/database.py` e os
  arquivos em `app/routers/`. A ideia é você ler/escrever SQL de
  verdade: `SELECT`, `JOIN`, `WHERE` dinâmico, `INSERT ... RETURNING`.
- **Frontend:** HTML server-side renderizado com Jinja2 (sem
  framework JS) + CSS simples. Suficiente para o MVP, fácil de trocar
  depois por React/Vue se você quiser evoluir.
- **Autenticação:** sessão via cookie assinado (`SessionMiddleware`
  do Starlette) + senha com hash bcrypt.
- **Idiomas:** alemão e inglês, com um seletor no cabeçalho. Veja
  `app/i18n.py` (dicionário de traduções) e `app/render.py` (injeta a
  função `t()` e o idioma atual em todo template). O idioma escolhido
  fica salvo num cookie.
- **Deploy:** Docker + docker-compose para rodar localmente; instruções
  para Railway/Render abaixo.
- **CSRF:** proteção manual via "synchronizer token" — veja a seção
  dedicada mais abaixo.
- **E-mail:** confirmação de cadastro por e-mail e recuperação de senha,
  com um backend de e-mail plugável (`console` para desenvolvimento,
  `resend` para produção) — veja `app/email.py`.

## Estrutura do projeto

```
maestro-cantor/
├── app/
│   ├── main.py                 # cria o app FastAPI, monta rotas
│   ├── database.py             # conexão + helpers de SQL puro
│   ├── auth.py                 # hash de senha, sessão do usuário
│   ├── i18n.py                  # dicionário de traduções DE/EN
│   ├── render.py                # wrapper do Jinja2Templates com t()/lang
│   ├── routers/
│   │   ├── auth_routes.py      # /register, /login, /logout, verificação de
│   │   │                       #   e-mail, esqueci/redefinir senha
│   │   ├── listings_routes.py  # /, /listings/..., busca/filtro
│   │   ├── profile_routes.py   # /profile (editar), /users/{id} (público)
│   │   └── messages_routes.py  # /messages, caixa de entrada/enviados/lixeira
│   ├── csrf.py                  # proteção CSRF (synchronizer token)
│   ├── email.py                  # envio de e-mail (console/Resend)
│   ├── templates/              # HTML (Jinja2)
│   └── static/css/style.css
├── db/
│   ├── schema.sql               # DDL: CREATE TABLE, índices (já inclui as cidades)
│   ├── seed_cities.sql          # cidades DE/AT/CH (gerado, ver scripts/)
│   └── seed_sample_data.sql     # dados de exemplo (opcional)
├── scripts/
│   └── generate_cities_seed.py  # regenera db/seed_cities.sql a partir do GeoNames
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Modelo de dados (schema)

- `voice_types` — tabela de apoio, simplificada para as 4 categorias
  pedidas: Soprano, Alto, Tenor, Baixo. No cadastro, a pessoa escolhe
  diretamente uma dessas 4 opções OU "Dirigent(in)" (maestro/maestrina) —
  essa escolha única já define tanto o `role` quanto o `voice_type_id`.
- `users` — cantores e maestros na mesma tabela, diferenciados por `role`
- `singer_profiles` / `conductor_profiles` — dados extras 1:1 com `users`,
  incluindo `bio` (biografia, limitada a 1000 caracteres por um `CHECK`
  no banco — veja `db/schema.sql`)
- `singer_composer_tags` — hashtags de compositores que o(a) cantor(a)
  já cantou (até 10 por pessoa, limite aplicado na aplicação). É uma
  tabela separada — não uma coluna de array — de propósito, para você
  praticar JOIN/GROUP BY (ex: "quais compositores aparecem mais na
  plataforma?")
- `listings` — os anúncios do quadro de avisos, com `listing_type`:
  - `seeking_singer` — maestro procurando cantor(a)
  - `seeking_conductor` — cantor(a) procurando regência/oportunidade
  - `singer_available` — cantor(a) anunciando disponibilidade
  - `conductor_available` — maestro anunciando disponibilidade

- `singer_audio_links` — links externos (YouTube, SoundCloud, etc.) para
  "Audiobeispiele" do(a) cantor(a), até 3 por pessoa. **Não armazenamos
  arquivo de áudio nenhum** — de propósito: guardar arquivos de mídia
  exigiria object storage (S3/R2/Hetzner Object Storage) e mais
  infraestrutura, então a solução mais simples (e mais que suficiente
  para o caso de uso) é a pessoa colar o link de um áudio já hospedado
  em outro lugar.
- `email_verification_tokens` / `password_reset_tokens` — tokens de uso
  único e com prazo de validade para confirmar e-mail (48h) e redefinir
  senha (2h). Veja a seção "Verificação de e-mail e recuperação de senha".
- `messages` — sistema de mensagens interno entre usuários (veja a seção
  dedicada abaixo).
- `profile_views` — log write-only de visitas a perfis (veja a seção
  "Contagem de visitas a perfis").
- `cities` — cidades reais da Alemanha, Áustria e Suíça (~1.270, fonte
  GeoNames, população aproximada ≥ 15.000), cada uma já amarrada ao
  seu estado/cantão. Alimenta o select em cascata **País > Estado >
  Cidade** usado no cadastro, no perfil e no formulário de anúncio —
  em vez de cidade como texto livre, o que evitava que "München",
  "Munich" e "Muenchen" contassem como lugares diferentes na hora de
  cruzar cantores e maestros da mesma região. Nem toda cidade pequena
  está na lista; por isso sempre existe um "Minha cidade não está na
  lista" que libera texto livre. Os dados vêm de
  `db/seed_cities.sql`, gerado por `scripts/generate_cities_seed.py`
  (rode `pip install geonamescache --break-system-packages` e o
  script de novo só se quiser mudar o corte de população ou os dados
  ficarem desatualizados — não é uma dependência do app em produção).

Cada cantor(a) e maestro(a) tem uma página de perfil pública em
`/users/{id}` (nome, cidade, tipo de voz ou coro/orquestra, biografia,
hashtags de compositores, links de áudio e anúncios ativos) e pode editar
seus próprios dados em `/profile`.

## Home personalizada por papel (cantor x maestro)

A página inicial (`/`) muda de comportamento conforme quem está logado,
para que cantores não fiquem vendo o que interessa a maestros e
vice-versa:

- **Cantor(a) logado(a):** vê por padrão só vagas (`seeking_singer`)
  da própria categoria de voz — um tenor não vê vagas de contralto,
  por exemplo — mas pode ajustar os filtros (tipo de voz, cidade,
  busca) a qualquer momento.
- **Maestro(a) logado(a):** vê por padrão cantores disponíveis
  (`singer_available`), com filtros por tipo de voz, cidade **e
  hashtag de compositor** (ex: buscar só cantores que já cantaram
  Bach).
- **Visitante não logado** (ou qualquer usuário com `?board=all`): vê
  o quadro de avisos completo, sem filtro de papel — útil antes de
  criar conta, ou pra qualquer um querer ver tudo.

Anúncios do tipo "procura-se cantor(a)" (`seeking_singer`) — que tanto
maestros quanto outros cantores podem publicar, já que às vezes um(a)
cantor(a) também procura colegas para um gig — têm campos extras
obrigatórios: **Obra**, **Cidade**, **Cachê**, e **Tipo de voz** (com
opção explícita de "todas as vozes"); o campo **Onde/Ort** (igreja,
sala) é opcional. Quem publicou um anúncio pode editá-lo depois em
`/listings/{id}/edit`.

O schema completo com comentários está em `db/schema.sql` — vale a
pena ler linha por linha, é a melhor forma de entender o "porquê" de
cada `FOREIGN KEY` e índice.

## Rodando localmente com Docker (recomendado)

Pré-requisito: [Docker](https://www.docker.com/) instalado.

```bash
cd maestro-cantor
docker compose up --build
```

Isso sobe dois containers:
1. `db` — PostgreSQL, já inicializado com `schema.sql` + dados de exemplo
2. `web` — a aplicação FastAPI, em http://localhost:8000

Usuários de exemplo (senha para todos: `senha123`):
- `sofia.soprano@example.com` (cantora, soprano)
- `tobias.tenor@example.com` (cantor, tenor)
- `anna.dirigentin@example.com` (maestrina)
- `markus.dirigent@example.com` (maestro)

Para parar: `Ctrl+C` e depois `docker compose down` (adicione `-v` para
também apagar os dados do banco e começar do zero).

## Rodando sem Docker (Python local + Postgres local)

```bash
# 1. Crie um banco PostgreSQL local chamado maestro_cantor
createdb maestro_cantor

# 2. Rode o schema
psql maestro_cantor < db/schema.sql
psql maestro_cantor < db/seed_sample_data.sql   # opcional

# 3. Configure o .env
cp .env.example .env
# edite o .env com a DATABASE_URL do seu Postgres local

# 4. Instale as dependências
python -m venv venv
source venv/bin/activate  # no Windows: venv\Scripts\activate
pip install -r requirements.txt

# 5. Rode o servidor
uvicorn app.main:app --reload
```

Acesse http://localhost:8000

## Estrutura de páginas (freemium)

- **`/`** — tela de boas-vindas. Logado, mostra "Bem-vindo(a), {nome}" e até
  5 anúncios que combinam com o perfil (cantor: vagas `seeking_singer` da
  própria categoria de voz; maestro(a): vagas `seeking_conductor`),
  priorizando a própria cidade. Sem login, mostra um teaser com as 5
  vagas mais recentes (só título/cidade/tipo, sem descrição) e botões de
  cadastro/login.
- **`/board`** — o quadro de avisos completo, com todos os filtros
  (busca livre, cidade, país, tipo de voz, tipo de anúncio, hashtag de
  compositor). Aberto para qualquer visitante, logado ou não.
- **`/listings/{id}`** e **`/users/{id}`** — **modelo freemium**: sem
  login dá pra ver que o anúncio/perfil existe (título, cidade, badge,
  bolinha de status), mas a descrição completa, os dados de contato, a
  biografia, os hashtags e os links de áudio só aparecem para quem tem
  conta. Isso é decidido no backend (`locked = user is None` em
  `listings_routes.py`/`profile_routes.py`), não só escondido via CSS —
  então não dá pra "ver escondendo o JS".
- **`/profile`** — editar o próprio perfil.
- **`/my-listings`** — publicar e editar os próprios anúncios.
- **`/messages`** — mensageiro interno.

## Filtro por país

Anúncios agora têm um campo `country` (`DE`/`AT`/`CH`/`OTHER`), com
`DE` como padrão. O filtro por país em `/board` existe porque cantores e
maestros no Deutschsprachraum circulam entre os três países o tempo
todo — ver a seção de análise de mercado que conversamos no chat.

## Filtro por período (Zeitraum)

Em `/board` dá pra filtrar por intervalo de data (`date_from`/`date_to`,
comparados com `event_date`) — o caso de uso é literalmente "não tenho
nada marcado em agosto, me mostra o que existe entre 1º e 31/08".
Diferença importante de comportamento: escolher um período explícito
**substitui** o filtro padrão de "esconder eventos passados" — se você
escolher um intervalo que já passou, os anúncios daquele intervalo
aparecem mesmo assim (a pessoa está pedindo por aquele período
especificamente, então faz sentido mostrar mesmo que seja passado).
Anúncios sem `event_date` (ex: "cantor disponível", sem data marcada)
não têm como combinar com um período e ficam de fora quando esse
filtro está ativo.

## Indicador de status do evento (bolinha colorida)

Ao lado do título de qualquer anúncio com uma data de evento
(`event_date`), aparece uma bolinha colorida:

- 🟢 **verde** — evento ainda vai acontecer (mais de 7 dias)
- 🟡 **amarela** — evento acontece nos próximos 7 dias
- 🔴 **vermelha** — evento já passou

Isso é calculado **na hora da consulta**, com um `CASE` em SQL comparando
`event_date` com `CURRENT_DATE` (veja `EVENT_STATUS_SQL` em
`app/routers/listings_routes.py`) — não é uma coluna gravada no banco.
Essa é uma escolha deliberada: como o status depende só da data de hoje,
calcular na consulta evita a necessidade de um job noturno (cron) para
manter uma coluna "status" sempre atualizada. Anúncios sem `event_date`
não mostram bolinha nenhuma.

## Verificação de e-mail e recuperação de senha

Ao se cadastrar, a pessoa recebe um e-mail com um link de confirmação
(`/verify-email?token=...`), válido por 48 horas. Enquanto o e-mail não
é confirmado:

- Aparece um aviso no topo do site com um botão para reenviar o e-mail
  de confirmação.
- A pessoa **não consegue publicar anúncios nem enviar mensagens** (mas
  pode navegar, filtrar e editar o próprio perfil normalmente).

A recuperação de senha (`/forgot-password` → `/reset-password`) segue o
mesmo padrão de token de uso único, válido por 2 horas. Por segurança
contra enumeração de e-mails cadastrados, `/forgot-password` sempre
mostra a mesma mensagem de confirmação, exista ou não uma conta com
aquele e-mail.

Em desenvolvimento, os e-mails não são enviados de verdade — eles são
só impressos no log do servidor (backend `console`, o padrão). Para
enviar e-mails de verdade em produção, configure no `.env`:

```
EMAIL_BACKEND=resend
RESEND_API_KEY=sua-chave-aqui
EMAIL_FROM="Maestro & Cantor <onboarding@resend.dev>"
```

O projeto usa a API do [Resend](https://resend.com/) como exemplo (tem
plano gratuito generoso e API simples via HTTP), mas `app/email.py` foi
escrito como uma função só (`send_email`), então trocar por outro
provedor (SendGrid, Mailgun, Amazon SES) é questão de reescrever essa
função.

## O que é CSRF e como este projeto se protege

**CSRF (Cross-Site Request Forgery)** é um ataque em que um site
malicioso faz o navegador da vítima enviar, sem ela perceber, uma
requisição para *outro* site (aqui, o Maestro & Cantor) aproveitando que
o navegador já manda automaticamente os cookies de sessão daquele site
em toda requisição — inclusive as disparadas por uma página diferente.

Exemplo concreto: você está logado no Maestro & Cantor. Sem perceber,
visita `site-malicioso.com`, que tem um formulário invisível apontando
para `POST maestro-cantor.de/listings/42/delete`. Se o servidor só
checasse "existe uma sessão válida?", o navegador enviaria seu cookie de
sessão automaticamente, e o ataque funcionaria — seu anúncio seria
apagado sem você ter clicado em nada no site de verdade.

A defesa usada aqui é o padrão **"synchronizer token"** (veja
`app/csrf.py`):

1. Ao carregar qualquer página com formulário, o servidor gera (ou
   reaproveita) um token aleatório e o guarda na sessão do usuário.
2. Esse mesmo token é colocado como campo escondido (`<input type="hidden"
   name="csrf_token">`) em todo formulário.
3. Em todo `POST`, o servidor compara o token que veio no formulário com
   o que está guardado na sessão. Se não bater (ou não existir), a
   requisição é rejeitada com erro 400.

Um site malicioso não tem como ler o token da sua sessão (ele não roda
no seu domínio, e o token não é um cookie — é um valor dentro do HTML da
página), então não consegue montar um formulário forjado que passe nessa
checagem. Testamos isso na prática: um `POST` com `csrf_token` errado ou
ausente é rejeitado com HTTP 400, mesmo com uma sessão válida.

## Sistema de mensagens interno

Em vez de expor o e-mail de todo mundo publicamente (o que já existia
antes), agora dá pra mandar mensagem direto pela plataforma, pelo botão
"Enviar mensagem" no perfil público ou no anúncio de alguém. O sistema
tem:

- **Caixa de entrada** (`/messages`) e **Enviados** (`/messages/sent`).
- **Contador de não lidas** no menu, ao lado de "Nachrichten/Messages".
- **Lixeira** (`/messages/trash`) e **"Esvaziar lixeira"**.

Cada mensagem tem **duas colunas de status** (`sender_status` e
`recipient_status`, cada uma `active` ou `trashed`) — uma para o remetente,
outra para o destinatário — porque jogar uma mensagem no lixo é uma ação
pessoal: se você apaga uma conversa da sua lixeira, isso não deveria
afetar o que a outra pessoa vê do lado dela.

**Simplificação didática, de propósito:** o botão "esvaziar lixeira" faz
um `DELETE` de verdade na linha da mensagem — o que remove a mensagem
também do lado da outra pessoa, mesmo que ela não tenha jogado a dela
fora. Um sistema "de verdade" só apagaria a linha quando **ambos os
lados** estivessem com status `trashed` (ou usaria uma coluna
`deleted_at` por lado, sem nunca fazer `DELETE` de fato). Deixei essa
simplificação de propósito como um próximo exercício de SQL: dá pra
mudar a query de `empty_trash` em `app/routers/messages_routes.py` para
só apagar quando `sender_status = 'trashed' AND recipient_status =
'trashed'`, e criar uma keyword tipo "ocultar da minha lista" separada
de "apagar de verdade".

## Contagem de visitas a perfis (métrica privada)

Toda visita a um perfil público (`/users/{id}`) grava uma linha em
`profile_views` (`profile_user_id`, `viewer_user_id` — nulo se
anônimo, `viewed_at`). **De propósito, isso não aparece em lugar nenhum
da interface** — nem para o dono do perfil — porque foi pedido como uma
métrica só para consulta direta no banco, tipo um Google Analytics
bem simples e caseiro. Exemplo de consulta:

```sql
SELECT profile_user_id, COUNT(*) AS views
FROM profile_views
GROUP BY profile_user_id
ORDER BY views DESC;
```

## Praticando SQL com este projeto

Algumas sugestões de exercícios usando o `psql` direto no banco
(`docker compose exec db psql -U maestro_user -d maestro_cantor`):

1. Liste todos os anúncios ativos com o nome de quem postou (JOIN simples).
2. Conte quantos anúncios existem por `listing_type` (GROUP BY + COUNT).
3. Liste cantores por tipo de voz, incluindo os que ainda não têm
   nenhum anúncio publicado (LEFT JOIN).
4. Ache a cidade com mais anúncios ativos nos últimos 30 dias.
5. Usando `singer_composer_tags`, ache os 5 compositores mais citados
   entre todos os cantores (JOIN + GROUP BY + COUNT + ORDER BY + LIMIT).
6. Em `profile_views`, ache quem são os 5 perfis mais visitados nos
   últimos 30 dias (GROUP BY + `WHERE viewed_at > now() - interval '30
   days'`).
7. Corrija a simplificação da lixeira de mensagens: reescreva a query de
   `empty_trash` (`app/routers/messages_routes.py`) para só apagar a
   linha quando **os dois lados** (`sender_status` e `recipient_status`)
   estiverem `'trashed'`.
8. Ache pares de usuários que trocaram mensagens mas nunca tiveram
   contato via `listings` (JOIN entre `messages` e `listings`,
   comparando `sender_id`/`recipient_id` com `author_id`).

## Deploy (Railway ou Render)

Ambos suportam "deploy a partir de um Dockerfile" de forma bem parecida.

### Railway

1. Crie um projeto novo → "Deploy from GitHub repo" (suba este projeto
   para um repositório seu no GitHub primeiro).
2. Adicione um serviço PostgreSQL pelo botão "New" → "Database" →
   "PostgreSQL". O Railway gera uma `DATABASE_URL` automaticamente.
3. No serviço da aplicação (o que usa o Dockerfile), configure as
   variáveis de ambiente:
   - `DATABASE_URL`: copie da aba "Variables" do serviço Postgres,
     mas troque o prefixo `postgresql://` por `postgresql+psycopg2://`
   - `SECRET_KEY`: gere uma com `python -c "import secrets; print(secrets.token_hex(32))"`
4. Depois do primeiro deploy, rode o schema no banco do Railway. Você
   pode usar o botão "Connect" do Postgres no painel do Railway para
   pegar a string de conexão e rodar:
   ```bash
   psql "<connection-string-do-railway>" < db/schema.sql
   ```

### Render

1. "New +" → "Web Service" → conecte seu repositório GitHub.
2. Render detecta o `Dockerfile` automaticamente.
3. "New +" → "PostgreSQL" para criar o banco gerenciado.
4. No Web Service, em "Environment", adicione `DATABASE_URL` (com
   `postgresql+psycopg2://`) e `SECRET_KEY`.
5. Rode o schema apontando para a "External Database URL" que o Render
   mostra na página do banco:
   ```bash
   psql "<external-database-url>" < db/schema.sql
   ```

Em ambos os casos, o healthcheck em `/health` pode ser usado pela
plataforma para saber se a aplicação está de pé.

## Domínio e hospedagem (indo além do subdomínio grátis)

Railway/Render te dão um subdomínio tipo `seu-app.up.railway.app` de
graça — ótimo para testar. Para um domínio próprio (`maestro-cantor.de`,
por exemplo):

- **Registrar o domínio:** recomendo separar "onde registro o domínio"
  de "onde hospedo o app" — dá mais liberdade para trocar de hospedagem
  sem perder o domínio.
  - [INWX](https://www.inwx.com/) — registradora alemã, boa opção para
    domínios `.de` (inclusive exige alguns dados de contato na Alemanha
    para `.de`, o que pode pesar na decisão do próximo tópico), preços
    justos, painel em alemão/inglês.
  - [Porkbun](https://porkbun.com/) ou [Namecheap](https://www.namecheap.com/) —
    boas opções para domínios genéricos (`.com`, `.io`, `.app`), preço
    transparente, sem "upsell" agressivo.
- **Hospedagem:** você já tem Railway/Render funcionando com pouquíssima
  configuração (bom para focar em aprender SQL/web, não DevOps). Se mais
  pra frente você quiser aprender mais infraestrutura (o que conversa
  bem com a sua trilha de Cloud/AWS no curso de tech consultant), vale
  considerar a [Hetzner Cloud](https://www.hetzner.com/cloud/) — provedor
  alemão, VPS bem barato, boa latência para usuários na Alemanha, mas
  exige que você mesmo configure o servidor (Docker, HTTPS com Let's
  Encrypt/Caddy, backups).
  - Domínio + Render/Railway = menor esforço.
  - Domínio + Hetzner = mais controle e mais aprendizado de ops, custo
    mensal menor a médio/longo prazo.

## Site voltado à Alemanha, mas operado (mais tarde) por alguém no Brasil

Você perguntou se dá pra manter o site operando para o público alemão
mas registrado/administrado no Brasil, pensando em passar a operação
para o seu irmão, que não mora na Alemanha. Não sou advogado, então
isto é só um mapa do terreno — não substitui uma consulta jurídica real
antes de lançar algo com dados de usuários de verdade:

- **Tecnicamente**, sim: nada impede que um site hospedado ou de
  titularidade no Brasil sirva usuários na Alemanha — isso é comum.
- **Impressumspflicht (aviso legal obrigatório):** sites acessíveis na
  Alemanha com qualquer caráter comercial/profissional precisam de um
  "Impressum" (identificação do responsável, endereço de contato, etc).
  Essa obrigação está hoje no *Digitale-Dienste-Gesetz* (DDG, que
  substituiu a antiga TMG). Não exige necessariamente que o responsável
  more na Alemanha, mas precisa ser uma forma de contato válida e
  alcançável — vale confirmar com um advogado especializado em direito
  digital alemão (*IT-Recht*) o que conta como suficiente no seu caso.
- **GDPR/DSGVO:** como a plataforma coleta dados pessoais (nome, e-mail,
  telefone, biografia) de pessoas na Alemanha/UE, o GDPR se aplica
  independentemente de onde a empresa/pessoa responsável está baseada
  (efeito extraterritorial, Art. 3). Se quem administra o site não
  estiver estabelecido na UE, o Art. 27 do GDPR geralmente exige nomear
  um **representante na UE** — a menos que o tratamento de dados seja
  ocasional e de baixo risco, o que dificilmente se aplica a uma
  plataforma de cadastro contínuo como essa.
- **Na prática**, os caminhos mais comuns para esse tipo de situação
  costumam ser: (a) manter você (residente na Alemanha) como responsável
  legal/Impressum enquanto seu irmão cuida da operação do dia a dia, ou
  (b) contratar um serviço de representante GDPR na UE quando/se a
  responsabilidade formal passar de fato para o Brasil. Vale muito a
  pena validar isso com um advogado antes de sair do modo "projeto de
  estudo" para "site com usuários reais" — ferramentas como
  [eRecht24](https://www.e-recht24.de/) ou uma *IT-Recht Kanzlei* geram
  Impressum/Datenschutzerklärung e também orientam sobre isso.

## Localização em cascata (País > Estado), tipo de vaga e filtros

O formulário de anúncio agora pede **Estado/Bundesland/Kanton**, além de
País e Cidade — obrigatório, junto com o resto do endereço (segue o
mesmo padrão de "obrigatório na aplicação, opcional no schema" que a
Cidade já usava). A lista de estados (`STATE_OPTIONS`, em
`app/routers/listings_routes.py`) é uma cascata simples em JavaScript:
ao trocar o País, o `<select>` de Estado é repopulado (para "Outro
país" vira texto livre). Não existe uma terceira cascata para Cidade —
isso exigiria uma base geográfica completa (tipo GeoNames), o que
ficou fora do escopo por enquanto; Cidade continua sendo texto livre.

O anúncio também ganhou um campo **Solo / Coro / Ambos**
(`ensemble_type`), pensado pra quem procura reforço de naipe vs. quem
procura um cantor(a) solista vs. os dois. Ambos os campos entraram
como filtros em `/board`.

## Redes sociais no perfil

Em `/profile`, cada pessoa pode adicionar (opcional) até um link por
plataforma: Website, Facebook, Instagram, Twitter, WhatsApp — tabela
`user_social_links`, uma linha por plataforma (`UNIQUE(user_id,
platform)`). No perfil público (`/users/{id}`), em vez do link cru,
aparece um botão com só o nome da plataforma ("Instagram",
"Facebook"...) pra não poluir a tela — a URL completa fica por trás do
`href`. Só links `http(s)://` são aceitos; qualquer outra coisa colada
ali é simplesmente ignorada ao salvar.

## Avaliação por estrelas (privada)

Em `/users/{id}`, qualquer pessoa logada (exceto a própria dona do
perfil) pode dar uma nota de 0 a 5 estrelas + comentário opcional.
**A regra pedida foi: só quem recebeu a avaliação pode vê-la — mais
ninguém.** Isso é garantido por *onde* a query roda, não por uma
checagem de permissão: `get_my_ratings()`/`get_rating_summary()` (as
únicas funções que buscam avaliações *recebidas*) só são chamadas a
partir de `/profile` — a própria pessoa vendo o que recebeu. A rota
pública `/users/{id}` nunca chama essas funções; ela só usa
`get_rating_given()`, que é "a nota que EU already dei pra essa
pessoa" (pra pré-preencher o formulário caso eu queira atualizar).
Reavaliar a mesma pessoa faz um UPSERT (`ON CONFLICT (rater_id,
rated_id) DO UPDATE`) em vez de acumular notas repetidas.

## Arquivamento de eventos passados

Anúncios com `event_date` no passado somem por padrão de `/board` e
das sugestões da Home (mas continuam no banco, acessíveis por link
direto e visíveis em "Meus anúncios"). Assim como a bolinha de status,
isso é calculado **na consulta** (`WHERE event_date IS NULL OR
event_date >= CURRENT_DATE`), sem nenhum job/cron — o filtro
"some/aparece" sozinho conforme os dias passam. `/board?show_past=1`
reexibe tudo, inclusive o que já passou.

## Paginação

`/board` agora pagina de 20 em 20 (`LIMIT`/`OFFSET` + uma query
`COUNT(*)` separada pra saber o total de páginas) — antes a página
inteira vinha numa lista só, o que ia ficar impraticável conforme o
volume de anúncios crescesse.

## "Mensagem já enviada"

Em `/listings/{id}`, se você já mandou pelo menos uma mensagem sobre
aquele anúncio específico, aparece um aviso "Mensagem já enviada para
este anúncio". Isso **não bloqueia** reenviar — é só um lembrete pra
evitar lotar a caixa de entrada de quem postou com a mesma pergunta
várias vezes.

## Trocar senha e excluir conta (com período de recuperação)

- **`/profile/change-password`** — pede a senha atual + a nova (mínimo
  6 caracteres), reusa `verify_password`/`hash_password` de
  `app/auth.py`.
- **Excluir conta** (seção "Gefahrenzone" em `/profile`) — pede a
  senha de novo por segurança. É um **soft delete**: grava
  `deleted_at = now()` na linha do usuário em vez de apagar de
  verdade. A partir daí, `get_current_user()` e todo JOIN com autor
  (`u.deleted_at IS NULL`) passam a ignorar essa conta — ela some do
  site como se tivesse sido excluída, mas os dados continuam no banco.
  Se a pessoa tentar logar de novo dentro de 6 meses, o login detecta
  a conta desativada e manda pra `/reactivate-account`, que só exige
  confirmar a senha (sem precisar de um novo fluxo de e-mail/token).
  Passados 6 meses, um script separado
  (`scripts/purge_deleted_accounts.py`, rodado via cron do sistema ou
  manualmente — **não** um job dentro do app, seguindo o mesmo
  princípio de "sem cron embutido" do resto do projeto) apaga essas
  contas definitivamente.

## Foto de perfil

Upload direto (sem serviço externo) em `/register` e `/profile` —
JPG/PNG/WebP, até 3 MB, validado por Content-Type e tamanho (ver
`app/avatars.py`). O arquivo é salvo em `app/static/avatars/{user_id}.
{ext}`, que já é servido publicamente pelo mesmo `StaticFiles` do
resto do CSS/JS (`/static/...`), sem precisar de nenhum mount novo.
**Ponto de atenção:** em plataformas como Railway/Render (free tier)
o disco do container é efêmero — um novo deploy apaga essas fotos.
Aceitável para um beta pequeno; se o projeto crescer, o próximo passo
é migrar para um object storage (S3, Cloudflare R2, etc.).

## Alerta de anúncio compatível

Quando alguém publica um anúncio `seeking_singer` ou `seeking_conductor`,
todo mundo com o perfil compatível (voz certa, ou papel de maestro(a))
e que não desligou os alertas recebe um e-mail na hora — não um resumo
diário, é imediato mesmo (`app/notifications.py`). Roda como uma
`BackgroundTask` do FastAPI: o anúncio é publicado e a pessoa é
redirecionada na hora, os e-mails saem depois, em segundo plano, sem
atrasar a resposta. Cada pessoa liga/desliga isso em `/profile`
(`users.notify_matches`, ligado por padrão).

## Favoritar anúncio

Botão "☆ Favoritar" em `/listings/{id}` (pra quem não é o autor),
listados em `/my-favorites`. Tabela simples `saved_listings` com
`UNIQUE(user_id, listing_id)` — favoritar de novo o que já está
favoritado não faz nada (`ON CONFLICT DO NOTHING`), e o `/board` marca
com uma ⭐ os anúncios já favoritados (calculado com um `EXISTS`
correlacionado direto na query da lista, sem N+1).

## Exportar meus dados

`/profile/export` — baixa um `.json` com tudo que a pessoa tem
cadastrado (perfil, anúncios, mensagens enviadas/recebidas, avaliações
dadas/recebidas, favoritos). Isso é o direito de portabilidade de
dados do GDPR (Art. 20) — deliberadamente NÃO inclui `password_hash`
(não é "seu dado" no sentido de portabilidade, é um segredo de
autenticação).

## Indicador de perfil completo

Em `/profile`, uma barra mostra quanto do perfil está preenchido
(`compute_profile_completeness()` em `app/routers/profile_routes.py`)
— foto, cidade, telefone, bio, rede social, e (pra cantores) tipo de
voz/hashtags/áudio, ou (pra maestros) nome do conjunto. Cada item vale
o mesmo peso; a mensagem reforça que um perfil mais completo passa
mais confiança pra quem visita e melhora os matches automáticos da
Home (voz/cidade/hashtags entram nesse cálculo).

## Novo visual ("quiet luxury")

O CSS foi reformulado (`app/static/css/style.css`) inspirado no estilo
(não no design literal — nada foi copiado) de sites de "premium beauty
studio": marfim/creme como fundo, bordô como cor de destaque, dourado
apagado como cor secundária, serifada (Playfair Display, via Google
Fonts) para títulos e sem serifa (Inter) para o corpo do texto. Como o
resto do site já usava variáveis CSS (`:root { --accent: ...; }`) em
vez de cores "cravadas" em cada regra, trocar a paleta inteira foi só
trocar essas variáveis — botões, badges, cartões e formulários se
adaptaram sozinhos.

## "Convide um amigo" (indicações)

Cada pessoa tem um código curto único (`users.referral_code`, gerado na
primeira vez que ela visita `/profile` — `app/referrals.py`), usado num
link tipo `/register?ref=CODE`. Quem se cadastra chegando por esse link
tem isso guardado em `users.referred_by_user_id`. Em `/profile` aparece
o link pronto pra copiar e quantas pessoas cada um já indicou.

Não existe nenhum prêmio/desconto automático por indicação (o site não
cobra nada) — é só uma forma de a própria comunidade trazer mais gente,
com o número de indicações servindo como um reconhecimento simples pra
quem indica.

## Bloquear pessoas

Em qualquer perfil público (`/users/{id}`) dá pra bloquear a pessoa
(motivo opcional), o que faz duas coisas: (1) nenhum dos dois lados
consegue mais mandar mensagem pro outro (checado nos dois sentidos em
`POST /messages/send`), e (2) os anúncios da pessoa bloqueada somem do
`/board` e dos matches da Home de quem bloqueou (filtro `NOT EXISTS`
contra `blocked_users`). A lista de quem você bloqueou, com botão pra
desbloquear, fica em `/profile`. Bloquear é uma decisão de uma via só
— bloquear alguém não impede que a outra pessoa ainda veja seus
anúncios, a não ser que ela também bloqueie você.

## Denunciar anúncio

Em cada anúncio (menos os seus próprios), um botão "Denunciar anúncio"
abre um formulário que exige um motivo com pelo menos 10 caracteres
(reforçado também no banco via `CHECK` em `listing_reports.reason` —
não é só validação de formulário). Não existe nenhuma tela de
moderação no site: as denúncias ficam guardadas em `listing_reports`
pra serem consultadas direto no banco por quem administra o site
(mesmo padrão já usado em `profile_views`, a contagem de visitas a
perfil).

## E-mail a cada nova mensagem

Além do alerta de "anúncio compatível" que já existia, agora cada
pessoa pode ligar/desligar (`/profile`, `users.notify_messages`) um
aviso por e-mail toda vez que recebe uma mensagem nova (`POST
/messages/send` em `messages_routes.py`, via `BackgroundTask` — não
atrasa o envio). De propósito o e-mail não mostra o conteúdo da
mensagem, só avisa que uma chegou — isso ajuda a trazer a pessoa de
volta ao site pra ler.

## Impressum

`/impressum` — obrigatório para qualquer site operando na
Alemanha/Áustria/Suíça (Impressumspflicht, Art. 5 TMG), mesmo sendo
administrado de fora. A página já deixa claro que o site é operado a
partir do Brasil, mas os dados reais (nome/razão social, endereço,
contato) ainda precisam ser preenchidos — ver `app/templates/impressum.html`,
marcados como `[PREENCHER: ...]`. **Não publique o site com esses
campos ainda vazios.**

## Código de conduta

`/code-of-conduct` — regras simples e diretas de comportamento no
site (respeito, honestidade nos anúncios, sem spam, privacidade,
manter o tom profissional, denunciar em vez de confrontar). Não
depende de nenhum dado pessoal, então já está pronto para uso.

## Badges (gamificação leve)

Em `/profile`, uma seção mostra "conquistas" calculadas na hora a
partir do que já existe no banco (`app/badges.py`): indicou um amigo
(que verificou o e-mail — veja "Indicações e abuso" abaixo), publicou
um anúncio, entrou em contato com alguém, respondeu uma mensagem em
até 24h pelo menos uma vez, perfil 100% completo, "gefragt/in demand"
por volume de visitas (100/500/1000), e "aniversário" por tempo de
conta (1 ano, 2 anos...). Só os badges DESBLOQUEADOS aparecem no
perfil público (`/users/{id}`); na sua própria página (`/profile`)
você vê todos, inclusive os que ainda faltam.

De propósito, isso **não é um ranking**: não existe nenhuma tela que
compare uma pessoa com a outra, e o badge de visitas mostra só "acima
de X visitas", nunca o número exato — preserva a decisão de manter
`profile_views` privado.

**E-mail a cada badge novo**: uma tabela `user_badges` (ver
`db/schema.sql`) registra quando cada badge/nível foi desbloqueado
pela primeira vez — ela não guarda a REGRA de nenhum badge (isso
continua calculado na hora), só o registro de "já avisei sobre esse".
Isso evita mandar o e-mail de novo toda vez que a página recalcula os
badges, e permite badges com vários níveis (visitas, aniversário)
mandarem um e-mail por degrau alcançado.

**Quando a checagem roda**: depois de ações que plausivelmente
desbloqueiam algum badge (publicar anúncio, mandar mensagem, salvar o
perfil) — e também, de forma "preguiçosa", toda vez que você abre o
próprio `/profile`. Isso cobre os badges de aniversário e visitas, que
não dependem de uma ação sua específica: como o projeto não usa nenhum
cron interno, a visita mais natural e frequente (você mesmo abrindo o
perfil) já é suficiente pra manter isso em dia sem precisar de nenhum
job agendado.

**Outras ideias de gamificação leve** (não implementadas, mas fáceis
de encaixar no mesmo padrão de `app/badges.py` se quiser):
- Badge por diversidade de indicações — indicou tanto cantores quanto
  maestros.
- Selo de "perfil verificado recentemente" (atualizou algo nos
  últimos 30 dias) — sinaliza atividade sem expor tempo online.
- Um e-mail de "resumo mensal" agregando tudo que aconteceu na semana
  (badges novos, mensagens, visitas ao anúncio) em vez de um e-mail
  por evento — reduz a quantidade de e-mails conforme a base cresce.
- Badge de "primeira resposta em menos de 1h" (um degrau acima da
  resposta em 24h) — mesmo padrão de `_has_fast_response`, só com
  janela menor.

### Indicações e abuso (referral gaming)

Uma coisa que vale flagar: como não existe CAPTCHA nem limite de
cadastros no `/register`, nada impedia (antes desta rodada) alguém
inflar o próprio contador de indicações — e agora o badge de
"Botschafter(in)" — criando várias contas falsas pelo próprio link.
Reduzi (não eliminei) isso: `get_referral_stats()` e o badge de
indicação só contam pessoas indicadas que **verificaram o e-mail**
(`app/referrals.py`). Não impede 100% (dá pra verificar e-mails
descartáveis), mas já é uma barreira de verdade contra o caso mais
simples. Se algum dia isso virar problema de verdade, as próximas
barreiras seriam: CAPTCHA no cadastro, ou um limite de X cadastros por
IP/dia.

## Bloqueio é invisível dos dois lados

Bloquear alguém (em `/users/{id}` ou pela lista em `/profile`) agora
faz o perfil de cada um desaparecer para o outro nos dois sentidos —
não importa quem bloqueou quem, nenhum dos dois consegue ver o perfil
do outro (`/users/{id}` mostra só um aviso genérico, sem revelar o
motivo nem quem bloqueou), mandar mensagem, ou ver os anúncios do
outro no `/board`/Home. Só quem bloqueou vê a pessoa na própria lista
de bloqueados (com botão de desbloquear) em `/profile` — a pessoa
bloqueada nunca fica sabendo que foi bloqueada por ali.

## Aviso de caixa de spam na Home

Quem está logado vê, na Home, um aviso lembrando de checar a caixa de
spam e marcar e-mails do site como "não é spam" (pra não perder
alertas de mensagem/anúncio compatível) — com um "✕" pra fechar. A
escolha fica salva no navegador da pessoa (`localStorage`) **com
data**, não como "nunca mais mostrar": o aviso reaparece
automaticamente uma semana depois de fechado (`app/templates/home.html`,
`ONE_WEEK_MS`). Isso equilibra não ser chato toda visita com não deixar
o aviso sumir de vez pra sempre.

## Nível de admin (`users.is_admin`)

Adicionei uma coluna `is_admin BOOLEAN` em `users` — um nível de
usuário especial, separado de `role` (singer/conductor), pensado só
pra tarefas administrativas leves DENTRO do próprio app (não é a mesma
coisa que o Adminer, que dá acesso total ao banco — ver seção
seguinte). Hoje ele libera uma única tela: `/admin`, um painel
**só de leitura** (`app/routers/admin_routes.py` +
`app/templates/admin.html`) com números gerais (usuários, anúncios,
mensagens, pares bloqueados, denúncias) e as denúncias/bloqueios mais
recentes — o suficiente pra uma triagem rápida sem abrir o Adminer só
pra "dar uma olhada".

**Como virar admin**: não existe cadastro de admin pela interface (de
propósito — é um nível sensível). Você vira admin direto no banco:
```sql
UPDATE users SET is_admin = TRUE WHERE email = 'seu-email@exemplo.com';
```
Quem é admin ganha um link "Admin" no menu; quem tenta acessar
`/admin` sem ser admin só é redirecionado pra home, sem nenhuma
mensagem revelando que a página existe. `require_admin()` em
`app/routers/admin_routes.py` é o ponto único que checa isso — qualquer
rota administrativa futura deveria chamar essa mesma função no início,
em vez de reimplementar a checagem.

Isso é deliberadamente pouco: um "nível de usuário especial" no
sentido que você perguntou é basicamente essa única coluna booleana +
uma função que checa ela antes de qualquer rota sensível — não precisa
de um sistema de permissões (roles/scopes) mais sofisticado a não ser
que um dia existam VÁRIOS tipos de tarefa administrativa com acessos
diferentes entre si (ex: alguém que só modera denúncias vs. alguém que
mexe em pagamento). Se chegar nesse ponto, a evolução natural seria
trocar o booleano por uma coluna `admin_role` (ex: 'moderator',
'superadmin') com um `CHECK` limitando os valores válidos, do mesmo
jeito que `users.role` já funciona pra singer/conductor.

## Administrar o site e ver o banco em tempo real

Minha recomendação segue a mesma: **não vale a pena construir uma API
administrativa separada** — o `/admin` acima já cobre o "dar uma
olhada rápida sem SQL", e o Adminer cobre "editar/consultar de
verdade". Pra "ver e editar em tempo real" sem escrever nenhum código,
duas opções prontas:

- **Adminer** — uma interface web de um arquivo só, já incluída neste
  projeto como um serviço opcional no `docker-compose.yml` (perfil
  `admin`, não sobe sozinho). Pra usar localmente:
  ```
  docker compose --profile admin up
  ```
  e abra `http://localhost:8080` (servidor: `db`, usuário/senha/banco
  como no seu `.env`). Dá pra navegar tabelas, rodar SQL, editar
  linhas na hora — exatamente o que você pediu.
- **pgAdmin** — mais pesado que o Adminer, mas com mais recursos
  (gráficos de query, editor mais completo) se um dia sentir falta
  de algo que o Adminer não tem.

**Importante se for além do seu computador**: nunca exponha a porta
do Adminer (8080), nem `/admin`, publicamente sem proteção extra na
frente — um túnel SSH (`ssh -L 8080:localhost:8080 seu-servidor`) ou
um proxy reverso com login (ex: Caddy/nginx com autenticação básica)
na frente. O Adminer sozinho só tem a senha do Postgres te protegendo,
e `/admin` só tem a sessão de login normal do site (sem 2FA) — o
que não é suficiente exposto direto na internet.

## CAPTCHA (proteção anti-bot)

Duas camadas, seguindo o mesmo padrão de "backend plugável" já usado
pra e-mail (`app/email.py`):

1. **Honeypot** (`app/captcha.py`) — sempre ativo, zero configuração.
   Um campo a mais (`website`) escondido via CSS fora da tela em
   `/register` e `/forgot-password`: humanos nunca veem nem preenchem,
   bots genéricos preenchem tudo automaticamente. Se vier preenchido,
   a gente trata como se o envio tivesse dado certo (mesmo
   redirecionamento/mensagem de sempre) só que **sem** criar a conta
   ou mandar o e-mail — não dá nenhuma pista pro bot sobre o motivo.
   Testado: um "bot" que preenche o campo não cria conta nem recebe
   e-mail de reset; um envio normal (campo vazio) continua funcionando
   igual.
2. **Cloudflare Turnstile** (opcional) — um desafio "quase invisível"
   de verdade, sem os problemas de privacidade do reCAPTCHA do Google.
   Só liga se você configurar duas chaves no `.env`:
   ```
   TURNSTILE_SITE_KEY=...
   TURNSTILE_SECRET_KEY=...
   ```
   Pra conseguir essas chaves (grátis): crie uma conta em
   https://dash.cloudflare.com/ (não precisa migrar seu domínio pra
   lá) → **Turnstile** → **Add site** → copie as duas chaves. Sem
   elas configuradas, o site segue protegido só pelo honeypot — o
   que já é uma barreira real contra bots genéricos, só não contra
   alguém tentando abusar do seu site especificamente.

O honeypot cobre o cadastro (que já ficou mais visado depois do
sistema de indicações) e o "esqueci minha senha" (evita spam de
e-mails de reset). Login não tem CAPTCHA — ali o risco é
força-bruta de senha, não bot de cadastro, e a defesa certa pra isso
é limitar tentativas por conta/IP (rate limiting), não CAPTCHA;
listado abaixo como próximo passo, não implementado ainda.

## Datenschutzerklärung

`/datenschutz` — a política de privacidade "de verdade" (o Impressum
identifica QUEM opera o site; isso aqui explica O QUE fazemos com os
dados). Cobre: quais dados coletamos e por quê (conta, anúncios,
mensagens, indicações, e-mails opcionais, visitas a perfil, denúncias/
bloqueios), cookies (só os técnicos — sessão e idioma, sem
rastreamento, por isso não precisa de banner de cookies), com quem
compartilhamos (hospedagem, Resend para e-mail, outros usuários só o
que você torna público), quanto tempo guardamos (ligado à exclusão de
conta com 6 meses de recuperação), seus direitos (acesso, correção,
exclusão, portabilidade — Art. 15–21 GDPR) e segurança (bcrypt, CSRF).

**Um ponto ficou marcado como `[NOCH MIT ANWALT/ANWÄLTIN ZU PRÜFEN]`
("ainda precisa ser revisado com advogado")**: a seção 4, sobre
transferência internacional de dados — como o site é operado do
Brasil mas atende principalmente Alemanha/Áustria/Suíça, existe uma
transferência de dados entre países que tecnicamente exige um
mecanismo de proteção específico (cláusulas contratuais padrão da UE,
por exemplo). Isso depende de detalhes do seu provedor de hospedagem
final e é o tipo de coisa que vale a pena confirmar com um(a)
advogado(a) antes de aceitar dados de usuários reais — não é algo que
dá pra resolver só escrevendo o texto certo.

## Próximos passos sugeridos

- Adicionar testes automatizados (pytest + banco de teste).
- Trocar autenticação por JWT se algum dia precisar de uma API separada
  para um app mobile.
- Preencher os dados reais no Impressum (nome, endereço, contato) — ver
  seção "Impressum" acima. As páginas de Impressum e Datenschutz já
  existem e renderizam normalmente com os campos marcados como
  `[PREENCHER: ...]`; nada impede publicar o site com elas assim,
  desde que o texto real entre o quanto antes puder depois.
- Revisar a Datenschutzerklärung com um(a) advogado(a) quando der — em
  especial a seção 4 (transferência internacional de dados), marcada
  como pendente. Recomendável fazer isso logo após o lançamento, mas
  não é um bloqueio técnico.
- Rate limiting em `/login` (tentativas de senha por conta/IP) — o
  CAPTCHA acima cobre bots de cadastro e spam de reset de senha, mas
  não força-bruta de login, que pede uma defesa diferente (contagem de
  tentativas, não desafio humano/bot).
- Um limite de mensagens por dia por conta, se o spam de mensagens
  virar um problema real conforme a base cresce (mencionado, ainda não
  implementado — fica pra quando/se fizer sentido).
- Ver a seção "Sistema de mensagens interno" acima para a simplificação
  pendente da lixeira.
- Elegibilidade pra avaliar ("só quem contratou/trabalhou com a pessoa
  pode avaliar"), fluxo de "match encontrado" (encerra o anúncio,
  libera avaliação mútua) e sistema de candidaturas ("eu quero" por
  anúncio) — três ideias discutidas na conversa, ainda não
  implementadas. Ver resposta detalhada no chat sobre como cada uma
  poderia funcionar.
- Repensar a ideia de "ranking de membros mais ativos" — ver resposta
  detalhada no chat sobre por que isso entra em tensão com a decisão de
  manter `profile_views` privado, e alternativas de retenção sugeridas.

# VokalBoard — Changelog de hoje (14/09/2026)

Tudo abaixo já está implementado, testado (33/33 testes passando) e
commitado localmente (commit `09f0c31`, branch `master`) no ambiente
de nuvem desta sessão. **Ainda não foi enviado para o seu computador**
porque a ponte com o seu PC estava desconectada no momento — assim que
ela reconectar (basta o app do Claude estar aberto), eu sincronizo os
arquivos para a sua pasta do Google Drive automaticamente. Depois é só
você revisar e rodar `git push`.

## 🔴 Zona Vermelha (tudo oculto/desligado por padrão)

- **Níveis de usuário** (`users.role_level`): 0 comum, 1 moderador
  (só vê a fila de denúncias), 2 admin (tudo que já existia:
  usuários, posts, análise de dados), 3 god mode (tudo acima + Zona
  Vermelha). O antigo `is_admin` continua existindo e é mantido em
  sincronia automaticamente — inclusive por um gatilho no próprio
  banco, para não quebrar o fluxo de "virar admin" que já estava
  documentado no README.
- **Modo Capitalismo**: liga/desliga a cobrança para o site inteiro.
  Enquanto desligado (padrão), nada relacionado a pagamento aparece
  em lugar nenhum — nem banner, nem preço. Alternar o estado exige
  **reautenticação por senha** (mesmo já logado como god mode) e fica
  registrado no log de auditoria, mesmo quando a senha está errada.
- **Preço da assinatura** (EUR/CHF), editável na Zona Vermelha, com a
  mesma trava de senha.
- **Log de auditoria** (`audit_log`): quem, quando, de qual IP, para
  toda ação sensível.

## 📖 Painel financeiro interno

- Lançamento de despesas (descrição, valor, moeda, categoria, data)
- Despesas recorrentes (mensal/anual)
- Anexo de comprovante (PDF ou imagem) — guardado à parte, só
  visível para god mode (diferente do avatar, que é público)
- Exportação de despesas em CSV
- Upload manual de extrato bancário: você cria um "perfil" de mapeamento
  de colunas uma vez por banco (qual coluna é data/valor/descrição), e
  reaproveita esse perfil em toda importação futura daquele banco —
  suporte a OFX fica para uma próxima etapa
- Analytics de aderência ao plano pago por país (usa o campo `country`
  que já existia + a nova tabela `subscriptions`, pronta para quando a
  cobrança for ligada de verdade)
- Alternância de gráfico (barra / pizza / linha) no painel financeiro
  e retrofitada na Análise de Dados que já existia
- Fechamento mensal/anual: congela um resumo do período e exporta em
  **Excel, CSV e PDF**

## Ainda pendente (decisão de negócio, não técnica)

- País de tributação (Alemanha vs. Brasil) — a decisão que você disse
  que tomaria depois
- Conexão com processador de pagamento real (Paddle ou outro) — por
  isso `/assinar` hoje é só uma página provisória, sem checkout de
  verdade
- Confirmação se você já colocou `.github/workflows/backup.yml` no
  lugar certo e criou o secret `PRODUCTION_DATABASE_URL`

## Como isso foi verificado

- 33 testes automatizados passando (20 já existentes + 13 novos),
  incluindo: senha errada não muda nada, cada nível de usuário só
  acessa o que deveria, toda ação sensível cai no log de auditoria,
  os três formatos de exportação do fechamento respondem corretamente
- Bandit (análise de segurança estática) sem apontamentos nos arquivos
  novos
- Todas as páginas novas renderizadas de ponta a ponta contra um banco
  Postgres real, sem erro

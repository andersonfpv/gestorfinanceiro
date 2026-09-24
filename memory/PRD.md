# PRD — Meu Controle Financeiro

## Problema original
Aplicativo web responsivo em português do Brasil para registrar, acompanhar e compartilhar finanças pessoais, familiares ou de pequenos grupos, com moeda R$, datas dd/mm/aaaa, autenticação, permissões, lançamentos, tags, dashboard, filtros, gráficos e dados demonstrativos removíveis.

## Decisões de arquitetura
- React 19 no frontend, FastAPI no backend e MongoDB usando MONGO_URL/DB_NAME existentes.
- Relacionamentos explícitos por UUIDs próprios (`user_id`, `control_id`, `tag_id`, `transaction_id`) e controle de acesso validado no backend.
- OAuth Google validado no backend, com state, nonce, e-mail verificado e sessão própria em cookie httpOnly.
- Implantação portátil via Docker Compose, com MongoDB persistente e proxy HTTPS opcional por Caddy.
- Valores armazenados como texto decimal quantizado em duas casas para evitar arredondamento binário.

## Personas
- Pessoa que organiza sua própria rotina financeira.
- Família que compartilha um controle com diferentes permissões.
- Pequeno grupo que precisa consultar entradas e saídas sem editar tudo.

## Requisitos principais
- Acesso seguro e páginas protegidas.
- Controles independentes, membros e papéis proprietário/editor/visualizador.
- Lançamentos de entrada/saída, tags obrigatórias, saldo e exclusão protegida.
- Dashboard com indicadores, gráficos, filtros por período/tipo/tag/pessoa.
- Interface mobile-first, navegação desktop/mobile e feedbacks claros.
- Dados de demonstração adicionáveis e removíveis.

## Implementado — 09/09/2026
- Tela de login com OAuth Google próprio do backend e acesso de demonstração configurável.
- Sessão, logout, controle financeiro, membership e isolamento por controle.
- Dashboard com saldo, entradas, saídas, contagem, gráfico temporal, gráfico por tag e filtros funcionais.
- Modal de lançamento com validação de valor, tipo, data, descrição e tag.
- Gestão de tags em `/tags` e pessoas/permissões em `/membros`.
- Dados demo dinâmicos do mês atual e remoção por botão.
- Layout responsivo validado em 390x844, sem overflow horizontal.
- Lista completa de lançamentos em `/lancamentos` com busca por descrição, ordenação por data/valor, edição em modal e exclusão com confirmação.
- Integração Google OAuth reforçada em 10/09/2026: callback protegido, validação server-side e cookie seguro.
- Insights com Gemini adicionados em 14/09/2026: SSE server-side usando somente totais agregados e despesas por tag; resultados são armazenados em `ai_insights`.
- Testes integrados finais: backend 7/7 e frontend/mobile aprovados.
- Revisão de segurança e consistência em 23/09/2026: CORS por origem exata, demonstrações isoladas por sessão, validação decimal/data no backend e resumo financeiro agregado no MongoDB.
- Lista de lançamentos paginada e pesquisável, exportação CSV com proteção contra fórmulas, remoção de membros pelo proprietário e exclusão de controles com confirmação e bloqueio quando ainda compartilhados.
- Insights de IA passaram a usar agregações de todo o histórico, sem limite fixo de 2.000 lançamentos.
- O cartão principal do dashboard foi renomeado para “Resultado líquido”; saldo bancário real exige cadastro de contas e transferências.
- Limite de uma nova chamada de IA por usuário a cada 10 minutos, com reaproveitamento do insight quando os totais agregados permanecem iguais.
- Encerramento de conta com confirmação por e-mail, revogação de sessões e acesso, exclusão dos dados de controles individuais, transferência de propriedade dos controles compartilhados e anonimização da autoria em registros preservados.
- Implantação própria: Dockerfiles, Compose com volume persistente, Nginx, Caddy/HTTPS, configuração de ambiente e instruções de backup.

## Backlog priorizado
- P1: criar contas financeiras, transferências e ciclo de cartão de crédito; até lá, não chamar resultado líquido de saldo bancário.
- P1: orçamentos por categoria e metas financeiras com progresso mensal.
- P1: lançamentos recorrentes e parcelados, com prévia antes de gerar ocorrências.
- P1: importação CSV/OFX com mapeamento de colunas, prévia, deduplicação e confirmação antes de gravar.
- P1: editar tags, excluir tags sem lançamentos associados e validar cor/tipo no backend.
- P1: recuperação de acesso conforme suporte do provedor OAuth e estados claros de convite pendente.
- P2: comparação mensal/anual, fechamento de período e histórico de insights.
- P2: trilha de auditoria de alterações e notificações de convites/lançamentos.
- P2: ampliar testes automatizados de autorização, isolamento, arredondamento, datas antigas, paginação e exclusões; hoje os testes de API dependem de um backend e MongoDB de teste em execução.

## Próximas tarefas
1. Criar o modelo de contas, transferências e cartões antes de apresentar “saldo bancário” ou fluxo de caixa por conta.
2. Implementar orçamentos por categoria e recorrência/parcela com testes de geração e deduplicação.
3. Adicionar importação CSV/OFX e comparação mensal.
4. Avaliar exclusão automatizada/solicitações de dados no provedor OAuth e retenção técnica de backups conforme a política operacional de implantação.

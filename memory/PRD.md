# PRD — Meu Controle Financeiro

## Problema original
Aplicativo web responsivo em português do Brasil para registrar, acompanhar e compartilhar finanças pessoais, familiares ou de pequenos grupos, com moeda R$, datas dd/mm/aaaa, autenticação, permissões, lançamentos, tags, dashboard, filtros, gráficos e dados demonstrativos removíveis.

## Decisões de arquitetura
- React 19 no frontend, FastAPI no backend e MongoDB usando MONGO_URL/DB_NAME existentes.
- Relacionamentos explícitos por UUIDs próprios (`user_id`, `control_id`, `tag_id`, `transaction_id`) e controle de acesso validado no backend.
- Sessão gerenciada pela Emergent via cookie httpOnly; callback OAuth usa a origem atual do navegador sem URL fixa.
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
- Tela de login com OAuth gerenciado e acesso de demonstração.
- Sessão, logout, controle financeiro, membership e isolamento por controle.
- Dashboard com saldo, entradas, saídas, contagem, gráfico temporal, gráfico por tag e filtros funcionais.
- Modal de lançamento com validação de valor, tipo, data, descrição e tag.
- Gestão de tags em `/tags` e pessoas/permissões em `/membros`.
- Dados demo dinâmicos do mês atual e remoção por botão.
- Layout responsivo validado em 390x844, sem overflow horizontal.
- Lista completa de lançamentos em `/lancamentos` com busca por descrição, ordenação por data/valor, edição em modal e exclusão com confirmação.
- Integração Google gerenciada da Emergent reforçada em 10/09/2026: redirect dinâmico, callback protegido contra reprocessamento, troca server-side, cookie seguro, erros visíveis e logout por cookie ou Bearer.
- Insights com Gemini adicionados em 14/09/2026: streaming SSE server-side com `gemini-3.8-flash`, usando somente totais agregados e despesas por tag; resultados são armazenados em `ai_insights`.
- Testes integrados finais: backend 7/7 e frontend/mobile aprovados.
- Revisão de segurança e consistência em 23/09/2026: CORS por origem exata, demonstrações isoladas por sessão, validação decimal/data no backend e resumo financeiro agregado no MongoDB.
- Lista de lançamentos paginada e pesquisável, exportação CSV com proteção contra fórmulas, remoção de membros pelo proprietário e exclusão de controles com confirmação e bloqueio quando ainda compartilhados.
- Insights de IA passaram a usar agregações de todo o histórico, sem limite fixo de 2.000 lançamentos.
- O cartão principal do dashboard foi renomeado para “Resultado líquido”; saldo bancário real exige cadastro de contas e transferências.

## Backlog priorizado
- P0: documentar retenção, privacidade e exclusão de conta; hoje é possível exportar lançamentos e excluir controles, mas não há fluxo para encerrar a conta OAuth.
- P0: adicionar limites de uso/cache nos insights de IA, para controlar custo e evitar chamadas repetidas por qualquer membro autorizado.
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
1. Fechar a política de retenção e adicionar exclusão da conta e dados pessoais sem apagar controles compartilhados de outras pessoas.
2. Criar o modelo de contas, transferências e cartões antes de apresentar “saldo bancário” ou fluxo de caixa por conta.
3. Implementar orçamentos por categoria e recorrência/parcela com testes de geração e deduplicação.
4. Adicionar importação CSV/OFX e comparação mensal.

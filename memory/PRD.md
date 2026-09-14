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

## Backlog priorizado
- P0: concluir e validar recuperação de senha nativa da autenticação gerenciada, conforme disponibilidade do provedor.
- P1: edição de lançamentos e tags, exclusão de tags não utilizadas e paginação da lista completa.
- P1: tela dedicada de lançamentos com paginação/carregamento eficiente para grandes volumes.
- P1: edição de membros e remoção de acesso pelo proprietário.
- P1: histórico de insights Gemini, comparação de períodos e opção de solicitar análises agregadas específicas.
- P2: exportação CSV/PDF, metas financeiras e relatórios comparativos por mês.
- P2: auditoria de alterações e notificações de convites.

## Próximas tarefas
1. Criar a tela completa de lançamentos com edição e confirmação de exclusão.
2. Adicionar recuperação de senha e estados de convite pendente.
3. Expandir gráficos com ranking de tags e comparativo mensal.
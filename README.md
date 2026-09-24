# Meu Controle Financeiro

Aplicativo de finanças pessoais e compartilhadas. A aplicação roda em infraestrutura própria com Docker Compose, MongoDB, FastAPI e React servido por Nginx. O login usa OAuth do Google configurado pelo administrador; os insights de IA usam a API Gemini do Google e são opcionais.

## Testar no computador

Requisitos: Docker Engine e o plugin Docker Compose. Copie o arquivo de exemplo, defina uma senha exclusiva para o MongoDB e inicie os serviços:

```bash
cp .env.example .env
```

Edite `.env` e troque `MONGO_USER` e `MONGO_PASSWORD` por valores exclusivos compostos por letras e números. Depois:

```bash
docker compose up -d --build
docker compose ps
```

Abra [http://localhost:8080](http://localhost:8080) e use **Entrar na demonstração**. Ela cria uma conta isolada e temporária; sair remove os dados dessa sessão. Os registros ficam no volume Docker `mongo_data` e sobrevivem a reinicializações.

Para acompanhar erros de inicialização:

```bash
docker compose logs -f backend frontend mongo
```

## Hospedar em um servidor próprio

Use um servidor Linux com Docker, um domínio apontado para o IP do servidor e as portas TCP 80 e 443 liberadas. Copie `.env.example` para `.env` e configure:

```env
APP_DOMAIN=financeiro.seudominio.com
APP_BASE_URL=https://financeiro.seudominio.com
ACME_EMAIL=voce@seudominio.com
COOKIE_SECURE=true
ENABLE_DEMO_LOGIN=false
MONGO_PASSWORD=uma_senha_forte_so_com_letras_e_numeros
```

Defina também o login Google conforme a seção abaixo. O proxy Caddy do Compose obtém e renova o certificado HTTPS automaticamente:

```bash
docker compose --profile public up -d --build
```

O frontend e a API ficam no mesmo domínio; o MongoDB e o backend não ficam expostos publicamente. A porta local 8080 continua disponível apenas no próprio servidor para diagnóstico.

### Configurar login Google

1. No Google Cloud Console, crie ou selecione um projeto e configure a tela de consentimento OAuth.
2. Crie uma credencial **ID do cliente OAuth** do tipo **Aplicativo da Web**.
3. Adicione como URI de redirecionamento autorizado `https://financeiro.seudominio.com/api/auth/google/callback` (use exatamente o domínio definido em `APP_BASE_URL`).
4. Copie o ID e o segredo para `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` em `.env`.
5. Reinicie com `docker compose --profile public up -d --build`.

Para testes locais, o callback é `http://localhost:8080/api/auth/google/callback`. Enquanto a tela OAuth estiver em modo de teste, adicione sua conta Google como usuário de teste. A aplicação valida a resposta no backend e mantém uma sessão própria.

### Configurar insights Gemini (opcional)

Crie uma chave da Gemini API e coloque em `GEMINI_API_KEY`. O backend envia somente totais agregados e gastos agrupados por tag ao Gemini. Sem essa chave, cadastro, lançamentos e relatórios continuam funcionando; o painel de insights informa que a integração não está configurada.

## Configuração e dados

- `APP_BASE_URL`: endereço público completo do app, sem barra no final.
- `MONGO_USER` e `MONGO_PASSWORD`: credenciais do MongoDB. Use letras e números na senha para manter a URL de conexão simples.
- `DB_NAME`: nome do banco, padrão `gestorfinanceiro`.
- `ENABLE_DEMO_LOGIN`: habilita acesso sem conta Google. Use `true` só para teste e `false` no servidor público.
- `COOKIE_SECURE`: `true` no servidor HTTPS; `false` apenas no endereço local HTTP.
- `CORS_ORIGINS`: lista opcional de origens extras separadas por vírgula. Para o frontend servido junto da API, deixe vazio.
- `GEMINI_API_KEY` e `GEMINI_MODEL`: integração opcional de IA e modelo, padrão `gemini-2.5-flash`.

Faça cópias de segurança do MongoDB e guarde-as fora do servidor. Um backup manual compactado pode ser criado assim:

```bash
docker compose exec -T mongo sh -c 'mongodump --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --db "$DB_NAME" --archive --gzip' > backup-financeiro.archive.gz
```

Os dados persistentes estão no volume `mongo_data`. Remover esse volume apaga todos os usuários e lançamentos; não use `docker compose down -v` em um servidor com dados.

## Desenvolvimento e testes automatizados

Para desenvolver sem Docker, inicie MongoDB local e API com variáveis de ambiente próprias:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
export MONGO_URL='mongodb://localhost:27017'
export DB_NAME='gestorfinanceiro_dev'
export APP_BASE_URL='http://localhost:3000'
export COOKIE_SECURE=false
export ENABLE_DEMO_LOGIN=true
export CORS_ORIGINS='http://localhost:3000'
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

Em outro terminal:

```bash
cd frontend
yarn install
yarn start
```

Os testes em `backend/tests` são de integração. Rode-os com uma instância separada da API e um banco descartável, nunca contra os dados reais. Uma forma é copiar `.env.example` para `.env.test` e alterar `DB_NAME=gestorfinanceiro_test`, `MONGO_USER`, `MONGO_PASSWORD`, `MONGO_PORT=27018` e `BACKEND_PORT=8001`. Inicie só MongoDB e API de teste:

```bash
docker compose --env-file .env.test -p gestorfinanceiro-test up -d --build mongo backend
```

Instale as dependências de teste e aponte a suíte para essa instância:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
export MONGO_URL='mongodb://financeiro_test:SENHA_ALFANUMERICA@localhost:27018/gestorfinanceiro_test?authSource=admin'
export DB_NAME='gestorfinanceiro_test'
export REACT_APP_BACKEND_URL='http://localhost:8001'
export COOKIE_SECURE=false
pytest tests/test_finance_api.py
```

`tests/test_ai_insights.py` também precisa de uma `GEMINI_API_KEY` válida configurada no `.env.test` do backend. Para descartar somente o banco isolado de teste, use `docker compose --env-file .env.test -p gestorfinanceiro-test down -v`.

## Recursos atuais

- Controles pessoais e compartilhados com permissões de proprietário, editor e visualizador.
- Entradas, saídas, tags, filtros, resumo e exportação CSV.
- Encerramento de conta com confirmação e transferência dos controles compartilhados.
- Insights calculados sobre valores agregados, com cache e limite de uma nova geração por usuário a cada 10 minutos.

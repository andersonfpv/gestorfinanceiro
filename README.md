# Meu Controle Financeiro

Aplicativo web responsivo para registrar e acompanhar entradas e saídas em controles pessoais ou compartilhados. O projeto usa React no frontend, FastAPI no backend e MongoDB.

## Configuração local

### Backend

Crie `backend/.env` com as variáveis abaixo. `CORS_ORIGINS` deve conter somente as origens exatas do frontend, separadas por vírgula. Não use `*`.

```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=gestorfinanceiro
CORS_ORIGINS=http://localhost:3000
EMERGENT_LLM_KEY=
```

Instale as dependências e inicie a API:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

No Windows, ative o ambiente com `.venv\\Scripts\\activate`.

### Frontend

Crie `frontend/.env` apontando para a API:

```env
REACT_APP_BACKEND_URL=http://localhost:8000
```

Instale as dependências e inicie a aplicação:

```bash
cd frontend
npm install
npm start
```

Ao hospedar frontend e API em origens diferentes, adicione a origem pública do frontend a `CORS_ORIGINS` no backend. Por exemplo: `https://financeiro.exemplo.com`. Reinicie a API depois de alterar essa variável.

## Testes

Os testes de integração precisam da API e de um MongoDB de teste em execução. Configure a API e o processo de teste para usar o mesmo `DB_NAME` exclusivo, separado dos dados reais. O teste de insights também precisa que `EMERGENT_LLM_KEY` esteja configurada no backend.

```bash
cd backend
MONGO_URL=mongodb://localhost:27017 DB_NAME=gestorfinanceiro_test REACT_APP_BACKEND_URL=http://localhost:8000 pytest
```

## Segurança e dados

- Configure apenas origens confiáveis em `CORS_ORIGINS`; a API recusa origens não autorizadas.
- Use um banco exclusivo para desenvolvimento e testes.
- O acesso de demonstração cria uma identidade isolada por sessão.
- Valores são armazenados com duas casas decimais e datas novas são armazenadas no formato ISO `AAAA-MM-DD`.

# Roteiro de testes de autenticação

## Sessão de teste

Criar um usuário e uma sessão diretamente no MongoDB de teste, sempre usando `user_id` próprio e um `session_token` válido. O documento de sessão deve apontar para o mesmo `user_id` do usuário e expirar em sete dias.

## API

- Verificar `GET /api/auth/me` usando o token no header `Authorization: Bearer`.
- Verificar que endpoints protegidos respondem 401 sem sessão.
- Verificar que a sessão via cookie `session_token` também é aceita.

## Navegador

- Adicionar cookie de sessão e abrir o app.
- Confirmar que o dashboard protegido é exibido.
- Confirmar que usuário não autenticado é redirecionado para a tela de acesso.
- Confirmar que o callback OAuth processa `session_id` no fragmento da URL e redireciona ao dashboard.

## Checklist

- Usuários e sessões usam `user_id` customizado.
- Respostas MongoDB nunca expõem `_id`.
- Cookies são httpOnly, secure e sameSite none.
- Sessões são verificadas no backend.
- Identidades de teste e permissões devem ser registradas em `/app/memory/test_credentials.md` quando existirem.
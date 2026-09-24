# Authentication testing

- Check that `GET /api/auth/config` only returns whether Google login and demo login are enabled. It must not return OAuth secrets.
- With demo login enabled, check that `POST /api/auth/demo` creates an isolated session, `GET /api/auth/me` accepts it, and logout invalidates it.
- With demo login disabled, check that `POST /api/auth/demo` returns 404.
- Without a session, protected API routes return 401. Both cookie and bearer-token sessions are supported.
- On a deployment configured with Google OAuth credentials, verify the complete browser redirect, state and nonce validation, verified-email check, cookie creation, logout, and return to the app.
- Confirm cookies are HttpOnly and SameSite=Lax. Set Secure=true on HTTPS deployments and false only on local HTTP.
- Never run integration tests against a database that contains personal financial data.

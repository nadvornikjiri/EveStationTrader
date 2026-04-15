# Current task

All backlog items complete. HMAC-signed state implemented and tested.

# End goal with specs

- `GET /auth/login` returns an `authorize_url` that includes a `state` query param (random secure token)
- `GET /auth/callback?code=...&state=...` validates the returned `state` matches what was issued (CSRF protection)
- If state is missing or mismatched, return a 400 error
- Existing tests pass; new tests cover state generation and validation

## File ownership
- YOU OWN: `backend/app/core/security.py`, `backend/app/api/routes/auth.py`, `backend/app/services/auth/service.py`
- Read first: `backend/app/api/schemas/auth.py`, `backend/tests/api/test_endpoints.py`, `backend/tests/services/test_auth_service.py`

## Key facts
- `get_auth_redirect_config()` in `security.py` builds the OAuth params dict — it currently omits `state`
- The callback route (`auth.py`) only accepts `code`, not `state`
- State needs to be generated per-request and validated on callback — use `secrets.token_urlsafe(32)`
- For now, stateless validation is acceptable: generate state, sign/encode it, verify on callback (no server-side session storage needed). A simple HMAC-signed state using `settings.secret_key` is fine.
- OR: if there's already a session/cookie mechanism, use that for state storage — check `app/core/security.py` and `app/services/auth/service.py`

# Roadmap (Completed)
- Identified root cause: `get_auth_redirect_config()` never emits `state`

# Roadmap (Upcoming)
- Add state generation and inclusion in authorize URL
- Add state validation in callback

# Backlog
- [x] Read security.py, auth.py, service.py, schemas/auth.py fully
- [x] Decide stateless (HMAC) vs stateful (store in DB/cache) approach based on existing session infra
- [x] Implement state generation in get_auth_redirect_config() or login route
- [x] Add state param to callback route and validate it
- [x] Update/add tests for state generation and validation
- [x] Run tests and confirm passing
- [x] Commit

## Loop Control
STOP

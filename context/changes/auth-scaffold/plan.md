# Auth Scaffold (F-01) Implementation Plan

## Overview

Integrate Supabase Auth end-to-end through FastAPI and bootstrap the frontend's auth foundation. The backend gains `register` / `login` / `logout` / `refresh` / `me` endpoints (FastAPI is the sole Supabase client), a layered JWT-verification dependency guard that protects every domain route, and local user provisioning (`users` + default `user_preferences`) at register time. The frontend gains its `app/` / `lib/` / `features/` foundation with a Polish auth entry screen that registers, logs in, and logs out, surviving page refresh.

This is the F-01 foundation slice from the roadmap: minimal auth UI needed to exercise the flow — not account settings or profile management.

## Current State Analysis

- **Backend auth is empty stubs**: `backend/app/api/v1/auth/router.py` holds only a commented example; `service.py` / `crud.py` are docstring-only. `app/core/config.py` exposes just `database_url`. Neither `supabase-py` nor `pyjwt` is in `backend/pyproject.toml`. The v1 aggregator (`app/api/v1/router.py:12`) already includes the (empty) `auth_router`.
- **Data layer is live** (F-02/F-03 done): migrations applied for `users`, `user_preferences`, `cabinet_entries`, `medication_registry`. `cabinet_entries.user_id` is a FK to `users.id` (`backend/app/api/v1/cabinet/models.py`). Design intent: `users.id` **equals** the Supabase auth user id (the JWT `sub`). `UserPreferences` carries the FR-007 default fields (`expiry_threshold_days=30`, `close_to_finish_threshold_days=7`, `min_package_count=1`).
- **DB session plumbing exists**: `app/db/connector.py` provides `get_session` (async) and `init_db`. `app/main.py` is the app factory with CORS already configured (`allow_methods` GET/POST/PUT/DELETE, origins from `FRONTEND_URL` + localhost:5173). CORS currently has **no `allow_credentials`** — the httpOnly refresh cookie will require it.
- **Frontend is a bare Vite scaffold**: only `src/App.tsx`, `src/main.tsx`, `src/index.css` (Tailwind v4 `@import "tailwindcss"` + `@theme` tokens). `package.json` has only `react`/`react-dom` + Tailwind — **no** router, TanStack Query, zod, or react-hook-form. `vite.config.ts` has the Tailwind plugin but **no `@/` alias** and **no Vitest block**. None of the AGENTS.md target tree (`app/`, `features/`, `lib/`, `components/`) exists yet.
- **Research settled the libraries** (`research.md`): `supabase-py` (Auth client) + `PyJWT` with JWKS / `PyJWKClient` for local token verification (no per-request network call to Supabase). Pin `algorithms` explicitly; validate `audience="authenticated"`, `issuer`, and expiry. Layer the dependencies (extract+validate → load user → enforce). Avoid `python-jose` and avoid `supabase.auth.get_user(token)` per request.

## Desired End State

A user opens the app, sees a Polish auth entry screen, registers with email+password, is immediately logged in (auto-confirm), and lands on a protected placeholder route. Refreshing the page keeps them logged in. Logging out returns them to the entry screen. Every `/api/v1` domain route (except public auth + health) rejects requests without a valid Bearer JWT with `401`. On register, a local `users` row (id = Supabase `sub`) and a default `user_preferences` row are created.

Verify: `uv run pytest` passes (guard + endpoint tests); `npm run build` passes; manual flow register → refresh page → logout works against a live Supabase project; an unauthenticated `curl` to a protected route returns 401; an authenticated one passes the guard.

### Key Discoveries

- `users.id` must equal the Supabase JWT `sub` claim — provisioning inserts the row with `id=UUID(claims["sub"])`, not a fresh `uuid4` (`backend/app/api/v1/users/models.py:11`).
- The refresh-token cookie requires CORS `allow_credentials=True` **and** the frontend `fetch`/api-client sending `credentials: "include"` — both currently absent (`app/main.py:30`).
- The transaction-pooler workaround in `connector.py:16` is unrelated to auth but confirms the DB connection is Supabase Postgres via `DATABASE_URL`.
- Auto-confirm → email-confirmation later is purely additive (new `/auth/confirm` endpoint + callback route), so nothing built here needs rework.
- AGENTS.md mandates: no barrel files (direct `@/*` imports), kebab-case filenames with PascalCase component identifiers, feature-based layout created just-in-time, `lib/api-client.ts` as the sole backend client attaching `Authorization: Bearer <jwt>`.

## What We're NOT Doing

- **No email confirmation** this slice (auto-confirm). No SMTP, no `/auth/confirm` callback, no "check your email" UI. Deferred to a later additive slice.
- **No password reset / forgot-password**, no email change, no profile or account-settings UI.
- **No silent/proactive token refresh** — only on-401 retry-once. No background timers.
- **No frontend unit tests** (Vitest/RTL) and **no Playwright E2E** this slice — backend pytest only. `auth.setup.ts` is left for S-01's golden path.
- **No RLS policy work** — RLS is defence-in-depth and out of scope for the scaffold; enforcement is the FastAPI guard.
- **No admin/service-role key usage** — provisioning writes to our own DB via `get_session`, not the Supabase admin API.
- **No styling polish / design system** beyond a minimal usable Polish entry screen.

## Implementation Approach

Backend first (Phases 1–2) so the API contract is real before the frontend consumes it. The JWT guard is built and applied before the endpoints exist conceptually, but landed together so tests can exercise both. Frontend foundation (Phase 3) is stood up before the auth feature (Phase 4) because the auth feature depends on `api-client`, `query-client`, the router, and the auth store.

Token model: `register`/`login` return the **access JWT in the JSON body** (frontend stores it in localStorage) and set the **refresh token as an httpOnly cookie**. `GET /auth/refresh` reads the cookie, exchanges it via supabase-py, returns a new access JWT (and rotates the cookie). `logout` clears the cookie. The api-client attaches `Authorization: Bearer`, and on a `401` performs a single-flight refresh-and-retry once before redirecting to login.

## Critical Implementation Details

- **`users.id` = Supabase `sub`.** Provisioning must use the auth user's UUID as the primary key, or the `cabinet_entries.user_id` FK will never match. Idempotent upsert (on register; safety-net on login) using `ON CONFLICT DO NOTHING` semantics so a re-register/re-login does not error.
- **Refresh-cookie CORS contract.** The cookie only works if `CORSMiddleware` gets `allow_credentials=True` and the cookie is set with `httponly=True`, `samesite="lax"` (or `"none"` + `secure=True` in prod cross-site). The api-client must send `credentials: "include"` on the refresh call. Mismatch here is the most likely silent failure.
- **Single-flight refresh.** Concurrent 401s must share one in-flight refresh promise, or rotation will invalidate the cookie mid-flight and kill the session. A module-level promise latch in `api-client.ts` is sufficient.
- **Algorithm pinning.** `jwt.decode` must pass `algorithms=["ES256","RS256"]` explicitly and never read `alg` from the token header (RFC 8725). `PyJWKClient` caches keys; instantiate it once at module load, not per request.

---

## Phase 1: Backend — Auth Config & JWT Guard

### Overview

Add Supabase/JWT configuration, install the auth libraries, build the Supabase client wrapper and the layered JWT-verification dependency, and apply the guard to protected domain routers.

### Changes Required

#### 1. Dependencies

**File**: `backend/pyproject.toml`

**Intent**: Add the two researched libraries so auth code can import them.

**Contract**: Add `supabase>=2.15` and `pyjwt[crypto]` to `[project].dependencies`. Install via `uv add "supabase>=2.15" "pyjwt[crypto]"`.

#### 2. Settings

**File**: `backend/app/core/config.py`

**Intent**: Expose Supabase URL + anon key and derived JWT validation params as a typed singleton.

**Contract**: Add fields `supabase_url: str`, `supabase_anon_key: str`. Add derived properties / constants for `jwt_issuer` (`f"{supabase_url}/auth/v1"`), `jwt_audience = "authenticated"`, `jwt_algorithms = ["ES256", "RS256"]`, and `jwks_url` (`f"{jwt_issuer}/.well-known/jwks.json"`). No service-role key needed.

#### 3. Supabase client wrapper

**File**: `backend/app/core/supabase_client.py` (new)

**Intent**: Single configured `supabase-py` client instance used by the auth service for sign_up/sign_in/sign_out/refresh.

**Contract**: Module-level `supabase = create_client(settings.supabase_url, settings.supabase_anon_key)`. Exported for import by `auth/service.py`.

#### 4. JWT verification dependency (layered guard)

**File**: `backend/app/api/v1/auth/dependencies.py` (new)

**Intent**: The reusable route guard. Low-level dependency extracts + validates the Bearer token; mid-level builds a `CurrentUser` from claims; this is what protected routers depend on.

**Contract**: Module-level `_jwks = PyJWKClient(settings.jwks_url)` (instantiated once). `get_token_claims(request) -> dict` extracts the Bearer token, resolves the signing key via `_jwks.get_signing_key_from_jwt`, and calls `jwt.decode(token, key, algorithms=settings.jwt_algorithms, issuer=settings.jwt_issuer, audience=settings.jwt_audience)`; raises `HTTPException(401)` on any failure. `get_current_user(claims=Depends(get_token_claims)) -> CurrentUser` maps `sub`/`email` into a small `CurrentUser` model. Export `get_current_user` as the guard dependency.

```python
# Non-obvious: key resolution + explicit algorithm pinning (RFC 8725)
key = _jwks.get_signing_key_from_jwt(token).key
claims = jwt.decode(
    token, key,
    algorithms=settings.jwt_algorithms,   # never trust token's alg header
    issuer=settings.jwt_issuer,
    audience=settings.jwt_audience,
)
```

#### 5. CurrentUser model

**File**: `backend/app/api/v1/auth/schemas.py` (new)

**Intent**: Typed request/response + the `CurrentUser` claims model shared by the guard.

**Contract**: Pydantic models `RegisterRequest{email, password}`, `LoginRequest{email, password}`, `AuthResponse{access_token, token_type="bearer", user: UserOut}`, `UserOut{id: UUID, email}`, `CurrentUser{id: UUID, email}`. Email validated with `EmailStr`; password min length enforced (e.g. ≥8) with a Polish error message.

#### 6. Apply guard to protected routers

**File**: `backend/app/api/v1/medicines/router.py`, `cabinet/router.py`, `users/router.py`

**Intent**: Make every domain route secure-by-default; health and public auth endpoints stay open.

**Contract**: Add `dependencies=[Depends(get_current_user)]` to each protected domain `APIRouter(...)` constructor. `health/router.py` and the public auth endpoints (register/login/refresh) remain unguarded.

#### 7. Document the guard convention

**File**: `AGENTS.md` (Backend layer rules section)

**Intent**: Ensure future domain routers attach the guard.

**Contract**: One bullet: "New protected domain routers must add `dependencies=[Depends(get_current_user)]`; only `health/` and public `auth/` endpoints are unguarded."

### Success Criteria

#### Automated Verification

- Dependencies install: `cd backend && uv sync`
- Lint + format pass: `uv run ruff check . && uv run ruff format --check .`
- Imports resolve / app builds: `uv run python -c "from app.main import app"`

#### Manual Verification

- **Note**: no guarded *route* exists yet at this boundary — the domain routers (medicines/cabinet/users) are empty (zero path operations), so FastAPI never reaches the router-level guard and a request returns 404, not 401. The real 401/200 route check moves to Phase 2 (after `GET /auth/me` exists). Phase 1 guard confidence comes from the monkeypatched guard unit test, not a live curl.
- The guard unit test (missing/expired/wrong-audience → 401, valid → passes) is present and the guard is wired onto the three domain routers (code review of the `dependencies=[...]` constructor arg).
- `/health` and `/auth/*` remain reachable without a token.

**Implementation Note**: After automated verification passes, pause for manual confirmation before Phase 2.

---

## Phase 2: Backend — Auth Endpoints & Provisioning

### Overview

Implement `register` / `login` / `logout` / `refresh` / `me` through router→service→crud, set/clear the httpOnly refresh cookie, provision the local `users` + default `user_preferences` rows at register time, and add pytest coverage.

### Changes Required

#### 1. Auth CRUD (provisioning)

**File**: `backend/app/api/v1/auth/crud.py`

**Intent**: Idempotent local provisioning of the user identity + default preferences keyed to the Supabase user id.

**Contract**: `async def provision_user(session, user_id: UUID, email: str) -> None` — upsert a `users` row (`id=user_id`) and, if absent, a `user_preferences` row with model defaults. Use PostgreSQL `ON CONFLICT DO NOTHING` so re-runs are safe. No business logic beyond inserts.

#### 2. Auth service

**File**: `backend/app/api/v1/auth/service.py`

**Intent**: Orchestrate Supabase Auth calls + local provisioning; translate Supabase errors into HTTP errors with Polish messages.

**Contract**:
- `register(session, data: RegisterRequest) -> tuple[AuthResponse, refresh_token]` — calls `supabase.auth.sign_up`; on success extracts `session.access_token`/`refresh_token` and `user.id`/`email`, calls `provision_user`, returns the response + refresh token for the router to set as a cookie.
- `login(session, data) -> tuple[AuthResponse, refresh_token]` — `supabase.auth.sign_in_with_password`; safety-net `provision_user`.
- `refresh(refresh_token: str) -> tuple[AuthResponse, new_refresh_token]` — `supabase.auth.refresh_session`; returns rotated tokens.
- `logout(access_token)` — `supabase.auth.sign_out`.
- Map Supabase auth failures (bad credentials, duplicate email) to `HTTPException(401/409)` with Polish `detail`.

#### 3. Auth router

**File**: `backend/app/api/v1/auth/router.py`

**Intent**: Public auth endpoints + the protected `me`; own the httpOnly refresh cookie lifecycle.

**Contract**:
- `POST /auth/register`, `POST /auth/login` → call service, set refresh cookie on the `Response` (`httponly=True`, `samesite="lax"`, `secure` in prod), return `AuthResponse`.
- `GET /auth/refresh` → read `request.cookies["refresh_token"]`, call service, reset rotated cookie, return new `AuthResponse`; 401 if cookie missing/invalid.
- `POST /auth/logout` → clear the cookie, call service sign_out, return 204.
- `GET /auth/me` → `Depends(get_current_user)`, return `UserOut`. (Used by frontend rehydrate-then-validate.)
- Cookie name `refresh_token`; path scoped to `/api/v1/auth`.

#### 4. CORS credentials

**File**: `backend/app/main.py`

**Intent**: Allow the browser to send/receive the httpOnly refresh cookie cross-origin.

**Contract**: Add `allow_credentials=True` to `CORSMiddleware`. (Origins already explicit, which is required when credentials are allowed — wildcard origins are incompatible.)

#### 5. Tests

**File**: `backend/tests/test_auth.py` (new), `backend/tests/conftest.py` (**extend — already exists** with a live-DB `db_session` fixture; do not overwrite it)

**Intent**: Cover the security-critical guard and the endpoint contracts **hermetically** — no live Supabase Auth and no live Postgres, so the suite runs from the agent's Bash tool (per lessons.md **L-001**, any TLS DB connection hard-aborts under Bash; the existing live-DB `db_session` fixture must NOT be in the auth-test path).

**Contract**: `httpx.AsyncClient` against the app. **DB isolation**: override the app's session dependency with `app.dependency_overrides[get_session] = lambda: <AsyncMock session>` so `provision_user` writes are asserted against the mock, never live Postgres (prefer mocking the session/crud over aiosqlite — aiosqlite won't honor the PG `ON CONFLICT` syntax). Guard tests: missing token → 401, expired token → 401, wrong-audience → 401, valid token → passes (monkeypatch the JWKS/decode path). Endpoint tests: register/login return access token + set refresh cookie and assert `provision_user` was called; refresh with/without cookie; logout clears cookie — all with the `supabase` client mocked. Add fixtures to the **existing** `conftest.py`: the async client fixture, the mocked Supabase client, and the `get_session` override teardown. The real provisioning SQL (`ON CONFLICT` against Postgres) is exercised by the Phase 2 **manual** gate (2.3, rows verified in the Supabase table editor), not the automated suite.

### Success Criteria

#### Automated Verification

- Tests pass: `cd backend && uv run pytest`
- Lint + format pass: `uv run ruff check . && uv run ruff format --check .`

#### Manual Verification

- Against a live Supabase project: `register` creates a Supabase user, returns an access token, sets the refresh cookie, and inserts `users` + `user_preferences` rows (verify in Supabase table editor).
- `login` then `GET /auth/refresh` (cookie present) returns a fresh access token.
- `logout` clears the cookie; a subsequent refresh returns 401.
- Now that `GET /auth/me` exists, the guard is verifiable on a live route: `curl` `/auth/me` with no/invalid token → 401; with a valid Bearer → 200. (This is the real-route check deferred from Phase 1.)

**Implementation Note**: After automated verification passes, pause for manual confirmation before Phase 3.

---

## Phase 3: Frontend — Foundation

### Overview

Install the frontend libraries, configure the `@/` alias, build the `lib/` layer (api-client with single-flight refresh retry, query-client, cn util), the `app/` composition root (providers, router, layouts including ProtectedLayout), and the auth store.

### Changes Required

#### 1. Dependencies + alias

**File**: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.app.json`

**Intent**: Add routing, server-state, validation, and form libs; enable `@/*` imports.

**Contract**: Add `react-router-dom`, `@tanstack/react-query`, `zod`, `react-hook-form`, `@hookform/resolvers`, `clsx`, `tailwind-merge`. Add `@` → `./src` alias in both `vite.config.ts` (`resolve.alias`) and `tsconfig.app.json` (`compilerOptions.paths`).

#### 2. api-client

**File**: `frontend/src/lib/api-client.ts` (new)

**Intent**: Sole backend client — base URL, Bearer attach, single-flight on-401 refresh-and-retry.

**Contract**: `apiFetch(path, options)` prefixes `${import.meta.env.VITE_API_URL}/api/v1`, attaches `Authorization: Bearer <token-from-store>`, sends `credentials: "include"`. On `401`: call `GET /auth/refresh` once through a shared module-level in-flight promise (single-flight); on success update the stored token and retry the original request; on failure clear the auth store and redirect to `/login`. Typed JSON helpers.

```ts
// Non-obvious: single-flight latch so concurrent 401s share one refresh
let refreshing: Promise<string | null> | null = null;
function refreshOnce() {
  refreshing ??= doRefresh().finally(() => { refreshing = null; });
  return refreshing;
}
```

#### 3. query-client + cn util

**File**: `frontend/src/lib/query-client.ts` (new), `frontend/src/lib/utils.ts` (new)

**Intent**: Configured TanStack `QueryClient` and the `cn()` helper.

**Contract**: `query-client.ts` exports a `QueryClient` with sensible defaults (no aggressive retry on 401). `utils.ts` exports `cn(...inputs)` = `twMerge(clsx(inputs))`.

#### 4. Auth store

**File**: `frontend/src/features/auth/store.ts` (new)

**Intent**: Hold session state (access token + user) with localStorage persistence for the token.

**Contract**: A small store (React context or `useSyncExternalStore`/zustand-free context) exposing `token`, `user`, `setSession`, `clearSession`. Token read from / written to `localStorage` under a single key. `clearSession` removes the key.

**Security note (accepted risk)**: the access JWT in `localStorage` is readable by any injected script (XSS) — the very exposure the httpOnly refresh cookie avoids. Accepted for this slice; mitigated by short access-token lifetime + strict input handling. Revisit (in-memory token + silent refresh) if the threat model tightens.

#### 5. App composition root

**File**: `frontend/src/app/providers.tsx`, `frontend/src/app/router.tsx`, `frontend/src/app/layouts/protected-layout.tsx`, `frontend/src/app/layouts/public-layout.tsx`, updated `frontend/src/main.tsx`

**Intent**: Wire providers (QueryClientProvider, auth store provider, RouterProvider) and define public vs protected route trees.

**Contract**: `providers.tsx` nests QueryClient + auth providers. `router.tsx` defines routes: public (`/login`, `/register`) under `public-layout`; protected (`/`, placeholder dashboard) under `protected-layout`. `ProtectedLayout` redirects to `/login` when no token; renders an `<Outlet/>` otherwise. `main.tsx` renders `<Providers><RouterProvider/></Providers>`.

#### 6. Env

**File**: `frontend/.env.local` (gitignored), `frontend/.env.structure` (or example)

**Intent**: Point the api-client at the backend.

**Contract**: `VITE_API_URL=http://localhost:8000`. Document the var; never commit real values.

### Success Criteria

#### Automated Verification

- Install: `cd frontend && npm install`
- Type + build pass: `npm run build`
- Lint pass: `npm run lint`
- Format pass: `npx prettier --check src/`

#### Manual Verification

- `npm run dev` serves; navigating to a protected route with no token redirects to `/login`.
- `@/` imports resolve in the editor and at build.

**Implementation Note**: After automated verification passes, pause for manual confirmation before Phase 4.

---

## Phase 4: Frontend — Auth Feature & Entry Screen

### Overview

Build the auth feature (RHF+zod login/register forms, logout control, typed api fetchers + Query hooks + query-key factory, zod schemas), the Polish entry-screen UI, and rehydrate-then-validate session restoration on load.

### Changes Required

#### 1. Auth schemas

**File**: `frontend/src/features/auth/schemas/auth-schemas.ts` (new)

**Intent**: Single source for validation + inferred form types.

**Contract**: zod `loginSchema` (email, password) and `registerSchema` (email, password, min length) with **Polish** error messages; export inferred `LoginValues` / `RegisterValues` types.

#### 2. Auth api + query hooks

**File**: `frontend/src/features/auth/api/auth-api.ts` (new), `frontend/src/features/auth/api/auth-queries.ts` (new)

**Intent**: Typed REST contract + cache/mutation layer over the backend auth endpoints.

**Contract**: `auth-api.ts`: `register`, `login`, `logout`, `refresh`, `getMe` calling `apiFetch`. `auth-queries.ts`: a query-key factory `authKeys`, `useLogin`/`useRegister`/`useLogout` mutations (set/clear auth store on success), `useMe` query for rehydrate validation.

#### 3. Auth forms + logout control

**File**: `frontend/src/features/auth/components/login-form.tsx`, `register-form.tsx`, `logout-button.tsx` (new)

**Intent**: The entry-screen forms and the logout action, all Polish copy.

**Contract**: `LoginForm` / `RegisterForm` use `useForm` + `zodResolver(loginSchema/registerSchema)`, render fields with inline Polish validation errors, submit via `useLogin`/`useRegister`, show server-error state and a pending state. `LogoutButton` calls `useLogout`. Use `components/ui` primitives if created, else minimal Tailwind.

#### 4. Auth pages

**File**: `frontend/src/features/auth/components/login-page.tsx`, `register-page.tsx` (new), placeholder `frontend/src/features/dashboard/components/dashboard-page.tsx` (new)

**Intent**: Route targets — entry screen (login/register, link between them) and a protected landing placeholder bearing the logout control.

**Contract**: `LoginPage`/`RegisterPage` compose the forms + a link to the other. `DashboardPage` is a minimal protected placeholder rendering "Zalogowano" + `LogoutButton`. Wire these into `app/router.tsx`.

#### 5. Session rehydration

**File**: `frontend/src/app/layouts/protected-layout.tsx` (update), `frontend/src/features/auth/hooks/use-session-init.ts` (new)

**Intent**: On app load, validate a persisted token before granting access; auto-logout on invalid.

**Contract**: `use-session-init`: if a token exists in the store, call `getMe` (`/auth/me`); on success hydrate `user`, on 401 clear the session. `ProtectedLayout` shows a brief loading state while validating, then redirects to `/login` if unauthenticated or renders the `<Outlet/>`.

### Success Criteria

#### Automated Verification

- Type + build pass: `cd frontend && npm run build`
- Lint pass: `npm run lint`
- Format pass: `npx prettier --check src/`

#### Manual Verification

- Register on the entry screen → immediately logged in → lands on the protected placeholder (auto-confirm).
- Refresh the page while logged in → stays logged in (rehydrate-then-validate).
- Logout → returns to `/login`; the protected route is no longer reachable.
- Invalid credentials show a Polish error; invalid form input shows Polish field errors.
- Let the access token expire (or clear it) → next API call triggers the single-flight refresh-and-retry; if refresh fails, redirected to `/login`.

**Implementation Note**: After automated verification passes, pause for manual confirmation. This completes the slice.

---

## Testing Strategy

### Unit / Integration Tests (backend, this slice)

- JWT guard: missing / expired / wrong-audience / wrong-issuer tokens → 401; valid token → passes (JWKS/decode path monkeypatched).
- Endpoints (Supabase client mocked): register returns access token + sets refresh cookie + provisions `users`/`user_preferences`; login likewise; refresh with/without cookie; logout clears cookie.

### Manual Testing Steps

1. Start backend (`uv run uvicorn app.main:app --reload`) + frontend (`npm run dev`) against a live Supabase project with email confirmation disabled.
2. Register a new user → confirm immediate login + rows in Supabase `users`/`user_preferences`.
3. Refresh the browser → still logged in.
4. Logout → back to `/login`; protected route blocked.
5. `curl` a protected route without a token → 401; with a valid Bearer → passes.

### Deferred (not this slice)

- Frontend Vitest/RTL component tests; Playwright `auth.setup.ts` + golden-path E2E (lands in S-01).

## Performance Considerations

- JWKS verification is local (no per-request Supabase round-trip); `PyJWKClient` caches signing keys — instantiate once at module load.
- TanStack Query should not retry on 401 (avoids hammering during an expired session); the api-client handles refresh, not Query retries.

## Migration Notes

- No schema changes — `users` / `user_preferences` already exist (F-02). Provisioning only inserts rows.
- Supabase project must have **email confirmation disabled** for the auto-confirm flow. Document this as a prerequisite.
- New env vars: backend `SUPABASE_URL`, `SUPABASE_ANON_KEY`; frontend `VITE_API_URL`. Keep out of git (AGENTS.md secret rule).

## References

- Library research: `context/changes/auth-scaffold/research.md`
- Roadmap slice F-01: `context/foundation/roadmap.md:68`
- PRD auth + access control: `context/foundation/prd.md:77`, `:171`
- Existing models: `backend/app/api/v1/users/models.py`, `backend/app/api/v1/cabinet/models.py`
- Backend layer rules / frontend structure rules: `AGENTS.md`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles.

### Phase 1: Backend — Auth Config & JWT Guard

#### Automated

- [x] 1.1 Dependencies install: `uv sync`
- [x] 1.2 Lint + format pass: `uv run ruff check . && uv run ruff format --check .`
- [x] 1.3 App imports / builds: `uv run python -c "from app.main import app"`

#### Manual

- [x] 1.4 No guarded route exists yet — real 401/200 check deferred to Phase 2 (Phase 1 confidence via monkeypatched guard unit test)
- [x] 1.5 Guard unit test present + guard wired onto the three domain routers (code review of `dependencies=[...]`)
- [x] 1.6 `/health` and `/auth/*` reachable without a token

### Phase 2: Backend — Auth Endpoints & Provisioning

#### Automated

- [ ] 2.1 Tests pass: `uv run pytest`
- [ ] 2.2 Lint + format pass: `uv run ruff check . && uv run ruff format --check .`

#### Manual

- [ ] 2.3 Register creates Supabase user + returns access token + sets refresh cookie + inserts `users`/`user_preferences`
- [ ] 2.4 Login then `GET /auth/refresh` (cookie) returns a fresh access token
- [ ] 2.5 Logout clears cookie; subsequent refresh returns 401
- [ ] 2.6 `GET /auth/me`: no/invalid token → 401, valid Bearer → 200 (real-route guard check deferred from Phase 1)

### Phase 3: Frontend — Foundation

#### Automated

- [ ] 3.1 Install: `npm install`
- [ ] 3.2 Type + build pass: `npm run build`
- [ ] 3.3 Lint pass: `npm run lint`
- [ ] 3.4 Format pass: `npx prettier --check src/`

#### Manual

- [ ] 3.5 Protected route with no token redirects to `/login`
- [ ] 3.6 `@/` imports resolve at build and in editor

### Phase 4: Frontend — Auth Feature & Entry Screen

#### Automated

- [ ] 4.1 Type + build pass: `npm run build`
- [ ] 4.2 Lint pass: `npm run lint`
- [ ] 4.3 Format pass: `npx prettier --check src/`

#### Manual

- [ ] 4.4 Register → immediately logged in → protected placeholder
- [ ] 4.5 Page refresh keeps the session (rehydrate-then-validate)
- [ ] 4.6 Logout returns to `/login`; protected route blocked
- [ ] 4.7 Invalid credentials + invalid form input show Polish errors
- [ ] 4.8 Expired token triggers single-flight refresh-and-retry; failed refresh redirects to `/login`

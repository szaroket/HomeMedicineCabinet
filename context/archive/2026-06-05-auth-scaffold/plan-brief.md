# Auth Scaffold (F-01) — Plan Brief

> Full plan: `context/changes/auth-scaffold/plan.md`
> Research: `context/changes/auth-scaffold/research.md`

## What & Why

Wire Supabase Auth end-to-end through FastAPI (FastAPI is the sole Supabase client) and bootstrap the frontend's auth foundation. F-01 is the foundation slice every downstream feature depends on: without a verified user identity and a route guard, no cabinet data can be safely read or written, and auth bugs found late are expensive to retrofit.

## Starting Point

Backend auth is empty stubs; `config.py` has only `database_url`; no `supabase-py`/`pyjwt`. The data layer is already live (F-02/F-03): `users`, `user_preferences`, `cabinet_entries`, `medication_registry` tables exist, with `cabinet_entries.user_id` FK → `users.id`. The frontend is a bare Vite scaffold — no router, TanStack Query, zod, `@/` alias, or `app/`/`lib/`/`features/` tree yet.

## Desired End State

A user opens the app, sees a Polish entry screen, registers (auto-confirmed → immediately logged in), and lands on a protected route that survives page refresh; logout returns them to the entry screen. Every `/api/v1` domain route except public auth + health rejects unauthenticated requests with 401. Registration provisions a local `users` row (id = Supabase `sub`) + default `user_preferences`.

## Key Decisions Made

| Decision | Choice | Why | Source |
| --- | --- | --- | --- |
| Auth client + token verification | `supabase-py` + `PyJWT` JWKS/`PyJWKClient` | Official SDK + FastAPI-recommended local verification, no per-request round-trip | Research |
| Access token storage | localStorage | Simplest for an SPA talking only to FastAPI; matches Bearer contract | Plan |
| Refresh token storage | httpOnly cookie + `GET /auth/refresh` | Keeps the long-lived credential out of JS; browser auto-sends it, solving auth-at-refresh | Plan |
| Refresh automation | endpoint + on-401 retry-once (single-flight) | Sessions survive expiry without timers; one contained interceptor | Plan |
| Email confirmation | auto-confirm now | Keeps F-01 minimal/verifiable; confirmation is purely additive later (no rework) | Plan |
| User provisioning | F-01, at register time | DB is live; registration is the natural moment; unblocks all FK-dependent slices | Plan |
| Frontend forms | react-hook-form + zod resolver | One schema = validation + types; scales to richer later forms | Plan |
| Route protection | ProtectedLayout + rehydrate-then-validate | Single choke point, survives refresh | Plan |
| Backend guard scope | all `/api/v1` except public auth + `/health`, router-level dep | Secure-by-default, matches layered-deps pattern | Plan |
| Testing | backend pytest only (guard + endpoints) | Covers the security-critical surface without over-investing in a scaffold | Plan |

## Scope

**In scope:** register/login/logout/refresh/me endpoints; layered JWT guard applied to domain routers; local user + default-preferences provisioning; frontend `app/`/`lib/`/`features/auth` foundation; Polish entry screen; session rehydration; backend tests.

**Out of scope:** email confirmation/SMTP, password reset, profile/account settings, silent/timer refresh, frontend unit tests + Playwright E2E, RLS policy work, admin/service-role usage.

## Architecture / Approach

Frontend POSTs credentials → FastAPI calls `supabase-py` → returns access JWT (body) + sets refresh token (httpOnly cookie). Frontend stores the access token in localStorage and sends `Authorization: Bearer`; a single-flight `api-client` refreshes once on 401. A `PyJWKClient`-backed dependency validates tokens locally and guards every domain router. Backend phases land first so the contract is real before the frontend consumes it.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Backend config & guard | Settings, libs, Supabase client, JWT dependency applied to routers | Algorithm pinning / JWKS setup correctness |
| 2. Backend endpoints & provisioning | register/login/logout/refresh/me, refresh cookie, provisioning, pytest | Refresh-cookie + CORS `allow_credentials` contract |
| 3. Frontend foundation | deps, `@/` alias, `lib/` (api-client single-flight), `app/` root, auth store | Single-flight refresh race handling |
| 4. Frontend auth feature | RHF+zod forms, entry screen, route protection, rehydration | Session rehydrate/auto-logout edge cases |

**Prerequisites:** Supabase project with Auth enabled and **email confirmation disabled**; env vars `SUPABASE_URL`, `SUPABASE_ANON_KEY` (backend), `VITE_API_URL` (frontend).
**Estimated effort:** ~2–3 sessions across 4 phases (2 backend, 2 frontend).

## Open Risks & Assumptions

- Assumes `users.id` is intended to equal the Supabase auth `sub` (strongly implied by the existing FK design) — provisioning depends on it.
- Refresh cookie cross-origin requires `allow_credentials=True` + `credentials: "include"` + correct `samesite`/`secure`; the most likely silent failure point.
- React is new territory (tech-stack self-check 4/5) — the single-flight refresh and rehydration logic warrant extra review.

## Success Criteria (Summary)

- Register → immediate login → protected route that survives refresh; logout works.
- Unauthenticated requests to protected routes return 401; valid Bearer passes.
- Registration creates the local `users` + default `user_preferences` rows.

<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Auth Scaffold (F-01)

- **Plan**: context/changes/auth-scaffold/plan.md
- **Scope**: Full plan, Phases 1–4 of 4
- **Date**: 2026-06-08
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 7 warnings, 3 observations
- **Triage (2026-06-08)**: 8 fixed (F1, F2, F4, F5, F6, F9, F10 + F3 via Fix A), 1 confirmed-no-change (F8), 1 skipped (F7). F3 deferred true-revocation logged as v2 in plan.md.

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | WARNING |
| Safety & Quality | WARNING |
| Architecture | WARNING |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

**Note**: Both review sub-agents independently rated F1 (missing `Secure` cookie flag) CRITICAL. Set to WARNING / HIGH-impact here because the scaffold is localhost-only with no prod deploy yet — but it is a hard gate that must be fixed before any non-localhost deployment.

**Automated verification (all pass)**: backend `uv run pytest tests/test_auth.py` → 12 passed; `ruff check` clean; `ruff format --check` clean. frontend `npm run build` ✓, `npm run lint` ✓, `npx prettier --check src/` ✓. (`test_db.py` is a live-DB smoke test that aborts under the Bash tool per lessons L-001 — outside this slice's hermetic auth suite.)

## Findings

### F1 — Refresh cookie missing `Secure` flag

- **Severity**: ⚠️ WARNING (sub-agents: CRITICAL)
- **Impact**: 🔬 HIGH — architectural stakes; think carefully before deciding
- **Dimension**: Safety & Quality
- **Location**: backend/app/api/v1/auth/router.py:25–32 (_set_refresh_cookie)
- **Detail**: The refresh cookie is set `httponly=True, samesite="lax"` but never `secure=True`. The plan's contract explicitly required "secure in prod". As written the long-lived refresh token can traverse plain HTTP. The matching `delete_cookie` must use the same attributes or the clear won't match the set cookie.
- **Fix**: Add `secure` gated on environment (e.g. an `auth_cookie_secure` setting defaulting True, False for localhost dev) on both set and clear, so dev over HTTP still works while prod is hardened.
- **Decision**: FIXED — added `auth_cookie_secure` setting (default True), applied `secure` + matching attributes on both set and clear cookie.

### F2 — provision_user commit not isolated; register can 500 post-signup

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/app/api/v1/auth/crud.py:16–35; service.py register path
- **Detail**: `provision_user` calls `session.commit()` with no try/except and no rollback. If the DB write fails after `supabase.auth.sign_up` already created the auth user, register raises an uncaught 500 — the Supabase user exists but has no local rows, and the response/cookie is lost. Partly mitigated by idempotent re-provision on next login.
- **Fix**: Wrap the provision call in service-layer handling that maps DB failure to a domain error (e.g. `ProvisioningError` in utilities/errors.py) and rolls back the session.
- **Decision**: FIXED — added `ProvisioningError`; `provision_user` now rolls back + raises on `SQLAlchemyError`; router maps it to 500 in register + login.

### F3 — logout doesn't revoke the Supabase session

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/app/api/v1/auth/router.py:119–122; service.py logout
- **Detail**: Router calls `logout(access_token="")` and the service calls `sign_out()` on the shared module client with no user session bound, so the refresh token stays valid at Supabase until expiry. Only the cookie is cleared. The docstring claims it signs the user out of Supabase, overstating behaviour.
- **Fix**: Either pass the real token and call `sign_out` with proper scope to truly revoke, or drop the Supabase call and re-document the endpoint as cookie-clear-only so it isn't misleading.
- **Decision**: FIXED (Fix A) — removed the no-op `sign_out` call and the unused `service.logout`; logout is now cookie-clear-only with an honest docstring. True revocation deferred to v2 (added to plan).
- **Observation (for v2)**: Fix B is the strictly safer option and the right long-term target. Mechanics confirmed against the vendored `supabase_auth/_sync/gotrue_client.py`:
  - The access-token JWT **cannot** be revoked by any approach — it stays valid until expiry (`gotrue_client.py:786`). Mitigate via a short JWT expiry in the Supabase dashboard.
  - The current `sign_out()` was a no-op because it relies on `get_session()`, which is empty on the shared module-level client (`gotrue_client.py:791-792`).
  - To truly revoke the refresh token at Supabase: use a **request-scoped** client (never `set_session` on the shared client — it mutates state across concurrent requests), call `set_session(access_token, refresh_token)` then `sign_out(scope="global")` (which routes to `admin.sign_out`, `gotrue_client.py:794`). This revokes ALL of the user's refresh tokens server-side.
  - Router wiring needed: capture the raw access token (logout currently discards it) and read the refresh cookie, passing both to the service.

### F4 — Cold-start refresh race: un-latched duplicate refresh path

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: frontend/src/features/auth/hooks/use-session-init.ts:5–19 vs frontend/src/lib/api-client.ts:8–23
- **Detail**: `use-session-init` re-implements a refresh fetch that does NOT share api-client's single-flight `refreshing` latch. On cold load a hook refresh and a 401-triggered api-client refresh can run concurrently, each rotating the refresh token; with Supabase rotation one rotated token becomes invalid → intermittent logout on startup. (The api-client latch itself is correct in isolation.)
- **Fix**: Export `refreshOnce()` from api-client and have `use-session-init` reuse it so all refreshes share one latch / one rotation.
- **Decision**: FIXED — exported `refreshOnce()` from api-client; `use-session-init` now reuses it and its duplicate `trySilentRefresh` fetch was removed, so all refreshes share one latch.

### F5 — Hard navigation inside the transport layer

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Architecture
- **Location**: frontend/src/lib/api-client.ts:54–56
- **Detail**: On refresh failure api-client does `window.location.href = "/login"` and removes the token directly, bypassing React Router and the store's `clearSession` — in-memory user/token state is left stale, and a full reload mid-request can race concurrent in-flight calls.
- **Fix**: Reject with a typed auth error and let `use-session-init` / router handle `clearSession()` + `<Navigate>`, keeping navigation out of the fetch wrapper.
- **Decision**: FIXED — added `lib/errors.ts::AuthError`; api-client now throws it (no DOM/storage side-effects) on refresh failure; `AuthProvider` subscribes to the query/mutation caches and calls `clearSession()` on `AuthError`, letting `ProtectedLayout` do the `<Navigate to="/login">`. Retry guard in query-client also skips retry on `AuthError`. Frontend `npm run build` + `npm run lint` pass.

### F6 — `Security()` vs `Depends()` guard inconsistency

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: medicines/cabinet/users router.py (Security) vs auth/router.py:117 (Depends) + AGENTS.md:76 (Depends)
- **Detail**: Domain routers guard with `Security(get_current_user)`; the auth router and AGENTS.md use `Depends(get_current_user)`. Both work (Security is better for OpenAPI lock icons) but the mix will trip future authors.
- **Fix**: Pick one — recommend Security everywhere — and update AGENTS.md:76 to match.
- **Decision**: FIXED — auth/router.py now uses `Security(get_current_user)` for logout + me; AGENTS.md:76 updated to mandate `Security`. ruff clean.

### F7 — Three unused placeholder components (dead code)

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: frontend/src/features/auth/components/login-placeholder.tsx, register-placeholder.tsx, dashboard/components/dashboard-placeholder.tsx
- **Detail**: Confirmed via grep: defined but never imported or routed — superseded by the real `*-page.tsx` files. Harmless but clutters the feature tree.
- **Fix**: Delete the three placeholder files.
- **Decision**: SKIPPED

### F8 — Backend error `detail` strings are English (plan said Polish)

- **Severity**: ℹ️ OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: backend/app/utilities/errors.py; auth/schemas.py:34
- **Detail**: Plan repeatedly specified Polish detail messages, but the project memory rule mandates English-only backend error messages, and the frontend forms render their own Polish copy (ignoring server detail). This is a PLAN defect, not an implementation miss — the code follows conventions. Worth confirming the detail string is non-user-facing.
- **Fix**: Confirm the contract; if `detail` is never surfaced to users, leave English and note it. Optionally add a machine-readable `code`.
- **Decision**: CONFIRMED — contract is English in backend error messages, Polish in the UI for end users. Implementation is correct; this is a PLAN defect, not a code miss. No change. (Matches existing project convention in memory `feedback_error_conventions`.)

### F9 — Test coverage gaps vs plan

- **Severity**: ℹ️ OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: backend/tests/test_auth.py; conftest.py
- **Detail**: Plan listed a wrong-audience→401 guard test (`InvalidAudienceError` branch is untested); `test_logout_clears_cookie` asserts the substring "refresh_token" appears rather than that it's a deletion (Max-Age=0); fixtures live inline in test_auth.py rather than extending conftest.py as planned. All 12 present tests pass.
- **Fix**: Add a wrong-audience guard case and tighten the logout assertion.
- **Decision**: FIXED — added `test_guard_wrong_audience` (InvalidAudienceError → 401); tightened `test_logout_clears_cookie` to also assert `Max-Age=0` (true deletion). Suite now 13 passed, ruff + format clean. (Inline-fixtures-vs-conftest noted but left as-is — out of scope for this fix.)

### F10 — Duplicated hardcoded `"auth_token"` key; writes bypass store

- **Severity**: ℹ️ OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: features/auth/store.ts; lib/api-client.ts:45; use-session-init.ts
- **Detail**: The literal `"auth_token"` is repeated across three files and api-client writes localStorage directly instead of going through the store — drift risk if the key/format ever changes.
- **Fix**: Export a `TOKEN_KEY` + setter from store.ts and route all token writes through it.
- **Decision**: FIXED — added `setStoredToken()` to store.ts (single source for the key); api-client and use-session-init now write through it instead of the hardcoded literal. Frontend build + lint + prettier clean.

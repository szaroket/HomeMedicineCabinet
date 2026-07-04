<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Delete User Account

- **Plan**: context/changes/delete-user-account/plan.md
- **Mode**: Deep
- **Date**: 2026-07-04
- **Verdict**: REVISE → SOUND (all 4 findings fixed in triage 2026-07-04)
- **Findings**: 1 critical, 1 warning, 2 observations (all FIXED)

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | FAIL → PASS (F1, F2 fixed) |
| Plan Completeness | WARNING → PASS (F3, F4 fixed) |

## Grounding

9/9 paths ✓ (facade.py correctly new), symbols ✓, brief↔plan ✓, Progress↔Phase ✓.
Verified: FK declared without `ondelete` (users/models.py:29, cabinet/models.py:20);
`persist` signature (connector.py:40); `settings = Settings()` module singleton
(config.py:53); CI env blocks (ci-cd.yml:93-97, 208-212, 220-232); frontend
`clearSession`/`LogoutButton`/`apiFetch` patterns; `provision_user` idempotency
(auth/crud.py:20).

## Findings

### F1 — New required config field breaks every CI test job

- **Severity**: ❌ CRITICAL
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 1 §1 (config) + Migration Notes
- **Detail**: Plan adds `supabase_service_role_key: str` as a REQUIRED field (no
  default). `settings = Settings()` is a module-level singleton (config.py:53),
  evaluated at import time whenever any module imports app code. CI provides
  Supabase env vars inline and only three of them: ci-cd.yml:93-97 (unit-test
  job), ci-cd.yml:208-212 (integration job), ci-cd.yml:220-232 (e2e job +
  secrets-presence loop) — all supplying DATABASE_URL, SUPABASE_URL,
  SUPABASE_ANON_KEY. A required field with no default makes `Settings()` raise
  ValidationError at collection time → every CI test job fails as an import crash,
  not a test failure. The plan's own Phase 1 automated verification runs in these
  jobs. Plan covers local `.env` (1.4) and Render (1.4) but never mentions
  ci-cd.yml; `.env.example` doesn't exist so that conditional is moot.
- **Fix A ⭐ Recommended**: Keep required, extend CI + docs — add
  SUPABASE_SERVICE_ROLE_KEY to the two test `env:` blocks (placeholder value is
  fine; Supabase admin is mocked in tests) and to the e2e secrets loop; add the
  key to local `.env`; add a Phase 1 step for it.
  - Strength: Fail-fast on misconfig; matches how the other three required
    Supabase vars are already wired in CI.
  - Tradeoff: Must touch ci-cd.yml in three places or the branch is red on first push.
  - Confidence: HIGH — verified the exact env blocks and the import-time singleton.
  - Blind spot: None significant.
- **Fix B**: Make the field optional, validate at the delete call site —
  `supabase_service_role_key: str | None = None`; raise a clear config error inside
  `get_supabase_admin()` if unset, so only the delete path requires it.
  - Strength: Config load never breaks; CI/tests unaffected.
  - Tradeoff: Misconfiguration surfaces only at delete time (runtime 5xx) instead
    of at boot; weaker guarantee for a highly sensitive credential.
  - Confidence: HIGH.
  - Blind spot: Need a test asserting the "unset key" path errors cleanly rather
    than leaking a stack trace.
- **Decision**: FIXED via Fix A

### F2 — Post-commit Supabase failure leaves client authenticated over half-deleted local state

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Critical Implementation Details + Phase 3 §2/§3
- **Detail**: The plan reasons carefully about the *server* half-state (orphaned
  auth user, idempotent re-provision) but not the *client* half-state. On
  `AccountDeletionError` (Supabase delete fails AFTER the local commit), the
  frontend contract says "show a Polish error and keep the user on the page." At
  that point `clearSession` has NOT run (it's `onSuccess`-only per §2), so the user
  sits on Settings with a still-valid JWT but their
  `users`/`user_preferences`/`cabinet_entries` rows already gone. The preferences
  endpoint tolerates this (returns defaults), but any protected endpoint assuming a
  live users row or cabinet data now behaves oddly until a re-login re-provisions
  empty rows. The user has no signal their data is already destroyed.
- **Fix**: On the chosen 5xx, still tear down the client session (clearSession +
  queryClient.clear + redirect to /login) and show a "częściowo usunięto — spróbuj
  zalogować się ponownie"-style notice, rather than leaving them authenticated over
  destroyed state. Retry-after-relogin is already idempotent, so this is safe. If
  instead you accept keeping them on-page, document the rationale in "What We're NOT
  Doing".
  - Strength: Client state never contradicts server state; recovery path
    (re-login → retry) is already sound.
  - Tradeoff: Slightly more error-path UI than the happy path needs.
  - Confidence: MED — depends on which other protected endpoints assume a users
    row; not exhaustively swept.
  - Blind spot: Behavior of non-preferences protected endpoints when the local
    users row is missing is unverified.
- **Decision**: FIXED via Fix

### F3 — Unresolved HTTP status for AccountDeletionError

- **Severity**: 🔷 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 2 §4; Success Criteria 2.3; Progress 2.3
- **Detail**: Endpoint contract says "AccountDeletionError → 502 or 500 — pick one,"
  but Success Criteria 2.3 and Progress 2.3 assert the mapping ("chosen 5xx"). The
  integration test can't be finalized until the number is fixed. Small, but it's a
  real TBD a success criterion depends on.
- **Fix**: Decide now — 502 Bad Gateway is the honest choice (an upstream Supabase
  admin failure is a bad response from a dependency). Lock it into the router
  contract and 2.3.
- **Decision**: FIXED — locked in 502

### F4 — `persist` fit + commit-ownership underspecified for bulk deletes

- **Severity**: 🔷 OBSERVATION
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Plan Completeness
- **Location**: Phase 2 §1/§2/§3 (crud + facade contracts)
- **Detail**: The established `persist(session, *instances)` (connector.py:40) is an
  add-and-refresh helper: `async with persist(session, obj): session.add(obj)` — it
  flushes then `session.refresh(instance)` for each passed instance, then commits. A
  bulk `delete(...).where(...)` has no ORM instance to add or refresh. The plan says
  each crud "does not independently commit; the facade controls the single commit"
  and "use persist/session transaction," but doesn't pin down the shape. Concretely:
  the facade should wrap both crud calls in a single `async with persist(session):`
  with NO instances (the refresh loop is then a harmless no-op); the crud fns keep
  their L-004 try/except around `session.execute` (catches the immediate DML error)
  but must NOT commit. Left vague, an implementer might nest a per-crud `persist`,
  breaking atomicity, or be unsure which domain error a commit-time failure maps to.
- **Fix**: In the facade contract, state explicitly: single `persist(session)` (no
  instances) around both crud deletes; crud fns execute+wrap per L-004 but never
  commit; deletes are child-before-parent so no FK error is expected at commit.
- **Decision**: FIXED via Fix

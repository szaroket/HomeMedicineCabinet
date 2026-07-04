<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Backend safety net — integration harness fixtures

- **Plan**: context/changes/testing-backend-safety-net/plan.md
- **Scope**: Phase 3 of 5
- **Date**: 2026-06-30
- **Verdict**: APPROVED
- **Findings**: 0 critical, 1 warning, 3 observations

## Verification notes

- Verified independently from the agent Bash tool: `ruff check tests/integration`
  (clean), CI-path suite `pytest --ignore=tests/db --ignore=tests/integration`
  (349 passed, DB-free).
- Docker-backed criteria (3.1 smoke, 3.2 isolation) and pyright (3.5) **cannot**
  run from the agent Bash tool: the `alembic upgrade head` subprocess inherits the
  Git Bash/MSYS environment and aborts with the L-001 OpenSSL applink error even
  against the plain-TCP container. They rely on the PowerShell run recorded for
  commit `49530dd`. Container teardown confirmed clean (no leftover containers).

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

## Findings

### F1 — Seed factories typed as AsyncIterator, forcing a type:ignore cascade

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/tests/integration/conftest.py:176, 205, 238, 277
- **Detail**: Each `seed_*` fixture returns an `async def _seed(...) -> tuple[...]`
  (i.e. `Callable[..., Awaitable[tuple[...]]]`) but is annotated
  `Callable[..., "AsyncIterator[tuple[...]]"]`. The annotation is wrong twice — it
  says AsyncIterator (async generator) when the callable returns an awaitable, and
  it omits the real payload. This forces `# type: ignore[return-value]` on every
  fixture and cascades into `# type: ignore[misc]` / `[assignment]` at all six call
  sites in test_harness_smoke.py:28,30,31,49. pyright "passes" only because the
  call sites are silenced — no real type safety on the factories. Phases 4 & 5 lean
  on these factories heavily, so the wrong types propagate ignore-noise and hide
  genuine mis-calls (wrong kwargs, wrong unpacking) exactly where coverage matters.
- **Fix**: Annotate as `Callable[..., Awaitable[tuple[User, CurrentUser]]]` (and the
  matching payloads for the other three), import `Awaitable` from `collections.abc`,
  and delete the now-unneeded `# type: ignore` comments in conftest and
  test_harness_smoke.py.
- **Decision**: FIXED

### F2 — SAVEPOINT restart relies on private `transaction._parent`

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/tests/integration/conftest.py:111
- **Detail**: The `after_transaction_end` listener gates the savepoint restart on
  `transaction.nested and not transaction._parent.nested`, reaching into
  SQLAlchemy's private `_parent` attribute — the legacy (1.3-era) form. On
  SQLAlchemy 2.0.50 (confirmed installed) the documented "join an external
  transaction" recipe checks public state (`nested.is_active` /
  `conn.in_nested_transaction()`). Works today (isolation verified under random
  order), but a private-attribute contract can shift on a minor upgrade and the
  failure mode is silent cross-test bleed, not a clean error. Minor inconsistency:
  the initial savepoint opens on `db_conn.begin_nested()` while the restart uses
  `sync_session.begin_nested()`.
- **Fix**: Adopt the 2.0 documented recipe — track the nested handle and restart on
  `if not nested.is_active`.
- **Decision**: FIXED (connection-state variant: `if not db_conn.in_nested_transaction()` with a `db_conn.closed` guard — avoids an AsyncTransaction→NestedTransaction handle type-flip)

### F3 — Manual 3.7 (act_as switches identity within a test) marked done, unexercised

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: context/changes/testing-backend-safety-net/plan.md:662
- **Detail**: Progress item 3.7 is checked, but neither smoke test performs an
  intra-test A→B identity switch — each calls `act_as` once. The capability is just
  a nonlocal setter (conftest.py:151), so the manual claim is plausible by
  inspection, but the switch isn't observably proven until the Phase 5 ownership
  tests. Not a defect — flagging so it isn't treated as already-covered when Phase 5
  writes the real two-identity test.
- **Fix**: No code change; ensure a Phase 5 ownership test exercises the within-test
  switch.
- **Decision**: QUEUED (follow-ups/review-fixes.md)

### F4 — authed_db_client docstring uses the wrong route

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/tests/integration/conftest.py:137
- **Detail**: The usage example shows `client.get("/api/v1/cabinet")`, but the real
  list route is `/api/v1/cabinet/entries` (what the smoke tests actually hit).
  Harmless, but it's the copy-paste source future phases will follow.
- **Fix**: Update the docstring example to `/api/v1/cabinet/entries`.
- **Decision**: FIXED

## Plan-accuracy note (not a code finding)

Critical Detail #1 and the Phase 2 contract claim the integration tier is "runnable
from the agent Bash tool." This is inaccurate — the `alembic` subprocess inherits the
MSYS environment and hits the L-001 applink abort. Reality is the L-001 PowerShell
execution fallback. Worth correcting in the plan/test-plan cookbook if revisited.

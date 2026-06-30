<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Backend business-logic + CRUD safety net (test-plan Phase 1)

- **Plan**: context/changes/testing-backend-safety-net/plan.md
- **Mode**: Deep
- **Date**: 2026-06-30
- **Verdict**: REVISE
- **Findings**: 0 critical · 2 warnings · 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | WARNING |
| Blind Spots | WARNING |
| Plan Completeness | WARNING |

## Grounding

9/9 paths ✓, 10/10 symbols ✓ (to_tsquery@crud.py:312, _sufficiency_clauses@crud.py:184,
find_entry_by_id@crud.py:433, service merge funcs@service.py:62-141, uq_cabinet_entries_user_med_expiry@models.py:15,
CI `--ignore=tests/db`@ci-cd.yml:97, pytest-randomly pinned @pyproject.toml), brief↔plan ✓.
Progress↔Phase contract ✓ (one `## Progress` block; all 5 phases mapped; every Success Criteria bullet → an `N.M` item).
Cornerstone assumptions independently verified: connector.py:21 and migrations/env.py:29 build the engine from the URL
with **no** forced SSL context → plain-TCP localhost genuinely sidesteps L-001 (claim correct). `search_vector` is **not**
mapped in the `MedicationRegistry` SQLModel model → plain ORM insert lets Postgres compute it (claim correct).

## Findings

### F1 — Event-loop scope / cross-loop connection pooling not addressed

- **Severity**: ⚠️ WARNING
- **Impact**: 🔬 HIGH — architectural stakes; think carefully before deciding
- **Dimension**: Blind Spots
- **Location**: Phase 2 (session-scoped AsyncEngine) + Phase 3 (function-scoped per-test session) + "Critical Implementation Details"
- **Detail**: The plan creates a **session-scoped** `AsyncEngine` (Phase 2) consumed by **function-scoped** async per-test
  session fixtures (Phase 3). The repo runs `asyncio_mode = "auto"` (pyproject.toml:45) with **no**
  `asyncio_default_fixture_loop_scope` and no engine pool override. Under pytest-asyncio ≥0.24 (pinned), each async test
  gets its own function-scoped event loop while the engine's default pool (`AsyncAdaptedQueuePool`) caches asyncpg
  connections. A connection opened in test A's loop and reused in test B's loop raises
  `RuntimeError: ... got Future attached to a different loop` / "Event loop is closed". This is the classic
  testcontainers + SQLAlchemy-async gotcha and lands exactly on Phase 3 (the brief's load-bearing unknown). The plan's
  "Critical Implementation Details" covers the SAVEPOINT recipe meticulously but is silent on loop scope.
- **Fix**: Add a "Critical Implementation Details" bullet (and a Phase 2 contract line) pinning the async lifecycle:
  create the session-scoped engine with `poolclass=NullPool` (no connection reuse across loops) **and/or** set
  `asyncio_default_fixture_loop_scope = "session"` + mark session-scoped async fixtures `loop_scope="session"`.
  NullPool is the lower-risk default for a disposable test container; per-test cost is negligible since isolation is
  the SAVEPOINT, not the connection.
  - Strength: Removes a whole class of intermittent loop-mismatch failures before they eat a session; grounded in the pinned ≥0.24 version and the existing `asyncio_mode="auto"` config.
  - Tradeoff: One config decision made explicit now rather than discovered mid-Phase-3.
  - Confidence: HIGH — function-loop vs session-engine mismatch is a documented, reproducible pytest-asyncio failure mode.
  - Blind spot: NullPool vs session-loop-scope choice depends on how the SAVEPOINT fixture holds its single connection — settle when writing Phase 3.
- **Decision**: PENDING

### F2 — Docker-from-agent is the load-bearing execution assumption, no fallback

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Phase 2, Contract bullet "runnable from the agent Bash tool"
- **Detail**: The plan asserts the container path "is runnable both by the agent and in CI" and "runnable from the agent
  Bash tool." That hinges on a Docker daemon being reachable from the agent's Windows Bash environment — research
  explicitly notes "no docker-compose/testcontainers setup exists today," and L-001 already forced all DB work onto
  user-run PowerShell. If the agent can't reach Docker, Phases 2–5 cannot self-verify and must hand commands to the user,
  but the plan has no such fallback, so an implementer hits this cold at Phase 2. (The SSL angle is *not* the risk:
  connector.py:21 and migrations/env.py:29 force no SSL context, so plain-TCP localhost sidesteps L-001's applink crash.)
- **Fix**: Add a Phase 2 pre-check + execution-fallback note: gate on `docker info` succeeding; if Docker isn't reachable
  from the agent, mirror L-001 and run the integration tier from native PowerShell / hand exact commands to the user.
  Make verifying "container provisions from the agent" the *first* Phase-2 step, before building fixtures on top of it.
  - Strength: Surfaces the one unknown that can block 4 of 5 phases on step one.
  - Tradeoff: Slightly more ceremony in Phase 2; none if Docker is present.
  - Confidence: HIGH — the dependency is real; only its availability is unknown.
  - Blind spot: Actual agent Docker availability is untested in this review.
- **Decision**: PENDING

### F3 — Phase 1 extends the exact file L-006 was raised on; no imports-at-top note

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Architectural Fitness
- **Location**: Phase 1 — "extend backend/tests/cabinet/test_service.py"
- **Detail**: L-006 was surfaced *in this very file* when a second import block was appended mid-file and silenced with
  `# noqa: E402`. Phase 1 extends the same file with new parametrized tests (likely new imports) but doesn't reference L-006.
- **Fix**: Add a one-line Phase 1 note: merge any new imports into the existing top-of-file import block (L-006) — no
  mid-file import block, no `# noqa: E402`.
- **Decision**: PENDING

### F4 — "integration" terminology collides with the existing cookbook definition

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 2 #4 (docs) vs test-plan.md §6.2
- **Detail**: test-plan §6.2 already calls the mocked-session HTTP tests "integration tests" and points them at
  `tests/<domain>/test_router.py`. The new real-DB tier reuses the same word for `tests/integration/`. Phase 2's doc
  update mentions the location convention but not the name clash — a future contributor could file a mocked test under
  `tests/integration/` or a real-DB test under `tests/<domain>/`.
- **Fix**: In the Phase 2 §6.2/§6.5 cookbook edit, disambiguate explicitly — e.g. "DB-backed integration
  (`tests/integration/`, real Postgres)" vs the existing hermetic HTTP-contract tests (`tests/<domain>/`, mocked session).
- **Decision**: PENDING

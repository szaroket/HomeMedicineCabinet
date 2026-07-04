<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Backend business-logic + CRUD safety net (test-plan Phase 1)

- **Plan**: context/changes/testing-backend-safety-net/plan.md
- **Scope**: Phase 2 of 5 (Test environment preparation)
- **Date**: 2026-06-30
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical · 2 warnings · 2 observations

## Re-verification (independent)

- Docker reachable: `docker info` → server 29.6.1.
- CI-path suite green and DB-free: `uv run pytest --ignore=tests/db --ignore=tests/integration` → 349 passed.
- Lint clean: `uv run ruff check tests/integration` → all checks passed.
- DB-dependent criteria (2.3 / 2.6 / 2.7 / 2.8) rest on the implementer's manual confirmation (no retained probe artifact, by design); Docker reachability is independently confirmed, so the approach is sound.

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | WARNING |

## Findings

### F1 — `__import__("os").environ` dodges the top-of-file import (L-006)

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency (lesson L-006)
- **Location**: backend/tests/integration/conftest.py:35
- **Detail**: The migration subprocess builds its env with `{**__import__("os").environ, "DATABASE_URL": pg_url}` instead of a top-level `import os` + `os.environ`. L-006 forbids function-body imports precisely because ruff E402 only catches module-level misplacement; `__import__("os")` is an obscure form of that dodge. Confirmed `ruff check tests/integration` passes, so it slipped silently — the exact failure mode L-006 names.
- **Fix**: Add `import os` to the top import block and use `os.environ`.
- **Decision**: FIXED

### F2 — uv.lock for testcontainers left uncommitted

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: backend/uv.lock (working tree, uncommitted)
- **Detail**: Commit c65ed10 added `testcontainers[postgres]>=4.9` to pyproject.toml but did not commit the resulting lockfile. The 173-line uv.lock delta (testcontainers 4.14.2, docker 7.1.0, wrapt, pywin32, …) is uncommitted in the working tree. Manifest and lock are out of sync in git history — a checkout of c65ed10 + frozen sync would get a stale lock. Criterion 2.2 (`uv sync --all-groups`) ran, but its artifact never landed in git.
- **Fix**: Stage and commit backend/uv.lock alongside the Phase 2 manifest change.
- **Decision**: FIXED

### F3 — Generator-fixture return annotations diverge from sibling convention

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/tests/integration/conftest.py:13, 45
- **Detail**: `db_engine` is an async-generator fixture (it `yield`s) annotated `-> AsyncEngine`, and `pg_container` has no return annotation. The sibling `tests/conftest.py` annotates async-generator fixtures as `AsyncIterator[...]` (lines 42, 63). `-> AsyncEngine` is also technically wrong for a yielding function. No gate catches it (`[tool.pyright] include = ["app"]` scopes type-checking to app/, so tests — including Phase 3's pyright gate — are never checked), but it breaks the established pattern.
- **Fix**: Annotate `db_engine` as `AsyncIterator[AsyncEngine]` and `pg_container` as `Iterator[PostgresContainer]` (import from collections.abc, matching tests/conftest.py).
- **Decision**: FIXED

### F4 — Migration subprocess swallows alembic output on failure

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality (reliability / observability)
- **Location**: backend/tests/integration/conftest.py:31-41
- **Detail**: `run_migrations` calls subprocess.run with `check=True, capture_output=True`. A failed `alembic upgrade head` raises CalledProcessError whose default message omits the captured stderr/stdout, so a migration failure during session setup surfaces as an opaque non-zero exit with no alembic traceback — the most likely Phase 3+ failure mode, made hard to debug.
- **Fix**: Catch CalledProcessError and re-raise / `pytest.fail` with `exc.stderr` + `exc.stdout`, or drop capture_output so output streams to the test log.
- **Decision**: FIXED

## Notes

- Clean matches: testcontainers dep, session-scoped container/migrated-schema fixture (NullPool, subprocess `alembic upgrade head`, asyncpg URL conversion), CI `--ignore=tests/integration`, README, and §6.2 name-clash disambiguation all match the plan's contract. §6.5 (facade cookbook) correctly needed no edit. No scope creep, no architecture violations.

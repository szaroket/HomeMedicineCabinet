# Integration Tests (DB-backed)

Tests in this directory run against a real Postgres database managed by
[testcontainers](https://testcontainers-python.readthedocs.io/). Each test
session starts a disposable container, migrates the full schema via
`alembic upgrade head`, and tears the container down when the session ends.
Per-test isolation is provided by transaction rollback (SAVEPOINT), not
re-migration.

## Two distinct test tiers

| Tier | Location | What it tests | DB needed |
|------|----------|---------------|-----------|
| Hermetic HTTP-contract tests | `tests/<domain>/test_router.py` | Endpoint shape + auth, mocked session | No |
| **DB-backed integration** (this folder) | `tests/integration/` | Real query path, filters, ownership, usage seam | Yes (Docker) |
| Low-level connector tests | `tests/db/` | DB connection, SELECT 1 | Yes (real Supabase/Docker) |

> "Integration test" in test-plan §6.2 refers to the hermetic HTTP-contract
> tier (`tests/<domain>/`). The DB-backed tier lives here.

## Prerequisites

- Docker daemon running (used by testcontainers to provision Postgres)
- `uv sync --all-groups` completed (installs `testcontainers[postgres]`)

## Running locally

```bash
cd backend

# DB-backed integration tier only
uv run pytest tests/integration

# Full suite including integration (Docker must be running)
uv run pytest

# CI path — DB-free, no Docker needed
uv run pytest --ignore=tests/db --ignore=tests/integration
```

## Isolation model

Each test runs inside a nested SAVEPOINT that is rolled back on teardown.
The outer transaction wraps the entire test; the app's `session.commit()`
(via `connector.persist()`) releases only the inner SAVEPOINT, not the outer
transaction, so all writes are invisible to other tests and vanish on teardown.

## CI status

Excluded from CI (`--ignore=tests/integration`) until test-plan Phase 4 wires
a Postgres service container into the GitHub Actions workflow.

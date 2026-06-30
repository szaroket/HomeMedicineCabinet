# Backend business-logic + CRUD safety net — Plan Brief

> Full plan: `context/changes/testing-backend-safety-net/plan.md`
> Research: `context/changes/testing-backend-safety-net/research.md`

## What & Why

Harden the hottest backend surface (the `cabinet` domain) so a code change can't
silently break the data path, corrupt tablet totals (FR-010), cross account
boundaries, or mis-resolve the dosage/usage path. The hermetic mocked-session suite
that exists today *cannot* catch these risks — a mock returns whatever you tell it —
so we add real-database integration coverage where only it gives signal. This is
test-plan **Phase 1**.

## Starting Point

A two-tier test base exists: hermetic `client`/`authed_client` over a mocked
`AsyncSession` (`tests/conftest.py`), and a thin real-DB tier under `tests/db/` that
only runs `SELECT 1` smoke + connector tests. CI runs `pytest --ignore=tests/db`
with placeholder DB creds. The cabinet query path is Postgres-only
(`to_tsquery('simple', …)`, generated `search_vector`, `_sufficiency_clauses` CAST
math), so SQLite can't stand in.

## Desired End State

`cd backend && uv run pytest` (with Docker running) runs the FR-010 unit tests plus a
new `tests/integration/` suite green against a disposable testcontainers Postgres;
the CI invocation `pytest --ignore=tests/db --ignore=tests/integration` stays green
and DB-free. A regression that empties the cabinet, returns the wrong filtered set,
leaks across accounts, or mis-resolves usage now fails a test.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Test DB target | Local **testcontainers** Postgres, plain TCP | Same engine as prod for FTS; disposable; sidesteps L-001 TLS abort | Research / Plan |
| Provisioning | testcontainers-python (auto lifecycle) | Zero manual steps; identical locally and (later) in CI | Plan |
| Schema bring-up | `alembic upgrade head` | `create_all` misses the FTS generated column + GIN index | Research / Plan |
| Isolation | Per-test transaction rollback (nested SAVEPOINT) | Fast, fully isolated; survives the service's `commit()` | Plan |
| Seeding | Shared factory fixtures, ORM (not XML import) | FK-ordered, reusable, deterministic PKs; reuse-fixtures convention | Research / Plan |
| Test location | Integration → `tests/integration/`; low-level → `tests/db/` | One canonical integration home, separate from connector tests | User |
| Surface breadth | Cabinet domain only (incl. usage path) | All Phase-1 risks live in the hottest dir | Plan |
| Risk #4 oracle | Exact id-set membership incl. filter intersection | Kills the "count only / single-filter" anti-patterns | Plan |
| Risk #6 residual | Included (usage path + SQL parity) | Closes the only untested #6 seam while fixtures are up | Plan |
| CI gating | Local-only now; CI wiring deferred to test-plan Phase 4 | Avoids pulling Phase-4 CI-service scope into this change | Plan |

## Scope

**In scope:** FR-010 merge-math unit tests (#3); DB-backed integration for cabinet
read/membership (#1, #4), cross-account ownership (#5), and the usage path + SQL
sufficiency-filter parity (#6 residual); the integration harness (container, schema,
isolation, seeding factories); CI `--ignore` update; docs.

**Out of scope:** wiring the DB tier into CI (test-plan Phase 4); medicines search
endpoint; real JWT/Supabase/framework internals; XML importer execution; SQLite;
re-testing the already-covered pure dosage formulas.

## Architecture / Approach

A session-scoped fixture starts a Postgres container and runs `alembic upgrade head`
once. Each test gets an `AsyncSession` joined to an outer transaction via a nested
SAVEPOINT (re-opened on `after_transaction_end`) and rolled back on teardown — so the
service's `commit()`/`persist()` still rolls back. The app's `get_session` override
yields that **same** session, so seeded rows and the HTTP request share one
transaction. An `act_as(user)` override switches identity for the two-user (#5) tests.
Factory fixtures seed in FK order: `users → user_preferences → medication_registry →
cabinet_entries`.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Merge-math unit (#3) | Pure FR-010 tests, no DB, CI-gated today | Oracle copied from impl instead of FR-010 |
| 2. Environment prep | testcontainers + `alembic` schema + CI `--ignore` + docs | Programmatic Alembic vs async `env.py`; Docker availability |
| 3. Harness fixtures | Isolation, `act_as`, seeding factories, smoke | SAVEPOINT recipe vs committing service |
| 4. #1 + #4 integration | Populated-cabinet shape + exact membership/intersection | Combinatorial seeding for filter sets |
| 5. #5 + #6 integration | Ownership reads/writes + usage path & SQL parity | Keeping SQL `_sufficiency_clauses` ↔ Python parity honest |

**Prerequisites:** Docker daemon available locally for Phases 2–5; Phase 1 needs
nothing. Phases 3–5 depend on Phase 2's container fixture.
**Estimated effort:** ~3–4 sessions across 5 phases (Phase 2's container/Alembic
wiring and Phase 3's SAVEPOINT isolation are the load-bearing unknowns).

## Open Risks & Assumptions

- Async `migrations/env.py` may complicate programmatic `alembic upgrade head`;
  fallback is a subprocess `alembic upgrade head` with `DATABASE_URL` pointed at the
  container.
- The SAVEPOINT-rollback recipe must correctly survive the service's `commit()`; if it
  leaks, switch the leaking tests to truncate-between-tests (the considered fallback).
- Assumes Docker is available wherever the suite runs; CI stays DB-free until Phase 4.

## Success Criteria (Summary)

- A silent-empty, wrong-filter-set, cross-account-leak, or usage-misresolve regression
  fails a test (verified by temporarily deleting a `WHERE` clause and watching it go
  red).
- Full suite green locally with Docker; CI path green and DB-free without Docker.
- Integration tests live under `tests/integration/`; low-level DB tests remain in
  `tests/db/`.

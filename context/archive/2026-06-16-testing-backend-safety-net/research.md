---
date: 2026-06-30T13:57:16+0200
researcher: szaroket
git_commit: cf4330416fb434b929e00f6f95f8ec133434b406
branch: develop
repository: szaroket/HomeMedicineCabinet
topic: "How to implement integration tests for the backend; do we need a real database?"
tags: [research, codebase, testing, integration, database, fastapi, pytest]
status: complete
last_updated: 2026-06-30
last_updated_by: szaroket
last_updated_note: "Added follow-up: registry seeding (ORM vs XML import), JWT/auth handling, and FK seeding order for DB-backed tests"
---

# Research: How to implement integration tests for the backend; do we need a real database?

**Date**: 2026-06-30T13:57:16+0200
**Researcher**: szaroket
**Git Commit**: cf4330416fb434b929e00f6f95f8ec133434b406
**Branch**: develop
**Repository**: szaroket/HomeMedicineCabinet

## Research Question

How can we implement integration tests for the backend? Do we need a real
database for it?

## Summary

**Short answer: it depends on which risk you are testing — and for this
change's hot risks (#1, #4, #5), yes, you need a real Postgres.**

The codebase already has a deliberate **two-tier** test architecture:

1. **Hermetic tests (no real DB)** — the dominant pattern. The `get_session`
   FastAPI dependency is overridden with an `AsyncMock(spec=AsyncSession)`, so
   HTTP and CRUD tests run with zero database. This is what `tests/conftest.py`
   wires up (`client`, `authed_client`) and what every current `test_router.py`
   / `test_crud.py` uses.
2. **DB-backed tests (real Postgres)** — a thin, already-scaffolded second tier
   under `backend/tests/db/`, using a real `async_session_factory` against the
   live database. Today it contains only smoke tests (`SELECT 1`). It is
   **excluded from CI** (`pytest --ignore=tests/db`) and from agent-run
   commands (the OpenSSL-applink crash, lesson L-001).

The key tension for **Phase 1 (this change)**: the hermetic pattern *cannot*
catch the very risks this phase exists to close. If you mock `session.execute`
to return a hand-built list, you are asserting on your own mock, not on the real
SQL filter, the real ownership scoping, or the real "did a code change silently
empty the result" behavior (Risk #1 anti-pattern, test-plan §2). Those need a
real query against a real database.

And it must be **real Postgres**, not SQLite: the query layer uses
Postgres-only full-text search (`search_vector @@ to_tsquery('simple', ...)`,
`DISTINCT ON`, generated `tsvector` columns). SQLite/aiosqlite would not
execute these statements at all, so the cheap in-memory substitute is off the
table for the search/filter risks.

## Detailed Findings

### The two-tier architecture is already designed, not hypothetical

`backend/tests/conftest.py:1-12` states the split explicitly in its module
docstring: hermetic clients here, "DB-backed integration tests use the
`db_session` fixture in `tests/db/conftest.py` instead."

- **Hermetic tier** — `backend/tests/conftest.py:29-80`:
  - `mock_session` = `AsyncMock(spec=AsyncSession)` (`:29-32`)
  - `client` overrides only `get_session` so the **real auth guard still runs**
    (good for 401 tests) (`:41-57`)
  - `authed_client` also overrides `get_current_user` to return `fake_user`
    (`:60-80`)
  - Both build an `httpx.AsyncClient` over `ASGITransport(app=app)` — in-process,
    no network, no DB.
- **DB-backed tier** — `backend/tests/db/conftest.py:1-9`:
  - `db_session` opens a real session from `async_session_factory` and rolls
    back on teardown (`:6-9`). This is the seam an integration test that needs a
    real DB would build on.
  - Current contents are smoke-only: `tests/db/test_connection.py:5-9`
    (`SELECT 1`) and `tests/db/test_connector.py` (which actually tests the
    `persist()` context manager with mocks, not a live DB).

### How current "integration" tests work — and their blind spot

The existing `test_router.py` files are HTTP-contract tests, **not** full-stack
integration. They mock the service/facade layer entirely:

- `backend/tests/cabinet/test_router.py:96-99` patches
  `cabinet_service.add_entry` with an `AsyncMock` returning a hand-built result.
  The test asserts status code + response shape mapping. The DB, CRUD, and
  service logic never run.
- `backend/tests/cabinet/test_crud.py:27-31, 34-40` builds a fake `Result`
  whose `scalar_one_or_none` returns whatever the test wants, then asserts the
  CRUD function returns it. This verifies error-wrapping and call wiring (good
  for Risk: DB-error→503 mapping) but **cannot** verify the SQL filters rows
  correctly.

The **blind spot**: a `_build_base_query` that silently drops a `WHERE user_id`
clause, or a filter that returns the wrong set, passes every hermetic test. The
suite already half-acknowledges this — `test_crud.py:155-252`
(`TestBuildBaseQueryBelowMinimum`, `TestBuildBaseQuerySufficiency`) stringifies
the SQL and asserts substrings are present (`"package_count <" in sql`,
`"nullif(" in sql`). That is a clever no-DB proxy, but it tests *that the SQL
text contains a clause*, not *that the clause selects the right rows*. For
membership correctness (Risk #4) and ownership enforcement (Risk #5), only
executing the query against seeded data proves it.

### Why a real database is required for Phase 1's risks (and SQLite won't do)

The query path is Postgres-specific:

- `backend/app/api/v1/cabinet/crud.py:312` —
  `medication_registry.search_vector @@ to_tsquery('simple', :tsquery)`
- `backend/app/api/v1/medicines/queries.py:13-20` — `SELECT DISTINCT ON (...)
  ... WHERE search_vector @@ to_tsquery('simple', :tsquery)`
- `backend/app/api/v1/cabinet/crud.py:216-238` — `cast(...)` arithmetic for the
  sufficiency/days-of-supply set filter (Postgres `CAST ... AS INTEGER/FLOAT`,
  `NULLIF`).

`to_tsquery`, `tsvector`/`search_vector`, and `DISTINCT ON` do not exist in
SQLite. An in-memory SQLite test DB (the usual "cheap real DB" trick) cannot
execute these statements, so for Risk #1 (data path) and Risk #4
(filter/search/status set) the database under test must be **Postgres**.

Mapping each Phase-1 risk to what it needs:

| Risk | Can hermetic mock prove it? | Needs real Postgres? |
|------|-----------------------------|----------------------|
| #1 silent data-path regression (non-empty cabinet still returns its rows) | No — a mock returns whatever you tell it | **Yes** — seed rows, hit endpoint, assert they come back |
| #3 dedup/merge math (FR-010) | **No DB needed** — the arithmetic is a pure function in `service.py`; unit-test it (test-plan §6.1, oracle from FR-010) | No |
| #4 filter/search/status returns exact set | No — substring-on-SQL is a proxy, not membership | **Yes** — Postgres FTS + filters against seeded data |
| #5 cross-account leak / wrong-owner write | No — happy-path mock never exercises the scoping | **Yes** — two real users (A, B); B must get empty/403 on A's rows |
| #6 usage-assignment integration path (residual) | Partly (calc is unit-tested) | **Yes for the persist→resolve seam** (test-plan §3 note) |

So Risk #3 is a pure-unit job (no DB); Risks #1, #4, #5, and the #6 residual
are genuine DB-backed integration and need real Postgres.

### Schema provisioning is already available (Alembic)

`backend/alembic.ini` + `backend/migrations/` (env.py, `versions/` with 3
revisions) exist. A test database can be brought to the correct schema —
including the `search_vector`/`tsvector` columns and indexes the FTS queries
depend on — by running migrations, rather than `SQLModel.metadata.create_all`
(which would miss the hand-written FTS DDL). This matters: the search risk can
only be tested if the test DB has the same generated columns as production.

### The hard constraint: TLS-DB work can't run from the agent / Git Bash

Lesson **L-001** (`context/foundation/lessons.md:134-171`): any TLS database
connection from the agent's Bash tool aborts with `OPENSSL_Uplink ... no
OPENSSL_Applink`. This hits Alembic, `connector.py`, and therefore any
DB-backed test that connects over TLS to Supabase. Consequences for design:

- DB-backed integration tests **must be run from native Windows PowerShell**
  (by the user, or with the agent handing over exact commands) — not from the
  agent Bash tool.
- This is environment-only; **do not** weaken SSL or add workaround contexts to
  "fix" it (L-001 is explicit).
- A **local/containerized Postgres reachable over plain TCP (non-TLS)** would
  sidestep the applink crash entirely and is the cleaner long-term option for a
  test DB — but no `docker-compose`/testcontainers setup exists today
  (confirmed: no such files in repo).

### CI today excludes DB tests — a decision to make for Phase 1

`.github/workflows/ci-cd.yml:91-97` runs
`uv run coverage run -m pytest --ignore=tests/db` with **placeholder** env vars
(`DATABASE_URL: postgresql+asyncpg://user:pass@localhost/testdb`, fake Supabase
values). So:

- CI never connects to a database; `tests/db/` is skipped on purpose.
- If Phase 1 adds DB-backed integration tests under `tests/db/`, they will
  **not** run in CI as wired today. To gate them you would need a CI Postgres
  service container (GitHub Actions `services: postgres:...`) + run migrations +
  drop the `--ignore=tests/db`. That is arguably Phase 4 ("Quality-gates
  wiring") territory, but Phase 1 should at least decide whether its new
  integration tests are CI-gated or run-locally-only for now.

## Code References

- `backend/tests/conftest.py:29-80` — hermetic fixtures (`mock_session`,
  `client`, `authed_client`); ASGITransport in-process client, no DB
- `backend/tests/db/conftest.py:6-9` — `db_session` real-DB fixture (rollback
  on teardown) — the seam for DB-backed integration
- `backend/tests/db/test_connection.py:5-9` — only existing live-DB test
  (`SELECT 1`)
- `backend/tests/cabinet/test_router.py:96-108` — pattern: mock service, assert
  HTTP contract (no DB)
- `backend/tests/cabinet/test_crud.py:27-64` — pattern: fake `Result`, assert
  CRUD wiring/error-wrapping (no DB)
- `backend/tests/cabinet/test_crud.py:155-252` — SQL-substring proxy tests
  (no-DB approximation of filter behavior)
- `backend/app/db/connector.py:21-36` — `engine`, `async_session_factory`,
  `get_session` (the override target)
- `backend/app/api/v1/cabinet/crud.py:312` — Postgres FTS
  (`to_tsquery('simple', ...)`)
- `backend/app/api/v1/medicines/queries.py:13-20` — `DISTINCT ON` + FTS
- `backend/alembic.ini`, `backend/migrations/versions/` (3 revisions) — schema
  provisioning for a test DB
- `.github/workflows/ci-cd.yml:91-97` — `pytest --ignore=tests/db` with
  placeholder DB env
- `context/foundation/lessons.md:134-171` — L-001 (TLS DB work → PowerShell, not
  Bash tool)

## Architecture Insights

- **Two-tier-by-design.** The project's testing convention is hermetic by
  default (cheap, CI-safe, fast) with a separate, opt-in DB tier
  (`tests/db/`). Integration tests that need a DB belong in `tests/db/` (or a
  parallel structure), not mixed into the mocked-session suites — that's what
  the `--ignore=tests/db` boundary and the two conftests encode.
- **Cost × signal (test-plan §1).** Push everything you can to the cheapest
  layer: Risk #3 (FR-010 merge math) is pure → unit test, no DB. Reserve the
  expensive real-DB layer for what only it can prove: result-set membership
  (#4), ownership scoping (#5), and the "still returns rows" data path (#1).
- **The mock-the-DB anti-pattern is called out explicitly** in test-plan §2
  Risk #1: "over-mocking the DB so the empty-result bug cannot surface." Phase 1
  is precisely the change that should *not* over-mock.
- **Real-DB tier must be Postgres + migrated schema**, because correctness here
  depends on FTS columns and Postgres-only operators. SQLite is not a valid
  stand-in for the search/filter risks.
- **L-001 + non-TLS local Postgres** is the likely path to make DB-backed tests
  runnable by the agent and in CI without the applink crash and without TLS to
  Supabase.

## Decisions

- **Test database target (DECIDED 2026-06-30): local/containerized Docker
  Postgres over plain TCP.** Not PROD (writes are destructive by design — Risk
  #3 mutates totals, Risk #5 creates users), and not SQLite (FTS/`to_tsquery`/
  `DISTINCT ON` are Postgres-only). A disposable Docker Postgres:
  - sidesteps L-001 (plain TCP, no TLS → runnable from the agent Bash tool *and*
    CI), is free, and is safe to truncate/recreate between runs;
  - is the same engine as PROD, so search/filter (#4) tests faithfully;
  - the same image later becomes a GitHub Actions `services: postgres` container
    for CI gating (see Open Question on CI timing).
  - **Setup shape**: `docker run` Postgres → point a test `DATABASE_URL` at it →
    `alembic upgrade head` (NOT `create_all`, so the `search_vector` FTS columns/
    indexes exist) → run `tests/db/`.

## Open Questions

1. **CI gating now or later**: do Phase 1's DB-backed tests get a Postgres
   service container in `ci-cd.yml` now, or stay local-only (keeping
   `--ignore=tests/db`) and defer CI wiring to Phase 4?
3. **Seeding/isolation strategy**: per-test transaction-rollback (as
   `db_session` already hints) vs. truncate-between-tests; and unique
   per-test user ids (timestamp suffix) to keep Risk #5's two-user tests from
   colliding on re-runs.
4. **Schema setup in tests**: run Alembic migrations against the test DB (gets
   FTS columns/indexes) vs. `create_all` (misses hand-written FTS DDL) —
   migrations look required given the `search_vector` dependency.
5. **Risk #6 residual** (`PATCH /entries/{id}/usage` → persist → resolve): the
   test-plan asks Phase 1 to absorb it; confirm it's in this change's scope.

## Follow-up Research 2026-06-30

### Do we need the registry import script to seed the test DB? No.

`search_vector` is a **Postgres generated column** —
`GENERATED ALWAYS AS (to_tsvector('simple', coalesce(name,'') || ' ' ||
coalesce(active_ingredient,''))) STORED`
(`backend/migrations/versions/2c7067ce3f56_varchar_to_text.py:30-37`, and the
initial schema `0e56afa1e4b6:52-62`, GIN-indexed). Postgres recomputes it on
every insert, so a plain ORM insert of a `MedicationRegistry` row makes FTS
(`to_tsquery`) work with no import step.

**Decision: seed registry rows directly via the ORM in a fixture; do NOT run
the import to seed.** Once `alembic upgrade head` has built the table + generated
column + GIN index, insert a handful of `MedicationRegistry` rows by hand. The
only constraint: set `name` and `active_ingredient` to the terms the search
tests query (those two columns feed `search_vector`), and set `capacity` /
`is_tablet_based` for the merge-math (#3) and sufficiency (#6) paths.

### Can we use the sample XML files for integration tests?

Two files exist:
- `docs/reference/rejestr_lekow_sample_20260603.xml` — 5 real products
  (Apap/Paracetamolum tablet; Acodin Duo syrup; Gensulin R injection; Edelan
  cream; FANHDI powder).
- `backend/tests/registry/fixtures/registry_sample.xml` — the **parser-test**
  fixture (consumed by `tests/registry/test_parser.py`): deliberately crafted
  with a duplicate Apap (IR + NAR variants → dedup case) and a `Vetmedin`
  veterinary product (`rodzajPreparatu="weterynaryjny"` → must be filtered out).

**Decision: use the XML as a *data reference*, not as the seeding mechanism.**
Pull realistic values from it (names, `nazwaPowszechnieStosowana` →
`active_ingredient`, tablet vs syrup/cream/injection → `is_tablet_based`,
`pojemnosc` → `capacity`) into hand-built ORM fixture rows. Do **not** feed the
XML through `scripts/registry_import` to populate the test DB, because:

1. **Couples cabinet/medicines tests to the import pipeline** — a parser/loader
   change would break unrelated integration tests.
2. **Non-deterministic PKs** — the loader assigns the registry `id` from the
   model's `uuid4` default (`loader.py:52`), *not* the XML `id` (which maps to
   `source_product_id`). So a cabinet-entry fixture can't reference a known
   `medication_registry_id`; you'd have to query-by-name first. Direct ORM
   seeding lets you pin the UUID and reference it straight away.
3. **Post-import contents depend on import logic** — Vetmedin is dropped, the two
   Apaps are deduped — a moving oracle for membership tests (Risk #4).
4. **The loader does a destructive full replace** — `sa.delete(MedicationRegistry)`
   first (`loader.py:49`), awkward for per-test isolation.

Running XML→loader→DB is only the right shape for the *importer's own*
integration test — which is explicitly out of scope (test-plan §7: import
*execution* not tested; the parser is already unit-tested in
`tests/registry/test_parser.py`). The curated `tests/.../registry_sample.xml` is
still the better *reference* of the two (it already encodes the dedup and
veterinary-filter edges).

### Do we need to worry about JWT / auth? Not the crypto — but yes, identity + FK.

**Don't verify real JWTs in these tests.** The hermetic `authed_client` already
overrides the `get_current_user` dependency (`tests/conftest.py:73-74`); keep
doing that. Real JWT verification (`app/core/jwt_security.py`) fetches Supabase
JWKS over the network — framework behavior, out of scope (test-plan §7). The
missing-token / 401 guard path is already covered by the `client` fixture
(`tests/cabinet/test_router.py:86-88`).

**But two real auth concerns for the DB-backed tier:**

1. **FK: `cabinet_entries.user_id` → `users.id`** (model `cabinet/models.py:20`;
   migration `0e56afa1e4b6:98`). The current `fake_user` is a random UUID with
   **no** `users` row — fine for mocked-session tests, but a real insert will
   fail the FK. The DB fixture must seed an actual `User` row (and a
   `UserPreferences` row — `users/models.py:25-34` — when exercising
   `min_package_count` / `below_minimum`) and inject *that same id* through the
   `get_current_user` override.
2. **Risk #5 needs two identities.** The override must be parametrizable so a
   test can "log in as" user A or user B. Seed cabinet rows owned by A, override
   the guard to B, and assert B gets empty/404 (read) or is rejected (write).
   The single-`fake_user` fixture is insufficient; the plan needs a
   `seed_user(...)` + "act as user X" helper.

**FK seeding order for any DB-backed cabinet test:** `users`
(→ optional `user_preferences`) → `medication_registry` → `cabinet_entries`.
Note the `cabinet_entries` unique constraint
`uq_cabinet_entries_user_med_expiry` (`user_id, medication_registry_id,
expiry_date`, `cabinet/models.py:10-17`) — the dedup/merge (FR-010, Risk #3) and
the concurrent-add `IntegrityError` race guard both hinge on it, so seed
fixtures must vary one of those three keys to create distinct rows.

## Related Research

- `context/foundation/test-plan.md` — §2 risk map & response guidance, §3
  Phase 1 scope, §4 stack, §6.1/§6.2 cookbook (the authoritative spec this
  research grounds)
- `context/changes/testing-backend-safety-net/change.md` — this change's intent
  and per-risk proof statements
</content>
</invoke>

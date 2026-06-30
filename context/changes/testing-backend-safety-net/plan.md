# Backend business-logic + CRUD safety net (test-plan Phase 1) — Implementation Plan

## Overview

Harden the hottest backend surface (the `cabinet` domain) so a code change
cannot silently break the data path, corrupt tablet totals, cross account
boundaries, or mis-resolve the dosage/usage path. We add two test tiers:

1. **Pure unit tests** for the FR-010 merge math (Risk #3) — no database.
2. A new **DB-backed integration tier** under `backend/tests/integration/`,
   bootstrapped on a disposable **testcontainers Postgres** (plain TCP, schema via
   `alembic upgrade head`), with **transaction-rollback isolation** and shared
   **seeding factories**, proving Risks #1, #4, #5 and the #6 usage-path residual
   against a real database.

The hermetic mocked-session suite that exists today cannot catch these risks: a
mock returns whatever you tell it, so a dropped `WHERE user_id` clause, a silent
empty result, or a wrong filter set passes every current test. Only executing the
real Postgres-only query path (`to_tsquery('simple', …)`, generated
`search_vector`, the `_sufficiency_clauses` CAST arithmetic) against seeded data
proves them.

## Current State Analysis

- **Two-tier test architecture already exists.** `backend/tests/conftest.py`
  provides hermetic `client` / `authed_client` over an `AsyncMock(spec=AsyncSession)`;
  `backend/tests/db/conftest.py` provides a real-DB `db_session` fixture used only
  by `SELECT 1` smoke + connector tests. CI runs `pytest --ignore=tests/db`
  (`.github/workflows/ci-cd.yml:97`) with placeholder DB creds.
- **The query path is Postgres-only.** `cabinet/crud.py:312` uses
  `to_tsquery('simple', :tsquery)` against a generated `search_vector` column;
  `_sufficiency_clauses` (`crud.py:184-260`) does `cast(... AS Integer/Float)`,
  `func.nullif`, and date arithmetic. SQLite cannot execute these — the test DB
  must be real Postgres with the migrated FTS schema.
- **The FR-010 merge math is pure** and lives in `cabinet/service.py`
  (`total_tablets:62`, `normalize_tablet_pool:82`, `merge_tablet_entry:100`,
  `merge_non_tablet_entry:128`) — directly unit-testable, oracle from FR-010.
- **FK chain for seeding:** `users` → (`user_preferences`) →
  `medication_registry` → `cabinet_entries`. `CabinetEntry.user_id` is a FK to
  `users.id` (`cabinet/models.py:20`); the current `fake_user` is a random UUID
  with **no** `users` row, so a real insert would fail the FK. The unique
  constraint `uq_cabinet_entries_user_med_expiry` (`cabinet/models.py:10-17`) is
  the dedup key — seed fixtures must vary `user_id`, `medication_registry_id`, or
  `expiry_date` to create distinct rows.
- **`search_vector` is a Postgres generated column** (GENERATED ALWAYS AS … STORED,
  GIN-indexed) created by the migrations — a plain ORM insert of a
  `MedicationRegistry` row makes `to_tsquery` work with no import step.
- **Environment constraint L-001:** TLS DB connections abort from the agent Bash
  tool (`OPENSSL_Uplink … no OPENSSL_Applink`). A **local testcontainer over plain
  TCP** sidesteps this entirely (no TLS) and is runnable both by the agent and in
  CI later. Do **not** weaken SSL to "fix" it.
- **The service commits.** `crud` write paths use `connector.persist()` which calls
  `session.commit()`. Transaction-rollback isolation therefore requires the
  join-an-external-transaction recipe (nested SAVEPOINT + restart listener), not a
  naive single `session.rollback()`.

## Desired End State

After this plan:

- `cd backend && uv run pytest` (with Docker running) executes the pure unit tests
  **and** the new `tests/integration/` suite green, against a fresh disposable
  Postgres that testcontainers starts and tears down automatically.
- `cd backend && uv run pytest --ignore=tests/db --ignore=tests/integration`
  (the CI invocation) stays green with **no** Docker/DB requirement — the unit
  additions run here, the DB tier is excluded exactly as today.
- A regression that empties the cabinet (#1), returns the wrong filtered set (#4),
  leaks across accounts (#5), or mis-resolves the usage path (#6) **fails** a test.

### Key Discoveries:

- DB-backed integration belongs in `backend/tests/integration/` (new); low-level
  connector/connection tests stay in `backend/tests/db/` (project convention).
- Schema must come from `alembic upgrade head`, not `create_all` — `create_all`
  misses the hand-written FTS generated column + GIN index the search risk depends
  on (`migrations/versions/2c7067ce3f56_varchar_to_text.py`).
- Seed `MedicationRegistry` rows directly via the ORM; do **not** run the XML
  importer (it does a destructive full-replace, assigns non-deterministic PKs, and
  couples cabinet tests to the import pipeline). Use the sample XML only as a
  *data reference* (`backend/tests/registry/fixtures/registry_sample.xml`).
- Keep overriding `get_current_user` (no real JWT verification — that hits Supabase
  JWKS over the network, out of scope per test-plan §7), but back it with a **real
  seeded `User` row** and make it parametrizable to "act as" user A or B.

## What We're NOT Doing

- **Not** wiring the DB tier into CI now — CI keeps `--ignore`; a Postgres service
  container + migration step is test-plan **Phase 4** (Quality-gates wiring).
- **Not** testing the medicines search endpoint this phase — cabinet-only (every
  Phase-1 risk lives there); medicines FTS is a possible follow-up.
- **Not** verifying real JWTs, Supabase Auth, TanStack, or FastAPI/SQLModel
  internals (test-plan §7 — trust the framework).
- **Not** running the XML registry importer to seed; **not** testing the importer's
  execution (test-plan §7).
- **Not** using SQLite as a cheap stand-in — it cannot run the FTS/`DISTINCT ON`
  path.
- **Not** weakening SSL or adding workaround SSL contexts (L-001 is environment-only).
- **Not** re-testing the already-covered pure dosage formulas (`daily_consumption_rate`,
  `days_of_supply_from_rate` — covered in `tests/cabinet/test_service.py`); #6 work is
  the *integration/usage seam* only.

## Implementation Approach

Five phases, ordered cheapest-signal-first and infra-before-consumers:

1. Pure unit tests (Risk #3) — independent, runs in CI today, zero infra.
2. Test environment preparation — stand up the testcontainer + migrated schema and
   move the CI exclusion; standalone, verifiable on its own (container up, FTS schema
   present), no app/seeding logic yet.
3. Integration harness fixtures — isolation, auth override, seeding factories, and a
   round-trip smoke proving the harness before any risk tests are written.
4. Risk #1 + #4 integration (read / membership).
5. Risk #5 + #6 residual integration (ownership / usage).

Phases 3–5 depend on Phase 2's container fixture. Phase 1 is independent.

## Critical Implementation Details

- **Docker reachability is the load-bearing Phase-2 unknown — pre-check it first.**
  The whole DB tier hinges on a Docker daemon being reachable from the execution
  environment, and no testcontainers/compose setup exists today. Before building any
  fixtures, the **first** Phase-2 action is to confirm `docker info` succeeds from the
  agent Bash tool. If it does, Phases 2–5 self-verify normally. If Docker is **not**
  reachable from the agent, mirror L-001's execution model: run the integration tier
  from native PowerShell or hand the exact commands to the user to run, and treat their
  output as the verification signal. (This is purely an *execution-environment*
  fallback — not an SSL issue: `connector.py:21` / `migrations/env.py:29` force no SSL
  context, so plain-TCP localhost already sidesteps L-001's applink crash.)
- **Transaction-rollback with a committing service (Phase 3).** The service calls
  `session.commit()` via `connector.persist()`. To keep each test isolated, use the
  SQLAlchemy "join an external transaction" recipe: open a connection, begin an outer
  (non-ORM) transaction, bind the async session to that connection with a nested
  SAVEPOINT, and re-open the SAVEPOINT on each `after_transaction_end` so the
  service's inner `commit()` doesn't end the outer transaction; roll the outer
  transaction back on teardown. The same session object must be what the app's
  `get_session` override yields, so HTTP requests and the seeding code share one
  transaction and see each other's rows.
- **Same-session seam.** Seed rows through the test session, then issue the HTTP
  request through an `authed_db_client` whose `get_session` override yields that
  **same** session — otherwise the request runs in a different transaction and won't
  see the (uncommitted, rolled-back-on-teardown) seed data.
- **`pytest-randomly` is enabled** (random test order) — tests must not depend on
  ordering; the per-test transaction rollback guarantees this as long as no fixture
  leaks committed state outside the SAVEPOINT.
- **Schema bring-up is per-session, once.** Run `alembic upgrade head` against the
  container URL a single time in a session-scoped fixture (it is plain TCP → L-001
  does not apply). Per-test isolation is the SAVEPOINT rollback, not re-migration.
- **Async event-loop lifecycle (Phase 2 ↔ Phase 3 seam).** The session-scoped
  `AsyncEngine` is consumed by function-scoped per-test sessions, but the repo runs
  `asyncio_mode = "auto"` (pyproject.toml:45) with no loop-scope override. Under
  pytest-asyncio ≥0.24 each async test gets its own event loop; the default
  `AsyncAdaptedQueuePool` would cache an asyncpg connection opened in one loop and
  reuse it in the next, raising `RuntimeError: ... Future attached to a different loop`
  / "Event loop is closed". Pin the lifecycle explicitly: create the session-scoped
  engine with `poolclass=NullPool` (no cross-loop connection reuse) — the lower-risk
  default for a disposable container, since isolation is the SAVEPOINT, not the
  connection, so per-test connect cost is negligible. Alternatively (or additionally)
  set `asyncio_default_fixture_loop_scope = "session"` and mark the session-scoped
  async fixtures `loop_scope="session"`. Settle NullPool vs session-loop-scope when
  writing the Phase 3 SAVEPOINT fixture (it depends on how that fixture holds its
  single connection).

## Phase 1: FR-010 merge-math unit tests (Risk #3)

### Overview

Pure-function unit coverage for the dedup/merge arithmetic, with the oracle taken
from FR-010 (not from reading the implementation). No database.

> **Provenance note (impl-review-phase-1, 2026-06-30)**: The four merge-math test
> classes (`TestTotalTablets`, `TestNormalizeTabletPool`, `TestMergeTabletEntry`,
> `TestMergeNonTabletEntry`) were not authored by this phase — they were introduced
> earlier in commit `fe03838` (add-medication-from-registry, 2026-06-09), three weeks
> before this plan. Phase 1's work was an **audit**: confirming the pre-existing
> coverage satisfies the FR-010 contract below and that its oracle is independent of
> the implementation (Manual 1.5). The Phase 1 commit `fa65324` is docs-only; it adds
> no test code. Treat the "Changes Required" below as the contract the audit verified,
> not as net-new work this phase produced.

### Changes Required:

#### 1. Merge-math unit tests

**File**: `backend/tests/cabinet/test_service.py` (extend)

**Intent**: Prove known inputs → known merged totals / normalization per FR-010
across full-package and partial-package cases, for both tablet and non-tablet
variants. Catch a regression that mis-sums or mis-normalizes the tablet pool.

**Contract**: Parametrized tests over the pure functions in `cabinet/service.py`:
- `total_tablets(package_count, partial_tablet_count, tablets_per_package)` — full
  (`partial=None`) and partial cases.
- `normalize_tablet_pool(total, tablets_per_package)` — even-divide → `partial=None`;
  remainder → `(total//tpp + 1, total%tpp)`.
- `merge_tablet_entry(...)` — existing+new across full+full, full+partial,
  partial+partial; assert the normalized `TabletPool`.
- `merge_non_tablet_entry(existing, new)` — sum of package counts.
- Oracle values are computed by hand from FR-010 worked examples, never copied from
  the functions under test (Risk #3 anti-pattern). Use `pytest.mark.parametrize`;
  named args for 3+-argument calls (test-style convention).
- **L-006**: this is the file L-006 was raised on — merge any new imports into the
  existing top-of-file import block; do **not** append a mid-file import block or
  silence it with `# noqa: E402`.

### Success Criteria:

#### Automated Verification:

- Unit tests pass: `cd backend && uv run pytest tests/cabinet/test_service.py`
- Full default suite still green (no Docker needed):
  `cd backend && uv run pytest --ignore=tests/db --ignore=tests/integration`
- Linting passes: `cd backend && uv run ruff check tests/cabinet/test_service.py`
- Type checking passes: `cd backend && uv run pyright`

#### Manual Verification:

- Spot-check 2–3 parametrized expected values by hand against FR-010 to confirm the
  oracle is independent of the implementation.

**Implementation Note**: After automated verification passes, pause for manual
confirmation before Phase 2.

---

## Phase 2: Test environment preparation

### Overview

Stand up the disposable Postgres test environment and bring it to the production
schema, as a self-contained, independently verifiable step — no app wiring or
seeding logic yet. Move the CI exclusion so the (still-empty) integration tier is
excluded from the CI run.

### Changes Required:

#### 1. testcontainers dev dependency

**File**: `backend/pyproject.toml`

**Intent**: Add the testcontainers Postgres helper to the dev/test dependency group
so the container lifecycle is managed automatically by the suite.

**Contract**: Add `testcontainers[postgres]` to the dev dependency group (alongside
`pytest`, `pytest-asyncio`); run `uv sync --all-groups`. No production dependency
change.

#### 2. Session-scoped container + migrated schema fixture

**File**: `backend/tests/integration/conftest.py` (new) + `backend/tests/integration/__init__.py` (new)

**Intent**: Provide a session-scoped fixture that starts a Postgres container (plain
TCP), exposes its async connection URL, runs `alembic upgrade head` against it once,
and yields an async engine bound to it; the container is torn down at session end.

**Contract**:
- Session-scoped fixture starts `PostgresContainer`, derives a
  `postgresql+asyncpg://…@localhost:<mapped-port>/…` URL.
- Runs the existing Alembic config against that URL (env override) to build the full
  schema **including** the `search_vector` generated column + GIN index. If the async
  `migrations/env.py` complicates programmatic invocation, run `alembic upgrade head`
  as a subprocess with `DATABASE_URL` pointed at the container.
- Yields a session-scoped `AsyncEngine` (created with `create_async_engine` against
  the container URL, **`poolclass=NullPool`** to avoid cross-loop connection reuse —
  see "Async event-loop lifecycle" above) for the per-test session fixture (Phase 3)
  to consume.
- Plain TCP → L-001 does not apply; this fixture is runnable from the agent Bash tool
  and (later) CI.

#### 3. CI excludes the integration tier

**File**: `.github/workflows/ci-cd.yml`

**Intent**: Keep CI database-free; the new tier is local-only until test-plan Phase 4.

**Contract**: Change the backend-tests run to
`uv run coverage run -m pytest --ignore=tests/db --ignore=tests/integration`.

#### 4. Docs: how to run the integration tier

**File**: `backend/tests/integration/README.md` (new) and `context/foundation/test-plan.md` (§6.2 / §6.5 cookbook note)

**Intent**: Document that the integration tier needs a running Docker daemon, how to
run it locally, and that it is excluded from CI for now.

**Contract**: A short README in `tests/integration/` (Docker prerequisite, run
command, isolation model); a 1–2 line pointer added to the test-plan cookbook so the
location convention (`tests/integration/` for integration, `tests/db/` for low-level)
is discoverable. **Disambiguate the "integration" name clash** in the §6.2/§6.5 edit:
test-plan §6.2 already labels the mocked-session HTTP tests "integration tests" at
`tests/<domain>/test_router.py`. Spell out the two distinct tiers — "DB-backed
integration (`tests/integration/`, real Postgres)" vs the existing hermetic
HTTP-contract tests (`tests/<domain>/`, mocked session) — so a future contributor
files each kind in the right place.

### Success Criteria:

#### Automated Verification:

- **Docker reachable first**: `docker info` succeeds from the agent Bash tool. If it
  fails, switch to the L-001 execution fallback (run from native PowerShell / hand
  commands to the user) before proceeding — do not build fixtures on an unverified daemon.
- Deps resolve: `cd backend && uv sync --all-groups`
- Container starts and schema is present (temporary probe test or a one-off check):
  a session against the container can `SELECT` and the
  `medication_registry.search_vector` column + its GIN index exist.
- CI invocation stays green and DB-free:
  `cd backend && uv run pytest --ignore=tests/db --ignore=tests/integration`
- Linting passes: `cd backend && uv run ruff check tests/integration`

#### Manual Verification:

- With Docker running, the container provisions and is torn down cleanly (no leftover
  containers after the run).
- Confirm `alembic upgrade head` (not `create_all`) built the schema — the generated
  `search_vector` column and GIN index are present.
- Confirm L-001 does not trigger: the container path runs from the agent Bash tool
  without the OpenSSL applink abort (plain TCP).

**Implementation Note**: After automated verification passes, pause for manual
confirmation before Phase 3.

---

## Phase 3: Integration harness fixtures

### Overview

Build the per-test harness on top of Phase 2's container: transaction-rollback
isolation, a real-user auth override (`act_as`), and shared seeding factories — then
prove it with one seeded round-trip smoke test.

### Changes Required:

#### 1. Per-test joined-transaction session

**File**: `backend/tests/integration/conftest.py` (extend)

**Intent**: Give each test an isolated `AsyncSession` whose writes (including the
service's `commit()` via `persist()`) are rolled back on teardown.

**Contract**: Function-scoped fixture that opens a connection from the session-scoped
engine, begins an outer transaction, binds an `AsyncSession` to that connection with
a nested SAVEPOINT, re-opens the SAVEPOINT on `after_transaction_end`, and rolls the
outer transaction back on teardown. This is the SQLAlchemy "join an external
transaction (for test suites)" recipe — required because the service commits
mid-test.

#### 2. `authed_db_client` + `act_as` override

**File**: `backend/tests/integration/conftest.py` (extend)

**Intent**: An HTTPX client over the real app whose `get_session` yields the **same**
per-test session, and whose `get_current_user` returns a chosen seeded user — so the
two-identity (Risk #5) tests can switch between user A and user B.

**Contract**:
- `authed_db_client` builds an `httpx.AsyncClient` over `ASGITransport(app=app)` with
  `app.dependency_overrides[get_session]` yielding the per-test joined session and
  `app.dependency_overrides[get_current_user]` returning the active `CurrentUser`;
  overrides are cleaned up on teardown.
- An `act_as(user)` helper sets which seeded user the override returns (defaults to a
  primary seeded user); supports switching identity within a test.
- Reuse `CurrentUser`, `get_current_user`, `get_session`, `app` imports as in
  `tests/conftest.py` — do not duplicate the hermetic fixtures.

#### 3. Seeding factory fixtures

**File**: `backend/tests/integration/conftest.py` (extend)

**Intent**: Centralize FK-ordered seeding so tests stay readable and the two-user /
dedup-key logic lives in one place (reuse-fixtures convention).

**Contract**: Factory fixtures returning helpers with sensible defaults and
overridable kwargs, honoring FK order `users → user_preferences → medication_registry
→ cabinet_entries`:
- `seed_user(...)` → inserts a `User`, returns it (and a matching `CurrentUser`).
- `seed_user_preferences(user, ...)` → inserts `UserPreferences` (for
  `min_package_count` / `below_minimum` paths).
- `seed_registry(...)` → inserts a `MedicationRegistry`; caller pins `name` /
  `active_ingredient` (feed `search_vector`) and `capacity` / `is_tablet_based`
  (tablet math). Pin the UUID so cabinet fixtures can reference it directly.
- `seed_entry(user, registry, ...)` → inserts a `CabinetEntry`; varies one of
  (`user_id`, `medication_registry_id`, `expiry_date`) to respect the unique
  constraint. Use realistic values pulled from `registry_sample.xml`.
- Always pass `spec=`/`autospec=` where any mock is used (mock-spec convention) —
  though this tier is largely mock-free.

#### 4. Harness smoke test

**File**: `backend/tests/integration/test_harness_smoke.py` (new)

**Intent**: Prove the harness end-to-end before risk tests: seed a user + registry +
entry, hit `GET /cabinet` via `authed_db_client`, and assert the seeded entry comes
back — and that a second test does not see the first test's rows (isolation).

**Contract**: One test seeds and asserts the round-trip returns the seeded entry id;
a second test asserts an empty/independent starting state, proving rollback isolation
under `pytest-randomly`.

### Success Criteria:

#### Automated Verification:

- Harness smoke passes (Docker running):
  `cd backend && uv run pytest tests/integration/test_harness_smoke.py`
- Isolation holds under random order across repeated runs:
  `cd backend && uv run pytest tests/integration -p randomly` (re-run a few times)
- CI invocation still green and DB-free:
  `cd backend && uv run pytest --ignore=tests/db --ignore=tests/integration`
- Linting passes: `cd backend && uv run ruff check tests/integration`
- Type checking passes: `cd backend && uv run pyright`

#### Manual Verification:

- Confirm the seeded rows are visible to the HTTP request (same-session seam works)
  and gone after teardown (no rows persist between tests).
- Confirm `act_as` switches identity within a single test.

**Implementation Note**: After automated verification passes, pause for manual
confirmation before Phase 4.

---

## Phase 4: Risk #1 + #4 integration (read / membership)

### Overview

DB-backed tests proving a populated cabinet returns its rows with the correct
response shape (#1) and that filters return exactly the right entry set, including
filter intersection (#4).

### Changes Required:

#### 1. Risk #1 — populated cabinet returns its rows (correct shape, not silent-empty)

**File**: `backend/tests/integration/cabinet/test_list_entries.py` (new) + `backend/tests/integration/cabinet/__init__.py` (new)

**Intent**: Seed a non-empty cabinet, hit `GET /cabinet`, and assert the rows come
back with the correct response shape — not an empty list, and not just a 200.

**Contract**: Seed N entries for a user; assert the response contains exactly those
entry ids and that representative fields (`name`, `package_count`, `expiry_date`,
`status`, `total_tablets`, `is_tablet_based`) are populated/correct. Explicitly
assert non-empty membership so a silent-empty regression fails (Risk #1 anti-pattern:
"200 OK ⇒ correct data").

#### 2. Risk #4 — exact membership across filters incl. intersection

**File**: `backend/tests/integration/cabinet/test_filters.py` (new)

**Intent**: Prove status classification, search, and category filters return exactly
the expected entry set — by id, not by count — and that combined filters intersect
correctly.

**Contract**: Seed a known mix spanning valid / expiring / expired (relative to a
fixed `today` and `expiry_threshold_days`), important vs not, below-minimum vs not,
and distinct `name` / `active_ingredient` for search. For each input assert the
returned id set equals the expected set:
- `status` ∈ {valid, expiring, expired}
- `search` (drives `to_tsquery` against the real `search_vector`)
- `category` ∈ {important, used}
- `below_minimum` (requires seeded `UserPreferences.min_package_count`)
- `sufficiency` ∈ {sufficient, insufficient}
- **at least one intersection case** (e.g. `status=expiring & category=important` or
  `search & status`) asserting AND semantics (FR-004), not single-filter happy-path.
Assert exact id-set membership, never count-only (Risk #4 anti-patterns).

### Success Criteria:

#### Automated Verification:

- Read/membership tests pass (Docker running):
  `cd backend && uv run pytest tests/integration/cabinet/test_list_entries.py tests/integration/cabinet/test_filters.py`
- Full integration tier green and order-independent:
  `cd backend && uv run pytest tests/integration`
- CI invocation still green and DB-free:
  `cd backend && uv run pytest --ignore=tests/db --ignore=tests/integration`
- Linting passes: `cd backend && uv run ruff check tests/integration`
- Type checking passes: `cd backend && uv run pyright`

#### Manual Verification:

- Temporarily delete a `WHERE` clause (e.g. the search filter) and confirm a
  membership test goes red — proving the test exercises the real SQL, not a proxy.
- Confirm `to_tsquery` search actually matches against the seeded `search_vector`
  (prefix match on a seeded name).

**Implementation Note**: After automated verification passes, pause for manual
confirmation before Phase 5.

---

## Phase 5: Risk #5 + #6 residual integration (ownership / usage)

### Overview

DB-backed tests proving per-account isolation on reads and writes (#5) and the
usage-assignment integration path plus its SQL sufficiency-filter parity (#6
residual).

### Changes Required:

#### 1. Risk #5 — cross-account read/write ownership

**File**: `backend/tests/integration/cabinet/test_ownership.py` (new)

**Intent**: Prove a user cannot read or write another user's cabinet — ownership is
enforced at the app/query layer, not merely authentication.

**Contract**: Seed user A with entries and user B (via `seed_user` / `act_as`):
- **Read:** as B, `GET /cabinet` returns none of A's entries; `GET`/detail of A's
  entry id (if such a route exists) returns empty/404.
- **Write:** as B, the importance toggle and usage `PATCH` against A's entry id are
  rejected (404 `EntryNotFoundError` — the `find_entry_by_id` scope is `user_id` +
  `entry_id`, `crud.py:433-467`), and A's row is unchanged afterward.
- Use unique per-test user ids (factory default) so parallel/re-runs don't collide.
  Assert ownership (the wrong-owner request changes nothing), not just a 200/401.

#### 2. Risk #6 residual — usage path round-trip + sufficiency-filter parity

**File**: `backend/tests/integration/cabinet/test_usage.py` (new)

**Intent**: Prove the `PATCH /entries/{id}/usage` → persist → resolve seam works end
to end, and that the set-based SQL `_sufficiency_clauses` filter agrees with the
per-row Python `compute_usage_view` verdict (the two are deliberately duplicated and
must stay in parity).

**Contract**:
- Seed a used tablet entry; `PATCH /entries/{id}/usage` with a valid dosage block;
  assert the persisted entry resolves to the expected `days_of_supply` /
  `days_until_end` / `is_sufficient` in the response (independent oracle from
  FR-016/017, not mirrored from the formula).
- Seed entries spanning sufficient / insufficient / no-verdict (zero-rate, closed
  window, missing capacity); assert the `sufficiency` filter selects exactly the rows
  whose Python `compute_usage_view` yields the matching verdict — proving SQL↔Python
  parity. Cover per-week vs per-day period and a partial-pack case.
- Clearing usage (`is_used=False`) nulls the dosage/date columns.

### Success Criteria:

#### Automated Verification:

- Ownership + usage tests pass (Docker running):
  `cd backend && uv run pytest tests/integration/cabinet/test_ownership.py tests/integration/cabinet/test_usage.py`
- Full integration tier green and order-independent:
  `cd backend && uv run pytest tests/integration`
- CI invocation still green and DB-free:
  `cd backend && uv run pytest --ignore=tests/db --ignore=tests/integration`
- Linting passes: `cd backend && uv run ruff check tests/integration`
- Type checking passes: `cd backend && uv run pyright`

#### Manual Verification:

- Temporarily drop the `user_id` predicate in `find_entry_by_id` and confirm a
  cross-account ownership test goes red.
- Confirm the sufficiency-filter parity test would catch a divergence: tweak one
  branch of `_sufficiency_clauses` and confirm a parity assertion fails.

**Implementation Note**: After automated verification passes, pause for final manual
confirmation. Append 2–3 cookbook lines to test-plan §6.6 capturing anything the
phase taught (e.g. the SAVEPOINT isolation gotcha).

---

## Testing Strategy

### Unit Tests:

- FR-010 merge math (`total_tablets`, `normalize_tablet_pool`, `merge_tablet_entry`,
  `merge_non_tablet_entry`) — full + partial-package, tablet + non-tablet; oracle
  from FR-010.

### Integration Tests (DB-backed, `tests/integration/`):

- #1: populated cabinet returns its rows with correct shape (not silent-empty).
- #4: exact id-set membership for status/search/category/below_minimum/sufficiency,
  incl. a filter-intersection case.
- #5: cross-account reads return nothing of the other user's; cross-account writes
  rejected; victim row unchanged.
- #6 residual: usage `PATCH` → persist → resolve round-trip; SQL sufficiency-filter
  parity with `compute_usage_view` (per-week / partial-pack / no-verdict edges).

### Manual Testing Steps:

1. With Docker running, `cd backend && uv run pytest` — full suite incl. integration
   green; no leftover containers afterward.
2. `cd backend && uv run pytest --ignore=tests/db --ignore=tests/integration` — green
   with Docker stopped (proves CI path is DB-free).
3. Delete a `WHERE` clause (search or `user_id`) and confirm the relevant membership /
   ownership test goes red (proves the tests exercise real SQL).

## Performance Considerations

- One container + one `alembic upgrade head` per **session** (session-scoped); per-test
  cost is just the SAVEPOINT rollback — fast. Do not re-migrate per test.
- The integration tier is excluded from the default CI run, so PR latency is unchanged
  until test-plan Phase 4 deliberately adds it.

## Migration Notes

- No production schema/data changes. The test DB schema is built from existing
  migrations against a disposable container; nothing touches Supabase/prod.

## References

- Research: `context/changes/testing-backend-safety-net/research.md`
- Change identity: `context/changes/testing-backend-safety-net/change.md`
- Test-plan spec: `context/foundation/test-plan.md` (§2 risk map, §3 Phase 1, §6 cookbook)
- L-001 (TLS DB → PowerShell, plain-TCP container sidesteps): `context/foundation/lessons.md:134-171`
- Postgres FTS: `backend/app/api/v1/cabinet/crud.py:309-314`; sufficiency clauses
  `crud.py:184-260`
- Pure merge math: `backend/app/api/v1/cabinet/service.py:62-141`
- Hermetic fixtures (reuse, don't duplicate): `backend/tests/conftest.py:29-80`
- Existing low-level DB tier (stays in place): `backend/tests/db/conftest.py`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: FR-010 merge-math unit tests (Risk #3)

#### Automated

- [x] 1.1 Unit tests pass (`pytest tests/cabinet/test_service.py`) — fa65324
- [x] 1.2 CI-path suite green (`pytest --ignore=tests/db --ignore=tests/integration`) — fa65324
- [x] 1.3 Linting passes (`ruff check tests/cabinet/test_service.py`) — fa65324
- [x] 1.4 Type checking passes (`pyright`) — fa65324

#### Manual

- [x] 1.5 Spot-check 2–3 expected values against FR-010 (oracle independence) — fa65324

### Phase 2: Test environment preparation

#### Automated

- [x] 2.1 Docker reachable (`docker info`) from the agent, or L-001 PowerShell fallback engaged — c65ed10
- [x] 2.2 Deps resolve (`uv sync --all-groups`) — c65ed10
- [x] 2.3 Container starts; `search_vector` column + GIN index present — c65ed10
- [x] 2.4 CI invocation green and DB-free (`--ignore=tests/db --ignore=tests/integration`) — c65ed10
- [x] 2.5 Linting passes (`ruff check tests/integration`) — c65ed10

#### Manual

- [x] 2.6 Container provisions and tears down cleanly (no leftovers) — c65ed10
- [x] 2.7 Schema built via `alembic upgrade head`, not `create_all` — c65ed10
- [x] 2.8 No L-001 applink abort on the container path (plain TCP) — c65ed10

### Phase 3: Integration harness fixtures

#### Automated

- [x] 3.1 Harness smoke passes (`pytest tests/integration/test_harness_smoke.py`)
- [x] 3.2 Isolation holds under random order across repeated runs
- [x] 3.3 CI invocation still green and DB-free
- [x] 3.4 Linting passes (`ruff check tests/integration`)
- [x] 3.5 Type checking passes (`pyright`)

#### Manual

- [x] 3.6 Same-session seam works; rows gone after teardown
- [x] 3.7 `act_as` switches identity within a single test

### Phase 4: Risk #1 + #4 integration (read / membership)

#### Automated

- [ ] 4.1 Read/membership tests pass (list_entries + filters)
- [ ] 4.2 Full integration tier green and order-independent
- [ ] 4.3 CI invocation still green and DB-free
- [ ] 4.4 Linting passes (`ruff check tests/integration`)
- [ ] 4.5 Type checking passes (`pyright`)

#### Manual

- [ ] 4.6 Deleting a WHERE clause turns a membership test red
- [ ] 4.7 `to_tsquery` search matches the seeded `search_vector`

### Phase 5: Risk #5 + #6 residual integration (ownership / usage)

#### Automated

- [ ] 5.1 Ownership + usage tests pass
- [ ] 5.2 Full integration tier green and order-independent
- [ ] 5.3 CI invocation still green and DB-free
- [ ] 5.4 Linting passes (`ruff check tests/integration`)
- [ ] 5.5 Type checking passes (`pyright`)

#### Manual

- [ ] 5.6 Dropping the `user_id` predicate turns an ownership test red
- [ ] 5.7 Tweaking `_sufficiency_clauses` turns a parity assertion red
- [ ] 5.8 Cookbook lines appended to test-plan §6.6

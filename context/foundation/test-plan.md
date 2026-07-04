# Test Plan

> Phased test rollout for this project. Strategy is frozen at the top
> (§1–§5); cookbook patterns at the bottom (§6) fill in as phases ship.
> Read before writing any new test.
>
> Refresh: re-run `/10x-test-plan --refresh` when stale (see §8).
>
> Last updated: 2026-07-04 (reconciled with implementation: S-05 dosage, F-04 CI,
> and §3 Phase 4 quality-gates-wiring shipped; §2 Risk #6, §3 Phase 4, §4, §5,
> §6.2, §7 updated)

## 1. Strategy

Tests follow three non-negotiable principles for this project:

1. **Cost × signal.** The cheapest test that gives a real signal for the
   risk wins. Do not promote to e2e because e2e "feels safer." Do not put a
   vision model on top of a deterministic visual diff that already catches
   the regression.
2. **User concerns are first-class evidence.** Risks anchored in "the team
   is worried about X, and the failure would surface somewhere in <area>"
   carry the same weight as PRD lines or hot-spot data.
3. **Risks are scenarios, not code locations.** This plan documents *what
   could fail* and *why we believe it's likely* — drawn from documents,
   interview, and codebase *signal* (churn, structure, test base). It does
   NOT claim to know which line owns the failure. That knowledge is
   produced by `/10x-research` during each rollout phase. If the plan and
   research disagree about where the failure lives, research is the
   ground truth.

Hot-spot scope used for likelihood weighting: `backend/app`, `frontend/src`
(excluding `.venv`, `node_modules`, `__pycache__`, docs, archive, build output).

## 2. Risk Map

The top failure scenarios this project must protect against, ordered by
risk = impact × likelihood. Risks are failure scenarios in user / business
terms, not test names. The Source column cites the *evidence that surfaced
this risk* — never a specific file as "where the failure lives" (that is
research's job, see §1 principle #3).

| # | Risk (failure scenario) | Impact | Likelihood | Source (evidence — not anchor) |
|---|--------------------------|--------|------------|---------------------------------|
| 1 | Silent data-path regression — a code change makes an endpoint return empty/partial data; the user opens the app and their cabinet is blank or missing rows. | High | High | interview Q2 (already happened); hot-spot dir `backend/app/api/v1/cabinet/` (35 commits/30d), `backend/app/api/v1/medicines/` (21 commits/30d) |
| 2 | Critical journey breaks at the frontend↔API seam — "login → add medication → see it in cabinet" or "display/filter cabinet data" silently breaks; the frontend renders nothing or the wrong data. | High | High | interview Q2, Q3, Q4; tech-stack.md (e2e golden path planned); frontend test base = none; hot-spot dir `frontend/src/features/cabinet/components/` (23 commits/30d), `frontend/src/features/cabinet/api/` (8 commits/30d) |
| 3 | Dedup/merge math corrupts tablet totals — adding the same drug a second time mis-sums or mis-normalizes the tablet pool (FR-010), so stored quantities are wrong. | High | Medium | PRD FR-010; roadmap S-01 risk note ("most complex business rule"); interview Q1 ("miscalculations"); hot-spot dir `backend/app/api/v1/cabinet/` (35 commits/30d) |
| 4 | Cabinet filter/search/status returns the wrong set — wrong valid/expiring/expired classification, broken filter intersection, or search misses matches at the pharmacy. | Medium | High | PRD FR-004, FR-006, FR-020; roadmap S-02 (done); hot-spot dir `backend/app/api/v1/cabinet/` (35 commits/30d) |
| 5 | Cross-account leak / wrong-owner write — a user reads or writes another user's cabinet (sees someone else's meds, or an add/edit lands on the wrong account). | High | Low-Med | PRD NFR (per-account data isolation) + guardrail; interview Q1; hot-spot dir `backend/app/api/v1/auth/` (15 commits/30d), `backend/app/api/v1/cabinet/` (35 commits/30d) — *abuse / IDOR row* |
| 6 | Dosage finish-date / sufficiency miscalc — a "used" medication tells the user they have enough supply when they don't, and they run out mid-course (or a run-out alert fails to fire). | High | Medium | PRD FR-016, FR-017, FR-019 + guardrail; interview Q1; roadmap S-05 (**shipped**, archived `2026-06-25-dosage-tracking`); calc already unit-tested (`tests/cabinet/test_service.py`) |

**Impact × Likelihood rubric.** Both axes are coarse High / Medium / Low.
High impact = user loses access, data, or money. High likelihood = area
changes weekly or we have already been burned here. Protect High × High
first (#1, #2). #5 is High-impact × Low-likelihood (no incident yet, auth
currently works) but is retained because it never surfaces from happy-path
tests. #6 (S-05 dosage) **shipped** on 2026-06-25 and its pure calc functions
already carry unit coverage; the residual risk is now the integration/usage
path, not the arithmetic — see §3 note.

### Risk Response Guidance

| Risk | What would prove protection | Must challenge | Context `/10x-research` must ground | Likely cheapest layer | Anti-pattern to avoid |
|------|-----------------------------|----------------|--------------------------------------|-----------------------|-----------------------|
| #1 | After a representative change, a populated cabinet still returns its rows with the correct response shape (not silently empty). | "200 OK ⇒ correct data" — an empty list is also a 200. | The real query path per domain and what a non-empty fixture looks like. | integration (httpx AsyncClient) | Asserting status code only; over-mocking the DB so the empty-result bug cannot surface. |
| #2 | The crucial journeys complete end-to-end against a real API and the cabinet data renders. | "Components render ⇒ app works" — the seam is where it breaks. | e2e auth setup; the add and display/filter flows; the API contract shape consumed by the frontend. | e2e (journeys) + thin unit on the API-calling layer | Snapshot / presentational tests; an e2e for what integration already covers. |
| #3 | Known inputs produce known merged totals and normalization per FR-010, across full and partial-package cases. | "Output matches the code" — the oracle must come from FR-010, not from reading the implementation. | The exact normalization rule and which function is pure vs DB-bound. | unit (pure function) | Oracle problem — copying expected values from the implementation under test. |
| #4 | A seeded cabinet plus filter/search/sort/status inputs returns exactly the expected entry set (membership, not just count). | "Filter returned rows ⇒ correct rows"; filter intersection vs union semantics. | Status classification thresholds; filter combination semantics (FR-004). | integration | Asserting count only; happy-path single-filter only. |
| #5 | A request for user A's resource by user B is rejected or empty; a write authenticates *and* verifies ownership. | "Logged-in ⇒ authorized" — authentication is not ownership. | Where `user_id`/ownership scoping is enforced; whether it is per-query or relies on RLS only. | integration (two users) | Testing only the happy-path owner; trusting RLS without an app-layer assertion. |
| #6 | Known dosage inputs produce the known finish-date / sufficiency result per FR-016/017. | "Pure calc is tested ⇒ the risk is closed" — the usage-assignment + display path (mark-used → persist → resolve) is the untested seam now. | The calc lives in `daily_consumption_rate` / `days_of_supply_from_rate` (already unit-tested); ground the `PATCH /entries/{id}/usage` path, persistence, and per-week / partial-pack / non-tablet edges. | integration (usage path); unit edges already covered | Re-testing the already-covered pure formula; mirroring the formula instead of an independent oracle. |

## 3. Phased Rollout

Each row is a discrete rollout phase that will open its own change folder
via `/10x-new`. Status moves left-to-right through the values below; the
orchestrator updates Status as artifacts appear on disk.

| # | Phase name | Goal (one line) | Risks covered | Test types | Status | Change folder |
|---|------------|-----------------|----------------|------------|--------|----------------|
| 1 | Backend business-logic + CRUD safety net | Harden the hottest backend surface so a change can't silently break data, corrupt totals, or cross account boundaries. | #1, #3, #4, #5 | unit + integration | change opened | context/changes/testing-backend-safety-net/ |
| 2 | Frontend critical-path E2E | Lock the crucial user journeys (login → add → see; display/filter cabinet) so they can't break unnoticed. Bootstraps Playwright. | #2, #1 | e2e | not started | — |
| 3 | Frontend data-seam unit tests | Verify the API-calling layer (typed fetchers, request/response shape, error handling) cheaply. Bootstraps Vitest. Narrow by design. | #2, #1 | unit | implementing | context/changes/frontend-data-seam-tests/ |
| 4 | Quality-gates wiring | Close the remaining CI gaps: wire the **frontend-unit** and **e2e** jobs into `ci-cd.yml` (the e2e job was previously disabled). Lint/typecheck/backend-test/build gates already ship via F-04. | #1–#6 | gates | complete | context/changes/quality-gates-wiring/ |

**Status vocabulary** (fixed — parser literals): `not started` → `change opened`
→ `researched` → `planned` → `implementing` → `complete`.

**Risk #6 status (was deferred, now shipped).** Roadmap slice S-05 (dosage
finish-date / sufficiency) **shipped** on 2026-06-25 (archived
`2026-06-25-dosage-tracking`). Its pure calc functions
(`daily_consumption_rate`, `days_of_supply_from_rate`) already carry unit
coverage in `tests/cabinet/test_service.py` (`test_days_of_supply_from_rate`,
`test_per_week_rate`, `test_sufficient_with_future_end_date`, plus the
usage-assignment validation tests). Risk #6 therefore has **no rollout phase of
its own**: the arithmetic oracle is covered. The residual gap is the
usage-assignment integration path (`PATCH /entries/{id}/usage` → persist →
resolve), which Phase 1's integration scope (Risk #1) should absorb when it
runs — flag it for `/10x-research` rather than opening a separate phase.

## 4. Stack

The classic test base for this project. Backend has a meaningful suite;
the frontend has none yet and is bootstrapped by Phases 2–3. AI-native
tooling is deliberately omitted (see §7).

| Layer | Tool | Version | Notes |
|-------|------|---------|-------|
| backend unit + integration | pytest + pytest-asyncio | pytest ≥8.0, asyncio ≥0.24 | 17 test files across domains (`auth`, `cabinet`, `medicines`, `users`, `registry`, `core`, `db`); `httpx.AsyncClient` as the FastAPI test client; shared fixtures in `backend/tests/conftest.py` |
| backend mocking | pytest-mock + `unittest.mock` | pytest-mock ≥3.15 | always pass `spec=`; `autospec=True` for patched functions (AGENTS.md) |
| backend coverage | coverage | ≥7.14 | run via `uv run pytest`; CI-gated, not local-gated |
| frontend unit | Vitest + React Testing Library | Vitest 4.1.9; RTL/jest-dom/user-event installed, unused this phase | bootstrapped by §3 Phase 3 via a `test` block in `frontend/vite.config.ts`; scoped to the API layer (`src/lib/api-client.ts`, `features/*/api/`) |
| e2e | Playwright | none yet — see §3 Phase 2 | planned in tech-stack.md; no `playwright.config.ts` / `frontend/e2e/` exists; Phase 2 bootstraps it + `auth.setup.ts` |
| CI gates | GitHub Actions | shipped (F-04 + §3 Phase 4) | `.github/workflows/ci-cd.yml` exists (F-04 `ci-cd-wiring`, archived `2026-06-29-ci-cd-wiring`; gaps closed by `quality-gates-wiring`): jobs for pip-audit, npm audit, pre-commit (ruff/eslint/tsc), backend pytest+coverage (`--ignore=tests/db --ignore=tests/integration`), frontend build, pyright, frontend-unit (Vitest), frontend-typecheck (`tsc -b`), backend-integration (testcontainers), frontend-e2e (Playwright, secrets-gated) |

**Stack grounding tools (current session):**
- Docs: Context7 / framework docs MCP — none; not available in current session; checked: 2026-06-16
- Search: Exa.ai — available (`web_search_exa`, `web_fetch_exa`); not needed for this write (stack is stable, locally grounded); checked: 2026-06-16
- Runtime/browser: Playwright MCP — none in session (Playwright is a planned test dependency, not a session tool); not used; checked: 2026-06-16
- Provider/platform: GitHub / Supabase MCP — none in session; not used; checked: 2026-06-16

## 5. Quality Gates

The full set of gates that must pass before a change reaches production.
"Required after §3 Phase N" means the gate is enforced once that rollout
phase lands; before that, the gate is `planned`.

| Gate | Where | Required? | Catches |
|------|-------|-----------|---------|
| lint + typecheck (ruff; eslint + tsc; pyright) | local (pre-commit) + CI | **enforced now** (CI pre-commit + pyright jobs, F-04) | syntactic / type / format drift |
| backend unit + integration | local + CI | **enforced now** (CI runs pytest+coverage, `--ignore=tests/db`); suite hardened by §3 Phase 1 | backend logic, CRUD, ownership, and calc regressions |
| frontend unit (API layer) | local + CI | **enforced now** (CI `frontend-unit` job, §3 Phase 4) | request/response shape + error-handling regressions at the seam |
| frontend typecheck (`tsc -b`) | local (implicit in build) + CI | **enforced now** (CI `frontend-typecheck` job, §3 Phase 4) | type errors surfaced as a discrete, fast gate symmetric with `backend-typecheck` |
| backend integration (DB-backed, testcontainers) | local + CI | **enforced now** (CI `backend-integration` job, §3 Phase 4) | real SQL path, filters, ownership, usage-seam regressions |
| e2e on critical flows | CI on PR | **enforced now** (CI `frontend-e2e` job, §3 Phase 4; secrets-gated, fails fast if unconfigured) | broken critical user journeys (add / display cabinet) |
| post-edit hook | local (agent loop) | optional (later module) | regressions at edit time |
| visual diff / multimodal review | CI on PR | optional — deliberately out of scope (see §7) | rendering regressions |
| pre-prod smoke | between merge + prod | optional | environment-specific failures (Render cold start) |

## 6. Cookbook Patterns

How to add new tests in this project. Backend entries reflect the existing
suite. Frontend entries fill in once Phases 2–3 ship; before that they read
"TBD — see §3 Phase N."

### 6.1 Adding a backend unit test (pure logic)

- **Location**: `backend/tests/<domain>/test_service.py` (pure domain functions live in `service.py` per project convention).
- **Naming**: `test_<behavior>`; use `pytest.mark.parametrize` for multiple inputs; named args when calling functions with 3+ arguments.
- **Reference test**: `backend/tests/cabinet/test_service.py`.
- **Oracle rule**: expected values come from the PRD/FR, never from reading the implementation (see Risk #3 anti-pattern).
- **Run locally**: `cd backend && uv run pytest`.

### 6.2 Adding a backend integration test (endpoint + CRUD)

Two distinct tiers both called "integration" — file each kind in the right place:

**Hermetic HTTP-contract tests** (`tests/<domain>/test_router.py` / `test_crud.py`) — mocked session, no DB needed:
- Mirror `app/api/v1/<domain>/`; request shared fixtures (`client`, `authed_client`, `mock_session`, `fake_user`) from `backend/tests/conftest.py` — do not duplicate mocks.
- Mocking policy: always pass `spec=` to mocks; `autospec=True` for patched functions. Assert response *shape and membership*, not just status code (see Risk #1).
- Reference test: `backend/tests/cabinet/test_router.py`, `backend/tests/cabinet/test_crud.py`.
- Run locally: `cd backend && uv run pytest`.

**DB-backed integration** (`tests/integration/`) — real Postgres via testcontainers, Docker required:
- Use when the risk lives in a real SQL path that mocks cannot reproduce (FTS `to_tsquery`, `DISTINCT ON`, generated columns, ownership scoping).
- Fixtures are in `backend/tests/integration/conftest.py`; see `tests/integration/README.md` for prerequisites and isolation model.
- Run locally: `cd backend && uv run pytest tests/integration` (Docker must be running).
- Now runs in CI via the `backend-integration` job (testcontainers provisions Postgres; no `services:` container needed), wired by test-plan Phase 4 (`quality-gates-wiring`).

### 6.3 Adding an e2e test

- TBD — see §3 Phase 2. (Will bootstrap `playwright.config.ts`, `frontend/e2e/`, and `auth.setup.ts`.)

### 6.4 Adding a frontend unit test (API-calling layer)

- **Location**: colocated as `*.test.ts` next to the source it covers —
  `src/lib/api-client.test.ts`, `src/features/<feature>/api/<feature>-api.test.ts`.
  Shared helpers live in `src/test/` (`setup.ts`, `api-test-utils.ts`).
- **Runner**: Vitest, `environment: "jsdom"`, config lives in a `test` block in
  `frontend/vite.config.ts` (not a separate `vitest.config.ts`). Run locally:
  `cd frontend && npm run test:run` (or `npm test` for watch mode).
- **Pattern**: `vi.stubGlobal("fetch", vi.fn())` in a `beforeEach`; seed
  responses with `jsonResponse(body, { status? })` from
  `src/test/api-test-utils.ts` — a **real** `Response` (not a typed stub), so
  `error instanceof Response` is exercised faithfully. Assert the request side
  via `callInfo(fetch.mock.calls[n])`, which strips the computed `BASE` prefix
  so path assertions read as `/cabinet/entries?status=valid` rather than an
  absolute URL.
- **What to assert**: request shape (URL/query string, method, headers, JSON
  body) and error propagation (`throw res` on `!ok`, `AuthError` on failed
  refresh) — not response-shape mapping; the fetchers are thin pass-throughs
  so happy-path returns need only one representative fixture per fetcher.
- **Reference tests**: `frontend/src/lib/api-client.test.ts` (transport: bearer
  attach, 401→refresh→retry, `/auth/` skip, single-flight `refreshOnce`);
  `frontend/src/features/cabinet/api/cabinet-api.test.ts` (densest URL
  building — `encodeURIComponent`, conditional params, `below_minimum` →
  `"true"`, POST/PATCH/DELETE bodies).
- **Isolation gotcha**: the `refreshing` single-flight latch in
  `api-client.ts` only self-resets via `.finally` when its promise settles —
  every refresh `fetch` mock in a test must **resolve** (never reject or
  hang), even for the failed-refresh case (resolve with a non-`ok` `Response`),
  or the latch leaks into the next test.

### 6.5 Adding a test for a cross-domain flow (facade)

- **Test type**: integration, exercised through the facade layer.
- **Pattern**: facade is the only layer allowed to call other domains' services/cruds; test it through the router or directly, asserting the orchestrated result.
- **Reference test**: `backend/tests/cabinet/test_facade.py`.

### 6.6 Per-rollout-phase notes

(Filled in as phases land — `/10x-implement` appends 2–3 lines capturing anything surprising a phase taught.)

**Phase 3 (Frontend data-seam unit tests, 2026-07-04):**
- **`tsc -b` + test files.** `npm run build` runs `tsc -b`, which type-checks
  `*.test.ts` too; without `"vitest/globals"` / `"@testing-library/jest-dom"`
  in `compilerOptions.types` the build breaks on `describe`/`expect`/matcher
  calls. Verify `npm run build` explicitly after bootstrapping — it's the
  most likely regression, not the test run itself.
- **Single-flight latch reset.** `refreshOnce`'s `refreshing` latch has no
  exported reset hook; it only clears via `.finally` when its promise
  settles. Every refresh mock (including the failed-refresh case) must
  *resolve* — a rejecting/never-resolving mock leaks the latch across tests.
- **`below_minimum` edge.** `listEntries` serializes `below_minimum` as the
  literal string `"true"` only when truthy — `false` omits the param
  entirely (not `"false"`); worth its own test, not folded into the
  all-params-together case.
- **`Response` is real, not a stub.** `jsonResponse()` returns
  `new Response(...)` (jsdom/undici supplies the global) so
  `error instanceof Response` — the contract `query-client.ts` depends on —
  is exercised for real, not simulated with a plain object.

**Phase 5 (Risk #5 + #6, 2026-06-30):**
- **Unique-constraint trap in parity tests.** When seeding multiple entries for the same user + registry, passing an explicit `expiry_date` to every call overrides the factory counter and triggers `uq_cabinet_entries_user_med_expiry`. Omit the override and let the counter handle it, or use a distinct registry per group.
- **Boundary case required for `>=` vs `>` parity.** A sufficiency parity test with only "clearly sufficient" entries (supply >> until_end) cannot catch a `>=` → `>` mutation. Seed at least one boundary entry where `supply == until_end` exactly; without it the mutation silently passes.
- **Wrong `tablets_per_package` breaks the oracle.** The Python `compute_usage_view` oracle must receive the capacity of the entry's *actual* registry. Using a hardcoded tpp when entries span multiple registries produces a wrong prediction and causes the parity assertion to fail on the wrong filter.

## 7. What We Deliberately Don't Test

Exclusions agreed during the rollout (Phase 2 interview, Q5). Future
contributors should respect these unless the underlying assumption changes.

- **XML registry import *execution* (the one-off bulk load/run)** — not a live path, so the load script run itself is not tested. **Correction (2026-06-30):** the *parser logic* is in fact already unit-tested — `backend/tests/registry/test_parser.py` (landed 2026-06-09, before this plan) covers `parse_registry`, `_parse_capacity`, `_is_tablet_based`, etc. The original "registry parsing is not tested" claim was inaccurate; only the import *execution* stays out of scope. Re-evaluate the whole area if periodic/incremental registry refresh ships (PRD v2 item). (Source: Phase 2 interview Q5; reconciled with the existing suite.)
- **Framework behavior** — Supabase Auth internals, TanStack Query, FastAPI/SQLModel machinery. Trust the library; test our logic on top of it. Re-evaluate only on a major version upgrade. (Source: Phase 2 interview Q5.)
- **Trivial pass-through functions** — one-liners that only delegate to another function with no real logic. Re-evaluate if such a function grows branching/business logic. (Source: Phase 2 interview Q5.)
- **Presentational UI / styling / layout snapshots** — no snapshot or pixel tests of components; budget goes to business logic and CRUD. (Source: Phase 2 interview Q5.)
- **AI-native / multimodal visual review** — deliberately not in the rollout: the domain is deterministic (CRUD + arithmetic), scale is small, and presentational testing is de-prioritized, so a vision layer adds cost without signal classic tests don't already give. Reconsider if a complex, visually-driven screen ships where layout regressions would silently mislead the user.

## 8. Freshness Ledger

- Strategy (§1–§5) last reviewed: 2026-06-30 (reconciled with implementation)
- Stack versions last verified: 2026-06-30
- AI-native tool references last verified: 2026-06-16

Refresh (`/10x-test-plan --refresh`) when:

- a new top-3 risk surfaces from the roadmap or archive,
- a recommended tool's `checked:` date is older than three months,
- the project's tech stack changes (new framework, new test runner),
- §7 negative-space no longer matches what the team believes.

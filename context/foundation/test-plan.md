# Test Plan

> Phased test rollout for this project. Strategy is frozen at the top
> (§1–§5); cookbook patterns at the bottom (§6) fill in as phases ship.
> Read before writing any new test.
>
> Refresh: re-run `/10x-test-plan --refresh` when stale (see §8).
>
> Last updated: 2026-06-16 (Phase 1 change opened)

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
| 6 | Dosage finish-date / sufficiency miscalc — a "used" medication tells the user they have enough supply when they don't, and they run out mid-course (or a run-out alert fails to fire). | High | Medium (future) | PRD FR-016, FR-017, FR-019 + guardrail; interview Q1; roadmap S-05 (next, **not yet shipped**) |

**Impact × Likelihood rubric.** Both axes are coarse High / Medium / Low.
High impact = user loses access, data, or money. High likelihood = area
changes weekly or we have already been burned here. Protect High × High
first (#1, #2). #5 is High-impact × Low-likelihood (no incident yet, auth
currently works) but is retained because it never surfaces from happy-path
tests. #6 targets a feature (S-05) that is not yet shipped — see §3 note.

### Risk Response Guidance

| Risk | What would prove protection | Must challenge | Context `/10x-research` must ground | Likely cheapest layer | Anti-pattern to avoid |
|------|-----------------------------|----------------|--------------------------------------|-----------------------|-----------------------|
| #1 | After a representative change, a populated cabinet still returns its rows with the correct response shape (not silently empty). | "200 OK ⇒ correct data" — an empty list is also a 200. | The real query path per domain and what a non-empty fixture looks like. | integration (httpx AsyncClient) | Asserting status code only; over-mocking the DB so the empty-result bug cannot surface. |
| #2 | The crucial journeys complete end-to-end against a real API and the cabinet data renders. | "Components render ⇒ app works" — the seam is where it breaks. | e2e auth setup; the add and display/filter flows; the API contract shape consumed by the frontend. | e2e (journeys) + thin unit on the API-calling layer | Snapshot / presentational tests; an e2e for what integration already covers. |
| #3 | Known inputs produce known merged totals and normalization per FR-010, across full and partial-package cases. | "Output matches the code" — the oracle must come from FR-010, not from reading the implementation. | The exact normalization rule and which function is pure vs DB-bound. | unit (pure function) | Oracle problem — copying expected values from the implementation under test. |
| #4 | A seeded cabinet plus filter/search/sort/status inputs returns exactly the expected entry set (membership, not just count). | "Filter returned rows ⇒ correct rows"; filter intersection vs union semantics. | Status classification thresholds; filter combination semantics (FR-004). | integration | Asserting count only; happy-path single-filter only. |
| #5 | A request for user A's resource by user B is rejected or empty; a write authenticates *and* verifies ownership. | "Logged-in ⇒ authorized" — authentication is not ownership. | Where `user_id`/ownership scoping is enforced; whether it is per-query or relies on RLS only. | integration (two users) | Testing only the happy-path owner; trusting RLS without an app-layer assertion. |
| #6 | Known dosage inputs produce the known finish-date / sufficiency result per FR-016/017. | Whether the calculation code even exists yet (S-05 is not shipped). | Confirm feature existence first; then the calc rule and edge cases (per-week period, partial pack). | unit (when shipped) | Writing tests against unbuilt code; mirroring the formula instead of an independent oracle. |

## 3. Phased Rollout

Each row is a discrete rollout phase that will open its own change folder
via `/10x-new`. Status moves left-to-right through the values below; the
orchestrator updates Status as artifacts appear on disk.

| # | Phase name | Goal (one line) | Risks covered | Test types | Status | Change folder |
|---|------------|-----------------|----------------|------------|--------|----------------|
| 1 | Backend business-logic + CRUD safety net | Harden the hottest backend surface so a change can't silently break data, corrupt totals, or cross account boundaries. | #1, #3, #4, #5 | unit + integration | change opened | context/changes/testing-backend-safety-net/ |
| 2 | Frontend critical-path E2E | Lock the crucial user journeys (login → add → see; display/filter cabinet) so they can't break unnoticed. Bootstraps Playwright. | #2, #1 | e2e | not started | — |
| 3 | Frontend data-seam unit tests | Verify the API-calling layer (typed fetchers, request/response shape, error handling) cheaply. Bootstraps Vitest. Narrow by design. | #2, #1 | unit | not started | — |
| 4 | Quality-gates wiring | Enforce lint, typecheck, backend unit+integration, frontend unit, and the e2e golden path in CI so the floor is enforced, not aspirational. | #1–#6 | gates | not started | — |

**Status vocabulary** (fixed — parser literals): `not started` → `change opened`
→ `researched` → `planned` → `implementing` → `complete`.

**Deferred risk.** Risk #6 (dosage finish-date / sufficiency) targets roadmap
slice S-05, which is `proposed` and **not yet shipped**. It has no rollout
phase of its own here: there is no code to test. When S-05 lands, add its
coverage using the same pure-function unit pattern as Phase 1's dedup math
(§6.1) — open a phase via `--refresh` or fold it into the S-05 change plan.

## 4. Stack

The classic test base for this project. Backend has a meaningful suite;
the frontend has none yet and is bootstrapped by Phases 2–3. AI-native
tooling is deliberately omitted (see §7).

| Layer | Tool | Version | Notes |
|-------|------|---------|-------|
| backend unit + integration | pytest + pytest-asyncio | pytest ≥8.0, asyncio ≥0.24 | 16 test files across all domains; `httpx.AsyncClient` as the FastAPI test client; shared fixtures in `backend/tests/conftest.py` |
| backend mocking | pytest-mock + `unittest.mock` | pytest-mock ≥3.15 | always pass `spec=`; `autospec=True` for patched functions (AGENTS.md) |
| backend coverage | coverage | ≥7.14 | run via `uv run pytest`; CI-gated, not local-gated |
| frontend unit | Vitest + React Testing Library | none yet — see §3 Phase 3 | planned in tech-stack.md; no `vitest.config.ts` exists; Phase 3 bootstraps it, scoped to the API layer |
| e2e | Playwright | none yet — see §3 Phase 2 | planned in tech-stack.md; no `playwright.config.ts` / `frontend/e2e/` exists; Phase 2 bootstraps it + `auth.setup.ts` |
| CI gates | GitHub Actions | none yet — see §3 Phase 4 | no CI workflow exists (AGENTS.md); F-04 `ci-cd-wiring` is `ready` but not done |

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
| lint + typecheck (ruff; eslint + tsc) | local (pre-commit) + CI | required after §3 Phase 4 (locally enforced today via pre-commit) | syntactic / type / format drift |
| backend unit + integration | local + CI | required after §3 Phase 1 | backend logic, CRUD, ownership, and calc regressions |
| frontend unit (API layer) | local + CI | required after §3 Phase 3 | request/response shape + error-handling regressions at the seam |
| e2e on critical flows | CI on PR | required after §3 Phase 2 | broken critical user journeys (add / display cabinet) |
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

- **Location**: `backend/tests/<domain>/test_router.py` (HTTP) or `test_crud.py` (DB ops); mirror `app/api/v1/<domain>/`.
- **Client**: `httpx.AsyncClient`; request shared fixtures (`client`, `authed_client`, `mock_session`, `fake_user`) from `backend/tests/conftest.py` — do not duplicate mocks.
- **Mocking policy**: always pass `spec=` to mocks; `autospec=True` for patched functions. Assert response *shape and membership*, not just status code (see Risk #1).
- **Reference test**: `backend/tests/cabinet/test_router.py`, `backend/tests/cabinet/test_crud.py`.
- **Run locally**: `cd backend && uv run pytest`.

### 6.3 Adding an e2e test

- TBD — see §3 Phase 2. (Will bootstrap `playwright.config.ts`, `frontend/e2e/`, and `auth.setup.ts`.)

### 6.4 Adding a frontend unit test (API-calling layer)

- TBD — see §3 Phase 3. (Will bootstrap `vitest.config.ts`; scoped to typed fetchers / request-response handling in `features/<feature>/api/`, not presentational components.)

### 6.5 Adding a test for a cross-domain flow (facade)

- **Test type**: integration, exercised through the facade layer.
- **Pattern**: facade is the only layer allowed to call other domains' services/cruds; test it through the router or directly, asserting the orchestrated result.
- **Reference test**: `backend/tests/cabinet/test_facade.py`.

### 6.6 Per-rollout-phase notes

(Filled in as phases land — `/10x-implement` appends 2–3 lines capturing anything surprising a phase taught.)

## 7. What We Deliberately Don't Test

Exclusions agreed during the rollout (Phase 2 interview, Q5). Future
contributors should respect these unless the underlying assumption changes.

- **XML registry parsing / import script** — a one-off load, not a live path. Re-evaluate if periodic/incremental registry refresh ships (PRD v2 item). (Source: Phase 2 interview Q5.)
- **Framework behavior** — Supabase Auth internals, TanStack Query, FastAPI/SQLModel machinery. Trust the library; test our logic on top of it. Re-evaluate only on a major version upgrade. (Source: Phase 2 interview Q5.)
- **Trivial pass-through functions** — one-liners that only delegate to another function with no real logic. Re-evaluate if such a function grows branching/business logic. (Source: Phase 2 interview Q5.)
- **Presentational UI / styling / layout snapshots** — no snapshot or pixel tests of components; budget goes to business logic and CRUD. (Source: Phase 2 interview Q5.)
- **AI-native / multimodal visual review** — deliberately not in the rollout: the domain is deterministic (CRUD + arithmetic), scale is small, and presentational testing is de-prioritized, so a vision layer adds cost without signal classic tests don't already give. Reconsider if a complex, visually-driven screen ships where layout regressions would silently mislead the user.

## 8. Freshness Ledger

- Strategy (§1–§5) last reviewed: 2026-06-16
- Stack versions last verified: 2026-06-16
- AI-native tool references last verified: 2026-06-16

Refresh (`/10x-test-plan --refresh`) when:

- a new top-3 risk surfaces from the roadmap or archive,
- a recommended tool's `checked:` date is older than three months,
- the project's tech stack changes (new framework, new test runner),
- §7 negative-space no longer matches what the team believes.

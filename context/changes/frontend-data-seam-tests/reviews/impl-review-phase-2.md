<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Frontend Data-Seam Unit Tests

- **Plan**: context/changes/frontend-data-seam-tests/plan.md
- **Scope**: Phase 2 of 3
- **Date**: 2026-07-04
- **Verdict**: APPROVED
- **Findings**: 0 critical  0 warnings  1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS (1 observation) |
| Success Criteria | PASS |

## What was verified

Diff (commit 5915d08) touched exactly the two planned new files plus plan.md
Progress checkboxes — no unplanned source changed:

- `frontend/src/test/api-test-utils.ts` — `jsonResponse` real-`Response` factory,
  `stripBase` + `callInfo` (BASE-stripped path + `RequestInit` from a fetch mock call).
- `frontend/src/lib/api-client.test.ts` — transport suite.

Contract coverage (all four Phase-2 items, faithful to plan):

- **apiFetch** — attaches/omits `Authorization: Bearer`; non-`/auth/` 401 →
  refresh → retry once with the **new** token → returns the retry body;
  `/auth/`-path 401 does not refresh; failed refresh → `AuthError` (`instanceof`).
- **apiJson** — success → parsed JSON; `!ok` → throws the **raw `Response`**,
  asserted `instanceof Response` + `.status` (the `query-client.ts:10` contract).
- **refreshOnce** — two concurrent calls → exactly one fetch; latch resets so a
  subsequent call issues a fresh fetch. Both refresh mocks resolve so `.finally`
  clears the single-flight latch, exactly as the plan's Critical Implementation
  Details require.

Automated criteria (re-run during review):

- 2.1 `npm run test:run` → PASS (2 files, 10 tests, 702ms — meets "cheap" intent)
- 2.2 `npm run build` → PASS (`tsc -b` + `vite build` green with test files present)
- 2.3 `npm run lint` → PASS (eslint clean)
- 2.4 (manual) mutation sanity — marked `[x]` in commit; leaves no diff artifact
  by nature, accepted as pending-with-no-contradiction (not rubber-stamped).

## Findings

### F1 — Stubbed global `fetch` is never unstubbed in cleanup

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: frontend/src/test/setup.ts:5 / frontend/vite.config.ts:15
- **Detail**: The suite mocks via `vi.stubGlobal("fetch", vi.fn())`, but the
  shared `afterEach` only runs `cleanup()`, `localStorage.clear()`, and
  `vi.restoreAllMocks()`. `restoreAllMocks()` does NOT undo `stubGlobal` — that
  needs `vi.unstubAllGlobals()` (or `test.unstubGlobals: true` in config). Today
  this is harmless: each `describe` re-stubs in its own `beforeEach` and Vitest
  isolates test files, so nothing leaks. But it is a latent trap for Phase 3's
  cabinet/auth/settings suites — a test that forgets the `beforeEach` re-stub
  would silently inherit a leftover mock instead of failing loudly.
- **Fix**: Add `unstubGlobals: true` to the `test` block in `vite.config.ts`
  (auto-unstubs after each test, matches the existing restore-mocks intent, and
  covers every future suite for free).
- **Decision**: FIXED — added `unstubGlobals: true` to the `test` block in `frontend/vite.config.ts`

<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Frontend Data-Seam Unit Tests

- **Plan**: context/changes/frontend-data-seam-tests/plan.md
- **Mode**: Deep
- **Date**: 2026-07-03
- **Verdict**: REVISE
- **Findings**: 0 critical, 2 warnings, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | WARNING |
| Plan Completeness | WARNING |

## Grounding

10/10 paths ✓, transport/fetcher/query-client claims verified against source ✓,
Progress↔Phase mechanical contract well-formed ✓, brief↔plan consistent ✓.
No `docs/reference/contract-surfaces.md` (check skipped). Lessons priors L-005
(no single-letter names) and L-006 (imports at top) apply to the new test files.

## Findings

### F1 — Response factory "stub" option undermines the load-bearing `instanceof Response` contract

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Phase 2 §1 (api-test-utils) + §3 (apiJson tests)
- **Detail**: The plan's rationale for keeping the transport in scope is the load-bearing error contract: `apiJson` does `throw res` (raw Response, `api-client.ts:71`) and `query-client.ts:10` keys off `error instanceof Response && error.status === 401`. Phase 2 §3 says to "assert the thrown value is a Response". But Phase 2 §1's factory contract offers two equal options: "a real Response or a typed stub with ok, status, json()". These are in tension — a stub makes `throw res` throw a plain object, so an `instanceof Response` assertion FAILS; weakening the test to only check `.status` passes but no longer proves the contract query-client depends on. Node ≥18/undici supplies a global `Response`, so a real one is available under jsdom — the stub isn't necessary.
- **Fix**: In api-test-utils, mandate the factory return a **real** `Response` (`new Response(JSON.stringify(body), { status })`), not a stub, so `instanceof Response` is exercised faithfully. Drop the "typed stub" alternative from the §1 contract.
  - Strength: Makes the apiJson `throw res` test bite on the same predicate query-client.ts:10 uses in production.
  - Tradeoff: Slightly less control over `.json()` behavior than a stub.
  - Confidence: HIGH — `throw res` + `instanceof Response` verified in api-client.ts:71 and query-client.ts:10.
  - Blind spot: `Response` body is single-use; a test reading `.json()` twice needs a fresh instance (minor).
- **Decision**: FIXED — real-`Response` factory mandated in Phase 2 §1; typed-stub alternative dropped.

### F2 — Vitest ↔ Vite 8 peer compatibility gates the whole change with no documented fallback

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Phase 1 §1 (deps) / Critical Implementation Details
- **Detail**: package.json pins `vite: ^8.0.12` (bleeding edge). Vitest bundles a Vite dependency and declares a supported Vite peer range; if the current Vitest doesn't list Vite 8, `npm install` can fail peer resolution or the runner can misbehave. Phase 1's first automated criterion is `npm install`, so this failure blocks the entire change. The plan acknowledges the risk ("verified during Phase 1 install") but prescribes no contingency — no version pin, no `overrides`, no fallback to a standalone `vitest.config.ts`.
- **Fix**: Add a one-line contingency to Phase 1: if peer resolution fails, pin a Vitest version whose peer range includes Vite 8 (or set an npm `overrides` entry), and record resolved versions in the §6.6 note. Make "runner starts against Vite 8" an explicit Phase 1 checkpoint.
  - Strength: Turns a silent blocker into a planned decision point.
  - Tradeoff: Can't fully pre-verify versions at plan time.
  - Confidence: MED — Vite 8 is new enough that peer lag is plausible; exact Vitest support matrix unverified here.
  - Blind spot: RTL-for-React-19 adapter version is a second, related unverified pin in the same install.
- **Decision**: FIXED — peer-resolution contingency (pin/overrides) + record versions + criterion 1.2 as explicit Vite-8 checkpoint added to Phase 1 §1.

### F3 — Single-flight latch reset mechanism named but not specified

- **Severity**: 🔵 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 2 §4 + Critical Implementation Details
- **Detail**: `refreshing` (`api-client.ts:7`) is module-level state that only self-resets via `.finally` after the refresh promise settles (`api-client.ts:23-25`). The plan's afterEach (`vi.restoreAllMocks()` / `localStorage.clear()`) does NOT reset it, and the module exports no reset hook. If any test's refresh-fetch mock rejects or never resolves, the latch leaks into the next test and can mask a bug. The plan says "reset between tests" and "structure so a prior test's latch can't mask a bug" but names no concrete mechanism.
- **Fix**: State the mechanism — either (a) ensure every refresh mock resolves so `.finally` fires and clears the latch, or (b) use `vi.resetModules()` + dynamic re-import for a fresh module per single-flight test. Pick one in the plan.
- **Decision**: FIXED (option a) — Critical Implementation Details + Phase 2 §4 now mandate every refresh mock resolve (failed-refresh via non-`ok` Response, not a rejected fetch) so `.finally` clears the latch.

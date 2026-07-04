# Frontend Data-Seam Unit Tests — Plan Brief

> Full plan: `context/changes/frontend-data-seam-tests/plan.md`

## What & Why

Bootstrap **Vitest** and write the project's first frontend unit suite, scoped
narrowly to the **API-calling layer** — the shared transport
(`src/lib/api-client.ts`) and the three feature fetcher modules (cabinet, auth,
settings). This cheaply guards the frontend↔API seam where a change can silently
break the request shape or error handling (test-plan Risks **#2** and **#1**).
It is **Phase 3** of the frozen test plan.

## Starting Point

The frontend has **no unit tests and no Vitest** — no config, no deps, no
`src/test/setup.ts` (though `AGENTS.md` documents the intended home). Playwright
E2E (test-plan Phase 2) already shipped and coexists. The seam under test is
small: one transport module with the 401→refresh→retry / `AuthError` logic, plus
thin pass-through fetchers whose real logic is URL/query-string building.

## Desired End State

`npm test` in `frontend/` runs a green Vitest suite that pins the transport's
auth/refresh/error contract and every fetcher's request shape (URL, method,
headers, body) and error propagation. `npm run build` still passes with the test
files present. The test-plan §6.4 cookbook is filled in. No CI file is touched.

## Key Decisions Made

| Decision                | Choice                                   | Why (1 sentence)                                                              | Source |
| ----------------------- | ---------------------------------------- | ---------------------------------------------------------------------------- | ------ |
| HTTP mocking            | Mock `globalThis.fetch` (`vi.fn`)        | Zero new deps, fastest, tests the real `api-client` boundary directly.       | Plan   |
| Test environment        | jsdom                                    | Supplies `localStorage`/`Headers`/`fetch` the transport needs; RTL-ready.    | Plan   |
| Transport in scope      | Yes — include `api-client.ts`            | The 401/refresh/`AuthError` logic is the highest-signal code in the layer.   | Plan   |
| Feature coverage        | All three (cabinet, auth, settings)      | Small total surface; sets the §6.4 cookbook pattern uniformly.               | Plan   |
| Assertion depth         | Request-shape + error-contract focused   | Fetchers are thin pass-throughs; field-by-field asserts would be tautologies.| Plan   |
| Config placement        | `test` block in `vite.config.ts`         | Matches `AGENTS.md`; shares the `@/` alias, single config source.            | Plan   |
| CI wiring               | Out of scope (local `npm test` only)     | Frontend-unit CI job is test-plan Phase 4; keeps this change narrow.         | Test-plan |

## Scope

**In scope:** Vitest bootstrap (deps, `vite.config.ts` test block, `setup.ts`,
tsconfig types, npm scripts); transport tests (`api-client.ts`); fetcher tests
(cabinet/auth/settings); fill test-plan §6.4 + §6.6.

**Out of scope:** CI wiring (Phase 4); component/presentational/snapshot tests;
runtime response-shape/zod validation; testing framework behavior (TanStack
Query, Router); MSW; production source changes.

## Architecture / Approach

Per test, replace `globalThis.fetch` with a `vi.fn()`, stub its `Response`, and
assert on `fetch.mock.calls` for the request side. jsdom supplies the browser
globals; a small `Response` factory + a BASE-stripping URL helper keep
assertions legible. Test files are colocated `*.test.ts`. Config lives in a
`test` block in `vite.config.ts` sharing the `@/` alias.

## Phases at a Glance

| Phase                          | What it delivers                                        | Key risk                                                        |
| ------------------------------ | ------------------------------------------------------- | -------------------------------------------------------------- |
| 1. Bootstrap Vitest runner     | Deps, config, setup, tsconfig types, scripts, smoke test | `tsc -b` breaking on new test files / Playwright collision     |
| 2. Transport tests             | `api-client.ts` auth/refresh/error contract covered      | Single-flight latch + `localStorage` state leaking across tests|
| 3. Feature fetchers + cookbook | cabinet/auth/settings request shapes; §6.4/§6.6 filled    | Over-asserting thin pass-throughs; missing the `below_minimum` edge |

**Prerequisites:** None beyond the existing frontend toolchain (Vite 8, React
19, npm). Playwright already present.
**Estimated effort:** ~1–2 sessions across 3 phases.

## Open Risks & Assumptions

- Assumes RTL/jsdom versions resolve cleanly against Vite 8 / React 19 (RTL React
  adapter must support React 19) — verified during Phase 1 install.
- Assumes `tsc -b` can be made green with Vitest globals via a `types` addition
  or a test-scoped tsconfig — the most likely bootstrap snag (flagged in the plan).
- Mocked-fetch tests cannot catch a real backend field-shape regression — that is
  integration/e2e's job, and accepted per test-plan §7.

## Success Criteria (Summary)

- `npm run test:run` passes a suite covering the transport contract and all three
  fetcher modules.
- `npm run build` still passes with test files and config present; Playwright
  unaffected.
- Test-plan §6.4 cookbook is a followable recipe for the next contributor.

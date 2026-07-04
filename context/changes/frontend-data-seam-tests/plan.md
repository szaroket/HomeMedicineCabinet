# Frontend Data-Seam Unit Tests Implementation Plan

## Overview

Bootstrap **Vitest** for the frontend and write the project's first frontend
unit suite, scoped narrowly to the **API-calling layer** — the shared transport
(`src/lib/api-client.ts`) plus the three feature fetcher modules
(`features/cabinet/api`, `features/auth/api`, `features/settings/api`). The suite
guards the frontend↔API seam (test-plan Risks **#2** and **#1**) cheaply, by
mocking `globalThis.fetch` and asserting **what the fetcher sends** (URL, query
string, method, headers, body) and **how it handles errors** (`throw res` on
`!ok`, `AuthError` on failed refresh, 401→refresh→retry).

This is **Phase 3** of the frozen test plan (`context/foundation/test-plan.md`
§3, row 3). It bootstraps the Vitest runner that later component/integration
phases will build on. CI wiring (the frontend-unit job in `ci-cd.yml`) is
deliberately **out of scope** — that is test-plan **Phase 4**.

## Current State Analysis

- **Vitest is not bootstrapped.** No `vitest.config.ts`, no `test` block in
  `vite.config.ts` (`frontend/vite.config.ts` has only `plugins` + `resolve`),
  no `vitest`/RTL/`jsdom` in `frontend/package.json` devDependencies, and no
  `src/test/setup.ts` — even though `AGENTS.md` lines 50–51 document that
  intended home (`test/setup.ts` for Vitest, a `test` block in `vite.config.ts`).
- **Playwright/E2E (test-plan Phase 2) already shipped.** `frontend/e2e/`,
  `playwright.config.ts`, `tsconfig.e2e.json`, and `auth.setup.ts` all exist, so
  this phase adds *only* the unit runner — the two must coexist (Vitest picks up
  `src/**/*.test.ts`, Playwright owns `e2e/**/*.spec.ts`).
- **The seam surface is small and well-shaped:**
  - `src/lib/api-client.ts` — the transport. `apiFetch` attaches
    `Authorization: Bearer <token>` from the auth store, and on a non-`/auth/`
    `401` calls `refreshOnce()` (single-flight latch), stores the new token,
    and retries once; if refresh returns `null` it throws
    `AuthError`. `apiJson<T>` calls `apiFetch`, throws the raw `Response` when
    `!res.ok`, else returns `res.json()`. `refreshOnce()` collapses concurrent
    refreshes onto one promise.
  - `src/lib/errors.ts` — the `AuthError` class the transport throws and
    `query-client.ts` / the auth store key off of.
  - `src/features/cabinet/api/cabinet-api.ts` — the hot-spot (8 commits/30d).
    Rich URL/query-string building: `searchProducts` (`encodeURIComponent`),
    `listVariants` (conditional `strength`/`form` params), `listEntries`
    (8 optional params incl. the `below_minimum` boolean-as-`"true"` special
    case), plus POST/PATCH/DELETE fetchers (`addEntry`, `toggleImportant`,
    `setUsage`, `updateQuantity`, `deleteEntry`). `deleteEntry` uses `apiFetch`
    directly and throws `res` on `!ok` (no body to parse).
  - `src/features/auth/api/auth-api.ts` — `register`, `login` (POST bodies),
    `logout` (fire-and-forget `apiFetch`), `getMe`.
  - `src/features/settings/api/settings-api.ts` — `getPreferences`,
    `updatePreferences` (PATCH body).
- **Downstream contracts depend on the exact error shape.**
  `src/lib/query-client.ts` retry predicate checks
  `error instanceof Response && error.status === 401` and
  `error instanceof AuthError`; the auth store subscribes to the query/mutation
  caches and calls `clearSession()` on `AuthError`. Tests must therefore assert
  the transport throws a **raw `Response`** (not a parsed body) on `!ok`, and an
  **`AuthError`** on failed refresh — these are load-bearing.
- **Base URL is computed at module load:**
  `const BASE = ${import.meta.env.VITE_API_URL ?? "http://localhost:8000"}/api/v1`.
  In the test env `VITE_API_URL` is unset, so `BASE` resolves to
  `http://localhost:8000/api/v1`.
- **The fetchers are thin pass-throughs** (`return res.json()`), so their real
  logic — and thus the test value — is URL/param construction and error
  propagation, **not** response mapping.

## Desired End State

Running `npm test` (or `npm run test:run`) in `frontend/` executes a green
Vitest suite that:

- proves the runner, the `jsdom` environment, the `@/` alias, and the
  `@testing-library/jest-dom` matchers all resolve (Phase 1 smoke test);
- pins the transport's auth/refresh/error contract (Phase 2);
- pins every feature fetcher's request shape and error propagation (Phase 3).

`npm run build` (`tsc -b && vite build`) still passes with the new test files and
config present. The test-plan §6.4 cookbook and §6.6 per-phase notes are filled
in. No CI workflow file is touched.

### Key Discoveries:

- The highest-signal code in the layer is `api-client.ts:43-61` (the
  401→`refreshOnce`→retry→`AuthError` path), not the fetchers — confirming the
  decision to keep the transport **in scope**.
- `listEntries` (`cabinet-api.ts:141-156`) is the densest URL builder and the
  most valuable single fetcher target: 8 optional params, and `below_minimum`
  is serialized as the literal string `"true"` only when truthy.
- `apiJson` throws the **`Response` object itself** (`api-client.ts:72`), a
  contract `query-client.ts:10` depends on — assert the thrown value is a
  `Response` with the right `.status`, not a message string.
- `refreshOnce` (`api-client.ts:22-27`) uses `refreshing ??= …` with a
  `.finally` reset — a single-flight latch that must be reset between tests to
  avoid cross-test leakage.

## What We're NOT Doing

- **No CI wiring.** The frontend-unit job in `.github/workflows/ci-cd.yml` is
  test-plan **Phase 4**. This phase stops at local `npm test` scripts.
- **No component / presentational tests.** No RTL rendering, snapshots, or DOM
  assertions of components (test-plan §7). RTL packages are installed so the
  *next* phase needs no re-bootstrap, but this phase renders nothing.
- **No runtime response-shape / zod validation.** With mocked `fetch` the
  response is whatever we stub, so field-by-field asserts would be tautological;
  real field-shape regressions are integration/e2e's job (test-plan §7).
- **No testing of framework behavior** — TanStack Query hooks/cache, React
  Router, `fetch` internals (test-plan §7). We test *our* logic on top.
- **No changes to the fetchers or transport source** unless a genuine, testable
  defect surfaces — this is an additive test phase.
- **No MSW / network-interception layer.** Decided against; we mock
  `globalThis.fetch` directly.

## Implementation Approach

**Mock `globalThis.fetch` per test** with a `vi.fn()`, seed its resolved value
with a small `Response` factory, and assert on `fetch.mock.calls` for the
request side. Environment is **jsdom** (supplies `localStorage`, `Headers`,
`fetch` globals the transport relies on). Config goes in a **`test` block in
`vite.config.ts`** (per `AGENTS.md`), sharing the `@/` alias. Test files are
**colocated** as `*.test.ts` next to their source
(`src/lib/api-client.test.ts`, `src/features/cabinet/api/cabinet-api.test.ts`,
etc.).

A tiny per-suite **URL-assertion helper** strips the computed `BASE` prefix so
URL expectations read as paths (`/cabinet/entries?status=valid`) rather than
absolute URLs — keeping the string-based assertions legible. The auth store's
token accessors (`getStoredToken`/`setStoredToken`) are controlled per test
(seed via `localStorage` under the jsdom env, or `vi.mock` the store module) so
transport tests are isolated from store internals.

## Critical Implementation Details

- **`tsc -b` must stay green with test files present.** `npm run build` runs
  `tsc -b`, which will now see `*.test.ts` files and the Vitest globals. Either
  add `"vitest/globals"` + `"@testing-library/jest-dom"` to the `types` array of
  the compilation that covers `src/`, or scope test files to their own tsconfig.
  Verify `npm run build` passes as an explicit success criterion — a broken
  build is the most likely bootstrap regression.
- **Reset global state between tests.** The `refreshing` single-flight latch in
  `api-client.ts` persists across calls within a module load; `localStorage`
  persists across tests under jsdom. Use `afterEach` (in `src/test/setup.ts` or
  per-suite) to restore mocks and clear `localStorage`. **Latch-reset
  mechanism**: the `refreshing` latch (`api-client.ts:7`) has no exported reset
  hook and `afterEach` does not clear it — it only self-resets via `.finally`
  when the refresh promise settles (`api-client.ts:23-25`). Therefore **every
  refresh `fetch` mock must resolve (not reject or hang)** so `.finally` fires
  and clears the latch before the next test; a rejecting/never-resolving mock
  would leak the latch and mask a bug. For the failed-refresh case, resolve the
  refresh `fetch` with a non-`ok` `Response` so `refreshOnce` returns `null` and
  `.finally` still runs — don't reject the fetch.
- **`BASE` is fixed at import time from `import.meta.env.VITE_API_URL`.** Do not
  try to vary it mid-suite; assert against the resolved default
  (`http://localhost:8000/api/v1`) via the path-stripping helper.
- **Vitest and Playwright must not collide.** Ensure the Vitest `include`
  targets `src/**/*.test.ts` (or the default) and does **not** pick up
  `e2e/**/*.spec.ts`; Playwright already owns the `.spec.ts` extension under
  `e2e/`.

## Phase 1: Bootstrap Vitest Runner

### Overview

Stand up Vitest with the jsdom environment, the RTL base, a shared setup file,
tsconfig types, and npm scripts — proven by a single smoke test. No seam logic
is tested yet; this phase exists to make the runner real and keep `tsc -b` green.

### Changes Required:

#### 1. Test dependencies

**File**: `frontend/package.json`

**Intent**: Add the Vitest runner and the RTL base so this phase (and the next
component phase) run without a second bootstrap.

**Contract**: New devDependencies — `vitest`, `jsdom`,
`@testing-library/jest-dom`, `@testing-library/react`,
`@testing-library/user-event` — at versions compatible with Vite 8 / React 19
(RTL React adapter must support React 19). New scripts: `"test": "vitest"` and
`"test:run": "vitest run"`. `@testing-library/react`/`user-event` are installed
but unused this phase (no component tests) — they complete the runner per
`AGENTS.md` line 121.

**Peer-resolution contingency (Vite 8 is bleeding-edge)**: Vitest bundles its
own Vite dependency and declares a supported Vite peer range. If `npm install`
fails peer resolution against `vite ^8.0.12` — or the runner misbehaves — pin a
Vitest version whose peer range includes Vite 8, or add an npm `overrides` entry
to reconcile the bundled Vite. The RTL-for-React-19 adapter pin is a second
unverified version in the same install; resolve it the same way. Record the
resolved `vitest` / RTL / jsdom versions in the §6.6 per-phase note.
**Checkpoint**: treat "the runner starts and the smoke test passes against Vite
8" (criterion 1.2) as the explicit gate that this compatibility holds — do not
proceed past Phase 1 until it does.

#### 2. Vitest config

**File**: `frontend/vite.config.ts`

**Intent**: Add a `test` block so Vitest shares the existing build config and
`@/` alias, per `AGENTS.md` line 51.

**Contract**: Prepend a `/// <reference types="vitest/config" />` triple-slash
directive; add a `test` block with `environment: "jsdom"`, `globals: true`,
`setupFiles: ["./src/test/setup.ts"]`, and an `include` that matches
`src/**/*.test.ts(x)` while excluding `e2e/`. Alias resolution is inherited from
the existing `resolve.alias`.

#### 3. Vitest setup file

**File**: `frontend/src/test/setup.ts` (new)

**Intent**: Register jest-dom matchers and a global cleanup so every test starts
from a clean slate.

**Contract**: Import `@testing-library/jest-dom/vitest`; register an `afterEach`
that runs RTL `cleanup()` and clears `localStorage` and mocks
(`vi.restoreAllMocks()` / `localStorage.clear()`). Mirrors `AGENTS.md` line 50
("jest-dom, cleanup").

#### 4. TypeScript types for tests

**File**: `frontend/tsconfig.app.json` (and/or a test-scoped tsconfig)

**Intent**: Make `tsc -b` aware of Vitest globals + jest-dom matchers so the
production build doesn't fail on the new test files.

**Contract**: Add `"vitest/globals"` and `"@testing-library/jest-dom"` to the
relevant `compilerOptions.types` (or include test files via a dedicated
tsconfig). The concrete include/exclude split is the implementer's call as long
as `npm run build` passes and test files are type-checked somewhere.

#### 5. Smoke test

**File**: `frontend/src/test/smoke.test.ts` (new)

**Intent**: Prove the runner, jsdom env, `@/` alias, and jest-dom matchers all
resolve before any real seam test is written.

**Contract**: A trivial test that imports something via the `@/` alias (e.g.
`AuthError` from `@/lib/errors`), asserts a basic truth, and uses a jest-dom
matcher against a jsdom-created element. May be deleted or kept once Phase 2/3
tests exist — keep it minimal.

### Success Criteria:

#### Automated Verification:

- Dependencies install cleanly: `npm install` (from `frontend/`)
- Smoke test passes: `npm run test:run`
- Production build still passes with test files present: `npm run build`
- Lint passes: `npm run lint`
- Format check passes: `npx prettier --check src/`

#### Manual Verification:

- `npm test` (watch mode) starts, runs the smoke test, and watches for changes
- Playwright is unaffected: `npm run e2e -- --list` still enumerates E2E specs
  (Vitest did not swallow `e2e/**/*.spec.ts`)

**Implementation Note**: After completing this phase and all automated
verification passes, pause here for manual confirmation from the human that the
manual testing was successful before proceeding to the next phase.

---

## Phase 2: Transport Tests (`lib/api-client.ts`)

### Overview

Test the highest-signal code in the layer: the auth/refresh/error contract in
`api-client.ts`. Mock `globalThis.fetch`; control the stored token; assert
request headers, the 401→refresh→retry path, the `/auth/` skip, the single-flight
latch, and the exact thrown error shapes.

### Changes Required:

#### 1. Shared test helpers

**File**: `frontend/src/test/api-test-utils.ts` (new)

**Intent**: Provide a `Response` factory and a URL-path-stripping assertion
helper so every transport/fetcher suite reads cleanly.

**Contract**: Export a `jsonResponse(body, { status? })` factory returning a
**real `Response`** (`new Response(JSON.stringify(body), { status })`) — not a
typed stub — so the `throw res` path is thrown as a genuine `Response` and the
`error instanceof Response` predicate `query-client.ts:10` depends on is
exercised faithfully. (Node ≥18/undici supplies a global `Response` under
jsdom.) Also export a helper to extract the path (BASE-stripped) + `RequestInit`
from a `fetch` mock call. No production code imports this. Note: a `Response`
body is single-use — a test that reads `.json()` twice needs a fresh instance.

#### 2. `apiFetch` tests

**File**: `frontend/src/lib/api-client.test.ts` (new)

**Intent**: Pin bearer-attach, the 401 refresh/retry flow, the `/auth/` skip,
and the failed-refresh error.

**Contract**: Cover — (a) attaches `Authorization: Bearer <token>` when a token
is stored, omits it when none; (b) a non-`/auth/` `401` triggers a refresh, and
on success retries the original request once with the **new** token and returns
the retry response; (c) a `401` on a `/auth/`-prefixed path does **not** refresh
(returns the 401 as-is); (d) when refresh returns `null`, `apiFetch` throws
`AuthError` (assert `instanceof AuthError`). Requires stubbing both the main
`fetch` and the `refreshOnce`/refresh `fetch` call.

#### 3. `apiJson` tests

**File**: `frontend/src/lib/api-client.test.ts`

**Intent**: Pin the `!ok`→`throw res` and success→parsed-json contracts.

**Contract**: Cover — (a) on `res.ok`, returns the parsed JSON body typed as `T`;
(b) on `!res.ok`, throws the **raw `Response`** (assert the thrown value is a
`Response`/has `.status`, not a message string) — the contract
`query-client.ts:10` depends on.

#### 4. `refreshOnce` single-flight test

**File**: `frontend/src/lib/api-client.test.ts`

**Intent**: Prove concurrent callers share one in-flight refresh.

**Contract**: Two concurrent `refreshOnce()` calls issue exactly **one** refresh
`fetch`; after settlement the latch resets so a subsequent call issues a fresh
`fetch`. Assert `fetch` call count. Ensure the latch is reset between tests by
having **both** concurrent refresh mocks resolve so the shared promise's
`.finally` fires and clears `refreshing` before the next test (a rejecting or
never-resolving mock would leak the latch — see Critical Implementation
Details); this is what makes the "subsequent call issues a fresh `fetch`"
assertion meaningful.

### Success Criteria:

#### Automated Verification:

- Transport suite passes: `npm run test:run`
- Build still passes: `npm run build`
- Lint passes: `npm run lint`

#### Manual Verification:

- Temporarily breaking the `/auth/` skip guard or the `throw res` line makes the
  corresponding test fail (a quick mutation sanity check that the tests bite)

**Implementation Note**: After completing this phase and all automated
verification passes, pause here for manual confirmation from the human before
proceeding.

---

## Phase 3: Feature Fetcher Tests + Cookbook

### Overview

Test the three feature fetcher modules for request shape and error propagation,
then fill in the test-plan §6.4 cookbook and §6.6 per-phase notes so the next
contributor has a canonical pattern.

### Changes Required:

#### 1. Cabinet fetcher tests

**File**: `frontend/src/features/cabinet/api/cabinet-api.test.ts` (new)

**Intent**: Pin the densest URL-building and the POST/PATCH/DELETE request
shapes — the hot-spot module.

**Contract**: Cover — `searchProducts` (`encodeURIComponent` of the search
term); `listVariants` (includes `strength`/`form` only when non-null); `listEntries`
(each optional param appears only when set; `below_minimum` serialized as
`"true"`; empty params → no `?`); `addEntry`/`toggleImportant`/`setUsage`/
`updateQuantity` (method, `Content-Type: application/json`, JSON-stringified
body, correct path incl. `id`); `deleteEntry` (DELETE via `apiFetch`, throws the
raw `res` on `!ok`, returns void on ok). Happy-path returns are asserted as
pass-through of the stubbed body with one representative fixture — no field-by-
field mapping asserts.

#### 2. Auth fetcher tests

**File**: `frontend/src/features/auth/api/auth-api.test.ts` (new)

**Intent**: Pin the auth entry fetchers the critical journey depends on.

**Contract**: Cover — `register`/`login` (POST to correct path, JSON body,
returns parsed `AuthResponse`); `logout` (POST via `apiFetch`, no throw on ok);
`getMe` (GET `/auth/me`, returns `AuthUser`).

#### 3. Settings fetcher tests

**File**: `frontend/src/features/settings/api/settings-api.test.ts` (new)

**Intent**: Complete uniform coverage across all existing `api/` modules.

**Contract**: Cover — `getPreferences` (GET `/users/preferences`);
`updatePreferences` (PATCH, JSON body, returns `UserPreferences`).

#### 4. Fill the cookbook and per-phase notes

**File**: `context/foundation/test-plan.md`

**Intent**: Replace the §6.4 TBD with the concrete pattern this phase
established, and append a §6.6 note capturing anything surprising.

**Contract**: §6.4 documents location (`*.test.ts` colocated), the
mock-`globalThis.fetch` + jsdom pattern, the `Response` factory / path helper,
the request-shape + error-contract assertion style, and `npm run test:run` to
run. §6.6 gets a "Phase 3" entry (e.g. the `tsc -b` types gotcha, the
single-flight latch reset, the `below_minimum` string-`"true"` edge). Optionally
update §3 Phase 3 Status and §4 frontend-unit row to reflect completion.

### Success Criteria:

#### Automated Verification:

- Full suite passes: `npm run test:run`
- Build passes: `npm run build`
- Lint passes: `npm run lint`
- Format check passes: `npx prettier --check src/`

#### Manual Verification:

- Cookbook §6.4 reads as a followable recipe — a contributor could add a fetcher
  test for a new feature from it alone
- Suite runtime is fast (well under a few seconds) — confirms the "cheap" intent

**Implementation Note**: After completing this phase and all automated
verification passes, pause here for manual confirmation from the human. This is
the final phase — on confirmation the change can be closed out.

---

## Testing Strategy

### Unit Tests:

- **Transport** (`api-client.ts`): header attach, 401→refresh→retry, `/auth/`
  skip, failed-refresh `AuthError`, `apiJson` `throw res` vs parsed body,
  `refreshOnce` single-flight.
- **Fetchers** (cabinet/auth/settings): exact URL + query string, method,
  headers, JSON body; `deleteEntry` throw-on-`!ok`; happy-path pass-through.
- **Edge cases**: `encodeURIComponent`, all-optional-params-empty (no `?`),
  `below_minimum` → `"true"`, null `strength`/`form` omitted, retry uses the new
  token.

### Integration Tests:

- None added here. The real backend contract is covered by test-plan Phase 1
  (backend integration) and Phase 2 (E2E). This phase deliberately stops at the
  unit seam (test-plan §7).

### Manual Testing Steps:

1. `cd frontend && npm install && npm run test:run` — full suite green.
2. `npm run build` — production build passes with test files present.
3. `npm test` — watch mode runs and re-runs on edit.
4. Mutation sanity: temporarily break `throw res` (return instead) → the
   corresponding `apiJson` test fails; revert.
5. `npm run e2e -- --list` — Playwright still enumerates E2E specs (no collision).

## Performance Considerations

The suite mocks `fetch` and renders nothing, so it should complete in well under
a few seconds — matching the "cheapest test that gives a real signal" strategy
(test-plan §1). jsdom adds minor startup cost over node, accepted for
`localStorage`/`Headers` convenience and forward-compatibility with the later
component phase.

## Migration Notes

No data or runtime migration. Purely additive: new dev dependencies, config
block, setup file, and test files. No production source changes expected unless a
genuine defect surfaces during test-writing (surface it rather than encoding the
bug into an oracle).

## References

- Change identity: `context/changes/frontend-data-seam-tests/change.md`
- Frozen test strategy: `context/foundation/test-plan.md` (§3 Phase 3, §6.4,
  Risks #1/#2 in §2)
- Frontend structure rules: `AGENTS.md` lines 80–121; `docs/reference/frontend-structure.md`
- Transport under test: `frontend/src/lib/api-client.ts`
- Error contract consumers: `frontend/src/lib/query-client.ts:7-14`,
  `frontend/src/features/auth/store.ts`
- Hottest fetcher: `frontend/src/features/cabinet/api/cabinet-api.ts:141-199`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step
> lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Bootstrap Vitest Runner

#### Automated

- [x] 1.1 Dependencies install cleanly: `npm install` — feb65ab
- [x] 1.2 Smoke test passes: `npm run test:run` — feb65ab
- [x] 1.3 Production build passes with test files present: `npm run build` — feb65ab
- [x] 1.4 Lint passes: `npm run lint` — feb65ab
- [x] 1.5 Format check passes: `npx prettier --check src/` — feb65ab

#### Manual

- [x] 1.6 `npm test` watch mode runs the smoke test — feb65ab
- [x] 1.7 Playwright unaffected: `npm run e2e -- --list` enumerates E2E specs — feb65ab

### Phase 2: Transport Tests (`lib/api-client.ts`)

#### Automated

- [x] 2.1 Transport suite passes: `npm run test:run` — 5915d08
- [x] 2.2 Build still passes: `npm run build` — 5915d08
- [x] 2.3 Lint passes: `npm run lint` — 5915d08

#### Manual

- [x] 2.4 Mutation sanity: breaking `/auth/` skip or `throw res` fails a test — 5915d08

### Phase 3: Feature Fetcher Tests + Cookbook

#### Automated

- [x] 3.1 Full suite passes: `npm run test:run` — 0e9efad
- [x] 3.2 Build passes: `npm run build` — 0e9efad
- [x] 3.3 Lint passes: `npm run lint` — 0e9efad
- [x] 3.4 Format check passes: `npx prettier --check src/` — 0e9efad

#### Manual

- [x] 3.5 Cookbook §6.4 reads as a followable recipe — 0e9efad
- [x] 3.6 Suite runtime is fast (under a few seconds) — 0e9efad

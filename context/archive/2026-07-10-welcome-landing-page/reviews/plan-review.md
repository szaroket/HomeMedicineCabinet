<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Welcome Landing Page (S-10)

- **Plan**: context/changes/welcome-landing-page/plan.md
- **Mode**: Deep
- **Date**: 2026-07-10
- **Verdict**: REVISE → SOUND (all findings fixed in plan, 2026-07-10)
- **Findings**: 1 critical, 2 warnings, 0 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | FAIL |
| Plan Completeness | WARNING |

## Grounding

14/14 paths ✓, symbols ✓ (useAuth/token/TOP_NAV/Navigate), brief↔plan ✓, Progress↔Phase ✓ (well-formed: one `## Progress`, phases and success-criteria bullets all mapped 1.1–1.5, 2.1–2.10).

## Findings

### F1 — `/`-reference inventory misses auth.setup.ts; breaks the whole E2E suite

- **Severity**: ❌ CRITICAL
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: "Current State Analysis" §Every `/`-reference (plan:21-29); Phase 2 #7 (E2E)
- **Detail**: The section titled "Every `/`-reference that must change when the dashboard moves to `/dashboard`" lists 7 references but misses `frontend/e2e/auth.setup.ts:75` — `await page.waitForURL("/")` after the post-login redirect. This is the shared `setup` project that every `chromium` test depends on (`playwright.config.ts:39,47` via `dependencies: ['setup']`). Once login navigates to `/dashboard` (Phase 2 #3), the post-login URL becomes `/dashboard`, `waitForURL("/")` times out, the setup fails, and the ENTIRE E2E suite fails — including the new `welcome-landing.spec.ts`. Success criterion 2.5 ("E2E passes") is unreachable as written. Line 76-78's `getByRole(link, "Apteczka")` assertion still holds on the dashboard, so only line 75 needs to move.
- **Fix**: Add `e2e/auth.setup.ts:75` to the Phase-2 inventory: change `waitForURL("/")` → `waitForURL("/dashboard")`. Update the section so the reference count is 8, not 7 (or retitle it so the E2E setup is clearly in scope).
- **Decision**: FIXED (added auth.setup.ts:75 to inventory + Phase 2 #6; count bumped to 8)

### F2 — Two unit-test updates are under-specified; `vitest run` (2.4) will fail

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 2 #6 (Update affected tests)
- **Detail**: Phase 2 #6 updates only the sidebar href assertion and explicitly clears `not-found-page.test.tsx`, but two required test updates are missing:
  - (a) `app-sidebar.test.tsx:9,16` — test 1 renders with `initialEntries={["/"]}` and asserts `aria-current="page"` (active). With the link changed to `/dashboard` + `end: true`, it is NOT active at `/`, so line 16 fails. The plan patches line 15's href but leaves `initialEntries` (and the stale test-name string "link to / and marks it active") untouched.
  - (b) `account-deleted-page.test.tsx:15,58` — the test stubs `<Route path="/" element={<div>Dashboard</div>} />` and asserts `getByText("Dashboard")` after the authed redirect. Phase 2 #4 changes the component's `<Navigate to="/">` → `/dashboard`, so the redirect no longer matches the stub route and "Dashboard" never renders — the test fails. The plan mentions #4's component edit but never lists this test.
- **Fix**: In #6, add both: sidebar test — change `initialEntries={["/"]}` → `["/dashboard"]` (and refresh the test-name string); account-deleted test — change the stub `<Route path="/">` → `path="/dashboard"`. Both are required for criterion 2.4 to pass.
- **Decision**: FIXED (Phase 2 #6 expanded with both test files and all three sidebar touch-points)

### F3 — E2E's unauthenticated cases need an explicit storageState override

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Plan Completeness
- **Location**: Phase 2 #7 (E2E: landing and redirect flows)
- **Detail**: The plan says "keep the unauthenticated cases in a context without stored auth" but gives no mechanism. `playwright.config.ts:44` sets `storageState: 'e2e/.auth/user.json'` at the chromium PROJECT level, so every test is authenticated by default. A naive `page.goto("/")` in the new spec would arrive logged-in, hit the new PublicLayout guard, and redirect to `/dashboard` — so the "unauthenticated `/` shows welcome" and "`/dashboard`→`/login`" scenarios would silently test the wrong path (or fail confusingly) instead of the logged-out behaviour. Two of the four promised E2E scenarios are affected.
- **Fix**: Specify the override in #7 — the unauthenticated tests must opt out of the project storageState, e.g. `test.use({ storageState: { cookies: [], origins: [] } })` on a describe block, with the authed cases in a separate block using the default state.
  - Strength: Makes the two logged-out scenarios real; matches how Playwright scopes per-test auth against a project-wide storageState default.
  - Tradeoff: Splits the spec into two `describe` blocks by auth state — slightly more structure.
  - Confidence: HIGH — config applies storageState project-wide (playwright.config.ts:42-48); no per-test override exists in current specs.
  - Blind spot: Haven't confirmed the empty-storageState context also clears the backend-set refresh-token cookie; worth a quick check when writing the spec.
- **Decision**: FIXED (Phase 2 #7 now specifies the two-describe-block split, the storageState override, and the refresh-cookie check)

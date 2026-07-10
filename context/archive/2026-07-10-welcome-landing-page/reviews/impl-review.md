<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Welcome Landing Page (S-10)

- **Plan**: context/changes/welcome-landing-page/plan.md
- **Scope**: Phases 1–2 of 2 (full plan)
- **Date**: 2026-07-10
- **Verdict**: APPROVED
- **Findings**: 0 critical, 0 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS (2 deviations, both documented in plan) |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

## Automated verification (re-run this review)

- `npm run build` — PASS (pre-existing >500 kB chunk-size warning, unrelated to this change)
- `npm run lint` — PASS
- `npx prettier --check src/` — PASS
- `npx vitest run` — PASS (19 files, 75 tests)
- `npx playwright test welcome-landing` — NOT re-run here; requires native PowerShell + Supabase TLS (lessons L-001). Marked green in plan Progress at cd8c612.

## Findings

### F1 — E2E spec omits the plan's "post-login → /dashboard" scenario

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: frontend/e2e/welcome-landing.spec.ts:48-55
- **Detail**: Phase 2 #7 lists four scenarios for the new spec; three are present (unauth `/` + CTA→/register, unauth `/dashboard`→`/`, authed `/`→/dashboard). The fourth — "post-login lands on /dashboard" — is not in this file. It is exercised by the shared setup project (auth.setup.ts:75 asserts `waitForURL("/dashboard")` after a real UI login), which every chromium test depends on, so the risk is protected; it just lives in a different file than the plan implied.
- **Fix**: Leave as-is (coverage exists in auth.setup.ts) — or add a one-line authed-block case navigating login→/dashboard if you want the spec self-describing against the plan contract.
- **Decision**: FIXED — added an authed `/login → /dashboard` case to welcome-landing.spec.ts (respects the e2e CLAUDE.md "no UI login inside a test" rule; documents the login-route redirect contract the spec docstring already claims).

### F2 — Desktop reading order differs from visual order on welcome page

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality (a11y)
- **Location**: frontend/src/features/landing/components/welcome-page.tsx:58,73
- **Detail**: CTAs use `order-2 sm:order-3`; highlights use `order-3 sm:order-2`. On desktop the cards render visually above the CTAs, but DOM order (heading → paragraph → CTAs → cards) puts CTAs first, so the screen-reader reading sequence is CTAs-before-cards while the visual sequence is cards-before-CTAs (WCAG 1.3.2 nuance). Practical impact is near-zero: the highlight cards contain no focusable elements, so keyboard tab-order is unaffected — the only interactive items are the two CTA links.
- **Fix**: Optional. If you want DOM to match desktop visual order, place the highlights block before the CTAs in JSX and drop the `order-*` swap. Manual check 2.10 already passed, so this is polish, not a defect.
- **Decision**: SKIPPED — near-zero impact (no focusable elements in highlights; manual a11y check 2.10 passed).

## Notes

- Both behavioral deviations (`ProtectedLayout` unauth redirect `/login`→`/`; account-deleted "Powrót" `/login`→`/`) are recorded in the plan's "Deviations from plan" section and were approved during Phase 2 manual verification — no undocumented scope creep.
- All eight `/`-references enumerated in the plan were rewired; both auth forms navigate to `/dashboard`; `PublicLayout` guard mirrors `ProtectedLayout` (token-only, no `useSessionInit`) per Critical Implementation Details.

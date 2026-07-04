<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: SPA Refresh Fallback

- **Plan**: context/changes/spa-refresh-fallback/plan.md
- **Scope**: Phase 1 + 2 (all implemented; live checks 1.5/1.6 pending by design)
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
| Success Criteria | PASS (2 live-only checks pending, expected) |

## Verification Notes

- All 5 planned files changed, no unplanned code: `render.yaml` (rewrite `/* → /index.html`, `type: rewrite` not redirect), `context/foundation/infrastructure.md` (dashboard-fallback note), `frontend/src/app/components/not-found-page.tsx`, top-level `*` route in `frontend/src/app/router.tsx`, and `not-found-page.test.tsx`.
- Architecture matches plan reasoning: catch-all is a top-level sibling outside `ProtectedLayout` (no auth-gate redirect for 404s); `NotFoundPage` avoids `AppLayout` to sidestep the auth-coupled `LogoutButton` (`app-layout.tsx:6,43`).
- Scope guardrails respected: no HashRouter, no `errorElement`, no backend/API/auth changes.
- Automated criteria: `test:run` 35/35 pass, `typecheck` clean, `lint` clean, `build` succeeds. `render.yaml` YAML-parse not runnable in this env (no parser installed); block is correctly nested and build passed.
- Known MIME/stale-asset tradeoff (deleted hashed asset → `index.html` at 200) is documented and accepted in plan lines 66–70; not a new finding.
- Manual checks 1.5 (live Render deep-route refresh) and 1.6 (dashboard rewrite confirmed) are genuinely post-deploy and correctly left unchecked.

## Findings

### F1 — 404 page has no `<main>` landmark

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: frontend/src/app/components/not-found-page.tsx:5
- **Detail**: `NotFoundPage` is a standalone shell (correctly avoids `AppLayout` to dodge the auth-coupled `LogoutButton`), but its root is a bare `<div>`. `AppLayout` wraps page content in a semantic `<main>` (`app-layout.tsx:50`). This repo is a11y-conscious (getByRole-first locators, L-locator lesson), so a page with no landmark region is a small inconsistency. The `<h1>` is fine; only the landmark is missing.
- **Fix**: Change the outer `<div>` to `<main>` (or wrap content in one) so the standalone page still exposes a main landmark. Purely additive; no test or class changes needed.
- **Decision**: FIXED (2026-07-04) — changed outer `<div>` to `<main>`

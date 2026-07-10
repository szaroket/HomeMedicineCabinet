<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Dashboard Implementation Plan

- **Plan**: context/changes/dashboard/plan.md
- **Scope**: Phase 2 of 4 (Frontend dashboard data layer)
- **Date**: 2026-07-10
- **Verdict**: APPROVED
- **Findings**: 0 critical 0 warnings 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

## What Went Right

- All three planned changes match intent. `dashboard-api.ts` and `dashboard-queries.ts` mirror the cabinet feature's fetcher/query-key style; the frontend `CabinetSummaryOut` interface matches the backend schema field-for-field (`total, valid, expiring, expired, out_of_stock`).
- Invalidation landed on all five mutations (`useAddEntry`, `useToggleImportant`, `useSetUsage`, `useDeleteEntry`, `useUpdateQuantity`), and improved on the plan: instead of five literal `["cabinet","summary"]` copies, it extracted one `DASHBOARD_SUMMARY_KEY` constant with the sync comment — fewer copies to drift.
- Dependency direction respected — cabinet-queries invalidates the literal key and does not import `dashboardKeys` from the dashboard feature, exactly as the plan's architecture guard required.
- Automated criteria verified green: lint clean, `tsc -b` clean, 4/4 dashboard-api tests pass. The remaining unchecked item (2.4) is manual and correctly left pending.

## Findings

### F1 — Summary-key invalidation has no automated regression guard

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: frontend/src/features/cabinet/api/cabinet-queries.ts:69
- **Detail**: The dashboard summary key exists as two hand-synced literals: `dashboardKeys.summary()` (source of truth, dashboard-queries.ts:5) and `DASHBOARD_SUMMARY_KEY` (cabinet-queries.ts:69). If the dashboard key ever changes, the cabinet-side constant drifts silently and mutations stop refreshing the counts — with no test to catch it. Phase 2's tests cover the fetcher path/parse and the hook's success/error, but not the mutation→invalidation wiring; that seam is only guarded by the manual check 2.4. This matches the plan (it specified data-seam tests + manual verification and explicitly accepted the two-copy drift risk with a comment), so it is aligned with plan intent, not drift — just an inherent coverage gap.
- **Fix**: Optionally add a small test asserting one cabinet mutation's `onSuccess` invalidates `["cabinet","summary"]` (spy on `queryClient.invalidateQueries`), or defer to the manual 2.4 check as the plan allows.
- **Decision**: FIXED — added `frontend/src/features/cabinet/api/cabinet-queries.test.tsx` asserting `useAddEntry`'s `onSuccess` invalidates `dashboardKeys.summary()` (comparing against the dashboard source-of-truth key, so drift in either literal fails the test). Green: test passes, `tsc -b` and lint clean.

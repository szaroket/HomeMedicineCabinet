<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Notifications and Badges (S-06)

- **Plan**: context/changes/notifications-and-badges/plan.md
- **Scope**: Phase 8 of 8
- **Date**: 2026-07-09
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 2 warnings, 0 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | WARNING |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

Automated criteria — all green:
- 8.1 notification-bell.test.tsx: 7 passed (incl. row-click navigates + dismiss-does-not-navigate)
- 8.2 build (tsc + vite) ok; eslint clean; prettier clean

## Findings

### F1 — Trigger-specific filter navigation exceeds the plan and is untested

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Scope Discipline
- **Location**: frontend/src/features/notifications/components/notification-panel.tsx:21-46, 149-156
- **Detail**: The plan's Phase 8 contract specified a bare name match: `navigate(\`/cabinet?search=${encodeURIComponent(item.medication_name)}\`)`. The implementation instead adds `triggerFilterParams()`, which appends a trigger-specific filter alongside the name search — `status=expired/expiring` for `expiry`, `below_minimum=true` for `below_minimum`, `sufficiency=insufficient` for `run_out`. This is a genuine UX improvement (excludes same-name healthy packages). Verified: all three params are consumed by cabinet-page.tsx:56-67, and the expired/expiring split matches `classify_status`'s boundary (EXPIRED only when `expiry_date < today` ⇔ `days_remaining < 0`). BUT the row-click test (notification-bell.test.tsx:140) only asserts navigation happened ("Cabinet page" renders) and the panel closed — it never asserts the query string. The entire added branching (the actual value of this phase) has zero direct coverage; a wrong param would silently land the user on an empty filtered list.
- **Fix**: Strengthen the existing row-click test to assert the destination URL/params (e.g. render a `/cabinet` route that echoes `useSearchParams`, or assert `location.search` contains `search=Apap&status=expiring`), and add one case per `trigger_type` so each branch of `triggerFilterParams` is exercised.
- **Decision**: FIXED — added a `CabinetEcho` route that echoes `useSearchParams`; strengthened the row-click test to assert `search=Apap&status=expiring`; added an `it.each` block covering all four branches (expiring, expired, below_minimum, run_out). notification-bell.test.tsx now 11 passed.

### F2 — Unplanned cabinet-page.tsx URL-race fix, no regression test

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Scope Discipline
- **Location**: frontend/src/features/cabinet/components/cabinet-page.tsx:88-99
- **Detail**: Phase 8's stated scope names one file (notification-panel.tsx) and says "No backend change" — it did not anticipate touching the cabinet feature. The commit adds a `pendingSearch` guard to cabinet-page.tsx to fix a race: on an externally-set `search` param (a notification click), `debouncedSearch` lagged one render behind `searchInput`, so the sync effect briefly deleted the just-navigated `search` param and restored it ~400ms later. The fix is correct and arguably necessary (without it the new navigation flickers); traced branches (normal typing, clear, sub-MIN_SEARCH_LEN input) still behave. But: (1) it is scope creep into another feature's file, and (2) unlike the Phase-6 panel-scroll fix (which got a jsdom regression test), this subtle debounce-timing fix ships with no test — a future refactor of the search/debounce logic could silently reintroduce the flicker.
- **Fix A ⭐ Recommended**: Keep the fix; add a plan addendum (matching the Phase-6 F1/F4 and Phase-7 F2 addenda) documenting the cabinet-page race fix as discovered scope, and add a cabinet-page test that navigates in with `?search=X` and asserts the param survives the first debounce window (isn't deleted).
  - Strength: Preserves a necessary fix; matches how prior discovered scope was handled here; closes the regression-risk gap.
  - Tradeoff: Plan keeps accreting addenda; the timing test needs fake timers to be deterministic.
  - Confidence: HIGH — addendum pattern already used three times in this change.
  - Blind spot: A fake-timer test for debounce races can be flaky if not carefully written.
- **Fix B**: Document via addendum only, skip the test.
  - Strength: Minimal effort; the fix is already manually verified.
  - Tradeoff: Leaves the reintroduction risk uncovered by CI.
  - Confidence: MED — fine short-term, weaker as the file evolves.
  - Blind spot: No CI signal if the race returns.
- **Decision**: FIXED via Fix A — added a Phase-8 addendum (plan.md, "from impl-review-phase-8 F1/F2") documenting the row-filter narrowing and the cabinet-page race fix as discovered scope; added `cabinet-page.test.tsx` (fake-timer regression test) that navigates in with `?search=Apap` and asserts the param survives the flush + debounce window. Verified the test fails when the `pendingSearch` guard is removed.

<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Important Category

- **Plan**: context/changes/important-category/plan.md
- **Scope**: Phase 7 of 7
- **Date**: 2026-06-16
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 2 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | WARNING |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

Success criteria checked live: `npm run lint` (clean), `npm run build` (built),
`uv run pytest tests/cabinet` (125 passed). Phase 7 Progress 7.1–7.7 all `[x]`.

## Findings

### F1 — Unplanned backend `below_minimum` filter + "Zapasy" stock dropdown

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Scope Discipline
- **Location**: backend/app/api/v1/cabinet/crud.py:142,187 (+ facade.py:56, router.py:61, service.py:258, schemas.py:42); frontend cabinet-page.tsx STOCK_OPTIONS
- **Detail**: Phase 7 is scoped frontend-only (plan.md:426–472), consuming Phase 3–5 endpoints; the only filter named for this phase is the category select. The commit added a new `below_minimum` query-filter chain through schemas → router → facade → service → crud (new SQL WHERE branch) plus a third frontend "Zapasy" stock dropdown. Real backend feature work inside a frontend phase, and — unlike Phases 2/3/5/6 — not recorded as a plan addendum. The planned category filter itself is implemented correctly.
- **Fix A ⭐ Recommended**: Keep the feature; add a Phase 7 plan addendum documenting the `below_minimum` filter + stock dropdown (mirroring existing addenda).
  - Strength: Preserves working, useful code; restores plan as ground truth; matches how prior drift was handled.
  - Tradeoff: Plan keeps absorbing scope; the frontend-only boundary is softened retroactively.
  - Confidence: HIGH — addendum pattern established across this plan.
  - Blind spot: Pairs with F2 — documenting it does not test it.
- **Fix B**: Revert the backend `below_minimum` chain; drive the stock filter client-side or defer to a follow-up.
  - Strength: Restores frontend-only boundary; removes an untested SQL branch.
  - Tradeoff: Loses shipped functionality; client-side filtering breaks with pagination (below-minimum entries on later pages hidden).
  - Confidence: MEDIUM — pagination interaction makes client-side a real regression risk.
  - Blind spot: Haven't checked whether the UI depends on the server filter for correct paging.
- **Decision**: FIXED via Fix A — Phase 7 plan addendum added (plan.md, after §5)

### F2 — New `below_minimum` SQL filter shipped with no test coverage

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/app/api/v1/cabinet/crud.py:187–189
- **Detail**: `grep below_minimum backend/tests/` returns nothing. The new branch `if below_minimum and min_package_count is not None:` adds two WHERE clauses (`is_important IS TRUE AND package_count < min_package_count`) with zero tests. Phase 3 set the precedent of endpoint-testing each filter (`?category=important` filters; invalid → 422, plan.md:227); the equivalent for `?below_minimum=true` is absent. Phase 7's success criteria are frontend-only (build + lint), so nothing gated this logic. The guard also silently no-ops when `min_package_count` is None — untested. Wider cabinet suite passes (125) but none exercise this path.
- **Fix**: Add a parametrized endpoint test in tests/cabinet/test_router.py asserting `?below_minimum=true` returns only important entries under the minimum, plus a crud/service test for the None-guard no-op — following the Phase 3 category-filter test shape.
  - Strength: Closes the one untested branch this phase introduced; reuses existing `authed_client` + mocked-session pattern.
  - Tradeoff: Small effort; needs a fixture with a known below-minimum entry.
  - Confidence: HIGH — same harness already covers the category filter.
  - Blind spot: None significant.
- **Decision**: FIXED — added crud `_build_base_query` parametrized test (active clause + None-guard/off no-ops) in test_crud.py and `?below_minimum=true`/default forwarding tests in test_router.py; 6 new tests pass.

### F3 — Below-minimum rule duplicated in SQL and in the pure function

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Architecture
- **Location**: backend/app/api/v1/cabinet/crud.py:187–189 vs. cabinet/service.py `is_below_minimum` (Phase 3)
- **Detail**: The plan named `is_below_minimum()` as the single source of truth for the out-of-stock signal (plan.md:166–172). The new SQL filter re-encodes the same rule (`is_important AND count < min`) in a second place. They agree today, but a future rule change (e.g. `<=`) must be made in both or the row badge and the filter will disagree.
- **Fix**: Leave as-is (SQL can't call the Python predicate per-row in a filtered query); add a code comment in crud linking the two so the coupling is visible.
- **Decision**: FIXED — added a comment in crud.py linking the SQL filter to service.is_below_minimum and noting they must change together.

### F4 — Unplanned status-label rename "Ważny" → "Aktualny"

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: frontend cabinet-list.tsx:49, cabinet-page.tsx:14
- **Detail**: The `valid` expiry status label changed from "Ważny" to "Aktualny" in both list and filter dropdown. Not in the plan, but a sensible disambiguation — "Ważny" (valid) would otherwise collide with the new "Ważne" (important) category. Benign UI copy change.
- **Fix**: None needed — keep. Mention in the F1 plan addendum if writing one.
- **Decision**: FIXED (kept) — recorded in the Phase 7 plan addendum alongside F1.

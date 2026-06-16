<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Cabinet View and Search

- **Plan**: context/changes/cabinet-view-and-search/plan.md
- **Scope**: Phase 4 of 5
- **Date**: 2026-06-16
- **Verdict**: NEEDS ATTENTION (all 4 findings resolved 2026-06-16)
- **Findings**: 0 critical, 3 warnings, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | WARNING |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS (4.9 mobile manual pending) |

## Findings

### F1 — Search box and URL are desynced dual sources of truth

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Plan Adherence
- **Location**: frontend/src/features/cabinet/components/cabinet-page.tsx (search input onChange + searchInput useState init)
- **Detail**: The plan (Phase 4, item 2) says the search input "writes `q` to the URL via the existing use-debounce hook" — i.e. the *debounced* value drives the URL. The implementation instead: (a) writes the RAW value to the URL on every keystroke via `setParam("search", ev.target.value, true)`, while only the API query uses `debouncedSearch`. Because `setSearchParams` defaults to push (not replace), typing "apap" pushes 4 browser history entries — Back steps through each character. (b) initializes `searchInput` from the URL only once (useState initial value), with no effect re-syncing it; browser Back/Forward changes the URL but leaves the input box showing a stale value. Criterion 4.7 (paste-into-new-tab) works because that is a fresh mount; in-app Back/Forward does not.
- **Fix**: Stop writing search on each keystroke. Drive the URL from a `useEffect` on `debouncedSearch` using `setSearchParams(next, { replace: true })`, and either derive the input value from the URL or re-sync `searchInput` when `rawSearch` changes. Matches the plan's debounced-write intent and fixes both Back-button symptoms in one edit.
  - Confidence: HIGH — react-router setSearchParams defaults to push; debounce hook confirmed.
  - Blind spot: None significant.
- **Decision**: FIXED — debounced replace-write to URL + input re-sync effect

### F2 — Unplanned changes to the add-medication flow

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Scope Discipline
- **Location**: frontend/src/features/cabinet/components/add-medication-form.tsx; frontend/src/features/cabinet/components/product-autocomplete.tsx
- **Detail**: Phase 4 is "list controls + URL-driven state." Two files outside that scope were modified in the same commit: add-medication-form gains a `formKey` reset mechanism + `defaultValue={1}` on package_count; product-autocomplete gains a `productLabel()` helper and a scrollable dropdown (maxHeight). Reasonable add-flow UX fixes but unrelated to the cabinet list, undocumented in the plan, and unverified by any Phase 4 success criterion.
- **Fix A ⭐ Recommended**: Document as a Phase 4 addendum in plan.md
  - Strength: Matches how earlier F1/F2/F3 were handled in this same plan (addenda blocks); preserves the work and keeps the plan the source of truth.
  - Tradeoff: Plan absorbs slightly off-topic scope.
  - Confidence: HIGH — addendum pattern already established here.
  - Blind spot: The add-flow changes weren't manually verified under this review.
- **Fix B**: Split into a separate change/commit
  - Strength: Keeps Phase 4 history strictly on-topic.
  - Tradeoff: Rewriting an already-landed commit for benign changes.
  - Confidence: MEDIUM — low payoff for the churn.
  - Blind spot: None significant.
- **Decision**: FIXED via Fix A — Phase 4 addendum added to plan.md

### F3 — Single-letter parameter `p` violates L-005

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: frontend/src/features/cabinet/components/product-autocomplete.tsx (new `function productLabel(p: ProductOut)`)
- **Detail**: Lesson L-005 ("Never use single-letter variable or argument names") is a standing project rule. The newly added `productLabel(p)` helper uses `p`. The same commit *fixed* L-005 in cabinet-list.tsx (`e` → `entry`, `v` → `prev`), so this is an inconsistency introduced alongside a correction. The pre-existing `products.map((p) => …)` is unchanged context but would ideally be renamed too.
- **Fix**: Rename the parameter to `product` (and optionally the map callback) to satisfy L-005.
- **Decision**: FIXED — renamed p→product across productLabel/handleSelect/map; e→event in handleChange

### F4 — parsePage accepts non-integer / out-of-range pages

- **Severity**: 🔎 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: frontend/src/features/cabinet/components/cabinet-page.tsx (parsePage)
- **Detail**: `parsePage` returns `num >= 1 ? num : 1`. A hand-crafted URL like `?page=2.5` passes through as 2.5 and is sent to the backend, which expects an int and returns 422 → generic error state. `?page=999` (beyond total) yields an empty page with Prev enabled but no clamp. Edge-only (controls never produce these).
- **Fix**: `Math.floor` the parsed value and clamp to ≥1.
- **Decision**: FIXED — Math.floor + Number.isFinite + clamp ≥1

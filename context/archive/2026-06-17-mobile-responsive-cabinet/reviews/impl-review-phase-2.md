<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Mobile Responsive Cabinet

- **Plan**: context/changes/mobile-responsive-cabinet/plan.md
- **Scope**: Phase 2 of 3
- **Date**: 2026-06-17
- **Verdict**: APPROVED
- **Findings**: 0 critical, 1 warning, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | WARNING |

Notes: Mobile controls, `FilterSheet`, `Sortowanie` toggle, and FAB all match plan
intent. Filter options correctly extracted into the shared `filter-options.ts` (the
plan suggested this). The sheet reuses the page's `setParam`/`clearFilters` — no
parallel state, exactly as required. Overlay follows the `app-sidebar.tsx` drawer
pattern faithfully. Automated checks (build, lint, prettier) all pass.

## Findings

### F1 — FAB can overlap the still-verbose mobile pagination

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: cabinet-page.tsx:306, 317-323, 325-363
- **Detail**: Criterion 2.7 ("FAB never obscures last card or pagination") is marked
  `[x]`, but only the *scroll area* gets clearance via `pb-20 md:pb-0` (line 306). The
  pagination block (lines 325-363) is a `flex-shrink-0` sibling OUTSIDE that scroll
  area, pinned to the bottom of the column. The FAB is `fixed bottom-6 right-4` (z-30),
  and at phase-2 state the mobile pagination is still the verbose `justify-between` row
  whose right-aligned "Następna →" button sits under the FAB on a ~375px screen. The
  "last card" half of the criterion holds; the "pagination" half is questionable until
  Phase 3 replaces this with compact centered pagination.
- **Fix**: Acknowledge as Phase-3-dependent (the compact centered pagination there
  resolves the overlap), or add interim right/bottom spacing to the mobile pagination
  row. Given Phase 3 is next and explicitly reworks this block, deferring is reasonable
  — just don't treat 2.7 as fully proven yet.
- **Decision**: SKIPPED — deferred to Phase 3, which reworks the mobile pagination block.

### F2 — Mobile search input has no accessible label

- **Severity**: ℹ️ OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: cabinet-page.tsx:185-193
- **Detail**: The desktop search has a `<label>Szukaj</label>` (line 216); the mobile
  one relies on placeholder text only, so it has no accessible name. Dropping the
  visible label on mobile for space is fine, but an `aria-label="Szukaj"` would restore
  the accessible name.
- **Fix**: Add `aria-label="Szukaj"` to the mobile search input.
- **Decision**: SKIPPED

### F3 — Filter sheet: no Esc-close / scroll-lock; clear doesn't close

- **Severity**: ℹ️ OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: filter-sheet.tsx (overlay block)
- **Detail**: The sheet closes via overlay click and ✕ (matches the plan and the
  `app-sidebar.tsx` drawer), but has no Escape-key handler or body scroll-lock — the
  same gap the existing drawer has, so it's consistent, not a regression. Separately,
  "Wyczyść filtry" clears filters but leaves the sheet open. All minor UX polish.
- **Fix**: Optional — add an Escape handler (ideally shared with the drawer) and call
  `setIsOpen(false)` after `clearFilters()`.
- **Decision**: FIXED — added a local Escape-key handler (`useEffect` while open) and
  `setIsOpen(false)` after `clearFilters()`. Body scroll-lock intentionally omitted to
  stay consistent with the `app-sidebar.tsx` drawer (option 1).

## Post-review note — device-found bug (fixed)

Not a plan finding; discovered by the user on a physical phone after deploy. Selecting
a filter in the sheet appeared to flicker the sheet closed/open. Root cause: native
`<select>` controls inside the `position: fixed` bottom sheet trigger the OS picker,
which slides up over the sheet and dismisses on selection. Fixed in commit `2005b53` by
replacing the three native selects with tap-to-select option pills (`FilterGroup`),
keeping the same `setParam` wiring and URL behavior. Confirmed fixed on-device by the
user.

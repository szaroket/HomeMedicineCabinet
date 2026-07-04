<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Manage Cabinet Entry (FR-005)

- **Plan**: context/changes/manage-cabinet-entry/plan.md
- **Scope**: Full plan — Phases 1–5 of 5
- **Date**: 2026-07-03
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 1 warning, 4 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | WARNING |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

Success Criteria note: non-DB automated checks re-run green during this review —
backend `pytest tests/cabinet` (226 passed), `ruff check`/`format` clean, frontend
`npm run lint`/`prettier --check src/`/`npm run build` clean. Integration and E2E
suites are TLS-DB (L-001) and were not re-run here; they are checked complete in
the plan's Progress with commit shas and were covered by prior phase reviews.

## Findings

### F1 — Decrement-to-zero of a categorised tablet entry persists a negative total

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality (data integrity)
- **Location**: frontend/src/features/cabinet/hooks/use-cabinet-entry.ts:197-212; backend/app/api/v1/cabinet/service.py:955-1009 (+ total_tablets:77)
- **Detail**: An important OR used tablet entry at package_count=1 with partial_tablet_count > 0 (opened last pack), when decremented, skips the zero-delete confirm branch (isZeroDeleteCategory = !is_important && !is_used → false) and PATCHes { package_count: 0, partial_tablet_count: entry.partial_tablet_count } (forwards existing partial, lines 207-209). Backend `_validate_and_get_tpp` only range-checks the partial and never cross-checks package_count; `UpdateQuantityRequest` allows package_count >= 0 and validates the partial independently. `total_tablets(0, partial, tpp) = (0-1)*tpp + partial = partial−tpp` → NEGATIVE. A contradictory row (0 packages, >0 loose tablets) is persisted and a negative "Sztuki" count is returned to the UI. Silent — no confirm dialog fires on the categorised branch, no error. This is the mirror of the loose-tablet data-loss case the plan guards on the uncategorised branch; the categorised branch is unguarded.
- **Fix A ⭐ Recommended**: Backend cross-field guard in set_entry_quantity / UpdateQuantityRequest — coerce partial_tablet_count → None (or reject) when package_count == 0.
  - Strength: Closes the raw-API path too, not just the stepper; a 0-pack entry logically has no open package, so partial→None is the correct normalized state. Single source of truth.
  - Tradeoff: A few lines in the service/schema + a unit test; must decide coerce-silently vs. 422-reject (coerce is friendlier here).
  - Confidence: HIGH — total_tablets math and the missing cross-check both confirmed in-file.
  - Blind spot: None significant.
- **Fix B**: Frontend-only — in decrementPackage send partial_tablet_count: nextCount === 0 ? null : entry.partial_tablet_count.
  - Strength: Smallest edit; fixes the only UI path that can reach it.
  - Tradeoff: Leaves the backend accepting the inconsistent state from any direct API caller; defends the symptom, not the invariant.
  - Confidence: MED — correct for the stepper, but not defence-in-depth.
  - Blind spot: Any other future caller of the quantity endpoint.
- **Decision**: FIXED via Fix A — backend cross-field guard coercing partial_tablet_count→None when package_count==0 (service.py set_entry_quantity).

### F2 — ConfirmDialog ships an unplanned `note?` prop

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: frontend/src/components/ui/confirm-dialog.tsx:8,58
- **Detail**: Plan item 6 listed a fixed prop set; the impl adds a `note?` prop that renders the adaptive badge-cleared / loose-tablets Polish copy. Benign and arguably required to satisfy Phase 2/4's adaptive-copy intent, but an addition beyond the stated component contract.
- **Fix**: None needed — accept as a justified addition. Optionally record it in the plan's Phase 2 contract so the primitive's real API is captured.
- **Decision**: FIXED — recorded the `note?` prop in the plan's Phase 2 ConfirmDialog contract (plan.md).

### F3 — Dead InvalidPackageCountError branch in the quantity router

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/app/api/v1/cabinet/router.py:241
- **Detail**: `except (InvalidPackageCountError, InvalidPartialTabletCountError) → 422`. set_entry_quantity never raises InvalidPackageCountError — negatives are rejected by Pydantic (→422) before the handler runs, and 0 is explicitly allowed. Harmless (same 422) but dead/misleading. The plan specified this mapping, so it's a plan-level over-spec, not implementer drift.
- **Fix**: Drop InvalidPackageCountError from that except tuple.
- **Decision**: DISMISSED — attempted the drop, but `tests/cabinet/test_router.py::test_invalid_package_count_returns_422` asserts the InvalidPackageCountError→422 mapping. It is a tested, deliberate defensive contract, not dead code (finding itself admitted "harmless, same 422"). Reverted to keep the mapping and its coverage.

### F4 — E2E locates the package-count cell by column index

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: frontend/e2e/manage-cabinet-entry.spec.ts:248
- **Detail**: `myRow.getByRole("cell").nth(1)` anchors on table column order — mild DOM-structure coupling that e2e/CLAUDE.md discourages. Low-risk inside a table, but a role/label-anchored locator would survive column reordering.
- **Fix**: Anchor the count via an accessible label/text within the row.
- **Decision**: FIXED — added `aria-label="Liczba opakowań"` to the count span (cabinet-list.tsx) and re-anchored the spec on `getByLabel` (a11y-over-testid, not DOM index).

### F5 — No user-visible error on a failed stepper/delete mutation

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality (reliability)
- **Location**: frontend/src/features/cabinet/api/cabinet-queries.ts:104-128
- **Detail**: useDeleteEntry / useUpdateQuantity have no onError. A failed DELETE (e.g. 503) leaves the confirm dialog open with no message; a failed PATCH is swallowed. No data loss (buttons re-enable, count unchanged). Consistent with existing useToggleImportant / useSetUsage siblings, so not a regression — flagged only because a hard-delete is higher-stakes.
- **Fix**: Optional — add onError toast/inline message (larger pattern change across all cabinet mutations; out of this slice's scope).
- **Decision**: FIXED (delete path only) — added a red `error?` slot to ConfirmDialog and wired `deleteEntry` onError → `deleteError` (use-cabinet-entry.ts), surfaced in both list + card dialogs. Quantity PATCH + sibling-mutation error surfacing left as a follow-up (see follow-ups/review-fixes.md) — belongs with a shared toast layer, not this slice.

## Verified Correct (no issue)

- Cross-account isolation on both new routes: `find_entry_by_id` filters on `id` + `user_id` → 404 for non-owners; router-level `Security(get_current_user)` guard applies.
- Hard-delete gated by `ConfirmDialog` on both the trash and zero-delete paths; no silent delete.
- Rapid-click race guard: `disabled={mutationPending}` + early-return, per-row `useCabinetEntry` instance — no lost decrements; zero-branch reads freshly-invalidated query state.
- Critical router ordering: `CabinetInvariantError → 500` before `CabinetError → 400` (confirmed CabinetInvariantError subclasses CabinetError).
- Google-style docstrings, English error messages, SQLAlchemyError wrapping, `exc` naming, imports at top.
- E2E role/text locators with state-based waits (no `waitForTimeout`); unique per-run expiry; teardown via DELETE with swallowed teardown errors.
- All 15 planned items landed as MATCH; the two "drifts" (`deleteEntry` using `apiFetch` for the 204 body; badge copy keyed to `below_minimum`) are improvements/defensible narrowings, not regressions.

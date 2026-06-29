<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Important Category

- **Plan**: context/changes/important-category/plan.md
- **Scope**: Phase 4 of 7
- **Date**: 2026-06-16
- **Verdict**: APPROVED (with 2 minor warnings)
- **Findings**: 0 critical, 2 warnings, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | WARNING |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

## Findings

### F1 — Variant refetch bypasses the _get_variant_or_raise guard

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/app/api/v1/cabinet/service.py:586-593
- **Detail**: `set_entry_importance` calls `crud.get_registry_by_id(...)` directly and passes the result into `_map_row_to_entry_out`. If the registry row is missing, `_map_row_to_entry_out` dereferences `variant.is_tablet_based` on None → AttributeError → generic 500. The add path solves exactly this with the existing `_get_variant_or_raise` helper (service.py:304), which raises `MedicationNotFoundError`. The plan literally said "reuse get_registry_by_id", so this is a plan-level miss too. Practically near-unreachable given FK integrity, hence LOW impact.
- **Fix**: Replace the direct `crud.get_registry_by_id` call with `variant = await _get_variant_or_raise(session, entry.medication_registry_id)`.
- **Decision**: FIXED

### F2 — Unplanned _resolve_prefs refactor touches the Phase 3 list path

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: backend/app/api/v1/cabinet/facade.py:18-45, 74-83
- **Detail**: Phase 4 introduces a `_ResolvedPrefs` NamedTuple + `_resolve_prefs` helper and rewires the already-shipped Phase 3 `list_entries` facade to consume it. Beyond Phase 4's stated "facade resolves prefs and delegates" scope; modifies a previously-reviewed code path. Benign, sensible DRY of the prefs read now shared by `list_entries` and `set_entry_importance` — all 117 cabinet tests (incl. Phase 3 facade tests) still pass, so behavior is preserved.
- **Fix**: Keep it — note it as an addendum in plan.md Phase 4 so the plan stays the source of truth.
- **Decision**: FIXED (documented as addendum in plan.md)

### F3 — No test for generic CabinetError → 400 on the PATCH route

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: backend/tests/cabinet/test_router.py:500-541
- **Detail**: `TestSetEntryImportanceErrorMapping` covers 404, 503, and 401, but not the generic `CabinetError → 400` branch (the add route has this test at test_router.py:398). The 404 test already pins the `EntryNotFoundError`-before-`CabinetError` ordering, so this is a small completeness gap, not a real risk.
- **Fix**: Add a test raising `CabinetError("...")` and asserting 400, mirroring `TestAddEntryErrorMapping.test_cabinet_error_returns_400`.
- **Decision**: FIXED

## Notes

- Automated success criteria verified passing on 2026-06-16: `uv run ruff check .` (all checks passed), `uv run ruff format --check .` (80 files formatted), `uv run pytest tests/cabinet` (117 passed).
- Security check: entry lookup in `find_entry_by_id` is correctly scoped to `user_id` (no IDOR/cross-user mutation).
- The drift sub-agent's claim that the `EntryNotFoundError`-before-`CabinetError` ordering is untested was found to be incorrect — `test_entry_not_found_returns_404` pins that precedence.

<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Important Category Implementation Plan

- **Plan**: context/changes/important-category/plan.md
- **Scope**: Phase 3 of 7
- **Date**: 2026-06-16
- **Verdict**: APPROVED
- **Findings**: 0 critical, 1 warning, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | WARNING |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

## Findings

### F1 — status/order refactored to StrEnum beyond the planned category addition

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: backend/app/api/v1/cabinet/schemas.py:20-43
- **Detail**: The plan asked only to add `category: Literal["important"] | None` to CabinetListParams (Phase 3.3). The implementation introduced three StrEnum classes and converted the pre-existing `status` and `order` fields from `Literal[...]` to `CabinetStatus` / `CabinetOrder`. The `category` field is `CabinetCategory` (StrEnum) rather than the planned Literal — also a deviation, benign. This is EXTRA scope touching two params already shipped in S-02. Behavior is unchanged (StrEnum serializes to identical string values; comparisons like `status == "expired"` and `category == "important"` still hold; invalid values still 422) and the commit message documents it — benign, not dangerous.
- **Fix**: Keep the refactor (improves type safety, already tested green) and record it as a one-line addendum under Phase 3 in plan.md, mirroring the Phase 2 CRUD-split addendum already present.
- **Decision**: FIXED — Phase 3 addendum added to plan.md (2026-06-16).

### F2 — min_package_count default hardcoded as 1 instead of DEFAULT_MIN_PACKAGE_COUNT

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/app/api/v1/cabinet/service.py:193, 254
- **Detail**: `_map_row_to_entry_out(..., min_package_count: int = 1)` and `list_entries(..., min_package_count: int = 1)` hardcode the literal 1, while facade.py resolves the value from DEFAULT_MIN_PACKAGE_COUNT. The constant exists and is imported one layer up; the literal duplicates it and can silently drift if the default changes. The facade always passes an explicit value in production, so this only affects direct/test callers.
- **Fix**: Import DEFAULT_MIN_PACKAGE_COUNT in service.py and use it as the default for both signatures.
- **Decision**: FIXED — service.py now imports and uses DEFAULT_MIN_PACKAGE_COUNT for both `_map_row_to_entry_out` and `list_entries` defaults; ruff clean, 111 cabinet tests pass (2026-06-16).

## Verification Evidence

- `uv run pytest tests/cabinet` → 111 passed.
- `uv run ruff check .` → All checks passed.
- `uv run ruff format --check .` → 80 files already formatted.
- `is_below_minimum` parametrized matrix covers below / at-min / above / non-important, including the `==min` no-signal boundary.
- Architecture confirmed: pure fn in service.py beside `classify_status`; facade is sole cross-domain reader; `min_package_count` fetched once per request (no N+1).
- Manual check 3.5 marked done; no diff evidence possible for a manual step — taken at face value.

<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Dosage Tracking (S-05)

- **Plan**: context/changes/dosage-tracking/plan.md
- **Scope**: Phase 5 of 6 (PATCH backend — update / unassign usage)
- **Date**: 2026-06-26
- **Verdict**: APPROVED
- **Findings**: 0 critical, 2 warnings, 0 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | WARNING |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

Success criteria notes: `ruff check` ✅, `ruff format --check` ✅,
`pytest tests/cabinet/` → 201 passed ✅. `pyright` aborts under the Bash tool
with the documented `OPENSSL_Uplink` quirk (L-001) — environment limitation, not
a code defect; 5.1 verified at commit 737007f.

## Findings

### F1 — Dosage value caps added outside Phase 5 scope (backend + frontend)

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: backend/app/api/v1/cabinet/schemas.py:18,20; frontend/src/features/cabinet/schemas/cabinet-schemas.ts:20,22
- **Detail**: Phase 5 §1 scoped this phase to `UsageRequest`/crud clear-update only. The commit also added bound constraints to the *shared* `UsageFields`: `dosage_times: Field(None, ge=1, le=24)` and `dosage_amount: Field(None, ge=1, le=100)`, plus matching `.max(24)`/`.max(100)` in the frontend zod schema. Because `UsageFields` is shared with the Phase 1 POST path, this silently widens the POST contract, and a frontend file is touched in a backend-only phase. Benign and well-tested (parametrized 422 cases for times 0/25, amount 0/101), but undocumented scope.
- **Fix**: Add a one-line addendum under Phase 5 in plan.md (mirroring the Phase 4 addendum) noting the shared dosage caps + frontend max() parity, so future reviews treat the plan as ground truth.
- **Decision**: FIXED

### F2 — Inline import violates L-006 (imports at top of file)

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/tests/cabinet/test_service.py (test_entry_not_found_raises_entry_not_found_error)
- **Detail**: The new test does `from app.utilities.errors import EntryNotFoundError` inside the function body. The top import block (lines 37–42) already imports `InvalidDosageError` and `MedicationNotFoundError` from the same module — `EntryNotFoundError` was placed inline instead. This is exactly the pattern L-006 forbids (a rule established in this change's Phase 3 review). Ruff's E402 doesn't catch function-local imports, so it slipped past lint.
- **Fix**: Add `EntryNotFoundError` to the top import block (alphabetically before `InvalidDosageError`) and delete the inline import.
- **Decision**: FIXED + ACCEPTED-AS-RULE: L-006 (extended to cover function-local imports)

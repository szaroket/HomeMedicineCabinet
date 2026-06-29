<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Dosage Tracking (S-05)

- **Plan**: context/changes/dosage-tracking/plan.md
- **Scope**: Phase 3 of 6
- **Date**: 2026-06-26
- **Verdict**: APPROVED
- **Findings**: 0 critical, 1 warning, 3 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

Success criteria evidence: `ruff check .` + `ruff format --check .` pass;
`pytest tests/cabinet/` → 176 passed; `category=used` router test passes;
calc tests (Risk #6) present and passing. `pyright` is not runnable from the
Bash tool (L-001 OpenSSL applink crash); recorded green per Progress 3.1 and
commit 7b3784c, run from PowerShell.

## Findings

### F1 — Mid-file imports with `# noqa: E402` in test_service.py

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/tests/cabinet/test_service.py:1212
- **Detail**: The Phase 3 calc tests append a fresh import block (`UsageView, compute_usage_view, daily_consumption_rate, days_of_supply_from_rate`) in the middle of the file, suppressed with `# noqa: E402`. The file's other service imports live at the top normally; the noqa exists only to silence the rule the placement creates. Tests pass, but it diverges from the file's own convention and hides a self-inflicted lint smell.
- **Fix**: Move the four names into the top-of-file import from `app.api.v1.cabinet.service` and drop the `# noqa: E402` block.
- **Decision**: FIXED + ACCEPTED-AS-RULE: L-006 — Keep all imports at the top of the file

### F2 — Misleading "Non-tablet used entry" comment on a branch unreachable for non-tablet entries

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/app/api/v1/cabinet/service.py:240
- **Detail**: `compute_usage_view` checks `tablets_per_package is None` first and returns null_view. For a genuinely non-tablet variant, tpp is always None in `_map_row_to_entry_out` (only set when `is_tablet_based`), so a non-tablet entry never reaches the later dosage-None branch — yet that branch carries the comment "Non-tablet used entry: date-only tracking". The dosage-None guard is correct defensive code, but the comment describes a case the earlier guard already absorbs.
- **Fix**: Reword the comment to its real role, e.g. "Used tablet entry with incomplete dosage fields — treat as date-only", or note the non-tablet case is handled by the tpp guard above.
- **Decision**: FIXED

### F3 — Duplicate `test_invalid_category_returns_422` across two classes

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/tests/cabinet/test_router.py:537
- **Detail**: The old `TestListEntriesImportanceFields.test_invalid_category_returns_422` was edited to use "unknown" (since "used" is now valid), and a new `TestListEntriesCategoryFilter.test_invalid_category_returns_422` with an identical body was added. Two identical invalid-category tests now exist. Harmless (different classes) but redundant.
- **Fix**: Drop one of the two; keep the invalid-category assertion next to the new category-used test.
- **Decision**: FIXED

### F4 — `is_sufficient` reports True for a past end date

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Plan Adherence
- **Location**: backend/app/api/v1/cabinet/service.py:248 (test_end_date_in_past, test_service.py)
- **Detail**: When the end date is in the past, days_until_end goes negative (e.g. -3) and `is_sufficient = supply >= days_until_end` evaluates True. This matches the plan's formula and the calc is internally consistent, but a Phase 4 "Wystarczy" badge would render for an entry whose tracking window has already closed. Not a Phase 3 bug; flagged so Phase 4 frontend explicitly handles the `days_until_end <= 0` case rather than trusting is_sufficient blindly.
- **Fix**: No backend change. Note for Phase 4: branch on `days_until_end <= 0` before showing the Wystarczy/Zabraknie badge.
- **Decision**: FIXED (backend) — `compute_usage_view` now guards `until_end > 0`, returning `is_sufficient = None` for a closed window. Phase 4 should gate the Wystarczy/Zabraknie badge on `is_sufficient is not None`.

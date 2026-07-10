<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Notifications and Badges (S-06)

- **Plan**: context/changes/notifications-and-badges/plan.md
- **Scope**: Phase 4 of 7 (Backend — editable thresholds)
- **Date**: 2026-07-08
- **Verdict**: APPROVED
- **Findings**: 0 critical, 0 warnings, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

## Evidence

- **Plan adherence** — All four planned files (`users/schemas.py`, `crud.py`, `service.py`, `router.py`) changed as specified. `update_min_package_count` → `update_preferences` rename; all three fields written in both existing-row and new-row paths; router passes both new fields through. Validation bounds match plan/PRD exactly: `expiry_threshold_days` `ge=7,le=90`, `close_to_finish_threshold_days` `ge=1`, `min_package_count` `ge=1,le=10`.
- **Scope** — Diff (commit 4fe5bf1) touched only planned source files plus their tests and the plan Progress checkboxes. No scope creep.
- **Safety/patterns** — L-004 try/except → `UserDatabaseError` intact; Google-style docstrings updated; named args for 3+ params; `DEFAULT_*` imports still used by `get_effective_preferences` (no dead import). The two now-required body fields are a documented, intended contract change (Phase 7 sends the full set).
- **Success criteria** — `uv run ruff check .` + `ruff format --check` clean; `uv run pytest tests/users` → 38 passed. Manual item 4.4 marked done.

## Findings

### F1 — New-row threshold behavior not pinned by a test

- **Severity**: 🔵 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: backend/tests/users/test_service.py:96-124
- **Detail**: The substantive Phase 4 change in service.py is that the new-row (insert) path now writes the *passed* thresholds instead of hardcoded `DEFAULT_*` constants (service.py:68-73). Both service tests (`test_inserts_new_row_when_none_exists`, `test_updates_existing_row`) pass `DEFAULT_EXPIRY_THRESHOLD_DAYS` / `DEFAULT_CLOSE_TO_FINISH_THRESHOLD_DAYS` as inputs and the mocks return those same values, so the assertions cannot distinguish "used the passed value" from "reverted to the default." The insert test only asserts `insert_mock.assert_awaited_once()`, not that the constructed `UserPreferences` carried the passed thresholds. The router `test_updates_min_package_count` has the same gap. Not a defect: crud `test_sets_all_fields_and_returns_prefs` (test_crud.py:84-98) asserts all three fields with non-default values (14/3/4), so field-level persistence is covered; 422 boundary tests are solid. This is only a "would a regression be caught" gap at the service/router layer.
- **Fix**: In `test_inserts_new_row_when_none_exists`, pass non-default thresholds (e.g. `expiry_threshold_days=45`, `close_to_finish_threshold_days=10`) and assert `insert_mock.call_args.kwargs["prefs"]` carries them.
- **Decision**: FIXED

<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Important Category

- **Plan**: context/changes/important-category/plan.md
- **Scope**: Phase 2 of 7 (PATCH /users/preferences)
- **Date**: 2026-06-16
- **Verdict**: APPROVED
- **Findings**: 0 critical, 0 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

Automated checks (re-run during review):
- `uv run pytest tests/users` — 22 passed
- `uv run ruff check app/api/v1/users tests/users` — All checks passed
- `uv run ruff format --check` — 10 files already formatted

## Findings

### F1 — CRUD upsert split into two functions; branch logic moved to service

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; informational
- **Dimension**: Plan Adherence
- **Location**: backend/app/api/v1/users/crud.py:46,80 + service.py:51-65
- **Detail**: Plan Phase 2 §2 named one CRUD function `upsert_min_package_count(session, user_id, min_package_count)`. Implementation instead ships `update_min_package_count(session, prefs, ...)` + `insert_preferences(session, prefs)` and keeps the get-existing → branch → construct-new logic in `service.update_preferences`. Behavior is equivalent and the split reads cleaner (crud stays thin, service orchestrates). Noted so the plan-vs-code name mapping is explicit for later phases.
- **Fix**: None needed. Optionally add a one-line addendum to Phase 2 §2 noting the two-function split.
- **Decision**: FIXED — added addendum to Phase 2 §2 (CRUD upsert) in plan.md noting the two-function split.

### F2 — Non-atomic read-then-write upsert can 503 on concurrent first write

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; rare race, transient failure
- **Dimension**: Safety & Quality (Reliability)
- **Location**: backend/app/api/v1/users/service.py:51-65
- **Detail**: `update_preferences` reads prefs, then inserts when absent. `user_id` has a UNIQUE constraint (models.py:29). Two concurrent first-writes for the same user both see None, both call `insert_preferences`; the second hits the unique violation → SQLAlchemyError → UserDatabaseError → HTTP 503 instead of a successful write. Same-user double-submit is unlikely and the failure is a single retryable request, hence observation not warning. The plan itself described upsert as read-then-write, so this is not a regression against the plan.
- **Fix**: None required for this slice. If hardened later, use a DB-level upsert (PostgreSQL `INSERT ... ON CONFLICT (user_id) DO UPDATE`) in a single CRUD call to make it atomic.
- **Decision**: SKIPPED — rare race, transient retryable failure; out of scope for this slice.

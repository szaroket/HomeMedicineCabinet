<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Important Category — GET /users/preferences

- **Plan**: context/changes/important-category/plan.md
- **Scope**: Phase 1 of 7
- **Date**: 2026-06-16
- **Verdict**: APPROVED
- **Findings**: 0 critical, 1 warning, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

### Automated criteria

- `uv run ruff check . && uv run ruff format --check .` → PASS (all checks; 80 files formatted)
- `uv run pytest tests/users/` → 10 passed
- `uv run pytest` (full, excluding `tests/db`) → 225 passed
  - `tests/db/test_connection.py` stalls on a live TLS-DB connection — environmental per L-001, not introduced by this phase.

## Findings

### F1 — Two router tests assert DB-state behavior they don't exercise

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/tests/users/test_router.py:30-67
- **Detail**: `test_returns_defaults_when_no_row_exists` and `test_returns_stored_values_when_row_exists` both fully mock `users_service.get_effective_preferences` (→ `_DEFAULT_PREFS` / `_STORED_PREFS`) and then assert the returned numbers. With the service mocked, neither test touches the "no row → defaults" vs "row exists → stored" logic — both verify the identical regression: the router serializes whatever the service returns. The names imply DB-state branching that actually lives in the (correctly tested) service layer. This is the "redundant copies" + misleading-name smell CLAUDE.md calls out; real branch coverage is in `test_service.py::TestGetEffectivePreferences`, which is solid.
- **Fix**: Collapse the two into one router pass-through test named for what it proves (e.g. `test_serializes_service_result`), or rename them to drop the "when no row / when row exists" framing. Keep the defaults-vs-stored oracle in `test_service.py`.
- **Decision**: FIXED — collapsed into `test_serializes_service_result`; removed unused `_DEFAULT_PREFS`. The defaults-vs-stored oracle stays in `test_service.py`.

### F2 — Router/service docstrings omit Raises (and Args/Returns on router)

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/app/api/v1/users/router.py:24, backend/app/api/v1/users/service.py:32
- **Detail**: `get_preferences` (router) has a one-line docstring with no Args/Returns/Raises; `get_effective_preferences` (service) has Args/Returns but no Raises for the `UserDatabaseError` that crud can surface. The project docstring rule asks for full Google-style docstrings, but every sibling router endpoint (`cabinet/router.py`) uses the same one-line summary, so this is consistent with the established codebase pattern rather than drift. Noted, not blocking.
- **Fix**: Optionally add a `Raises:` clause to `service.get_effective_preferences`; leave the router docstring matching its siblings.
- **Decision**: FIXED — added `Raises: UserDatabaseError` clause to `service.get_effective_preferences`; router docstring left matching its siblings.

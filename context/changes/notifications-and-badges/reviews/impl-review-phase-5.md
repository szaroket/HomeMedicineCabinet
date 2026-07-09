<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Notifications and Badges (S-06)

- **Plan**: context/changes/notifications-and-badges/plan.md
- **Scope**: Phase 5 of 7
- **Date**: 2026-07-08
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 1 warning, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | OBSERVATION |
| Success Criteria | PASS (integration tests env-blocked under Bash per L-001; unit + lint pass) |

## Findings

### F1 — Router error ladder doesn't catch NotificationsDatabaseError

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality (reliability)
- **Location**: backend/app/api/v1/users/router.py:64
- **Detail**: Phase 5 added `notifications_service.delete_by_user` inside `delete_account`, which per L-004 raises `NotificationsDatabaseError` on a DB failure. The router's DELETE /me handler still catches only `(UserDatabaseError, CabinetDatabaseError)` → 503. A failure in the new dismissal-delete falls through to the catch-all `except Exception` → HTTP 500 instead of the intended 503. The plan's convention (and L-004) is that each domain's `<Domain>DatabaseError` maps to 503; this new path breaks that. The transaction still rolls back safely via `persist` — only the status code is wrong.
- **Fix**: Add `NotificationsDatabaseError` to the except tuple at router.py:64 and to the imports at router.py:16.
- **Decision**: FIXED

### F2 — Facade docstring omits NotificationsDatabaseError

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency (docstrings)
- **Location**: backend/app/api/v1/users/facade.py:36
- **Detail**: `delete_account`'s `Raises:` block lists CabinetDatabaseError, UserDatabaseError, and AccountDeletionError, but the new `notifications_service.delete_by_user` call can now also raise `NotificationsDatabaseError`. Per the Google-docstring convention, the newly-possible exception should be documented.
- **Fix**: Add a `NotificationsDatabaseError:` line to the Raises: block (pairs with F1).
- **Decision**: FIXED

## Notes

- `crud.delete_by_user` / `service.delete_by_user` mirror the `cabinet` reference (`cabinet/crud.py:605`) exactly: signature, L-004 try/except → `NotificationsDatabaseError`, `delete(...).where(col(...))`, no commit (shared session), Google docstrings.
- Facade call sits inside the existing `persist` block, before the cabinet/user deletes, as planned (belt-and-suspenders alongside the FK cascade).
- Tests: autospec `mock_notifications_service` fixture + `assert_awaited_once_with`; real no-orphans integration test `test_delete_account_leaves_no_orphaned_dismissals`. No scope creep.
- Success criteria: `ruff check`/`format` pass; 38 unit tests pass. The 4 delete-account integration tests error on `alembic upgrade` under the Bash tool (`OPENSSL_Applink`, L-001) — run `uv run pytest tests/integration/users` from native PowerShell to close 5.1/5.3 locally.

<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Notifications and Badges (S-06)

- **Plan**: context/changes/notifications-and-badges/plan.md
- **Scope**: Phase 3 of 7 (Dismiss endpoint + load-time garbage collection)
- **Date**: 2026-07-08
- **Verdict**: APPROVED
- **Findings**: 0 critical, 0 warnings, 3 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS* |

\* Success Criteria PASS is partial: `ruff check` + `ruff format --check` passed and all
notifications modules import cleanly (3.3). Integration tests 3.1/3.2 could not be
independently re-run this session (Docker unavailable; tests use testcontainers Postgres),
and `pyright` typecheck hit the L-001 OpenSSL applink crash from the Bash tool. Both are
checked `[x]` against commit 549dc03 by the implementer; the test file is well-formed and
correctly located under `tests/integration/notifications/`.

## Findings

### F1 — Dead duplicate path: build_active_notifications no longer called

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/app/api/v1/notifications/service.py:217
- **Detail**: Phase 3 split the old `build_active_notifications` into `compute_active_notifications` + facade-level filter/order (facade.py:53-75). The original `build_active_notifications` was left behind and is referenced nowhere in the codebase (grep across backend/ finds only its own definition — no source, no test). It re-implements the filter+order logic the facade now owns, so the two paths can silently diverge on a future edit. Deleting it also orphans the `NotificationListOut` import at service.py:20 (ruff F401), which the fix should remove.
- **Fix**: Delete `build_active_notifications` (service.py:217-249) and drop the now-unused `NotificationListOut` import; the facade is the single source of truth for filter+order.
- **Decision**: FIXED — deleted the dead function and the orphaned `NotificationListOut` import (2026-07-08).

### F2 — insert_dismissal swallows all IntegrityErrors, not just the unique race

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/api/v1/notifications/crud.py:74
- **Detail**: `except IntegrityError: pass` treats every integrity violation as success. The plan scoped this to the unique-constraint race, but it also swallows the FK-violation raised when `cabinet_entry_id` doesn't exist — so `POST /dismiss` with a bogus entry id returns 204 while inserting nothing. Benign in practice (the UI only dismisses entries it is already showing; a cross-user-but-valid entry id inserts an inert row that self-GCs on the next user-scoped load), and the plan explicitly sanctioned mirroring the cabinet race-guard. Noted because, unlike the cabinet guard (crud.py:138, which re-raises for a service-layer handler), this one is a terminal swallow.
- **Fix**: Optional — narrow the catch to the unique constraint (inspect `exc.orig` / constraint name) so genuine FK violations surface as a 4xx; or accept as-is per the plan's stated tradeoff.
- **Decision**: FIXED — narrowed the swallow via a driver-agnostic post-rollback existence re-read: only the unique-constraint race (row now present) is treated as success; an FK violation (unknown `cabinet_entry_id`, row absent) raises the new `DismissalEntryNotFoundError` → router maps to 404. Added integration test `test_dismiss_unknown_entry_returns_404_and_inserts_nothing`. Idempotency test's 204-race path preserved. Ruff clean + modules import; integration run blocked locally by the L-001 OpenSSL crash (2026-07-08).

### F3 — GC read and delete are not in one transaction (plan-wording drift)

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: backend/app/api/v1/notifications/facade.py:48-65
- **Detail**: The plan's Critical Implementation Details said to do "the read + GC delete inside a single persist(session) transaction so a partial failure rolls back." The implementation reads dismissals via a separate uncommitted SELECT (get_dismissals) and issues the DELETE in its own persist() block. Because the read is an idempotent SELECT and the GC is a single atomic DELETE, there is no partial-failure window and the operation stays idempotent — the intent is met, only the literal "one transaction" wording differs. The post-commit read of dismissal attributes at facade.py:67 is safe because the session factory sets `expire_on_commit=False` (connector.py:30), so the GC commit does not expire the ORM objects.
- **Fix**: No action likely needed; recorded for the record.
- **Decision**: ACCEPTED — intent (idempotent, no partial-failure window) is met; the literal "one transaction" wording drift is benign. No code change (2026-07-08).

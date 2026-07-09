<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Notifications and Badges (S-06)

- **Plan**: context/changes/notifications-and-badges/plan.md
- **Scope**: All 8 phases (full-plan)
- **Date**: 2026-07-09
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 2 warnings, 3 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

## Success Criteria Note

Backend unit (15) + users unit (38), frontend tests (57), ruff lint+format, frontend
build, eslint, and prettier all pass. The backend **integration** suite could not run
in the Bash shell — `alembic upgrade head` fails with the OpenSSL/DB error L-001 warns
about (migrations must run from native PowerShell). Those tests were verified green
during phase implementation (Progress commit SHAs). Environment limitation, not a code
failure.

Not raised as findings (considered and dismissed): full-cabinet recompute per GET
(3 constant queries, not N+1 — explicitly accepted in the plan's Performance
Considerations); single-character `medication_name` stripped by cabinet `MIN_SEARCH_LEN=2`
on row-click nav (negligible — trigger-specific filters still apply).

## Findings

### F1 — Dismiss endpoint has no ownership check on cabinet_entry_id

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality (Security)
- **Location**: backend/app/api/v1/notifications/crud.py:70-92
- **Detail**: insert_dismissal takes cabinet_entry_id from the request; the only guard is the FK to cabinet_entries.id, satisfied by ANY user's entry. Consequences: (a) a user can create self-scoped dismissal rows referencing another user's entry (harmless to the other user, never surfaced); (b) POST /dismiss returns 204 when the entry exists for anyone and 404 when it doesn't — a cross-tenant existence oracle. The sibling cabinet domain always scopes lookups via crud.find_entry_by_id(user_id, entry_id); this path doesn't. Practical risk is low (cabinet_entry_id is uuid4, infeasible to enumerate), but it is a genuine object-level-authz gap.
- **Fix**: In the dismiss facade, verify ownership before inserting — call cabinet.crud.find_entry_by_id(session, user_id, entry_id) and raise DismissalEntryNotFoundError when the entry isn't the caller's. Closes the oracle and enforces ownership using the cabinet domain's existing pattern.
  - Strength: Reuses the established ownership pattern; removes both the oracle and the cross-tenant row.
  - Tradeoff: One extra read on the dismiss path.
  - Confidence: HIGH — cabinet.crud.find_entry_by_id already implements exactly this scoping.
  - Blind spot: None significant.
- **Decision**: FIXED — ownership check added in facade.dismiss via cabinet_crud.find_entry_by_id.

### F2 — GC delete failure turns a GET into a 503

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality (Reliability)
- **Location**: backend/app/api/v1/notifications/facade.py:62-65
- **Detail**: list_notifications (a read) calls delete_stale_dismissals when stale_keys is non-empty. If that housekeeping DELETE raises SQLAlchemyError → NotificationsDatabaseError → router 503, so a failed cleanup blocks the user from seeing ANY notifications. The bell mounts on every page load, refetches every 5 min, and is invalidated on every cabinet/settings mutation, so a high-frequency read's success now depends on an optional write. The plan mandated the transactional GC but didn't consider that its failure shouldn't fail the read — partly a plan gap.
- **Fix**: Make GC best-effort — wrap the delete_stale_dismissals call in facade.py in try/except, log the failure, and return the freshly-computed list anyway. Stale keys never intersect the active set, so skipping cleanup never corrupts the response; it just defers GC to the next load.
  - Strength: Decouples read availability from housekeeping; response stays correct.
  - Tradeoff: A persistently failing DELETE keeps re-attempting each load (log noise) until it succeeds.
  - Confidence: HIGH — stale keys are disjoint from active items by construction.
  - Blind spot: None significant.
- **Decision**: FIXED — GC wrapped in try/except NotificationsDatabaseError; logs warning and returns the list.

### F3 — Single-letter loop variable violates L-005

- **Severity**: ⚠️ OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/app/api/v1/notifications/facade.py:67
- **Detail**: `dismissed_keys = {(d.cabinet_entry_id, d.trigger_type) for d in dismissals}` uses `d`, violating L-005 (no single-letter names). The parallel service.compute_stale_dismissal_keys uses `dismissal` correctly — inconsistent with its own sibling.
- **Fix**: Rename `d` → `dismissal`.
- **Decision**: FIXED — renamed `d` → `dismissal` in the dismissed_keys comprehension.

### F4 — "Odrzuć wszystkie" partial-failure leaves stale UI (already accepted)

- **Severity**: ⚠️ OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline (Reliability)
- **Location**: frontend/src/features/notifications/api/notifications-queries.ts:34-50
- **Detail**: useDismissAllNotifications runs Promise.all(items.map(dismiss)). The O(N)-requests + partial-failure window is already documented/accepted in the Phase-6 addendum. Aspect not noted there: invalidateQueries runs only in onSuccess with no onError, so a partial failure shows a stale set with no feedback until the next 5-min poll.
- **Fix**: Switch to Promise.allSettled and invalidate in onSettled so the list re-syncs regardless of partial failure.
- **Decision**: FIXED — useDismissAllNotifications now uses Promise.allSettled + onSettled invalidation.

### F5 — Panel row copy differs from plan literals (intent preserved)

- **Severity**: ⚠️ OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: frontend/src/features/notifications/components/notification-panel.tsx
- **Detail**: Plan specified "Wygasa za {n} dni" / "Poniżej minimum"; actual uses richer wording ("Termin ważności kończy się za {n} dni" / "Termin ważności minął" / "Liczba opakowań poniżej minimalnej wartości"). Run-out copy matches. Same meaning, better UX wording — noted for traceability only.
- **Fix**: None needed — accept as an intentional copy improvement.
- **Decision**: ACCEPTED — richer Polish copy kept as an intentional UX improvement.

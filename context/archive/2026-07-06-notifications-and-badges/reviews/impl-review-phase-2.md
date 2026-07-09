<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Notifications and Badges (S-06)

- **Plan**: context/changes/notifications-and-badges/plan.md
- **Scope**: Phase 2 of 7
- **Date**: 2026-07-07
- **Verdict**: APPROVED
- **Findings**: 0 critical, 0 warnings, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS (1 observation) |
| Success Criteria | PASS |

## Verification

- `uv run pytest tests/notifications` (unit) → 15 passed
- `uv run ruff check .` → All checks passed
- `uv run ruff format --check .` → 109 files already formatted
- Integration test 2.2 (`GET /notifications` seeded triggers) not re-run in review (opens TLS DB connection — aborts under Bash tool per L-001). Verified at implementation time (commit e29ae20). Re-run from native PowerShell for fresh confirmation.

## Findings

### F1 — Naive date.today() in list_all_for_user vs. UTC elsewhere

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/app/api/v1/cabinet/crud.py:454
- **Detail**: `list_all_for_user` passes `today=date.today()` (naive/local date) into `_build_base_query`, whereas the rest of the codebase uses `datetime.now(timezone.utc).date()` (cabinet/service.py:494,544; notifications/facade.py). Currently INERT — this call passes `status=None`, so `_build_base_query` never reads `today` (only used in the status/sufficiency filter branches). Latent trap: if a WHERE filter is ever added to this path it would silently use local time, diverging from the UTC "today" the notifications facade computes for day-count math.
- **Fix**: Replace `date.today()` with `datetime.now(timezone.utc).date()` to match the codebase convention.
- **Decision**: FIXED (crud.py:5 import extended, crud.py:454 swapped; ruff clean)

## Notes (clean areas confirmed by deep review)

- Cabinet math genuinely reused — predicates read pre-computed `CabinetEntryOut` fields; no re-derivation of expiry/finish math.
- Ordering key exact — `_sort_key` matches spec `(expired_bucket, effective_days, trigger_type_rank, cabinet_entry_id)`, wrapped in a NamedTuple.
- `days_remaining` assembly per spec — expiry `(expiry_date - today).days`, run_out `days_of_supply`, below_minimum `None`.
- L-004 DB-boundary wrapping, facade-only cross-domain calls, English errors, Google-style docstrings, L-002 session typing, fixture reuse — all satisfied.
- Two benign additions (not scope creep): router 503 branch also catches `UserDatabaseError`/`CabinetDatabaseError` (facade orchestrates those reads); assembly logic in `service.build_active_notifications` rather than facade (keeps facade thin).

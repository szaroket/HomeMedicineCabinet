<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Dosage Tracking (S-05)

- **Plan**: context/changes/dosage-tracking/plan.md
- **Scope**: Phase 1 of 6 (POST backend — persist usage on add)
- **Date**: 2026-06-25
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 2 warnings, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | WARNING |
| Architecture | WARNING |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

Automated checks re-run during review: `ruff check` PASS · `ruff format --check` PASS ·
`pytest tests/cabinet/test_service.py tests/cabinet/test_router.py` (132 passed) PASS ·
`pyright` SKIPPED (could not run from the Bash tool — L-001 OpenSSL/applink crash;
verified at commit 27a2675).

## Findings

### F1 — Non-atomic merge: usage committed in a second transaction

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality (reliability / data safety)
- **Location**: backend/app/api/v1/cabinet/service.py:824-831 (_merge_and_commit)
- **Detail**: On a dedup merge that carries usage, the row is written by two separate
  committed transactions: `crud.update_entry_counts(...)` commits (persist → commit,
  crud.py:441), then `crud.update_entry_usage(...)` commits again (crud.py:160). If the
  second commit fails (SQLAlchemyError → CabinetDatabaseError), the entry is left with
  updated package counts but the OLD usage schedule — a partially-applied merge. The plan
  explicitly offered the atomic alternative ("...or extend update_entry_counts", plan §3),
  which would write both in one persist() block.
- **Fix A ⭐ Recommended**: Fold the usage write into the existing `update_entry_counts`
  persist block (pass `resolved_usage` through, call `_apply_usage` before the single
  persist) so counts + usage commit atomically on merge.
  - Strength: One transaction = no partial-merge state; matches the plan's own suggested
    alternative and the single-commit shape of every other write here.
  - Tradeoff: `update_entry_counts` grows one optional param and a branch; insert path still
    uses `_apply_usage` separately.
  - Confidence: HIGH — `_apply_usage` already isolates the field writes; the merge already
    calls `update_entry_counts` in the same place.
  - Blind spot: None significant — single row, same session.
- **Fix B**: Accept as-is.
  - Strength: Zero churn; keeps `update_entry_usage` reusable verbatim for the Phase 5 PATCH
    (which legitimately needs a standalone usage write).
  - Tradeoff: Leaves the partial-merge window open on a DB failure.
  - Confidence: MED — risk is real but low-probability (single user, same-row write moments
    apart).
  - Blind spot: Whether Phase 5 ends up wanting the standalone fn anyway, making A's split
    feel redundant.
- **Decision**: FIXED (Fix A)

### F2 — crud.py now imports from schemas (new layer dependency)

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Architecture (dependency direction)
- **Location**: backend/app/api/v1/cabinet/crud.py:13 (`from app.api.v1.cabinet.schemas import ResolvedUsage`)
- **Detail**: crud.py previously depended only on models + errors; every existing write
  (`update_entry_counts`, `update_entry_importance`, `insert_entry`) takes primitives.
  `update_entry_usage` breaks that by taking a schemas-module type, introducing a
  crud → schemas dependency that did not exist (medicines/crud.py and auth/crud.py have none
  either). `ResolvedUsage` is an internal value object, not a request/response contract, so
  schemas.py is an awkward home once crud needs it. No circular import today (schemas imports
  nothing from crud/service), so this is cleanliness/consistency, not a runtime bug.
- **Fix**: Move `ResolvedUsage` to a neutral shared location — `app/utilities/types.py`
  (where `NonEmptyStr` already lives) — and import it from there in both schemas.py and
  crud.py, so crud stays free of the schemas layer.
- **Decision**: FIXED — moved both `ResolvedUsage` and its dependency `DosagePeriod` to
  `app/utilities/types.py`; updated call-site imports directly in crud.py, service.py,
  schemas.py, and tests/cabinet/test_service.py (no re-export shim).

### F3 — validate_usage takes is_tablet_based, not the full variant

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: backend/app/api/v1/cabinet/service.py:176
- **Detail**: Plan §2 wrote the signature as `validate_usage(variant, is_used, ...)`; the
  implementation passes `is_tablet_based: bool` instead. This is a benign improvement — it
  keeps the validator a pure function of primitives (matching the plan's own stated purity
  goal and the injected-today style), and the parametrized tests confirm it. No action
  needed; noted only because it's a documented signature deviation from the plan text.
- **Decision**: ACKNOWLEDGED — benign improvement, accepted as-is.

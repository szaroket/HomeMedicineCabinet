<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Backend business-logic + CRUD safety net (test-plan Phase 1)

- **Plan**: context/changes/testing-backend-safety-net/plan.md
- **Scope**: Phase 1 of 5
- **Date**: 2026-06-30
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 1 warning, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS (N/A — test-only) |
| Pattern Consistency | PASS |
| Success Criteria | PASS (pyright deferred to PowerShell, L-001) |

## Verification (agent Bash tool, 2026-06-30)

- `pytest tests/cabinet/test_service.py` → 117 passed ✅
- `pytest --ignore=tests/db --ignore=tests/integration` → 349 passed ✅
- `ruff check tests/cabinet/test_service.py` → clean ✅
- `pyright` → not runnable from Bash (L-001 OpenSSL applink abort; confirm from native PowerShell)
- Manual 1.5 (oracle independence) → confirmed: expected values hand-derived from FR-010, not copied from the implementation.

## Findings

### F1 — Phase 1 authored no tests; the merge-math coverage predates the plan

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Plan Adherence
- **Location**: backend/tests/cabinet/test_service.py:51-176
- **Detail**: Phase 1's "Changes Required" plans to *extend* test_service.py with FR-010 merge-math unit tests (`total_tablets`, `normalize_tablet_pool`, `merge_tablet_entry`, `merge_non_tablet_entry`). All four test classes were introduced on 2026-06-09 in commit fe03838 (add-medication-from-registry, p1) — three weeks before this plan was created (957d38c, 2026-06-30). The Phase 1 commit fa65324 ("FR-010 merge-math unit tests verified (p1)") touched only plan.md + change.md: it flipped all five Progress rows to [x] and set status→implementing, adding zero test code. Phase 1 therefore ratified pre-existing coverage rather than producing it. The coverage is genuine and correct (117 tests pass; oracle verified independent of the implementation), but the plan record and commit message present it as new work, which can mislead a later reader or full-plan review into crediting this phase with authoring it.
- **Fix**: Annotate Phase 1 in plan.md to record that the merge-math coverage pre-existed (introduced in fe03838) and Phase 1 audited it for FR-010 oracle-independence rather than authoring it.
  - Strength: Keeps the plan honest as the ground truth future reviews read from; costs nothing in code and loses no real coverage.
  - Tradeoff: Phase 1 becomes a documented no-op; slightly deflates the apparent delta of this branch.
  - Confidence: HIGH — git history is unambiguous (fe03838 2026-06-09 vs plan 2026-06-30; fa65324 diff is docs-only).
  - Blind spot: None significant.
- **Decision**: FIXED — added provenance note to Phase 1 in plan.md (fe03838 pre-existed; Phase 1 audited).

### F2 — Duplicate parametrize case in TestMergeTabletEntry

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/tests/cabinet/test_service.py:121, 131
- **Detail**: Two parametrize tuples are byte-identical — `(1, None, 1, 5, 20, TabletPool(2, 5))` — one labeled "partial on new side only", the other "worked example from plan". Same inputs and expected, so the second adds no coverage and pytest disambiguates the colliding test id with a numeric suffix.
- **Fix**: Replace the line-131 duplicate with a distinct FR-010 worked example (e.g. a multi-package partial+partial remainder case).
- **Decision**: FIXED — replaced with `(2, 13, 3, 9, 20, TabletPool(5, 2))` (33+49=82 → 5 pkg partial 2); 117 tests pass.

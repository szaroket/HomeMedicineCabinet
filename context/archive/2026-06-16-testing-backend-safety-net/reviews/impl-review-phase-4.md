<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Backend business-logic + CRUD safety net (test-plan Phase 1)

- **Plan**: context/changes/testing-backend-safety-net/plan.md
- **Scope**: Phase 4 of 5 (Risk #1 + #4 read/membership)
- **Date**: 2026-06-30
- **Verdict**: APPROVED
- **Findings**: 0 critical 1 warning 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | WARNING |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

## Verification notes

- **Verified from the agent**: `ruff check tests/integration` clean; CI-path suite
  `pytest --ignore=tests/db --ignore=tests/integration` → 349 passed; all asserted
  response fields (`below_minimum`, `is_sufficient`, `is_tablet_based`, `merged`, etc.)
  exist in `cabinet/schemas.py`.
- **Attested only (not agent-runnable, L-001)**: 4.1/4.2 integration tests (need
  Docker + PowerShell), 4.5 pyright (aborted from the agent Bash tool with the OpenSSL
  applink error), and the 4.6/4.7 manual WHERE-clause mutation checks. Marked `[x]` in
  Progress; trusted, not re-confirmed.
- Risk #4 coverage fully matches the plan contract: status (valid/expiring/expired),
  search via real `to_tsquery`, category (important/used), below_minimum, sufficiency
  (sufficient/insufficient), plus an intersection case — all asserting exact id-set
  membership, never count-only.

## Findings

### F1 — Unplanned write-path test file (test_add_entry.py)

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: backend/tests/integration/cabinet/test_add_entry.py:1
- **Detail**: Phase 4's "Changes Required" lists exactly two new test files —
  test_list_entries.py (Risk #1) and test_filters.py (Risk #4). The commit also adds
  test_add_entry.py, which exercises the POST /cabinet/entries merge-on-duplicate path
  (FR-010 dedup). That is integration coverage of Risk #3 (merge math), not Risk #1 or
  #4, and it is a write-path test — writes are Phase 5's territory (ownership/usage),
  though merge-on-add isn't assigned to any DB phase. The test itself is correct and
  useful (same-session seam, rollback isolation, asserts merged=true + summed
  package_count + no duplicate row). Benign scope creep, not a defect.
- **Fix A ⭐ Recommended**: Keep it; note it as a Phase 4 addendum in plan.md.
  - Strength: Preserves correct, valuable coverage and updates the source of truth
    before Phase 5 review uses the plan as ground truth — matches how this plan already
    records discovered scope (inline "Correction (Phase 3 review)" addenda).
  - Tradeoff: Plan's per-phase file list becomes slightly less literal.
  - Confidence: HIGH — addendum pattern already used throughout this plan.
  - Blind spot: None significant.
- **Fix B**: Move the file under Phase 5's grouping / a follow-up.
  - Strength: Keeps Phase 4 strictly read/membership.
  - Tradeoff: Churn for a test that already passes; arbitrary since merge-on-add fits
    no existing phase cleanly.
  - Confidence: MEDIUM — depends how strict you want phase boundaries.
  - Blind spot: None significant.
- **Decision**: FIXED via Fix A — addendum added to plan.md Phase 4 (subsection #3)

### F2 — pytest.skip() in the today fixture's teardown

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/tests/integration/conftest.py:343
- **Detail**: The midnight-guard fixture is a thoughtful touch, but it calls
  pytest.skip() after yield (in teardown). By then the test body has already run and
  (usually) passed; skipping during finalization is an edge pytest handles
  inconsistently across versions — it can surface as a teardown error rather than
  cleanly converting a passed test to skipped. The path is a one-in-86400 flake, so the
  practical risk is negligible, but the guard may not behave exactly as the docstring
  implies ("skip the test").
- **Fix**: If you want the guard airtight, capture today at session/module scope, or
  assert-and-xfail rather than skip-in-teardown. Not worth changing for a 1/86400 path
  unless it ever bites.
- **Decision**: FIXED — moved the midnight guard to setup-time (skip within 5s of
  rollover before yield) in conftest.py, eliminating skip-in-teardown.

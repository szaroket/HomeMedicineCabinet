<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Backend business-logic + CRUD safety net (test-plan Phase 1)

- **Plan**: context/changes/testing-backend-safety-net/plan.md
- **Scope**: Phase 5 of 5 (Risk #5 + #6 residual — ownership / usage; commit 997738b)
- **Date**: 2026-06-30
- **Verdict**: APPROVED (2 minor warnings)
- **Findings**: 0 critical, 2 warnings, 1 observation

> Note: a prior full-plan sweep (`reviews/impl-review.md`) already raised F1 and F2 as PENDING.
> This fresh Phase-5 pass re-verifies both against source and adds F3. Verified here from the
> agent shell: CI-path suite green (349 passed, DB-free) and `ruff check tests/integration`
> clean. The Docker-backed run, isolation re-runs, and pyright (5.1/5.2/5.5) are PowerShell-only
> per L-001 and marked done at 997738b.

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | PASS |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

## Findings

### F1 — `today` fixture uses naive local time; server computes UTC

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality (Reliability)
- **Location**: backend/tests/integration/conftest.py:343
- **Detail**: The `today` fixture does `datetime.now()` (naive LOCAL) and yields `now.date()`, but the server computes its reference day as `datetime.now(timezone.utc).date()` (confirmed at service.py:494, 815, 887, 932). On this machine (Poland, UTC+2 in summer) the local date is one day ahead of the UTC date from local 00:00 until ~02:00. In that ~2h/day window the Phase-5 tests break deterministically: `test_usage` asserts `days_until_end == 60` exactly (server returns 61), and the boundary parity entry flips category — the parity test's Python oracle uses test-`today` while the SQL filter uses server UTC-today, so they diverge. The midnight guard (skip within 5s of LOCAL midnight) guards the wrong axis (intra-run local-midnight crossing, not local-vs-UTC skew) and gives false confidence. Also affects Phase-4 status-filter tests that depend on `today`.
- **Fix**: Set `now = datetime.now(timezone.utc)` in the fixture (still yield `now.date()`; the seconds-to-midnight guard reuses the same `now`, becoming UTC-correct too). `timezone` is already imported at conftest.py:7.
  - Strength: One-line change; aligns the oracle clock with the server's UTC reference used everywhere in the service layer.
  - Tradeoff: None significant.
  - Confidence: HIGH — server UTC source confirmed at service.py:494/815/887/932.
  - Blind spot: None significant.
- **Decision**: FIXED (now = datetime.now(timezone.utc) at conftest.py:343)

### F2 — Usage parity docstring overstates seeded no-verdict coverage

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: backend/tests/integration/cabinet/test_usage.py:143-146
- **Detail**: The docstring claims the seed spans "no-verdict (zero rate guard)", but no zero-rate (and no missing-capacity) entry is seeded — only `entry_closed_window` and `entry_unused` cover the no-verdict branch. Zero-rate is unreachable via the API path (validate_usage forces times/amount ≥ 1); those two SQL guards (`nullif(...)`, `capacity IS NOT NULL`) are covered by the unit parity suite (tests/cabinet/test_crud.py), not this integration test. The claim is harmless but misleading for a future reader.
- **Fix**: Trim the docstring's category list to what's actually seeded (closed-window + unused); or seed a missing-capacity registry + null-dosage entry via the factory kwargs and let the dynamic oracle classify them if integration-tier coverage is wanted.
  - Strength: Removes a misleading claim; keeps the docstring honest about what the test pins.
  - Tradeoff: Docstring-trim path leaves the guards covered only by unit tests (acceptable — structural SQL-string assertions).
  - Confidence: HIGH — confirmed seeded entries vs. unit coverage in test_crud.py.
  - Blind spot: None significant.
- **Decision**: FIXED via Fix A (trimmed docstring to API-reachable categories; noted unit-suite coverage of zero-rate/missing-capacity guards)

### F3 — Victim-unchanged assertion in usage-ownership test is a no-op

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality (test efficacy)
- **Location**: backend/tests/integration/cabinet/test_ownership.py:91-110
- **Detail**: `test_cross_account_usage_patch_returns_404` seeds A's entry with `is_used=False`, then (as B) PATCHes usage with `is_used=False`, and asserts the victim row is still `is_used=False`. Because the attempted mutation is itself a no-op, that victim-unchanged assertion would pass even if ownership leaked and B's write succeeded — only the 404 assertion actually protects against a cross-account write here. Contrast the importance test (line 58/75), which seeds `is_important=False` and PATCHes `True`, so its victim-unchanged check is genuinely load-bearing.
- **Fix**: Seed A's entry as `is_used=True` with a dosage block, have B PATCH `is_used=False`, then assert A's row is still `is_used=True` — making the victim-unchanged check a real leak detector, symmetric with the importance test.
- **Decision**: FIXED (seed is_used=True, B PATCHes False, assert unchanged True at test_ownership.py:91/110; no dosage block needed — factory writes the row directly, per test_filters.py:228)

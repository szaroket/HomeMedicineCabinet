<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Backend business-logic + CRUD safety net (test-plan Phase 1)

- **Plan**: context/changes/testing-backend-safety-net/plan.md
- **Scope**: Full plan (Phases 1–5); Phases 1–4 already have saved phase reviews, so this sweep focused on the unreviewed Phase 5 (commit 997738b) plus cross-phase integrity
- **Date**: 2026-06-30
- **Verdict**: APPROVED (with 2 minor warnings)
- **Findings**: 0 critical, 2 warnings, 0 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | PASS |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

Phase 5 is high quality: ownership enforced at the query layer (404 + victim-row-unchanged
assertions), SQL↔Python sufficiency parity derived dynamically from `compute_usage_view`
(a real oracle, not a mirror), a boundary entry catching a `>=`/`>` mutation, and a
within-test A→B `act_as` switch that closes the Phase-3 review follow-up
(`follow-ups/review-fixes.md`). CI-path suite green (349 passed); ruff clean. The DB-backed
tier and pyright could not be executed from the agent shell (L-001 applink abort) — this is
the documented PowerShell-only execution model; Progress marks 5.1–5.8 done at 997738b.

## Findings

### F1 — `today` fixture uses local wall-clock; server computes UTC

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality (Reliability)
- **Location**: backend/tests/integration/conftest.py:343-347
- **Detail**: The `today` fixture does `datetime.now()` (naive LOCAL time) and yields `now.date()`, but the server computes its reference day as `datetime.now(timezone.utc).date()` (service.py:494 `list_entries`, service.py:932 `set_entry_usage`). On this machine (Poland, UTC+2 in summer) the local date runs ~2 hours ahead of the UTC date: from local 00:00 until ~02:00 the oracle's `today` is one calendar day ahead of the server's. In that window the Phase-5 tests break deterministically — `test_usage` asserts `days_until_end == 60` exactly (server returns 61) and the boundary parity entry (supply == until_end) flips category. The existing midnight guard (skip within 5s of LOCAL midnight) guards the wrong axis (intra-run local-midnight crossing, not local-vs-UTC skew) and gives false confidence over a ~2h/day window.
- **Fix**: Make the fixture share the server's clock — `now = datetime.now(timezone.utc)` (then yield `now.date()`; the guard's seconds-to-midnight reuses the same `now`, so it becomes UTC-correct too). `timezone` is already imported at conftest.py:7.
  - Strength: One-line change; aligns oracle clock with the server's UTC reference used everywhere in the service layer.
  - Tradeoff: None significant.
  - Confidence: HIGH — server UTC source confirmed at service.py:494 and 932.
  - Blind spot: None significant.
- **Decision**: FIXED — already resolved in working tree; conftest.py:343 uses `datetime.now(timezone.utc)` and the guard reuses the same `now`.

### F2 — Usage parity docstring overstates seeded no-verdict coverage

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: backend/tests/integration/cabinet/test_usage.py:144-146
- **Detail**: The Phase-5 contract said to seed no-verdict cases spanning "zero-rate, closed window, missing capacity", and the test docstring claims it covers "no-verdict (zero rate guard)". Only `entry_closed_window` and `entry_unused` are actually seeded — there is no zero-rate or missing-capacity entry (zero-rate is unreachable via `seed_entry`, since `validate_usage` forces dosage_times/amount >= 1). Those two SQL guards (`nullif(...)`, `capacity IS NOT NULL`) ARE covered, but by the unit parity suite in `tests/cabinet/test_crud.py` (`test_zero_rate_guarded`), not by this integration test. So the docstring claims coverage this test doesn't provide.
- **Fix**: Trim the docstring's category list to what's seeded (closed window + unused); or, to exercise them at the integration tier too, seed a missing-capacity registry and a used-but-null-dosage entry via the factory's `**kwargs` and let the dynamic oracle classify them.
  - Strength: Removes a misleading claim; keeps the docstring honest about what the test pins.
  - Tradeoff: Docstring-trim path leaves the guards covered only by unit tests (acceptable — they are structural SQL-string assertions).
  - Confidence: HIGH — confirmed seeded entries vs. unit coverage in test_crud.py.
  - Blind spot: None significant.
- **Decision**: FIXED — already resolved in working tree; docstring at test_usage.py:141-148 trimmed to closed-window + unused, notes zero-rate/missing-capacity guards are pinned by the unit suite in test_crud.py.

<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Add Medication from Registry (S-01)

- **Plan**: context/changes/add-medication-from-registry/plan.md
- **Scope**: Phase 7 of 7
- **Date**: 2026-06-15
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 2 warnings, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | WARNING |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

## Verification

- `cd backend && uv run ruff check .` → All checks passed
- `cd backend && uv run ruff format --check .` → 74 files already formatted
- `cd backend && uv run pytest tests/registry tests/cabinet` → 102 passed
- 7.1 / 7.2 automated criteria: PASS. 7.3 manual: marked `[x]` with observable evidence
  (new `test_nar_wins_over_ir_regardless_of_document_order` + live re-import verify note).

## Findings

### F1 — Phase 7 solved via import-time parser dedup, not the planned query-level DISTINCT ON

- **Severity**: ⚠️ WARNING
- **Impact**: 🔬 HIGH — architectural stakes; think carefully before deciding
- **Dimension**: Plan Adherence
- **Location**: backend/scripts/registry_import/parser.py:222-269; backend/app/api/v1/medicines/queries.py:34 (planned, untouched)
- **Detail**: The plan's entire "Changes Required" for Phase 7 was a read-time query change — add `DISTINCT ON (capacity, capacity_unit)` to `LIST_VARIANTS` in queries.py/crud.py, with "VariantOut, the service, and the router are unchanged — confirm by inspection." Git confirms queries.py/crud.py were last touched in Phase 3 (c29d1ec) and were NOT modified in the Phase 7 commit (16cfdd3); `LIST_VARIANTS` still has no DISTINCT ON. Instead, Phase 7 added a two-pass import-time dedup in the parser (suppress IR parallel-imports when an original NAR/MRP/DCP/CEN exists; first-seen wins otherwise). This is a working — arguably cleaner — solution to the same user-facing problem (one row per pack size, canonical authorization row), and 7.3 was manually verified after a live re-import. Two consequences: (1) No addendum documents the drift — phases 3–6 each carry an "Addendum (impl)" note when they deviated; Phase 7 is the only deviating phase without one, so the plan now describes a query change that never happened. (2) The API has zero defensive dedup; variant uniqueness depends entirely on the import always running the dedup. The plan put dedup in the query precisely so the endpoint is correct regardless of data state; a fresh DB without re-import, or an import via another path, would resurface duplicates at the API with no guard.
- **Fix A ⭐ Recommended**: Add an "Addendum (Phase 7 impl)" note to the plan documenting the approach change (import-time dedup instead of query DISTINCT ON; NAR-over-IR + first-seen semantics).
  - Strength: Matches the established phases-3–6 addendum pattern; approach is sound and verified, so reconciling the plan to reality is the cheapest correct close-out.
  - Tradeoff: Leaves the API without a defensive dedup — correctness stays coupled to the import.
  - Confidence: HIGH — this repo consistently reconciles impl drift via plan addenda.
  - Blind spot: None significant.
- **Fix B**: Also add the planned `DISTINCT ON (capacity, capacity_unit)` to LIST_VARIANTS as defense-in-depth, keeping the parser dedup too.
  - Strength: Belt-and-suspenders — API correct even if a future import skips dedup; honours the plan's original intent.
  - Tradeoff: Redundant with the import dedup + per-query DISTINCT ON cost; still needs the addendum.
  - Confidence: MED — parser fix already covers the live case; this guards only against import-path regressions.
  - Blind spot: Whether endpoint volume makes the per-query DISTINCT ON cost worth it (NFR < 500ms p95).
- **Decision**: FIXED via Fix A — Phase 7 addendum added to plan.md documenting import-time dedup (NAR-over-IR + first-seen), the untouched query layer, and the deferred defensive DISTINCT ON.

### F2 — Unplanned helper script + parser change touch the "no registry data changes" guardrail

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: backend/scripts/find_ir_only_product.py (138 lines, new)
- **Detail**: The commit added `find_ir_only_product.py`, a manual-verification helper not in the plan's Changes Required, and modified the import parser — work under the slice's "No registry data changes" guardrail (forward-only; affects future imports, not rows already served). Both are benign and the helper supports 7.3's manual check, but the deviation is undocumented. Mirrors the Phase 3 parser-fix addendum, which was explicitly recorded.
- **Fix**: Fold into the same Phase 7 addendum as F1 — note the parser dedup is forward-only (outside the data-change guardrail) and the helper script is verification tooling.
- **Decision**: FIXED — folded into the Phase 7 addendum (forward-only parser dedup + find_ir_only_product.py verification helper both documented).

### F3 — Two-pass parser doubles I/O; safe only because callers pass a path

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/scripts/registry_import/parser.py:226-228
- **Detail**: `parse_registry` now reads the source twice (pass 1 scans original keys, pass 2 yields). For a non-seekable file-like object passed directly, `_scan_original_keys` exhausts the stream and the `hasattr(source, "seek")` guard skips the reset, so pass 2 would silently yield nothing. Not a live bug: `__main__.py` always passes a file path (URLs download to a temp file first), so each pass reopens fresh; tests pass seekable objects. Noted because the failure mode is silent (empty import, no error) if a caller ever streams a non-seekable source.
- **Fix**: No action required; optionally add a one-line docstring note that `source` must be a path or a seekable object.
- **Decision**: FIXED — added a docstring note to `parse_registry` that `source` must be a path or seekable file object (two-pass parsing exhausts a non-seekable stream).

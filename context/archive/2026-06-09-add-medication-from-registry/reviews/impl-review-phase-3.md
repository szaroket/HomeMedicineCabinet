<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Add Medication from Registry (S-01)

- **Plan**: context/changes/add-medication-from-registry/plan.md
- **Scope**: Phase 3 of 6
- **Date**: 2026-06-10
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 3 warnings, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | WARNING |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

### Automated criteria (Phase 3)

- 3.1 `ruff check` + `ruff format --check` — PASS (all checks passed, 65 files formatted)
- 3.2 existing tests still pass — PASS (142 passed; `tests/db` skipped, L-001 PowerShell-only)
- 3.3 manual PowerShell variants check — marked `[x]`; evidenced by new test_crud/test_router/test_service cases

## Findings

### F1 — ProductOut docstring detached by model_config placement

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/app/api/v1/medicines/schemas.py:9-23
- **Detail**: `model_config = ConfigDict(...)` was inserted as the FIRST statement in the ProductOut class body, pushing the triple-quoted docstring to line 12. A string literal that isn't the first statement is not a docstring — it's a dead expression, so `ProductOut.__doc__` is now None. This loses the Google-style docstring (project convention) and is inconsistent with the sibling VariantOut, which places `model_config` AFTER its docstring (schemas.py:42-58).
- **Fix**: Move the `model_config` line to below the docstring so the docstring is the first statement, matching VariantOut.
- **Decision**: FIXED

### F2 — Registry parser "sentinel" fix lands outside Phase 3 scope

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Scope Discipline
- **Location**: backend/scripts/registry_import/parser.py:30-40; backend/tests/registry/test_parser.py:98-120
- **Detail**: The commit ("variants endpoint + sentinel fix") changes `_clean()` so the "-" string maps to None, plus a new TestClean suite. This is registry-import logic, unrelated to the Phase 3 variants endpoint. The plan's "What We're NOT Doing" lists "no registry data changes", and the only plan.md edit in the commit was the Progress checkboxes — the parser change was not documented as an addendum. It's also forward-only: it affects future imports, not the rows /variants serves today (no re-import this slice), so it has no effect on Phase 3's observable behavior.
- **Fix A ⭐ Recommended**: Keep the change, add a one-line addendum to plan.md (or change.md) noting the parser sentinel fix and why.
  - Strength: Preserves the work and passing tests; updates the source of truth so the next review doesn't re-flag it as drift.
  - Tradeoff: Slightly widens this slice's footprint into the import script.
  - Confidence: HIGH — the repo already uses Phase-N addenda (see the Phase 2 addendum block in plan.md §Phase 4).
  - Blind spot: Whether "-" sentinels actually appear for tablet variants — unverified against live data (DB read is PowerShell-only).
- **Fix B**: Revert parser.py + test_parser.py from this branch; track as its own small registry-import change.
  - Strength: Keeps S-01 strictly to its planned endpoints.
  - Tradeoff: Loses landed, tested work; needs a separate PR.
  - Confidence: MEDIUM — depends whether anything in this slice relies on it (nothing does, since no re-import runs here).
  - Blind spot: None significant.
- **Decision**: FIXED via Fix A (addendum added to plan.md Phase 3)

### F3 — Wrong function name in search_products 500 log message

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/app/api/v1/medicines/router.py:53-57
- **Detail**: A new broad `except Exception → 500` handler was added to BOTH endpoints (reasonable defensive logging). But the one inside `search_products` logs `"Unexpected error in list_variants: %s"` — copied from the variants handler. A 500 in product search would be misattributed to list_variants in the logs, costing debugging time.
- **Fix**: Change the message in the search_products handler to reference "search_products".
- **Decision**: FIXED

### F4 — SQL extracted into new queries.py module (not in plan)

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Architecture
- **Location**: backend/app/api/v1/medicines/queries.py (new)
- **Detail**: The plan placed SQL in crud.py; the implementation moved SEARCH_PRODUCTS and added LIST_VARIANTS into a new queries.py. Benign, improves organization, and crud.py still owns execution. No action needed — noting it as an intentional, undocumented structural choice in case it should become a convention.
- **Decision**: DOCUMENTED + ACCEPTED-AS-CONVENTION — added a Phase 3 addendum to plan.md and a `queries.py` rule to AGENTS.md "Backend layer rules".

## Notes — what's solid

The `/variants` contract matches the plan: `VariantOut` carries exactly the specified fields; the query is case-insensitive on `name`, NULL-safe on `strength`/`form`, ordered `capacity NULLS LAST`. The `coalesce(...,'')` on both sides of `IS NOT DISTINCT FROM` is a reasoned improvement over the plan's literal text — it aligns the variants match with how `/products` folds the case-insensitive key, so a product selected from search reliably finds its variants. The cross-phase case-folding risk (Critical Implementation Details) is correctly handled.

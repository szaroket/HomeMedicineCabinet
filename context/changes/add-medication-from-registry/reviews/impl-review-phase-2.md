<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Add Medication from Registry (S-01)

- **Plan**: context/changes/add-medication-from-registry/plan.md
- **Scope**: Phase 2 of 6 — `GET /api/v1/medicines/products`
- **Date**: 2026-06-09
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 1 warning, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | WARNING |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

Automated checks: `ruff check` clean, `ruff format --check` clean, unit suite passes
(auth 33, cabinet 29). The only pytest failure is `tests/db/test_connection.py`, which
aborts on the documented L-001 OpenSSL/TLS issue (Bash-tool only; must run from
PowerShell) — not a Phase 2 regression.

## Findings

### F1 — Query param exposed as `?query=`, contract specifies `?q=`

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: backend/app/api/v1/medicines/router.py:18-39
- **Detail**: The plan's Phase 2 contract is `GET /products?q=<str>&limit=<int>`, manual check 2.3 uses `?q=apa`, and the Phase 6 frontend contract is `searchProducts(q)` (builds `?q=`). The endpoint binds the param to the Python name `query` with no alias, so the public param is actually `?query=`. A real `?q=apa` request would 422 (required `query` missing). This will break the Phase 6 frontend call unless reconciled, and means manual check 2.3 either wasn't run with the documented `?q=` form or was rubber-stamped.
- **Fix**: Add `alias="q"` to the `Query(...)` inside the `SearchQuery` Annotated, keeping the readable internal name `query` while the public param becomes `q` as the contract (and frontend) expect.
- **Decision**: FIXED (reconciled differently) — kept the implementation's `query` param; updated the plan contract (Phase 2 §4 line 150) and manual check 2.3 (line 161) to `?query=` instead of `?q=`. Phase 6 frontend must build `?query=` to match.

### F2 — Unplanned medicines error taxonomy + 503 path (benign EXTRA)

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: backend/app/utilities/errors.py:128-165; backend/app/api/v1/medicines/{crud,router}.py
- **Detail**: `MedicinesError` + `MedicineSearchError` and the crud `SQLAlchemyError → MedicineSearchError → 503` guard are not in the Phase 2 plan (error taxonomy was scoped to Phase 4's `CabinetError`). The addition is sound reliability hardening: a DB outage returns 503 instead of a raw 500, mirrors `AuthError`'s shape exactly (separate base, not extending AuthError), keeps `HTTPException` at the router layer only, and uses English messages — all per conventions. Flagged for scope-discipline visibility only; no defect.
- **Fix**: None required. Optionally note as a plan addendum so Phase 4's error work doesn't re-litigate the medicines taxonomy.
- **Decision**: FIXED (plan addendum) — added a Phase 2-review note above Phase 4 §1 so the medicines error taxonomy isn't re-litigated when `CabinetError` lands.

## Clean matches (no action)

- `ProductOut` schema is exact to the plan contract.
- crud `DISTINCT ON (lower(...))` case-folded search correctly implements the "Case-folded product key" Critical Detail and sets up Phase 3's case-insensitive variant lookup.
- Safe tsquery construction (word-token regex + bound parameter) is injection-safe.
- L-002 honored (crud `sqlalchemy` AsyncSession vs service/router `sqlmodel` AsyncSession).
- L-003 honored (`Query()` placed inside `Annotated`, not as a default).
- GIN index + limit cap protect the <500ms p95 NFR.

<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Add Medication from Registry (S-01)

- **Plan**: context/changes/add-medication-from-registry/plan.md
- **Mode**: Deep
- **Date**: 2026-06-09
- **Verdict**: SOUND after triage (was REVISE — all 5 findings resolved 2026-06-09)
- **Findings**: 0 critical, 2 warnings, 3 observations — all FIXED

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | PASS (was WARNING — F1 fixed) |
| Blind Spots | PASS (was WARNING — F2/F3/F4 fixed) |
| Plan Completeness | PASS (was WARNING — F5 fixed) |

## Grounding

9/9 paths ✓, 7/7 symbols ✓ (MedicationRegistry/CabinetEntry field names match plan
contracts; uq_cabinet_entries_user_med_expiry confirmed; search_vector generated column +
ix_medication_registry_search_vector GIN index confirmed in migrations 0e56afa1e4b6 /
2c7067ce3f56; CurrentUser type; UserPreferences.expiry_threshold_days default 30; auth-api
apiJson/apiFetch fetchers), brief↔plan ✓.

## Findings

### F1 — Cabinet/medicine errors have no defined base class

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Architectural Fitness
- **Location**: Phase 4, change #1 (app/utilities/errors.py)
- **Detail**: The plan says new errors (MedicationNotFoundError, InvalidPackageCountError, InvalidPartialTabletCountError) should "follow the existing AuthError-style base + default message pattern." But the only base in errors.py is `AuthError`, and every existing subclass extends it. Extending AuthError for a "medication not found" error is semantically wrong; inventing an ad-hoc base without guidance risks an inconsistent taxonomy. The plan leaves the implementer to guess the base-class decision.
- **Fix**: Specify a new domain base in errors.py — e.g. `CabinetError` (and/or `MedicineError`) mirroring AuthError's message-attribute + default-message shape — and have the new errors extend it. State it explicitly in Phase 4 change #1.
  - Strength: Keeps the error taxonomy clean per-domain and matches the router's "catch domain error → map to HTTP" pattern already in auth/router.py.
  - Tradeoff: One extra base class (trivial).
  - Confidence: HIGH — errors.py already establishes the exact pattern to copy.
  - Blind spot: None significant.
- **Decision**: FIXED — specified `CabinetError` base in Phase 4 change #1

### F2 — Unique-constraint race on add not handled (find→insert)

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Phase 4, change #4 (cabinet service add_entry)
- **Detail**: add_entry does find_entry → (merge+update | insert). Two POSTs for the same (user, registry_id, expiry_date) — a double-click on submit, made more likely by the "add another" flow that keeps the form open — can both miss find_entry and both attempt insert. The second hits uq_cabinet_entries_user_med_expiry (cabinet/models.py:10-17) and raises an unhandled IntegrityError → 500, not a merge or a clean error. The constraint is designed around this key, so the happy-path-only flow leaves its enforcement edge unhandled.
- **Fix A ⭐ Recommended**: Catch IntegrityError on insert, re-run find_entry, and merge into the now-existing row (treat the race as a merge).
  - Strength: Converges to the same correct end state FR-010 intends; no UX-visible failure on double-submit.
  - Tradeoff: One retry path + a transaction-state reset to reason about.
  - Confidence: MED — depends on session rollback semantics after the IntegrityError; verify with the async session.
  - Blind spot: Exact SQLModel/asyncpg rollback behavior not tested here.
- **Fix B**: Catch IntegrityError and map to a clean 409/422 "duplicate in flight — retry" at the router.
  - Strength: Minimal; no merge-retry logic.
  - Tradeoff: Surfaces a transient error to the user for what should silently merge.
  - Confidence: HIGH — pure mapping, mirrors existing router error handling.
  - Blind spot: None significant.
- **Decision**: FIXED — FE submit guard (Phase 6 #4) + backend IntegrityError→re-find→merge (Phase 4 #4). Single success-only popup confirmed; no UX change needed.

### F3 — Bad capacity on a tablet-based row: behavior unspecified

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 4, change #4 (Critical Implementation Details)
- **Detail**: The plan says to "guard a missing/non-integer capacity on a tablet-based row" but never says what the guard does — which error, which HTTP status, what the user sees. capacity is Decimal | None (medicines/models.py:23), so a tablet-based row with NULL/non-int capacity is a real data shape. Falls through to an unmapped 500.
- **Fix**: Name the outcome — e.g. raise a domain error (the new base from F1) mapped to 422 "registry entry has invalid capacity," and add it to the Phase 4 contract.
- **Decision**: FIXED (data-driven) — DB query returned 0 tablet-based rows with NULL/non-integer capacity; registry static this slice. Downgraded the vague guard to a cheap assert/log + recorded the verified invariant in the plan. No 422 path needed.

### F4 — Status uses UTC `today`; users are in Poland (UTC+1/+2)

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 1 (classify_status) / Critical Implementation Details
- **Detail**: classify_status takes `today` as a UTC date. Near midnight in Poland (UTC+1/+2) an entry expiring "today" could classify a day early/late at the valid↔expiring↔expired boundaries. Acceptable for MVP, but it's an unstated assumption worth recording.
- **Fix**: Note the UTC assumption explicitly (or compute `today` in the app's intended local zone). Either is fine — just make it a conscious decision, not an accident.
- **Decision**: FIXED — recorded explicit timezone policy: backend/DB UTC (status computed UTC-relative), frontend converts to the browser timezone for display. Boundary-near-midnight UTC behavior accepted for MVP. Added to Critical Implementation Details + Phase 6 list contract.

### F5 — Progress phase names don't match body phase headers

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: ## Progress vs ## Phase N headers
- **Detail**: Body headers (e.g. "## Phase 2: Backend — `GET /api/v1/medicines/products`") differ from the Progress entries ("### Phase 2: GET /medicines/products") for phases 2–6. The progress-format contract says Progress names should match the body headers. /10x-implement parses by phase number + checkbox index, so this will NOT break execution — but it's a documented-contract drift worth tidying.
- **Fix**: Align the Progress `### Phase N:` titles to the body `## Phase N:` titles (or shorten both consistently).
- **Decision**: FIXED — all six Progress `### Phase N:` titles aligned verbatim to the body `## Phase N:` headers.

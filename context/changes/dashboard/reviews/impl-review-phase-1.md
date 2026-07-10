<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Dashboard Implementation Plan

- **Plan**: context/changes/dashboard/plan.md
- **Scope**: Phase 1 of 4 (Backend summary endpoint)
- **Date**: 2026-07-10
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 1 warning, 3 observations

## Verification note

ruff check + format ✅, tests/cabinet ✅ (230 passed). Pyright and the DB-backed
integration tests abort under the OpenSSL applink quirk (L-001) from the Bash
tool — they were verified at commit time (1.3–1.6 marked `[x]` against d8b08c0).
`test_summary.py` was read directly to confirm coverage.

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

## Findings

### F1 — Summary re-implements filter rules inline instead of reusing _build_base_query

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Plan Adherence
- **Location**: backend/app/api/v1/cabinet/crud.py:449 (count_summary)
- **Detail**: Plan specified `count_entries(..., status=None, below_minimum=None) -> int` passing each filter INTO `_build_base_query` so counts and list share one definition (Critical Implementation Details: "Count definitions must reuse `_build_base_query`, not re-implement filters ... keeps the S-06 below-minimum rule in exactly one query path"). Implementation instead calls `_build_base_query(..., None, None)` unfiltered and re-derives each bucket as inline CASE (valid/expiring/expired boundaries + below-minimum). Correct today and mirrors crud.py:299–309 / 320–328, but the status boundaries and below-minimum rule now exist in three copies each (_build_base_query, count_summary, service.classify_status/is_below_minimum) instead of one. Count↔list invariant now held by manual sync (docstring: "keep all three in sync"). Genuine tradeoff: one aggregate query vs. the plan's five (a perf win the plan explicitly deemed unnecessary — "five count queries ... negligible for MVP").
- **Fix A ⭐ Recommended**: Keep the single-query implementation; amend the plan (Critical Implementation Details + Phase 1 contract) to describe conditional aggregation so the plan stops claiming reuse it no longer has.
  - Strength: Preserves better-performing, tested code; parity test guards status-count drift.
  - Tradeoff: below-minimum still lacks a list-parity test (F4); three-way duplication remains.
  - Confidence: HIGH — parity test exercises the exact divergence risk.
  - Blind spot: out_of_stock drift not caught by any parity test yet.
- **Fix B**: Refactor to the planned shape — a `count_entries` delegating filters to `_build_base_query`, called once per bucket.
  - Strength: Restores single-source-of-truth; matches list_entries' own count pattern (crud.py:393).
  - Tradeoff: Five queries per load; discards working, tested code for a perf regression the plan deemed negligible.
  - Confidence: MED — straightforward but re-opens a shipped, green phase.
  - Blind spot: None significant.
- **Decision**: FIXED via Fix A — plan amended (Critical Implementation Details + Phase 1 contracts #1/#2) to describe the single conditional-aggregation query.

### F2 — Stale docstring references the abandoned crud.count_entries approach

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/app/api/v1/cabinet/service.py:534 (summarize_cabinet docstring)
- **Detail**: Docstring says "Each count reuses `crud.count_entries`, which shares the same filtered query as `list_entries`, so the count and the corresponding filtered list always agree." No such function exists — code calls `crud.count_summary`, a single conditional-aggregation query. Describes the planned design, not the shipped one, and asserts a single-shared-query guarantee that F1 shows isn't literally true.
- **Fix**: Update the docstring to reference `crud.count_summary`, describe the single-aggregate approach and its manual-sync caveat.
- **Decision**: FIXED — docstring rewritten to describe `crud.count_summary`, the three synced rule copies, and the parity-test guard.

### F3 — "Brak zapasu" below-minimum-only narrowing awaits product sign-off

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Plan Adherence
- **Location**: backend/app/api/v1/cabinet/service.py (summarize_cabinet), crud.py:463
- **Detail**: Plan flagged a hard gate: "Confirm with the product owner that the 'Brak zapasu' number is intended as below-minimum-only before shipping." out_of_stock uses condition (b) only (package_count < minimum), not the full FR-020 badge (a: expiring/expired OR b: below-minimum). Code correctly implements the narrowed intent, but Manual item 1.6 is not evidence the product decision was made. A decision to close, not a code defect.
- **Fix**: Get explicit product sign-off that "Brak zapasu" = below-minimum-only before Phase 3 ships it to the UI; if the full badge is wanted, F1's scope decision must be revisited.
- **Decision**: CLOSED — product sign-off obtained 2026-07-10 (below-minimum-only). Recorded in change.md and the plan's "Brak zapasu" note; gate closed.

### F4 — No list-parity test for out_of_stock ↔ /cabinet/entries?below_minimum=true

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: backend/tests/integration/cabinet/test_summary.py:170
- **Detail**: Parity test loops only ("valid","expiring","expired") against the entries list. out_of_stock is the bucket whose rule is duplicated (F1) and flagged for sign-off (F3), yet its count is only asserted as an absolute (==1), never cross-checked against `GET /cabinet/entries?below_minimum=true`'s total — the seam most likely to silently drift.
- **Fix**: Extend the parity test to assert `summary["out_of_stock"] == entries(below_minimum=true).total`.
- **Decision**: FIXED — `test_summary_status_counts_match_entries_list_totals` now seeds a below-minimum important entry and asserts out_of_stock parity against `?below_minimum=true`. Not executed here (L-001 OpenSSL/applink quirk blocks alembic in the Bash tool); ruff clean, fixtures/params verified statically.

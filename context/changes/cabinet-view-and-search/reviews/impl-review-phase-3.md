<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Cabinet View and Search

- **Plan**: context/changes/cabinet-view-and-search/plan.md
- **Scope**: Phase 3 of 5
- **Date**: 2026-06-15
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical · 3 warnings · 0 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | WARNING |

Notes: backend `ruff check` + `ruff format --check` pass; 215 tests pass. The 8
`tests/db/` connection tests cannot run under the Bash tool (lessons L-001,
OpenSSL applink) — environment constraint, not a code defect. Parity, search,
pagination, and validation tests for Phase 3 are all present and green.

## Findings

### F1 — Parity test mirrors the SQL in Python instead of executing it

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Success Criteria
- **Location**: backend/tests/cabinet/test_service.py:210-240
- **Detail**: The plan's headline guard (Critical Implementation Details + criterion 3.3) is "a test must assert the SQL filter and the Python classifier agree." `TestStatusSQLParity` asserts a hand-written Python re-implementation `_sql_status()` equals `classify_status()`. It never executes the real predicates in `crud._build_base_query` (crud.py:159-169). If someone edits the actual SQL (e.g. flips `<` to `<=`), this test stays green — it only locks classify_status against its mirror, not against the query. Combined with L-001 (DB tests can't run under the Bash toolchain), the real predicates have no parity coverage running in that lane.
- **Fix A ⭐ Recommended**: Add a DB-backed integration test (PowerShell/CI DB lane) that seeds entries on the boundary dates and asserts each `status=` filter returns exactly the rows classify_status would label — exercising the real SQL.
  - Strength: Closes the loop the plan asked for; catches a real edit to `_build_base_query`.
  - Tradeoff: Needs a DB fixture; runs only in the DB lane (L-001), not under the Bash tool.
  - Confidence: HIGH — the join/predicate is small and seed-testable.
  - Blind spot: Haven't confirmed a DB integration harness exists yet in this repo's suite.
- **Fix B**: Keep the mirror test but bind it to the SQL via a single shared constant for the predicate boundaries used by both crud and the test.
  - Strength: Cheap; no DB needed.
  - Tradeoff: Still doesn't execute real SQL — weaker guarantee.
  - Confidence: MED — reduces drift risk but not the core gap.
  - Blind spot: A future SQL typo outside the shared constant slips through.
- **Decision**: DEFERRED-TO-E2E — queued in follow-ups/review-fixes.md with boundary-seeding requirement.

### F2 — build_tsquery relocated and called from service, not facade

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: backend/app/utilities/common.py:12 ; backend/app/api/v1/cabinet/service.py:254
- **Detail**: Plan items 1 & 5 said: promote `_build_tsquery` to public in medicines/service.py, and have the facade call `medicines_service.build_tsquery(q)`. Actual: it was moved to a new `app/utilities/common.py` (domain-neutral) and is called from the cabinet *service*; the facade forwards raw `search`. This is arguably cleaner — a shared util sidesteps the cross-domain hop and does NOT violate the facade rule (no domain crosses a domain). But it diverges from two plan items and leaves the plan's architectural rationale ("cross-domain reuse goes through the facade") stale.
- **Fix**: Add a short plan addendum (same style as the Phase 2 F1 addendum) noting build_tsquery became a shared utility called from the service, superseding plan items 1 & 5's facade routing.
- **Decision**: FIXED — addendum added to plan.md Phase 3 (impl review F2).

### F3 — Query-param model drops `sort`, renames `q`→`search`

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: backend/app/api/v1/cabinet/schemas.py:13-22 ; backend/app/api/v1/cabinet/router.py:42
- **Detail**: Plan item 7 enumerated inline `Query()` params including `sort: Literal["name"]="name"` and `q`. Implementation uses one `CabinetListParams` Pydantic model (a fine, cleaner approach; L-003 satisfied via field-level NonEmptyStr, proven by the whitespace test). But it (a) omits `sort` entirely and (b) renames `q`→`search` (the latter is correct per the new lesson L-005). With `extra="forbid"`, the plan's own documented URL contract (`?q=apap&sort=name&order=desc`, Overview line 60) now returns 422. The Phase-4 frontend matches (no `sort`, uses `search`), so there's no live break — but a hand-crafted/S-07 deep-link using the old contract would 422.
- **Fix**: In the same addendum, record the param-shape change (model, `q`→`search`, `sort` dropped because only name sort exists), and optionally re-add `sort: Literal["name"]="name"` to the model for forward-compat shareable URLs.
- **Decision**: FIXED (addendum only) — param-shape change documented in plan.md Phase 3; `sort` left dropped per decision.

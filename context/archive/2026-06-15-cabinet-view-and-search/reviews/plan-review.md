<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Cabinet View and Search

- **Plan**: context/changes/cabinet-view-and-search/plan.md
- **Mode**: Deep
- **Date**: 2026-06-15
- **Verdict**: REVISE → SOUND after triage (all 4 findings fixed in plan, 2026-06-15)
- **Findings**: 0 critical, 3 warnings, 1 observation
- **Re-grounded**: 2026-06-15 against plan.md after commit 9f8c387 (producer drop); F1–F3 unchanged, F4 added.

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | WARNING |
| Plan Completeness | WARNING |

> Re-grounding note (2026-06-15): commit 9f8c387 ("drop producer display field") removed the producer field from the Phase 1/2 *contracts* (now three fields: `route_of_administration`, `leaflet_url`, `specification_url`) but left nine producer/"four new fields" references in prose, verification, and one instruction. Captured as F4 below. F1–F3 are unaffected by that edit and remain valid.

## Grounding

10/10 paths ✓, symbols ✓ (`_build_tsquery`@medicines/service.py:20, `classify_status`@cabinet/service.py:127, `Status` enum = valid/expiring/expired, `search_vector` built with `to_tsvector('simple')` ↔ plan's `to_tsquery('simple')`, `NonEmptyStr`@medicines/router.py:23, `use-debounce` hook@src/hooks/use-debounce.ts, `useCabinetEntries`/`cabinetKeys`/`useAddEntry`), brief↔plan ✓. Progress↔Phase mechanical contract ✓ (one `## Progress`, all phases mirrored, every success-criteria bullet has a matching checkbox). Status SQL↔`classify_status` parity rule in the plan matches the classifier exactly.

## Findings

### F1 — Offset pagination has no deterministic tiebreaker

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 3 — crud "sort → ORDER BY lower(medication_registry.name)"
- **Detail**: Sort is name-only and pagination uses LIMIT/OFFSET. When two cabinet entries share a medication name (normal — e.g. two boxes of the same drug with different expiry dates as separate entries), their relative order under `ORDER BY lower(name)` is undefined and can differ between the page query and successive requests, causing a row to be repeated on one page and skipped on the next at page boundaries. classify_status/parity is unaffected; this is purely an ordering-stability gap the plan doesn't mention.
- **Fix**: Append an immutable unique tiebreaker to the ORDER BY in the page query, e.g. `ORDER BY lower(medication_registry.name) <asc|desc>, cabinet_entries.id ASC`. The COUNT query is unaffected. Note that the asc/desc toggle flips only the name key, not the tiebreaker.
- **Decision**: FIXED (Fix in plan — Phase 3 crud ORDER BY updated)

### F2 — `NonEmptyStr` is router-private to medicines; reuse path unspecified

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 3 — router params (`q: NonEmptyStr | None = None`)
- **Detail**: The router contract reuses `NonEmptyStr`, but that alias is defined privately inside `medicines/router.py:23` (commented as scoped "in this router") — there is no shared home. As written, the cabinet router would have to import a sibling router's private alias or silently redefine it. Separately, the plan's own L-003 note says "all Query() inside Annotated," yet `q: NonEmptyStr | None = None` carries no `Query()` — functionally safe (None default, not a Query() default, so L-003's trap doesn't fire), but it drops any OpenAPI description and is inconsistent with the stated convention.
- **Fix**: Decide where `NonEmptyStr` lives for cabinet — redefine it locally in `cabinet/router.py` (mirrors medicines) or promote it to a shared module — and write the param as `q: Annotated[NonEmptyStr, Query(description=...)] | None = None` to match the plan's own "Query() inside Annotated" rule.
- **Decision**: FIXED (Fix differently — promoted `NonEmptyStr` to new `app/utilities/types.py`; both routers import it; new Phase 3 §6, §7 amended with `Annotated[..., Query(description=...)]`. Widens Phase 3 blast radius to `medicines/router.py`.)

### F3 — Envelope break is verification-noted but not deploy-noted

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Critical Implementation Details / Open Risks
- **Detail**: The plan correctly flags that Phase 3 switches the response to an envelope and breaks the Phase-1/2 frontend until Phase 4, verified via Swagger. It doesn't state the deploy consequence: Phase 3 must not merge/ship to any environment ahead of Phase 4, or the live cabinet list breaks. Within one feature branch this is implicit; worth one explicit line.
- **Fix**: Add a one-line constraint: "Phases 3 and 4 land in the same merge/deploy; Phase 3 is never shipped standalone."
- **Decision**: FIXED (Fix in plan — deploy-coupling line added to the envelope note in Critical Implementation Details)

### F4 — Producer drop left nine stale references, including a live instruction to build the cut field

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Plan Completeness (also Lean Execution)
- **Location**: Overview / Phase 1 §2 / Phase 1 Manual Verification / Phase 2 §1–§2 / Progress 1.4
- **Detail**: Commit 9f8c387 dropped producer from the field contracts — Phase 1 §1 (line 142) and Phase 2 §1 (line 194) now add exactly three fields (`route_of_administration`, `leaflet_url`, `specification_url`). But nine references still describe a four-field, producer-bearing feature: Overview "registry-sourced producer" (line 10); Phase 1 §2 intent "carries its producer" (line 140) and "applying the producer fallback rule" (line 151) — a **live instruction** to implement a fallback for a field that no longer exists; Phase 1 Manual Verification "shows the four new fields" (line 170); Phase 2 §1 "Show the producer" (line 182); Phase 2 §2 "Mirror the four new backend fields" (line 192) and the `Producent` detail label (line 203); Progress 1.4 "four new fields" (line 497). An implementer following line 151/203 would re-add the descoped producer field and its fallback; line 170/497 verification would fail against a three-field response. (The line 481 References entry "Producer-field origin" is provenance and can stay.)
- **Fix**: Reconcile the prose to the three-field contract: change "four new fields" → "three new fields" (lines 170, 192, 497); strike "producer" from the Overview field list (line 10) and Phase 1 §2 intent (line 140); delete "applying the producer fallback rule" (line 151); drop "producer"/`Producent` from Phase 2 §1 intent (line 182) and §2 detail labels (line 203). Leave the line 481 References provenance note as-is.
- **Decision**: FIXED (Fix in plan — all eight in-scope references reconciled to three fields; References provenance note kept; verified only the line-481 provenance reference remains)

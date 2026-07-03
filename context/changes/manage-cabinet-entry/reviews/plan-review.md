<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Manage Cabinet Entry (FR-005)

- **Plan**: context/changes/manage-cabinet-entry/plan.md
- **Mode**: Deep
- **Date**: 2026-07-03
- **Verdict**: REVISE → SOUND (all 4 findings fixed 2026-07-03)
- **Findings**: 0 critical, 2 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | WARNING |
| Plan Completeness | WARNING |

## Grounding

11/11 paths ✓ (`components/ui/` is the new dir the plan creates, not a miss);
backend symbols ✓ (`update_entry_counts` crud.py:503, `find_entry_by_id` :433,
`set_entry_usage` service.py:897, `_validate_and_get_tpp` :547, `_get_variant_or_raise`
:525; all error classes present in errors.py); frontend symbols ✓ (mutation-hook
invalidate pattern cabinet-queries.ts, `OUT_OF_STOCK_LABEL` use-cabinet-entry.ts:5,
`is_important`/`is_used`/`below_minimum` on `CabinetEntryOut` schemas.py); brief↔plan ✓;
Progress↔Phase mechanically consistent ✓.

## Findings

### F1 — Quantity route mis-maps CabinetInvariantError to 400 (should be 500)

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 3 §4 — Quantity route (plan.md:205)
- **Detail**: The plan says the quantity route mirrors "the same except-ladder as the other PATCH handlers" — i.e. `set_entry_usage` (router.py:199-224), which does NOT catch `CabinetInvariantError` because `validate_usage` never raises it. But the quantity service (Phase 3 §2) reuses `_validate_and_get_tpp` (service.py:547) — the only other caller besides the add path — which CAN raise `CabinetInvariantError` (tablet variant with invalid capacity, service.py:568). Since `CabinetInvariantError` subclasses `CabinetError` (errors.py:279), the specified ladder catches it at `CabinetError → 400`. That contradicts the error class's own docstring ("The router maps this to 500") and the add route, which explicitly maps it to 500 (router.py:123-126). A corrupt-data breach would surface as a client 400 instead of 500.
- **Fix**: In the Phase 3 §4 contract, add an explicit `except CabinetInvariantError → 500` branch (before the generic `CabinetError → 400`), matching the add route rather than the usage route. `CabinetInvariantError` is already imported in router.py.
- **Decision**: FIXED — added `CabinetInvariantError → 500` (before generic `CabinetError → 400`) to the Phase 3 §4 route contract.

### F2 — Absolute-value quantity PATCH races on rapid −/+ clicks

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Phase 4 §2 — steppers (plan.md:246-248); Performance (plan.md:335)
- **Detail**: The brief picks absolute values to "avoid delta races," but absolute values computed from a stale client base introduce a different race. With no optimistic updates, the stepper derives the new count from the last-fetched list entry. Two fast decrements from base N both compute N-1 and both PATCH N-1 → net −1 instead of −2, because the refetch from click 1 hasn't landed when click 2 fires. The Performance section frames rapid clicks purely as a lag/refetch-cost issue ("softened by keepPreviousData") and doesn't flag the correctness loss. Nothing in the Phase 4 contract disables the stepper while a quantity mutation is in flight.
- **Fix**: Disable −/+ (and defer the zero-delete branch) while `useUpdateQuantity`/`useDeleteEntry` `isPending`; `keepPreviousData` keeps the number visible. Add to the Phase 4 §2 contract and manual criterion 4.4.
  - Strength: One-line guard; kills the race without optimistic state; matches the plan's "list stays authoritative" stance.
  - Tradeoff: Slightly slower feel on very rapid clicks (one PATCH at a time) — acceptable at PRD `low` scale.
  - Confidence: HIGH — `isPending` is already available from the mutation hook.
  - Blind spot: Whether desktop row and mobile card share the pending flag via use-cabinet-entry.ts (they should, per the plan's "one implementation" goal).
- **Decision**: FIXED — added a rapid-click race guard (disable −/+ while `isPending`) to Phase 4 §2 contract + new manual criterion 4.8 (and Progress 4.8).

### F3 — "Uncategorised entry at 0" is UI-reachable, not just raw-API

- **Severity**: 🔎 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: What We're NOT Doing (plan.md:46); brief Open Risks (:56)
- **Detail**: The plan accepts an uncategorised-at-0 entry as a raw-API-only edge ("the UI is the only client"). But it's reachable through the UI: an important entry decremented to 0 (kept at 0 by the rule) can then be un-starred via the existing importance toggle → uncategorised, at 0 — exactly the state the zero-delete rule exists to prevent. Not harmful (shows out-of-stock), but the "only a raw caller can do this" justification is inaccurate.
- **Fix**: Reword the NOT-doing note to acknowledge the un-star path, or note that un-starring a 0-count entry is out of scope for the zero rule. No behavior change needed.
- **Decision**: FIXED — reworded the "Server-enforced zero invariant" NOT-doing note to acknowledge the un-star→uncategorised-at-0 path and scope it out of the zero rule.

### F4 — Zero-delete silently discards loose tablets (partial_tablet_count)

- **Severity**: 🔎 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 4 §2 — zero rule (plan.md:246)
- **Detail**: Decrementing an uncategorised tablet entry from package_count 1 → 0 deletes it. If that entry also has partial_tablet_count > 0 (loose tablets in the opened package), the delete discards them with no mention in the confirm copy. The model treats package_count as the sole "do we still hold this?" signal, but a tablet entry can be 0 packages + N loose tablets. Low confidence — depends on product semantics of package_count for opened tablet packs.
- **Fix**: Decide intended semantics. Simplest: leave as-is (delete is explicit + confirmed) but consider mentioning loose tablets in the confirm message when partial_tablet_count > 0. No code-path change required for MVP.
- **Decision**: FIXED (mention in confirm copy) — Phase 4 §2 zero-delete copy now appends a sentence noting loose tablets are discarded when `partial_tablet_count > 0`.

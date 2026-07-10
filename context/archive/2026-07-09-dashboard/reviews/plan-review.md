<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Dashboard Implementation Plan

- **Plan**: context/changes/dashboard/plan.md
- **Mode**: Deep
- **Date**: 2026-07-09
- **Verdict**: REVISE
- **Findings**: 0 critical, 1 warning, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | WARNING |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | PASS |
| Plan Completeness | WARNING |

## Grounding

15/15 paths ✓, 4/4 symbols ✓ (`_build_base_query`, `_resolve_prefs`, `func.count().select_from()`, `is_below_minimum`), brief↔plan ✓, Progress↔Phase consistent ✓, `expiry_date` NOT NULL so the `total == valid + expiring + expired` partition holds ✓, route ordering clean (all entry routes are `/entries` or `/entries/{entry_id}`; no bare `/{param}` shadows `/summary`) ✓.

## Findings

### F1 — "Brak zapasu" count uses below_minimum only; FR-020's badge is broader

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: End-State Alignment
- **Location**: Phase 1 #2, Critical Implementation Details, Phase 3 card config
- **Detail**: FR-009 counts "out-of-stock badges active". FR-020 defines that badge as firing on an important entry when ANY of: (a) close to expiry / expired, OR (b) package count below minimum. The plan's out_of_stock count passes `below_minimum=True`, which in `cabinet/crud.py:319` and `service.is_below_minimum` (`service.py:159`) is exactly `is_important AND package_count < min_package_count` — condition (b) ONLY. An important medication that is expiring/expired but has enough packages has the badge active per FR-020 yet is not counted. The plan can pass all of its own success criteria (which assert only below_minimum parity) while diverging from FR-009 as literally specified. Tension with scope: the cabinet exposes `status` and `below_minimum` as *separate* filters — there is no single filter for "important AND (expiring/expired OR below-min)". The plan's core invariant ("count and list always agree because both derive from the same query") plus "no new cabinet filters" is partly what forces the narrow definition. This is a product decision, not a mechanical bug.
- **Fix A ⭐ Recommended**: Keep below_minimum-only; make the narrowing explicit and get sign-off
  - Strength: Preserves the count↔list invariant and the "no new cabinet filters" scope with zero cabinet changes. The PRD's FR-020 Socrates note already treats "out of stock" as a working name whose display copy is a UI concern.
  - Tradeoff: Count is narrower than a strict reading of FR-009; needs confirmation that below-minimum is the intended number.
  - Confidence: HIGH — matches the existing filter and keeps the invariant the plan is built around.
  - Blind spot: Whether the product owner reads FR-009 as the full badge is unverified — this fix asks you to confirm it.
- **Fix B**: Match FR-020's full badge (a OR b)
  - Strength: Count reflects FR-009/FR-020 literally.
  - Tradeoff: No existing cabinet filter yields that set, so either (i) add a new combined cabinet filter — breaking the "no new filters" scope — so the card link still agrees with the count, or (ii) let the card link show a subset and break the count↔list invariant. Both are costly.
  - Confidence: MED — correctness-faithful but forces a scope decision the plan deliberately closed.
  - Blind spot: Double-counting semantics vs the expiring/expired cards not thought through.
- **Decision**: FIXED via Fix A — narrowing made explicit in Critical Implementation Details + flagged for product sign-off; cross-referenced at Phase 1 #2.

### F2 — Literal summary key duplicated in cabinet mutations + soft "whichever import direction" wording

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 2 #2 and #3
- **Detail**: `dashboardKeys.summary()` is declared as the canonical `["cabinet","summary"]` key, but Phase 2 #3 has the five cabinet mutations invalidate the *literal* `["cabinet","summary"]` to avoid a cabinet→dashboard import. Defensible, but leaves two copies of the key that can silently drift. The contract also says "match whichever import direction the repo prefers" before landing on a recommendation — slightly soft for an implementer.
- **Fix**: Keep the literal-key approach (correct dependency direction), add a short comment at the cabinet-mutation invalidation pointing to `dashboardKeys.summary()` as the source of truth, and drop the "whichever the repo prefers" hedge so the instruction is unambiguous.
- **Decision**: FIXED — Phase 2 #3 contract now mandates the literal key, forbids the cabinet→dashboard import, and requires a sync comment against `dashboardKeys.summary()`.

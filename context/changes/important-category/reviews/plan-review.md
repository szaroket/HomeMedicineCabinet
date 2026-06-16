<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Important Category Implementation Plan

- **Plan**: context/changes/important-category/plan.md
- **Mode**: Deep
- **Date**: 2026-06-16
- **Verdict**: REVISE → SOUND (all 4 findings fixed during triage 2026-06-16)
- **Findings**: 1 critical · 1 warning · 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | WARNING |
| Plan Completeness | FAIL |

## Grounding

12/12 backend paths ✓, 8/8 frontend paths ✓ (settings/ + users/schemas.py correctly absent), symbols ✓ (const/errors/facade/service/schemas/crud/models confirmed; EntryNotFoundError correctly flagged as to-add), brief↔plan ✓.

## Findings

### F1 — Phase-body Success Criteria use `- [ ]` checkboxes

- **Severity**: ❌ CRITICAL
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Every phase, "#### Automated/Manual Verification:" blocks
- **Detail**: The mechanical Progress↔Phase contract requires phase blocks to contain plain `- ` bullets only — `- [ ]`/`- [x]` are reserved for the `## Progress` section, or /10x-implement may mis-parse Progress. This plan has 64 `- [ ]` lines because every Success Criteria bullet in every phase body is a checkbox (e.g. plan.md:96-102, 504-510). The prior, successfully-implemented plan (archive/2026-06-15-cabinet-view-and-search/plan.md:166-168) uses plain `- ` in phase bodies and `- [ ]` only under `## Progress` (2 checkbox lines total vs. this plan's 64). This plan inverted that.
- **Fix**: Convert the `- [ ]` bullets inside the `#### Automated Verification:` / `#### Manual Verification:` blocks of each phase body to plain `- `. Leave the numbered checkboxes in the `## Progress` section (lines 500-587) untouched — those are correct.
- **Decision**: FIXED — converted 32 phase-body checkbox bullets to plain `- ` (lines 1–495); Progress section untouched.

### F2 — Existing-test blast radius not enumerated

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Phases 3–5 (Success Criteria say only "Backend tests pass")
- **Detail**: Phase 3 adds required fields `is_important` / `below_minimum` to CabinetEntryOut and new params to service/facade `list_entries`. That breaks existing tests the plan never names: (1) tests/cabinet/test_router.py:215 — `_make_cabinet_entry_out` factory builds CabinetEntryOut from a fixed defaults dict; new required fields make every test using it fail validation. (2) tests/cabinet/test_service.py — ~8 `list_entries(...)` call sites (lines 545–689) break if `min_package_count` is required. (3) tests/cabinet/test_facade.py:40,51,69 — assert on `service.list_entries.call_args.kwargs`; new kwargs (`category`, `min_package_count`) change the asserted dict. "Backend tests pass" is a success criterion, but the work to keep them green isn't scoped. The prior plan did enumerate this ("Existing list_entries service test updated to assert the three new fields") — this plan dropped that habit.
- **Fix**: Add an explicit step to Phases 3/4/5 to update the named existing tests/factory, and prefer keyword params with sane defaults (e.g. `min_package_count` last) to minimize churn.
  - Strength: Turns a surprise mid-build cascade into planned work; matches the prior slice's convention.
  - Tradeoff: Slightly longer phase descriptions.
  - Confidence: HIGH — the factory and call sites are confirmed in tree (test_router.py:215, test_service.py:545+).
  - Blind spot: Haven't counted every test that calls the factory.
- **Decision**: FIXED — added explicit "Update existing tests" steps to Phases 3 (item 6), 4 (item 4), 5 (item 5) naming the factory + call sites, with defaulted-kwarg guidance.

### F3 — `_map_row_to_entry_out` signature change not spelled out

- **Severity**: 🔎 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 3, item 4
- **Detail**: The plan says `_map_row_to_entry_out` sets `below_minimum=is_below_minimum(...)`, but the mapper currently takes only `(entry, variant, today, expiry_threshold_days)` (service.py:170) — it has no `min_package_count`. The implementer must thread it through the mapper too (Phase 4 reuses the same mapper and its service signature already carries min_package_count, so it's implied — just make it explicit for Phase 3).
- **Fix**: Note that `_map_row_to_entry_out` gains a `min_package_count` parameter.
- **Decision**: FIXED — Phase 3 item 4 Contract now states the mapper gains a `min_package_count` parameter.

### F4 — Phase 4 404 handler must precede the CabinetError→400 catch-all

- **Severity**: 🔎 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 4, item 3 (router)
- **Detail**: The new `EntryNotFoundError(CabinetError)` subclasses CabinetError. The existing list route maps `CabinetError → 400` (router.py:61), so if the new PATCH route catches CabinetError before the not-found type, a missing entry returns 400 instead of 404. Precedent for the correct ordering exists: `MedicationNotFoundError` is caught before CabinetError in `add_entry` (router.py:96).
- **Fix**: Order the `except EntryNotFoundError → 404` branch before the generic `except CabinetError → 400` in the PATCH handler.
- **Decision**: FIXED — Phase 4 item 3 Intent now requires the 404 branch to precede the CabinetError→400 catch-all.

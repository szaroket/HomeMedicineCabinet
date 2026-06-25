<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Dosage Tracking (S-05)

- **Plan**: context/changes/dosage-tracking/plan.md
- **Mode**: Deep
- **Date**: 2026-06-25
- **Verdict**: REVISE
- **Findings**: 0 critical, 3 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | WARNING |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | WARNING |
| Plan Completeness | WARNING |

## Grounding

10/10 paths ✓, symbols ✓ (total_tablets, _map_row_to_entry_out, _merge_and_commit, _insert_with_race_guard, _build_base_query, CabinetCategory all confirmed), brief↔plan ✓, Progress↔Phase ✓ (6 phases, all automated/manual subsections match plan body). `docs/reference/contract-surfaces.md` absent — contract-surface check skipped.

## Findings

### F1 — Merge-overwrite silently wipes an existing schedule on restock

- **Severity**: ⚠️ WARNING
- **Impact**: 🔬 HIGH — architectural stakes; think carefully before deciding
- **Dimension**: Blind Spots / End-State Alignment
- **Location**: Phase 1 §3 (merge-overwrite); Phase 1 §1 (AddEntryRequest)
- **Detail**: The plan chose "incoming usage overwrites on merge" and contrasts it with importance, which is OR'd. The two are asymmetric: importance-OR can never lose state, usage-overwrite can. Common case — a user restocking the same drug+expiry sends a second `POST /cabinet/entries` that adds packages but carries no usage fields (the add form can't know it's a dup before submit, so it won't re-send the schedule). With overwrite semantics + `is_used` defaulting to False, that restock clears `is_used` and nulls every dosage/date column — the schedule silently vanishes, and the finish-date calc that "stock already reflects use" depends on disappears. `_merge_and_commit` (service.py:634) today only touches counts/importance; the plan extends it to overwrite usage unconditionally. Also: the plan lists `is_used: bool` on UsageFields with no default — if it lands required, it's a breaking change to the existing POST contract (every current add client/test must now send `is_used`).
- **Fix A ⭐ Recommended**: Overwrite usage on merge ONLY when the incoming POST provides usage; otherwise preserve existing. Make `is_used: bool = False`.
  - Strength: Restock keeps the schedule; "incoming wins" still holds when the caller actually expresses usage intent. Matches the non-destructive spirit of the importance-OR merge.
  - Tradeoff: "Provided usage" needs a sentinel (usage omitted vs is_used=false) — a small contract nuance to specify.
  - Confidence: HIGH — restock-without-usage is the dominant real path.
  - Blind spot: Need to define how an explicit unassign-on-add (is_used=false with a prior schedule) behaves — likely still clears.
- **Fix B**: Keep unconditional overwrite, but document it and have the add form pre-fetch existing usage to repopulate before a dup submit.
  - Strength: Single, simple merge rule on the backend.
  - Tradeoff: Pushes correctness into the UI; any non-form client (or a user who doesn't re-enter dosage) still wipes the schedule.
  - Confidence: MEDIUM — relies on every caller cooperating.
  - Blind spot: Add form doesn't currently detect dups pre-submit at all.
- **Decision**: PENDING

### F2 — Threading chain skips `_insert_with_race_guard`

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 1 §3
- **Detail**: The plan's contract says `add_entry` threads usage into `_dedup_or_insert`, then "`crud.insert_entry` gains usage params." But the insert path is `_dedup_or_insert` → `_insert_with_race_guard` (service.py:406) → `crud.insert_entry`. The intermediate `_insert_with_race_guard` must also forward the usage params; it's unnamed in the plan, so the implementer could miss it and usage would never reach a fresh insert.
- **Fix**: Name `_insert_with_race_guard` in the threading chain (it forwards usage params to crud.insert_entry), alongside `_dedup_or_insert` and `_merge_and_commit`.
- **Decision**: PENDING

### F3 — `compute_usage_view` doesn't guard tablet variant with invalid capacity

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 3 §1
- **Detail**: The plan says compute_usage_view returns all-None when "not used or non-tablet." But `_map_row_to_entry_out` (service.py:210-221) already handles a third case: a tablet-based variant whose `capacity` is None or ≤0 → `tpp=None` → `total_tablets=None` (it logs a warning). For such a "used" tablet entry, `days_of_supply(None, rate)` has no defined behavior in the plan.
- **Fix**: Specify that compute_usage_view also returns all-None when total_tablets is None (tpp unavailable), mirroring the existing capacity-invalid guard.
- **Decision**: PENDING

### F4 — `validate_usage` start-date default breaks purity/testability

- **Severity**: 📋 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 1 §2
- **Detail**: validate_usage is described as a pure validator but also "defaults dosage_start_date to UTC today when omitted." If it calls datetime.now() internally it's no longer pure and its tests can't pin a deterministic today — at odds with the project's pure-function-in-service convention and the parametrized-test plan for Risk #6.
- **Fix**: Pass `today: date` into validate_usage rather than reading the clock inside it.
- **Decision**: PENDING

### F5 — Phase 1 manual verification depends on Phase 3 (GET)

- **Severity**: 📋 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 1 Manual Verification
- **Detail**: Phase 1's manual check "persists is_used + dosage columns" can't be observed via API until Phase 3's GET lands — the plan acknowledges this ("verify via DB or a follow-up GET"). Not a blocker; just means Phase 1 manual sign-off needs DB inspection or deferral.
- **Fix**: None required — acknowledged. Optionally note the DB-inspection step explicitly so it isn't mistaken for a gap.
- **Decision**: PENDING

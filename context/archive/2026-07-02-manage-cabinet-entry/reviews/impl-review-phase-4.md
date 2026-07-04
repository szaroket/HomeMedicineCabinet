<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Manage Cabinet Entry (FR-005)

- **Plan**: context/changes/manage-cabinet-entry/plan.md
- **Scope**: Phase 4 of 5
- **Date**: 2026-07-03
- **Verdict**: APPROVED
- **Findings**: 0 critical, 1 warning, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

## Findings

### F1 — Partial-tablet input has no accessible name

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: frontend/src/features/cabinet/components/cabinet-list.tsx (~118) and cabinet-card.tsx (~145) — the `<input name="partial" …>` in the partial-tablet form
- **Detail**: The −/+ steppers correctly carry `aria-label` ("Zmniejsz/Zwiększ liczbę opakowań"), but the loose-tablet `<input>` ships only a `placeholder` ("Pełne opak.") and a `name` — no label association and no `aria-label`. Placeholder is not a reliable accessible name, and the text describes the empty state, not the field's purpose. Conflicts with the standing project rule (prefer real a11y over test-ids) and affects Phase 5: the e2e spec must locate this field, and `getByLabel` would be the intended locator.
- **Fix**: Add `aria-label="Liczba luźnych tabletek"` to the partial-tablet `<input>` in both cabinet-list.tsx and cabinet-card.tsx (keep the placeholder as a hint).
  - Strength: Restores parity with the steppers' a11y and gives the Phase-5 spec a stable `getByLabel` locator.
  - Tradeoff: None significant — two-line change.
  - Confidence: HIGH — matches the aria-label pattern already used on the steppers in the same components.
  - Blind spot: None significant.
- **Decision**: FIXED — added `aria-label="Liczba luźnych tabletek"` to the partial `<input>` in cabinet-card.tsx and cabinet-list.tsx.

### F2 — capacity-null fallback rejects all partial values

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality (reliability)
- **Location**: frontend/src/features/cabinet/hooks/use-cabinet-entry.ts:240-242
- **Detail**: `const capacity = entry.capacity ?? 0;` then reject on `parsed >= capacity`. If a tablet-based entry ever has null capacity, every value is rejected and the message reads "Podaj liczbę od 1 do 1" (`Math.max(0-1,1)`). In practice a tablet-based entry always carries `capacity` = tablets-per-package, so this is a defensive fallback rather than a live bug — the input only renders under `entry.is_tablet_based`, and the backend re-validates.
- **Fix**: Optionally hide/disable the partial editor when `entry.capacity == null`, or leave as-is (backend is authoritative). No action required.
- **Decision**: FIXED — added an explicit `capacity == null` guard in use-cabinet-entry.ts that rejects with a clear message and dropped the `?? 0` fallback so the range hint is always accurate.

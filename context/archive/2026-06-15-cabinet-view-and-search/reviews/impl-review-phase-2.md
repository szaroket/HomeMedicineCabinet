<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Cabinet View and Search

- **Plan**: context/changes/cabinet-view-and-search/plan.md
- **Scope**: Phase 2 of 4
- **Date**: 2026-06-15
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical · 2 warnings · 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | WARNING |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | WARNING |

## Findings

### F1 — Dawka/Postać columns moved into detail panel, beyond the contract

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: frontend/src/features/cabinet/components/cabinet-list.tsx:72-78,153-167
- **Detail**: The Phase 2 contract listed detail labels as exactly `Droga podania`, `Ulotka`, `Charakterystyka`. The implementation also pulled `Dawka` (strength) and `Postać` (pharmaceutical_form) out of the main table columns into the expandable detail, dropping the table from 7 to 5 columns. Not in the written contract — though it aligns with the Phase 2 Overview ("Keeps the table scannable on mobile by revealing details in an expandable row"). Benign and arguably an improvement.
- **Fix**: Accept and note as a plan addendum (table slimmed; Dawka/Postać moved to detail to keep it scannable). No code change needed.
- **Decision**: FIXED — added addendum to plan.md Phase 2 contract

### F2 — Row expand toggle is mouse-only (no keyboard / ARIA)

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: frontend/src/features/cabinet/components/cabinet-list.tsx:48-66
- **Detail**: The whole `<tr>` toggles via onClick + cursor-pointer, and the chevron is a decorative `<svg>` with no a11y wiring. There's no tabIndex, role, aria-expanded, or onKeyDown, so keyboard and screen-reader users can't expand a row. The plan called for "a toggle (chevron) controlling a collapsible detail sub-row" — implying an operable control. (The link stopPropagation + rel="noopener noreferrer" are done well — no reverse-tabnabbing, no accidental toggle.) Note: manual criterion 2.6 mobile/usability is still unchecked.
- **Fix**: Make the chevron cell a `<button aria-expanded={expanded} aria-label="Pokaż szczegóły">` driving the toggle (keep the row click as a convenience), so it's keyboard- and SR-operable.
- **Decision**: FIXED — chevron wrapped in accessible button (aria-expanded, aria-label, stopPropagation)

### F3 — `prettier --check src/` fails on 16 files, yet 2.3 marked done

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: frontend/ (16 files; NOT cabinet-list.tsx / cabinet-api.ts)
- **Detail**: Progress 2.3 ("Format passes — prettier --check src/") is checked `[x]`, but the check currently fails on 16 files (use-debounce.ts, dashboard-page.tsx, app-header.tsx, cabinet-page.tsx, …). The two Phase 2 files are clean — this is pre-existing formatting debt across the frontend, not a Phase 2 regression. But the criterion as written does not pass. Build (2.1) and lint (2.2) verified passing.
- **Fix**: Run `cd frontend && npx prettier --write src/` as a standalone formatting-cleanup commit so the documented check passes again.
- **Decision**: FIXED — ran prettier --write src/; `prettier --check src/` now passes (16 files reformatted)

## Notes

- Phase 2 changed exactly the two planned files (`cabinet-api.ts`, `cabinet-list.tsx`); no unplanned files touched.
- Plan adherence is solid: TS types mirror the backend, the three required Polish detail labels are present, links open in a new tab with `noopener noreferrer`, missing values degrade to "—", and expansion is local component state per the contract.
- Automated checks run during review: `npm run build` ✅, `npm run lint` ✅, `prettier --check src/` ❌ (see F3).

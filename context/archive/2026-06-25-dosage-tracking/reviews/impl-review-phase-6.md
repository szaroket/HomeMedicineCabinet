<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Dosage Tracking (S-05)

- **Plan**: context/changes/dosage-tracking/plan.md
- **Scope**: Phase 6 of 6 (PATCH frontend — inline usage form on the card)
- **Date**: 2026-06-29
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 3 warnings, 1 observation

> Scope note: the working-tree "modifications" to 5 files are pure LF→CRLF line-ending
> noise (no content change). Real reviewed scope = commit `e7c4b15`. Frontend `build`
> (tsc+vite) and `lint` (2 benign warnings, 0 errors) pass.

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | WARNING |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | WARNING |

## Findings

### F1 — Dosage UI + zod refinement duplicated instead of reusing DosageFields

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Plan Adherence / Pattern Consistency
- **Location**: frontend/src/features/cabinet/components/usage-edit-form.tsx:76-182 · frontend/src/features/cabinet/schemas/cabinet-schemas.ts:71-130
- **Detail**: The plan states twice that Phase 6 should "reuse the DosageFields component" (Phase 6 Overview + §2) and "Reuse the same zod refinement from Phase 2" (§2). Instead the commit re-implements both: usage-edit-form.tsx:76-182 is a near-verbatim copy of dosage-fields.tsx:34-140 (times/period/amount + date inputs), and usageSchema.superRefine duplicates addEntrySchema.superRefine (lines 26-69) field-for-field. The copies are in sync today (both carry the .max(24)/.max(100) caps) but future dosage-field/validation changes must now touch two places. Root cause is real: DosageFields/the refinement are typed to AddEntryValues while the edit form uses a distinct UsageValues shape — sharing needs a generic seam, which is why the author forked.
- **Fix A ⭐ Recommended**: Share the validation only — extract the cross-field dosage rules into one plain function both superRefines call; leave the JSX forked for now.
  - Strength: Kills the higher-risk duplication (validation drift is a correctness bug; markup drift is cosmetic) with a small, low-blast-radius change that doesn't touch the Phase 2 add form's typing.
  - Tradeoff: JSX stays duplicated — honors the plan only partially.
  - Confidence: HIGH — both refinements already operate on the same field names; lifting to a function is mechanical.
  - Blind spot: None significant.
- **Fix B**: Full reuse — make DosageFields generic over the form-value shape (register/errors) and drop usage-edit-form's inline inputs.
  - Strength: Fully honors the plan; single source for markup + rules.
  - Tradeoff: Generic RHF register/errors typing is fiddly and edits a component the add form depends on — wider blast radius for a feature already shipped and verified.
  - Confidence: MED — typing generic UseFormRegister is non-trivial.
  - Blind spot: Add-form regression risk if the generics leak.
- **Decision**: FIXED via Fix A — extracted `refineDosageRules` in cabinet-schemas.ts; both superRefines call it. JSX left forked. tsc clean.

### F2 — Save mutation has no error handling (inconsistent with add form)

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality (Reliability) / Pattern Consistency
- **Location**: frontend/src/features/cabinet/components/usage-edit-form.tsx:49
- **Detail**: `setUsage({ id, payload }, { onSuccess: onClose })` passes no onError. On a failed PATCH (422 the client missed, 503, network) the form silently resets isPending and stays open with no message — no user feedback. The sibling add form establishes the pattern: add-medication-form.tsx:112 wires onError → setServerError to show "Wystąpił błąd…". The edit form should mirror it.
- **Fix**: Add local error state + an onError on the setUsage call that sets a Polish error message, rendered above the buttons (mirroring add-medication-form.tsx:112-113).
- **Decision**: FIXED — added serverError state + onError in usage-edit-form.tsx; Polish message rendered above the buttons. tsc clean.

### F3 — Unplanned edit-form wiring in desktop table (cabinet-list.tsx)

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: frontend/src/features/cabinet/components/cabinet-list.tsx:15,21-22,95-160
- **Detail**: Phase 6 enumerated only the card files (cabinet-card.tsx, use-cabinet-entry.ts, the API/hook/schema). The desktop-table EntryRow also got the inline UsageEditForm + toggle. Benign and consistent — the Phase 4 addendum already established the table shares the same useCabinetEntry view as the card, so parity here is correct; it's just undocumented in the Phase 6 plan.
- **Fix**: Add a one-line Phase 6 addendum to plan.md noting the table view received the same inline edit form (mirroring the Phase 4 addendum).
- **Decision**: FIXED — added a Phase 6 addendum to plan.md documenting the table-view inline edit wiring.

### F4 — Success criterion 6.1: prettier --check is currently red

- **Severity**: 🔎 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: frontend/ (npx prettier --check src/)
- **Detail**: Phase 6 criterion 6.1 ("Build + lint + format pass") is checked [x], but prettier --check now reports 11 files with style issues. None are Phase 6 files (cabinet-page, entry-icons, filter-options, status-badge, settings-page, dosage-fields, etc.) — pre-existing line-ending/format drift, not a Phase 6 regression. Phase 6 files are clean; build (tsc+vite) and lint pass.
- **Fix**: Run `npx prettier --write src/` as a housekeeping pass to green the format gate (separate from this feature).
- **Decision**: FIXED (root cause) — added repo-root `.gitattributes` (`* text=auto eol=lf` + binary rules) so LF is pinned in the repo and every working tree regardless of `core.autocrlf`, matching prettier's default `endOfLine: lf`. Ran `prettier --write src/` + `git add --renormalize .` to flip the current Windows working tree to LF. `prettier --check src/` now green. Note: 10 of the 11 flagged files were CRLF-only (no content change); `cabinet-page.tsx` also had a genuine pre-existing content drift (a short union type collapsed to one line) which prettier corrected.

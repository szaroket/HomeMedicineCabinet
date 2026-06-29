<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Dosage Tracking (S-05)

- **Plan**: context/changes/dosage-tracking/plan.md
- **Scope**: Phase 2 of 6
- **Date**: 2026-06-26
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 1 warning, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

Automated success criteria re-run and confirmed green: `npm run build` ✓, `npm run lint` (0 errors, 1 benign React-Compiler `watch()` warning) ✓, `npx prettier --check` ✓.

## Findings

### F1 — Empty dosage fields surface English Zod errors; Polish superRefine messages are shadowed

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Pattern Consistency
- **Location**: cabinet-schemas.ts:18-22 + dosage-fields.tsx register calls
- **Detail**: The base object schema validates dosage fields before the superRefine runs. `dosage_times`/`dosage_amount` use `register(..., { valueAsNumber: true })`, so an empty input yields NaN and `z.number()` rejects it with the English default "Expected number, received nan". `dosage_period`'s `<select>` empty option is value="", and `z.enum(["day","week"])` rejects "" with the English default "Invalid enum value…". These base-field issues are added first (per path), so zodResolver surfaces the English text and the Polish superRefine messages ("Podaj liczbę dawek dziennych", "Wybierz okres dawkowania", "Podaj liczbę tabletek na dawkę") never reach the user. Polish-only UI text is a hard rule (AGENTS.md). The sibling field `partial_tablet_count` already handles this correctly at add-medication-form.tsx:197-200 with `setValueAs: "" → null`.
- **Fix**: Convert empty inputs to null at the register boundary so the base schema passes and the Polish superRefine owns messaging: `dosage_times`/`dosage_amount` → replace `valueAsNumber: true` with `setValueAs: (v) => v === "" || v == null ? null : Number(v)` (matching partial_tablet_count); `dosage_period` → coerce "" → null (setValueAs on the select, or `z.preprocess(v => v === "" ? null : v, …)` on the enum).
  - Strength: Reuses the established in-file pattern; makes every dosage validation message Polish and lets superRefine be the single source of cross-field rules.
  - Tradeoff: Touches three field registrations + possibly the enum.
  - Confidence: HIGH — Zod adds the base type/enum issue first; English text reaches the UI regardless of resolver dedup order.
  - Blind spot: Did not run the form in a browser; verdict is from reading Zod + RHF semantics, not observation.
- **Decision**: FIXED — setValueAs '' → null applied to dosage_times, dosage_period, dosage_amount in dosage-fields.tsx

### F2 — Unreachable manual start-date check in onSubmit

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: add-medication-form.tsx:98-104
- **Detail**: `handleSubmit(onSubmit)` only invokes onSubmit after Zod passes, and the superRefine already requires `dosage_start_date` whenever `is_used` is true. So this manual `setError(...)` + early-return block can never fire — it is dead code.
- **Fix**: Remove the block (lines 98-104); the schema already enforces it.
- **Decision**: FIXED — dead setError block removed from add-medication-form.tsx onSubmit

### F3 — `is_tablet_based` set via setValue only, under shouldUnregister

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: add-medication-form.tsx:61 + cabinet-schemas.ts:23
- **Detail**: `is_tablet_based` drives the superRefine's tablet branch but is only populated via `setValue` (no registered input) while `shouldUnregister: true`. setValue values persist in _formValues so this likely works, but the tablet-gating of dosage validation rests on a subtle RHF interaction. In practice the base-schema NaN/"" checks (see F1) also catch empty dosage, masking any gap — partly why manual criterion 2.5 reads as passing.
- **Fix**: After F1, confirm the tablet branch actually gates (submit a non-tablet "used" entry and verify no dosage required), or register a hidden input for is_tablet_based to make it explicit.
- **Decision**: SKIPPED — manually verified gating works (non-tablet "used" requires no dosage; tablet "used" requires dosage); setValue approach left as-is.

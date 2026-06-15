<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Add Medication from Registry (S-01)

- **Plan**: context/changes/add-medication-from-registry/plan.md
- **Scope**: Phase 6 of 7
- **Date**: 2026-06-12
- **Verdict**: APPROVED (with 2 minor warnings)
- **Findings**: 0 critical  2 warnings  3 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | WARNING |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | WARNING |

Highlights — done right:
- F4 race guard: submit disabled on `isPending` (`add-medication-form.tsx:184`).
- Phase-4 addendum honored: `AddEntryOut` omits `status`; the list reads status from `GET /cabinet/entries` (`CabinetEntryOut`), never from the add response (`cabinet-api.ts:22` vs `:50`).
- F4 timezone policy: dates rendered local via `new Date(d+"T00:00:00")` (`cabinet-list.tsx:10`).
- Two-step picker, conditional tablet fields, merge popup, routing under `ProtectedLayout` — all match the plan.

Automated gates: `npm run build` ✅, `npm run lint` ✅, `prettier --check` on phase-6 files ✅ (repo-wide `prettier --check src/` fails on 20 pre-existing files — see F2).

## Findings

### F1 — Unplanned app branding (logo + AppHeader + restyled auth pages)

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: frontend/src/app/components/app-header.tsx, frontend/src/assets/logo.png, login-page.tsx, register-page.tsx, index.css
- **Detail**: The commit adds a new AppHeader component + logo.png asset and restyles login/register/dashboard pages. None of this is in the Phase-6 plan, and "What We're NOT Doing" says no design-system build-out beyond the minimal elements this feature needs. The cabinet pages legitimately need a header, but propagating a logo + branding across auth/dashboard is scope creep. Benign and cohesive, but undocumented.
- **Fix**: Add a one-line addendum to the Phase-6 block noting the shared AppHeader/logo landed alongside the cabinet pages, so it isn't re-flagged as drift later.
- **Decision**: FIXED — addendum added to Phase-6 block in plan.md

### F2 — `prettier --check src/` gate fails repo-wide (criterion 6.3)

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: frontend/ (20 pre-existing files: auth/*, lib/*, app/*)
- **Detail**: Progress marks 6.3 "Format clean (prettier --check src/)" as [x], but the command currently fails on 20 files. Confirmed all 20 are PRE-EXISTING files untouched by Phase 6 — every phase-6 file passes prettier cleanly (verified in isolation). So this is not phase-6 drift, but the stated gate as written does not pass, which undermines using it as a green checkmark.
- **Fix**: Run `npx prettier --write src/` once to bring the legacy files into compliance (separate housekeeping commit), restoring the gate to green. The phase-6 code needs no change.
- **Decision**: RESOLVED (no commit needed) — root cause is local: `core.autocrlf=true` checks the legacy files out as CRLF, so `prettier --check` (endOfLine: lf) failed on the working tree. The committed/index content is already LF and prettier-clean. `prettier --write src/` made the local check green but produced no git diff (autocrlf normalizes back to LF = HEAD). The stated gate is fine against committed content; the failure was a working-tree artifact, not phase-6 drift.

### F3 — Cabinet list columns diverge from plan contract

- **Severity**: 🔵 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: frontend/src/features/cabinet/components/cabinet-list.tsx:80, :3
- **Detail**: Plan §6 specified columns "tablet count (capacity)" and "partial" plus a status badge mapped `expiring → wkrótce wygaśnie`. The impl instead shows a single "Sztuki" = total_tablets column (capacity and partial are not shown individually) and labels expiring as "Bliski termin". Both are reasonable UX choices and total_tablets is arguably more useful, but per-package capacity is no longer visible and the label copy deviates from the plan.
- **Fix**: Accept as-is (sensible simplification) or add capacity/partial back if the per-package count matters for the read-only verification view.
- **Decision**: SKIPPED — accepted as-is (sensible simplification; total_tablets is more useful for the read-only view).

### F4 — Partial upper-bound validation lives in onSubmit as `serverError`

- **Severity**: 🔵 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: frontend/src/features/cabinet/components/add-medication-form.tsx:51
- **Detail**: Plan §2 said the zod schema enforces partial `1…capacity−1`. Since capacity is dynamic (per selected variant), the upper bound is instead checked imperatively in onSubmit and surfaced via `setServerError(...)`. Functionally correct, but a client-side validation error is being routed through the "server error" channel, and it sits outside the schema/RHF error flow used for every other field.
- **Fix**: Acceptable as a pragmatic dynamic-bound check. Optionally move it to a zod `.superRefine` driven by the selected variant, or set it as an RHF field error on `partial_tablet_count` instead of `serverError`.
- **Decision**: FIXED — dynamic partial bound now routed via RHF `setError("partial_tablet_count", …)`; `serverError` reserved for the mutation onError. Lint + build clean.

### F5 — Array index used as React key in autocomplete list

- **Severity**: 🔵 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: frontend/src/features/cabinet/components/product-autocomplete.tsx:44
- **Detail**: `key={i}` on the suggestions list. ProductOut has no id, so the index is a forced choice, but index keys can cause subtle reconciliation glitches as results change. Low risk here since the list is replaced wholesale per query.
- **Fix**: Use a composite key like `${p.name}|${p.strength}|${p.pharmaceutical_form}`.
- **Decision**: FIXED — replaced index key with composite `${name}|${strength}|${pharmaceutical_form}`. Lint clean.

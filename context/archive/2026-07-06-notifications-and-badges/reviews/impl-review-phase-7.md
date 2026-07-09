<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Notifications and Badges (S-06)

- **Plan**: context/changes/notifications-and-badges/plan.md
- **Scope**: Phase 7 of 8
- **Date**: 2026-07-08
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 2 warnings, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | WARNING |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

Automated criteria — all green:
- 7.1 settings tests: 9 passed (seeds all three / rejects out-of-range with Polish / submits full payload)
- 7.2 build + lint + prettier: `tsc -b && vite build` ok, eslint clean, prettier clean

## Findings

### F1 — Threshold save doesn't refresh the notification bell

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: frontend/src/features/settings/api/settings-queries.ts:27-29
- **Detail**: `useUpdatePreferences.onSuccess` invalidates only `settingsKeys.preferences()`. But `GET /notifications` derives the active set from the user's effective thresholds, so changing `expiry_threshold_days` / `close_to_finish_threshold_days` directly changes which alerts fire. After a save, the bell/panel stay stale until the 5-min `refetchInterval`, a window refocus, or a reload. This is the same class of change Phase 6 §2 handled by having cabinet mutations also invalidate `notificationKeys.all()`; that cross-feature invalidation was not applied here. The plan's Phase 7 contract never called for it, so the code faithfully followed a plan gap.
- **Fix**: In `useUpdatePreferences.onSuccess`, also `queryClient.invalidateQueries({ queryKey: notificationKeys.all() })` (import `notificationKeys` from the notifications feature), mirroring the cabinet mutation pattern.
  - Strength: Reuses the established Phase 6 §2 pattern; one line; closes the stale-bell window entirely.
  - Tradeoff: One extra `GET /notifications` (with its GC side-effect) per save — negligible at PRD scale, already accepted in Phase-6 rationale.
  - Confidence: HIGH — same pattern already used for cabinet mutations.
  - Blind spot: None significant.
- **Decision**: FIXED

### F2 — Unplanned mobile-scroll fix: shared layout + cabinet file, untested, fragile coupling

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Scope Discipline
- **Location**: frontend/src/app/components/app-layout.tsx:18, frontend/src/features/cabinet/components/add-medication-page.tsx:8, frontend/src/features/settings/components/settings-page.tsx:67
- **Detail**: Phase 7's stated scope is "settings threshold controls," but the commit also ships a mobile-scroll fix: `h-screen`→`h-dvh` on the global `AppLayout`, and a `-mx-6 -my-8 h-[calc(100%+4rem)] px-6 py-8` scroll container on both settings-page.tsx AND add-medication-page.tsx (a cabinet-feature file unrelated to this phase). Beyond the scope creep: (1) the negative-margin trick hard-couples to AppLayout's exact `px-6 py-8` (app-layout.tsx:55) — if that padding changes, all three call sites silently misalign/clip, with no test to catch it; (2) unlike the analogous Phase-6 panel-scroll fix (which got a jsdom regression test, per change.md), this fix has no automated coverage and rests entirely on the manual Chromium check.
- **Fix A ⭐ Recommended**: Keep the fix but document + guard it — add a plan addendum (like the Phase-6 F1/F4 addenda) noting the scroll fix and its coupling to AppLayout's padding, and a short comment at the padding source (app-layout.tsx:55) pointing at the three dependents.
  - Strength: Preserves a genuine UX fix; makes the hidden coupling visible; matches how prior discovered scope was handled in this change (addenda).
  - Tradeoff: Plan keeps accreting addenda; a comment is a weak guard vs. a real test.
  - Confidence: HIGH — addendum pattern already used twice in this change.
  - Blind spot: A comment won't fail CI; only a viewport test would.
- **Fix B**: Extract a shared "full-bleed scroll container" component/util so the padding math lives in one place next to AppLayout and the three pages consume it.
  - Strength: Removes the duplicated fragile calc; single source of truth.
  - Tradeoff: More work than the phase warrants; touches more files.
  - Confidence: MED — clean, but arguably over-engineering for 3 sites.
  - Blind spot: Haven't checked whether other pages will soon need it.
- **Decision**: FIXED via Fix A

### F3 — Cleared threshold field surfaces an English NaN error

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: frontend/src/features/settings/schemas/settings-schemas.ts:4-12
- **Detail**: The inputs use `valueAsNumber` and the form is `noValidate`, so clearing a threshold field yields `NaN`. `z.number()` with no type-error message then emits Zod's default English string ("expected number, received NaN") instead of a Polish message. Out-of-range paths (5, 0) are covered and produce Polish; only the empty/NaN path regresses. Pre-existing on `min_package_count` too — the two new fields inherit the gap.
- **Fix**: Add a Polish type-error message to each `.number(...)` call (zod-version-appropriate, e.g. `z.number({ error: "Podaj liczbę." })`) so an empty field also shows Polish.
- **Decision**: FIXED

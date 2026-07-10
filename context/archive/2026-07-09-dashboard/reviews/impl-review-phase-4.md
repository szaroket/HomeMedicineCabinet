<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Dashboard

- **Plan**: context/changes/dashboard/plan.md
- **Scope**: Phase 4 of 4 (Navigation & landing wiring)
- **Date**: 2026-07-10
- **Verdict**: APPROVED
- **Findings**: 0 critical, 0 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

## Evidence

Plan → actual, all MATCH:

- "Panel główny" → "/" added to `TOP_NAV` above "Apteczka".
- `end: true` so it's active only on the exact "/" route.
- `SidebarLink` gains optional `end` prop and `string | ReactNode` icon.
- Inline `HomeIcon` SVG mirrors the app-layout hamburger style
  (`fill="none"`, `stroke="currentColor"`, `strokeWidth={2}`,
  `viewBox="0 0 24 24"`, rounded caps) + `aria-hidden` + `h-4 w-4` sizing.
- Existing `<img>` entries (Apteczka, Ustawienia) untouched.
- Login/register landing = verification-only, no code change (as planned).

Success criteria (Automated):

- 4.1 `npm run lint` — PASS (clean)
- 4.2 `npx tsc -b` — PASS (clean)
- 4.3 sidebar test — PASS (2/2)

Scope: diff touches only `app-sidebar.tsx` + its new test (+ plan.md). No
unplanned files; no "What We're NOT Doing" boundary crossed.

## Findings

### F1 — Active-state asserted via CSS class, not aria-current

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: frontend/src/app/components/app-sidebar.test.tsx:16,27
- **Detail**: The test proves active/inactive state by asserting the Tailwind class `bg-slate-700`. NavLink emits a semantic `aria-current="page"` when active, which is the styling-independent signal for exactly this. Class-based assertion is already used elsewhere in the repo (notification-bell.test.tsx), so this is consistent — but it couples the active-state test to a color token, so a restyle (e.g. switching the active background) breaks a passing test with no behavior change.
- **Fix**: Assert `toHaveAttribute("aria-current", "page")` (and its absence on /cabinet) instead of the `bg-slate-700` class.
- **Decision**: FIXED

### F2 — `string | ReactNode` union is redundant

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Architecture
- **Location**: frontend/src/app/components/app-sidebar.tsx:42
- **Detail**: `ReactNode` already includes `string`, so `icon: string | ReactNode` is type-equivalent to `icon: ReactNode`. Harmless — the runtime `typeof icon === "string"` discriminator still works correctly and the union documents the two intended shapes. Purely cosmetic.
- **Fix**: Optional — leave as-is (self-documenting) or narrow to `ReactNode`. No behavior change either way.
- **Decision**: SKIPPED

<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Dashboard

- **Plan**: context/changes/dashboard/plan.md
- **Scope**: Phase 3 of 4 (Frontend dashboard UI)
- **Date**: 2026-07-10
- **Verdict**: APPROVED
- **Findings**: 0 critical  2 warnings  1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | WARNING |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

Automated success criteria (all pass): lint clean (`npm run lint`), typecheck clean (`npx tsc -b`), prettier clean (`npx prettier --check src/features/dashboard`), component tests 4/4 (`npx vitest run src/features/dashboard/components`).

## Findings

### F1 — Card labels drifted from the plan's explicit copy

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: frontend/src/features/dashboard/components/summary-cards.config.ts:14-38
- **Detail**: Plan Phase 3 §2 and the Desired End State pin exact labels: "Aktualne", "Bliski termin", "Przeterminowane", "Brak zapasu". Implementation ships expanded copy: "Aktualne leki", "Leki bliskie terminu ważności", "Leki przeterminowane", "Leki bez zapasu". Only "Łącznie leków" matches. Tests read from the config so they pass regardless — the drift is invisible to CI. The long "Leki bliskie terminu ważności" also risks awkward wrapping in a narrow card (`text-sm max-w-[70%]` on mobile).
- **Fix**: Decide the canonical copy — either revert the four labels to the plan's concise forms, or keep the richer copy and note it as a plan addendum so the plan stays the source of truth.
- **Decision**: RESOLVED — kept richer copy; plan Phase 3 §2 amended with a 2026-07-10 addendum making the expanded labels canonical.

### F2 — Unplanned icon PNG assets added to the cards

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: frontend/src/features/dashboard/components/summary-card.tsx:2-6,40-53
- **Detail**: Plan's summary-card contract is "a Polish label + count" tinted per status token — no icons. Implementation adds five new binary assets (total/active/expiring/expired/out-of-stock.png) and renders them per card. Defensible under the plan's "styled after dashboard-v1.jpg" clause, and benign, but it is scope not described in the plan and commits 5 binaries to the repo. Both `<img>`s use `alt=""` (decorative) — accessibility is fine.
- **Fix**: Keep if the mockup shows these icons; add a one-line note to the plan's Phase 3 that cards carry decorative status icons.
- **Decision**: RESOLVED — kept icons; plan Phase 3 §1 amended with a 2026-07-10 addendum noting decorative per-status card icons.

### F3 — Empty-state vertical centering is inert

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: frontend/src/features/dashboard/components/dashboard-empty.tsx:5
- **Detail**: DashboardEmpty's root uses `flex flex-1 ... justify-center`, but its parent in dashboard-page.tsx (`<div className="h-full overflow-y-auto">`, line 13) is a block, not a flex container. So `flex-1` and the vertical `justify-center` are inert — the CTA renders directly under the title, top-aligned, not centered as the plan's "friendly add-CTA" intends. Cosmetic only; content is correct.
- **Fix**: Make the page content wrapper `flex flex-col` (or drop `flex-1` from the empty state and center it another way).
- **Decision**: FIXED — dashboard-page.tsx:13 wrapper changed to `flex h-full flex-col overflow-y-auto`; empty-state flex-1/justify-center now live.

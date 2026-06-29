<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Mobile Responsive Cabinet

- **Plan**: context/changes/mobile-responsive-cabinet/plan.md
- **Scope**: Phase 3 of 3
- **Date**: 2026-06-17
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 1 warning, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | PASS |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

Automated success criteria all pass: `npm run build`, `npm run lint`, and `npx prettier --check src/` are green. Phase-3 commit (1b1ca0f) touched only the two planned-scope files (`cabinet-page.tsx`, `plan.md`) — no unplanned-file drift.

## Findings

### F1 — FAB likely overlaps the mobile pagination's next-page button

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: frontend/src/features/cabinet/components/cabinet-page.tsx:316-350
- **Detail**: The mobile pagination is a flow sibling *after* the scroll area (`flex-shrink-0 ... md:hidden`, only `mt-2`), so it pins to the bottom edge of the viewport. The FAB is `fixed bottom-6 right-4 z-30`. The scroll area got `pb-20` (Phase 2) to keep the FAB off the last card, but the pagination sits *outside* that padded area. On a 375px viewport the pagination is centered while the FAB occupies the bottom-right ~16–136px; the `›` (next) button's right edge lands inside that band, so the FAB can cover it. Plan Phase 2 criterion 2.7 and Phase 3 manual item 3.4 both assert the FAB "never obscures pagination" and are checked `[x]`, but nothing in the diff adds clearance below the pagination row — possible rubber-stamp.
- **Fix**: Add bottom clearance to the mobile pagination row so it clears the FAB, e.g. change its wrapper to `mt-2 mb-20 md:mb-0` (or pad the outer column on mobile). Mirrors the `pb-20 md:pb-0` clearance already used on the scroll area.
  - Strength: Reuses the exact clearance idiom Phase 2 introduced for the same FAB; one-line, mobile-only, no desktop impact (`md:mb-0`).
  - Tradeoff: Slightly more empty space under the pager on mobile.
  - Confidence: MEDIUM — overlap reasoned from the Tailwind classes, not rendered at 375px.
  - Blind spot: Not visually verified in a browser; on a very narrow centered pager the arrow may happen to clear the FAB.
- **Decision**: FIXED (differently) — removed the mobile FAB and un-hid the existing header "Dodaj lek" button on mobile (same desktop style), eliminating the overlap at the source. Also dropped the now-pointless `pb-20 md:pb-0` FAB-clearance padding on the scroll area. Reverses the Phase 2 FAB decision by user choice.

### F2 — `Leków: {total}` rendered inline, not "beneath" as planned/mockup

- **Severity**: 🔎 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: frontend/src/features/cabinet/components/cabinet-page.tsx:337-339
- **Detail**: Plan Phase 3 contract says the count goes "with `Leków: {pageData.total}` beneath", and the mockup (`reference/mobile-list-v1.png`) shows `‹ 2 / 2 ›` on one line and `Leków: 23` on a second. Implementation renders a single line: `{page} / {totalPages} · Leków: {pageData.total}`. Behaviorally equivalent and satisfies the looser manual checkbox wording, but it deviates from both the plan text and the mockup layout.
- **Fix**: If matching the mockup matters, split into two stacked lines (wrap the pager in a `flex-col` and move `Leków: {total}` to its own line under the arrows). Otherwise accept the single-line form as a conscious simplification.
- **Decision**: ACCEPTED — single-line form kept as a conscious simplification; behaviorally equivalent and within the checkbox wording.

## Notes

- **Known sort-resets-page bug** (recorded in `change.md`) was not addressed in Phase 3. It was a "consider" suggestion, never part of the Phase 3 contract, so leaving it open is consistent with scope discipline — not a finding.
- Mechanically the planned changes landed correctly: desktop block gated to `hidden md:flex`, mobile block `md:hidden`, reusing `page<=1`/`page>=totalPages` disabled logic, `setParam("page", …)`, and page-size omitted on mobile.

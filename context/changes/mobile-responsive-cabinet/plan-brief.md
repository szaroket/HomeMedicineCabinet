# Mobile Responsive Cabinet — Plan Brief

> Full plan: `context/changes/mobile-responsive-cabinet/plan.md`

## What & Why

The cabinet (medicine list) renders only as a 6-column table that overflows or squashes on phones. We're making it mobile-friendly per `reference/mobile-list-v1.png`: stacked cards below the `md` breakpoint, while the existing table is preserved untouched on desktop.

## Starting Point

The app shell (header, hamburger drawer, sidebar, footer) is already responsive — no work there. The gap is the cabinet list page: `cabinet-list.tsx` renders a raw `<table>`, and `cabinet-page.tsx` packs search + 3 filters + sort + clear into one cramped `flex-wrap` row, with an inline `Dodaj lek` button and verbose pagination. All filter/sort/page state is already URL-driven.

## Desired End State

On a phone, the cabinet shows a full-width search, a `Filtry` button (opening a sheet with all three filters), a `Sortowanie` dropdown, a vertical list of cards (name + star, status pill, `Opak./Sztuki/Ważność`, `Brak w apteczce` badge, expandable details), a floating `Dodaj lek` FAB, and compact `‹ 2 / 2 ›` pagination. On desktop (`md+`) everything looks exactly as it does today.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Layout strategy | Cards below `md`, existing table at `md+` | Matches the mobile mockup while preserving desktop data density | Plan |
| Shared logic | Extract `EntryRow` logic into a `useCabinetEntry` hook | One source of truth for expand/star/status/date across both render paths | Plan |
| Mobile filters | Single `Filtry` button opens a sheet with all 3 filters | Keeps the clean mockup row AND preserves combining filters | Plan |
| Card extras | Star next to name; `Brak w apteczce` as a second badge | Keeps current functionality visible without cluttering the card | Plan |
| Status display | Pill badges on mobile only; desktop keeps colored text | Matches mockup without touching desktop or the `Ważny`/`ważny` collision | Plan |
| Valid label | Keep `Aktualny` (no rename to `Ważny`) | Avoids the valid-vs-important naming collision | Plan |
| Add button | Floating FAB on mobile; inline button stays on desktop | Mirrors the mockup's FAB | Plan |
| Pagination | Compact `‹ x / y ›` + `Leków: n` on mobile; verbose on desktop | Mockup's compact form for narrow screens | Plan |
| Scope | Cabinet list page only | Highest-impact, matches the single mockup, ships fast | Plan |
| Verification | Manual at breakpoints + `build` + `lint` | Right tool for a visual/responsive change | Plan |

## Scope

**In scope:** `cabinet-list.tsx`, `cabinet-page.tsx`, and new card/badge/filter-sheet/hook files under `features/cabinet/`.

**Out of scope:** desktop layout, app shell/nav, add-medication form, settings, auth pages, backend/data-model, automated tests.

## Architecture / Approach

Extract per-entry logic from `EntryRow` into a `useCabinetEntry` hook consumed by both the existing table row and a new `CabinetCard`. `CabinetList` shows the table inside `hidden md:block` and the cards inside `md:hidden`. In `cabinet-page.tsx`, mobile controls/FAB/pagination get `md:hidden` variants alongside the existing `hidden md:flex` desktop versions, all driving the same URL setters (`setParam`/`clearFilters`).

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Responsive list | Cards on mobile + table on desktop via shared hook + status pill | Refactoring `EntryRow` without changing desktop behavior |
| 2. Controls + FAB | Mobile search/`Filtry` sheet/`Sortowanie` + floating FAB | Filter sheet must reuse URL state, not fork it; FAB overlap |
| 3. Mobile pagination | Compact `‹ x / y ›` + `Leków: n` | Keeping desktop pagination untouched |

**Prerequisites:** none — all state and patterns already exist in the codebase.
**Estimated effort:** ~1–2 sessions across 3 phases.

## Open Risks & Assumptions

- The mockup omits the star toggle and `Brak w apteczce` indicator; we place them on the card per the agreed design — final spacing on the narrowest screens to confirm during manual verification.
- Two render paths in `cabinet-list.tsx` must stay in sync; the shared hook is the mitigation.

## Success Criteria (Summary)

- Cabinet list is fully usable at ~375px (cards, filter sheet, FAB, compact pagination) with no horizontal scroll.
- Desktop (`md+`) is visually and behaviorally unchanged.
- All filters, sort, star, expand, and pagination work identically across both layouts (URL-driven).

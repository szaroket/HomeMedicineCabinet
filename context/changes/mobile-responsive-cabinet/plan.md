# Mobile Responsive Cabinet Implementation Plan

## Overview

Make the cabinet (medicine list) usable on mobile screens, matching `reference/mobile-list-v1.png`. Below the Tailwind `md` breakpoint the list renders as stacked **cards**; at `md+` the existing **table** is preserved unchanged. The mobile controls collapse to a full-width search, a single `Filtry` button that opens a sheet holding all three filters, a `Sortowanie` dropdown, and a floating `Dodaj lek` FAB. Pagination becomes compact on mobile.

Scope is the cabinet list page only (`cabinet-list.tsx` + `cabinet-page.tsx`). No backend, no data-model, and no other screens change.

## Current State Analysis

- **App shell is already responsive.** `app-layout.tsx:21-44` renders a hamburger (`md:hidden`) that opens a drawer (`app-sidebar.tsx:89-101`); the desktop sidebar is fixed at `md+`. No work needed here.
- **The list is a raw table only.** `cabinet-list.tsx:238-270` renders a `<table>` wrapped in `overflow-x-auto`. On a phone its 6 columns either overflow horizontally or squash. `EntryRow` (`cabinet-list.tsx:63-191`) owns per-row state: `expanded` toggle, `toggleImportant` mutation, `STATUS_LABEL` lookup, `below_minimum` row tint, `formatDate`, and the expandable details `<dl>`.
- **Controls bar wraps but is cramped.** `cabinet-page.tsx:194-284` has search + 3 selects (status, category=`important`, stock=`below_minimum`) + a sort toggle button + a clear-filters button, all in one `flex-wrap` row. The page owns all filter state in the URL via `useSearchParams` and exposes `setParam(key, value, resetPage)` and `clearFilters()`.
- **Status renders as colored text.** `STATUS_LABEL` (`cabinet-list.tsx:48-52`) maps `valid→{Aktualny, text-green-400}`, `expiring→{Bliski termin, text-orange-400}`, `expired→{Przeterminowany, text-red-400}`.
- **`Dodaj lek` is an inline header button** (`cabinet-page.tsx:186-191`); pagination is verbose `Strona X z Y (łącznie Z)` + prev/next + page-size select (`cabinet-page.tsx:298-335`).

### Key Discoveries:

- Per-row behavior to share between table and card lives entirely in `EntryRow` (`cabinet-list.tsx:63-191`) — extracting it into a hook is the enabling step for two render paths.
- All filter/sort/page state is URL-driven in `cabinet-page.tsx` via `setParam`/`clearFilters`; the mobile filter sheet must reuse these same setters, not introduce parallel state.
- `MIN_SEARCH_LEN`, debounce, and out-of-range page correction (`cabinet-page.tsx:164-178`) are already in place and breakpoint-agnostic — mobile reuses them as-is.
- Tailwind v4 with `md` breakpoint and the `cn()` helper (`lib/utils.ts`) are the styling tools; follow the existing `md:hidden` / `hidden md:flex` pattern used in the layout.

## Desired End State

On a ~375px viewport the cabinet page shows: full-width search, a `Filtry` button + `Sortowanie` dropdown row, a vertical list of cards (name + star toggle, colored status pill, `Opak.`/`Sztuki`/`Ważność`, an amber `Brak w apteczce` badge when below minimum, and a chevron that expands the remaining fields), a floating `Dodaj lek` FAB, and compact `‹ 2 / 2 ›` + `Leków: 23` pagination. At `md+` the page is visually identical to today (table, full controls bar, inline `Dodaj lek`, verbose pagination).

Verify by resizing the browser across the `md` breakpoint: the card list and table swap cleanly, all filters/sort/pagination keep working through the URL, and the star/expand/below-minimum behaviors work in both layouts.

## What We're NOT Doing

- Not changing the desktop table layout, desktop controls bar, desktop pagination, or desktop status styling (stays colored text, label stays `Aktualny`).
- Not renaming the `valid` status label to `Ważny` (avoids the `Ważny` valid vs `ważny` important collision).
- Not touching the app shell / nav / header / footer (already responsive).
- Not redesigning the add-medication form, result dialog, autocomplete, settings, or auth pages.
- Not adding Vitest/RTL or Playwright tests for this change (verification is manual + build/lint).
- No backend, API, or data-model changes.

## Implementation Approach

Extract the shared per-entry logic out of `EntryRow` into a hook so a new mobile `EntryCard` and the existing table row can both consume it without duplicating the toggle/format/status logic. `CabinetList` renders the table inside a `hidden md:block` wrapper and the card list inside a `md:hidden` wrapper — both fed the same `pageData`. The empty/loading/error states are shared (rendered above the breakpoint switch). Controls and pagination in `cabinet-page.tsx` get a mobile variant (`md:hidden`) alongside the existing desktop variant (`hidden md:flex`), with the mobile filter sheet and FAB driving the *same* URL setters already in the page.

## Phase 1: Responsive list — cards on mobile, table on desktop

### Overview

Split the medicine list into a card layout below `md` and the existing table at `md+`, sharing per-entry logic via a hook.

### Changes Required:

#### 1. Shared entry-row hook

**File**: `frontend/src/features/cabinet/hooks/use-cabinet-entry.ts` (new)

**Intent**: Extract the stateful/derived logic currently inline in `EntryRow` so both the table row and the new card use one source of truth — no duplicated toggle or formatting logic.

**Contract**: A hook taking the `CabinetEntryOut` entry and returning the expand state + toggler, the `toggleImportant` mutation handler, the resolved status `{ label, className }`, the `below_minimum` flag, and a formatted expiry date. Move `formatDate` and `STATUS_LABEL` (plus the `OUT_OF_STOCK_LABEL` constant) into a module both the hook and renderers import. Follow the `[[feedback_pure_functions_in_service]]`-style colocation: pure helpers live beside the hook, not in a separate `logic.ts`.

#### 2. Mobile status pill badge

**File**: `frontend/src/features/cabinet/components/status-badge.tsx` (new)

**Intent**: Render the status as a colored pill badge for the mobile card (the desktop table keeps its colored-text style).

**Contract**: A small presentational component taking the resolved status `{ label, className }` and rendering a rounded pill (bg tint + text color per status: green/orange/red). Used only by the card, not the table.

#### 3. Mobile entry card

**File**: `frontend/src/features/cabinet/components/cabinet-card.tsx` (new)

**Intent**: Render one medicine as a card matching the mockup: header row, summary fields, expandable details.

**Contract**: Consumes `useCabinetEntry`. Card face = medicine name + star toggle button (reuse the existing `StarIcon` behavior), the status pill (`StatusBadge`), and — when `below_minimum` — an amber `Brak w apteczce` badge near the status. Summary line shows `Opak.: {package_count}`, `Sztuki: {total_tablets ?? "—"}`, `Ważność: {formatted date}`. A chevron button toggles an expanded section showing Dawka / Postać / Substancja czynna / Droga podania / Ulotka / Charakterystyka (same fields and link behavior as the current expanded `<dl>` in `cabinet-list.tsx:128-185`). Tapping the card body (outside the buttons/links) toggles expand, mirroring the row's `onClick` with `stopPropagation` on interactive children.

#### 4. Responsive switch in CabinetList

**File**: `frontend/src/features/cabinet/components/cabinet-list.tsx`

**Intent**: Render cards below `md` and the table at `md+`, with loading/empty/error states shared above the switch. Refactor `EntryRow` to consume the new hook so its inline logic is removed.

**Contract**: Keep the existing loading/error/empty-with-filters branches unchanged. For the populated state, wrap the current `<table>` block in a `hidden md:block` container and add a `md:hidden` container mapping `pageData.items` to `CabinetCard`. `EntryRow` keeps rendering `<tr>`s but sources expand/star/status/date from `useCabinetEntry`; `STATUS_LABEL`/`formatDate` move to the shared module.

#### 5. Shared entry icons (addendum)

**File**: `frontend/src/features/cabinet/components/entry-icons.tsx` (new)

**Intent**: Extract `StarIcon` and `ChevronIcon` (previously inline in `cabinet-list.tsx`) into a shared module so the table row (`EntryRow`) and the new `CabinetCard` consume one icon definition instead of duplicating SVG markup. Discovered during implementation; consistent with the phase's "share logic, don't duplicate" intent.

### Success Criteria:

#### Automated Verification:

- Type check + build passes: `cd frontend && npm run build`
- Lint passes: `cd frontend && npm run lint`
- Format check passes: `cd frontend && npx prettier --check src/`

#### Manual Verification:

- At ~375px the list shows stacked cards with name, star, status pill, `Opak./Sztuki/Ważność`, and chevron-expandable details.
- An entry below minimum shows the amber `Brak w apteczce` badge on its card.
- Star toggle and expand work on a card without triggering the other; expand reveals all detail fields and working Ulotka/Charakterystyka links.
- At `md+` the table is visually unchanged from today (same columns, colored-text status, `Aktualny` label, row tint for below-minimum).
- No regression: toggling important on mobile reflects in the table after resizing.

**Implementation Note**: After completing this phase and all automated verification passes, pause for human confirmation that mobile/desktop manual testing succeeded before starting Phase 2.

---

## Phase 2: Responsive controls + FAB

### Overview

Give the controls bar a mobile variant: full-width search, a `Filtry` button opening a sheet with all three filters, a `Sortowanie` dropdown, and a floating `Dodaj lek` FAB. Desktop controls bar stays as-is.

### Changes Required:

#### 1. Mobile filter sheet

**File**: `frontend/src/features/cabinet/components/filter-sheet.tsx` (new)

**Intent**: A single `Filtry` entry point that opens a panel/sheet containing the status, `Ważne` (category), and `Brak w apteczce` (stock) filters, preserving the ability to combine them.

**Contract**: A `Filtry` button (showing an active-count indicator when any filter is set) that opens a bottom sheet/overlay. The sheet renders the three existing selects/options (reusing `STATUS_OPTIONS`, `CATEGORY_OPTIONS`, `STOCK_OPTIONS` from `cabinet-page.tsx`) plus a `Wyczyść filtry` action. The sheet reads current values from props and calls the page's existing `setParam(key, value, resetPage=true)` / `clearFilters()` setters — no parallel state. Dismiss via overlay click / close button, following the drawer overlay pattern in `app-sidebar.tsx:89-101`. Consider extracting `STATUS_OPTIONS`/`CATEGORY_OPTIONS`/`STOCK_OPTIONS` into a shared module so both the page and sheet import them.

#### 2. Mobile controls + FAB in CabinetPage

**File**: `frontend/src/features/cabinet/components/cabinet-page.tsx`

**Intent**: Add a `md:hidden` mobile controls row (search + `Filtry` + `Sortowanie`) and a floating FAB; hide the inline header `Dodaj lek` on mobile. Keep the existing desktop controls bar and header button under `hidden md:flex` / `hidden md:block`.

**Contract**: Wrap the current controls `<div>` (`cabinet-page.tsx:195-284`) so it only shows at `md+`. Add a mobile block: full-width search input (bound to the same `searchInput`/`setSearchInput`), the `FilterSheet`, and a `Sortowanie` control toggling `order` via `setParam("order", …, true)` (label `Nazwa A→Z` / `Z→A`). Hide the header `Dodaj lek` link on mobile (`hidden md:inline-flex`) and add a fixed-position FAB (`md:hidden`) linking to `/cabinet/add` (blue rounded, `+ Dodaj lek`, bottom-right, above content). Ensure the FAB does not cover the last card/pagination — add bottom padding to the scroll area on mobile.

### Success Criteria:

#### Automated Verification:

- Type check + build passes: `cd frontend && npm run build`
- Lint passes: `cd frontend && npm run lint`
- Format check passes: `cd frontend && npx prettier --check src/`

#### Manual Verification:

- At ~375px the controls row shows search + `Filtry` + `Sortowanie`; the inline header `Dodaj lek` is gone and a floating FAB is present.
- Opening `Filtry`, changing status / `Ważne` / `Brak w apteczce`, and combining two filters all update the list and the URL; `Wyczyść filtry` resets them.
- `Sortowanie` toggles A→Z / Z→A and reorders the list.
- The FAB navigates to the add-medication page and never obscures the last card or pagination.
- At `md+` the controls bar, sort/clear buttons, and inline `Dodaj lek` are unchanged.

**Implementation Note**: After this phase and automated verification passes, pause for human confirmation of mobile/desktop manual testing before Phase 3.

---

## Phase 3: Compact mobile pagination

### Overview

Replace the verbose pagination with a compact `‹ 2 / 2 ›` + `Leków: 23` form on mobile; keep the existing verbose pagination + page-size select at `md+`.

### Changes Required:

#### 1. Mobile pagination in CabinetPage

**File**: `frontend/src/features/cabinet/components/cabinet-page.tsx`

**Intent**: Add a `md:hidden` compact pagination and gate the existing pagination block to `md+`.

**Contract**: Wrap the current pagination `<div>` (`cabinet-page.tsx:298-335`) in `hidden md:flex`. Add a `md:hidden` block centered below the list: prev arrow, `{page} / {totalPages}`, next arrow (reusing the existing `page<=1` / `page>=totalPages` disabled logic and `setParam("page", …)`), with `Leków: {pageData.total}` beneath. Page-size selection is omitted on mobile (defaults stay in effect via the URL).

### Success Criteria:

#### Automated Verification:

- Type check + build passes: `cd frontend && npm run build`
- Lint passes: `cd frontend && npm run lint`
- Format check passes: `cd frontend && npx prettier --check src/`

#### Manual Verification:

- At ~375px pagination shows `‹ {page} / {totalPages} ›` and `Leków: {total}`; arrows are disabled at the first/last page and navigate correctly.
- At `md+` the verbose pagination with page-size select is unchanged.
- Changing the page on mobile, then resizing to desktop, preserves the current page (URL-driven).

**Implementation Note**: After this phase and automated verification passes, pause for final human confirmation across both layouts.

---

## Testing Strategy

### Manual Testing Steps:

1. Load `/cabinet` on a desktop width — confirm the table, full controls bar, inline `Dodaj lek`, and verbose pagination are unchanged.
2. Resize to ~375px — confirm cards, mobile controls (search + `Filtry` + `Sortowanie`), FAB, and compact pagination appear and the table/desktop controls disappear.
3. On mobile: toggle star, expand a card, open the filter sheet and combine `Ważne` + `Bliski termin`, sort Z→A, page forward/back, tap the FAB.
4. Confirm an entry below the minimum shows `Brak w apteczce` on its card (mobile) and the amber row tint (desktop).
5. Cross the breakpoint mid-interaction (e.g. expand a card, resize) — confirm no broken state and URL params persist.

## Performance Considerations

Negligible — both layouts render the same already-paginated `pageData.items` (≤ page size). Only one layout is in the DOM per breakpoint (the other is `hidden`); the card list adds no new data fetching.

## References

- Mobile mockup: `reference/mobile-list-v1.png`
- Desktop reference: `reference/cabinet-data-v1.png`, `reference/webpage.jpg`
- Existing responsive pattern: `frontend/src/app/components/app-layout.tsx:21-44`, `frontend/src/app/components/app-sidebar.tsx:89-101`
- Current list: `frontend/src/features/cabinet/components/cabinet-list.tsx`
- Current page/controls: `frontend/src/features/cabinet/components/cabinet-page.tsx`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Responsive list — cards on mobile, table on desktop

#### Automated

- [x] 1.1 Type check + build passes: `cd frontend && npm run build` — 968b9c5
- [x] 1.2 Lint passes: `cd frontend && npm run lint` — 968b9c5
- [x] 1.3 Format check passes: `cd frontend && npx prettier --check src/` — 968b9c5

#### Manual

- [x] 1.4 Cards at ~375px show name, star, status pill, Opak./Sztuki/Ważność, expandable details — 968b9c5
- [x] 1.5 Below-minimum entry shows amber `Brak w apteczce` badge on its card — 968b9c5
- [x] 1.6 Star toggle and expand work independently; expand shows all fields + working links — 968b9c5
- [ ] 1.7 Desktop table unchanged (columns, colored-text status, `Aktualny`, row tint)
- [ ] 1.8 No regression: important toggled on mobile reflects in the table

### Phase 2: Responsive controls + FAB

#### Automated

- [ ] 2.1 Type check + build passes: `cd frontend && npm run build`
- [ ] 2.2 Lint passes: `cd frontend && npm run lint`
- [ ] 2.3 Format check passes: `cd frontend && npx prettier --check src/`

#### Manual

- [ ] 2.4 Mobile controls show search + `Filtry` + `Sortowanie`; header button hidden; FAB present
- [ ] 2.5 Filter sheet changes + combined filters update list and URL; `Wyczyść filtry` resets
- [ ] 2.6 `Sortowanie` toggles A→Z / Z→A and reorders
- [ ] 2.7 FAB navigates to add page and never obscures last card or pagination
- [ ] 2.8 Desktop controls bar + inline `Dodaj lek` unchanged

### Phase 3: Compact mobile pagination

#### Automated

- [ ] 3.1 Type check + build passes: `cd frontend && npm run build`
- [ ] 3.2 Lint passes: `cd frontend && npm run lint`
- [ ] 3.3 Format check passes: `cd frontend && npx prettier --check src/`

#### Manual

- [ ] 3.4 Mobile pagination shows `‹ page / totalPages ›` + `Leków: total`; arrows disable/navigate correctly
- [ ] 3.5 Desktop verbose pagination + page-size select unchanged
- [ ] 3.6 Page change on mobile persists across resize to desktop (URL-driven)

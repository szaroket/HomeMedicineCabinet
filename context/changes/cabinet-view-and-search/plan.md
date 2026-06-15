# Cabinet View and Search Implementation Plan

## Overview

S-01 shipped an "add a medication" flow and a cabinet list that shows **every**
entry, unsorted-beyond-name, with a computed expiry status. S-02 turns that flat
list into the cabinet the PRD describes (US-03, FR-004, FR-006): a list the user
can **filter by expiry status**, **search by medication name or active
ingredient**, **sort by name**, and **page through**, where each entry also shows
its registry-sourced **route of administration** and **leaflet /
specification links** (FR-011, FR-012).

We deliver this in four small, independently verifiable phases: (1) backend adds
the display fields, (2) frontend renders them, (3) backend adds
filter/search/sort/pagination, (4) frontend adds the controls.

## Current State Analysis

- **List endpoint exists but is parameterless.** `GET /api/v1/cabinet/entries`
  returns `list[CabinetEntryOut]` — all of the user's entries, joined to
  `medication_registry`, ordered by name, with a Python-computed `status`
  (`backend/app/api/v1/cabinet/router.py:30`, `crud.py:132`, `service.py:168`).
- **Status is computed, not stored.** `classify_status(expiry_date, today,
  threshold)` returns `valid` / `expiring` / `expired`
  (`service.py:127`). The user's `expiry_threshold_days` is fetched by the
  facade from the users domain, defaulting to `DEFAULT_EXPIRY_THRESHOLD_DAYS=30`
  (`cabinet/facade.py:18`, `utilities/const.py:3`).
- **All display fields already exist on the registry row.** `MedicationRegistry`
  carries `marketing_authorization_holder`, `manufacturer`,
  `route_of_administration`, `leaflet_url`, `specification_url`,
  `active_ingredient` (`medicines/models.py:18-27`). F-03 did not miss anything;
  `CabinetEntryOut` simply doesn't surface them yet (`cabinet/schemas.py:75`).
- **Categories are not assignable yet.** `CabinetEntry.is_important` /
  `is_used` columns exist (`cabinet/models.py:25-26`) but nothing sets them —
  that is S-04/S-05. The out-of-stock badge (FR-020) is S-04.
- **A proven full-text search exists.** `medication_registry.search_vector` is a
  GIN-indexed tsvector over name + active ingredient; `medicines/service.py:20`
  `_build_tsquery` turns raw input into an injection-safe prefix `to_tsquery`
  string, run by `medicines/crud.py:16`.
- **Frontend list is a static table.** `CabinetList` renders fixed columns from
  `useCabinetEntries()` (no params); the TS `CabinetEntryOut` mirrors the backend
  (`frontend/src/features/cabinet/...`). React Router is wired, so
  `useSearchParams` is available.
- **Scale is small.** PRD `target_scale: small/low/small`; a single user's
  cabinet is small, but we still paginate in the DB for correct totals and to
  stay forward-compatible.

## Desired End State

A logged-in user opens the cabinet and sees a paginated list (default 20/page,
selectable 20/50/100). They can type in a search box to narrow by name or active
ingredient, pick an expiry-status filter (valid / expiring / expired), toggle
name sort A↔Z, and page through results. Status filter + search + sort combine in
one request. Each row reveals (on expand) the route of administration and links to
the drug leaflet and specification. Filter/sort/search/page state
lives in the URL so views are shareable and the future S-07 dashboard can
deep-link to a pre-filtered cabinet. An empty cabinet and a no-match result show
**different** messages.

**Verification:** `GET /api/v1/cabinet/entries?status=expiring&q=apap&sort=name&order=desc&page=1&page_size=20`
returns a `{ items, total, page, page_size }` envelope whose `items` are the
expiring entries matching "apap", name-descending; the UI reflects the same state
from the URL; `uv run pytest` and `npm run build` pass.

### Key Discoveries:

- `classify_status` (`service.py:127`) is the single source of truth for status;
  the Phase 3 SQL predicates must mirror it exactly and be locked by a parity
  test, or status-filtered pages will disagree with the displayed badge.
- `_build_tsquery` (`medicines/service.py:20`) is private; Phase 3 promotes it to
  a public `build_tsquery` so the **cabinet facade** can reuse it cross-domain
  (the facade is the only layer permitted to call another domain — AGENTS.md).
- `search_vector` lives on `medication_registry`; cabinet search applies the
  predicate inside cabinet's existing `cabinet_entries ⨝ medication_registry`
  join — no change to the medicines domain query.
- Raw `text()` predicates require the crud session typed as
  `sqlalchemy.ext.asyncio.AsyncSession` (already the case in `cabinet/crud.py`) —
  lessons L-002.
- Every new `session.execute` must be wrapped in `try/except SQLAlchemyError` →
  `CabinetDatabaseError` → HTTP 503 — lessons L-004.
- FastAPI query params with Pydantic constraints must keep `Query()` **inside**
  `Annotated`, not as a default value — lessons L-003.

## What We're NOT Doing

- **No category filter (important / used).** Deferred to S-04/S-05 — nothing can
  set those columns yet, so a filter would act on always-false data.
- **No out-of-stock status filter / badge (FR-020).** Depends on the important
  category + global minimum; S-04.
- **No sort columns other than name.** FR-004 only requires sort-by-name.
- **No detail/edit page.** Entry management (increment/decrement/delete) is S-03.
- **No registry data changes.** Display-only; the registry is read.
- **No inline PDF preview.** Links only (FR-012); preview is a v2 non-goal.
- **No new DB migration.** All needed columns already exist.

## Implementation Approach

Phases 1–2 ship the display fields (additive, the list contract stays a bare
list, so the app keeps working). Phases 3–4 ship the
filter/search/sort/pagination behaviour; Phase 3 changes the response to a
paginated envelope (verified via Swagger and tests) and Phase 4 makes the
frontend consume it and adds the controls. Status filtering is pushed into SQL so
pagination totals are correct; search reuses the registry full-text index; the
frontend keeps all list state in the URL.

## Critical Implementation Details

- **Status SQL ↔ `classify_status` parity (Phase 3).** With `today` and the
  user's `threshold`, the predicates must be: `expired` → `expiry_date < today`;
  `expiring` → `today <= expiry_date <= today + threshold`; `valid` →
  `expiry_date > today + threshold`. These exactly partition the date line the
  same way `classify_status` does. A test must assert the SQL filter and the
  Python classifier agree for boundary dates (`today`, `today+threshold`,
  `today+threshold+1`).
- **Envelope is a coordinated contract change (Phases 3↔4).** Switching
  `GET /cabinet/entries` from `list[CabinetEntryOut]` to
  `{ items, total, page, page_size }` breaks the Phase-1/2 frontend until Phase 4
  lands. This is expected; between Phase 3 and Phase 4 the list is verified via
  Swagger, not the UI. **Deploy constraint:** Phases 3 and 4 land in the same
  merge/deploy — Phase 3 is never shipped standalone to any environment, or the
  live cabinet list breaks.
- **`page_size` allow-list.** Only 20 / 50 / 100 are accepted; any other value is
  a 422. Do not accept arbitrary page sizes (prevents unbounded result sets).

---

## Phase 1: Backend — entry display fields

### Overview

Surface the registry display fields on each cabinet entry without changing the
list's shape or behaviour. Purely additive: the endpoint still returns a bare
list ordered by name.

### Changes Required:

#### 1. Response schema

**File**: `backend/app/api/v1/cabinet/schemas.py`

**Intent**: Add the FR-011/FR-012 display fields to `CabinetEntryOut` so each
entry carries its route of administration and document links.

**Contract**: Add to `CabinetEntryOut`: `route_of_administration: str | None`,
`leaflet_url: str | None`, `specification_url: str | None`. (`AddEntryOut` is
unchanged — the add flow does not display these.)

#### 2. Service mapping

**File**: `backend/app/api/v1/cabinet/service.py`

**Intent**: Populate the new fields when building each `CabinetEntryOut` in
`list_entries`.

**Contract**: In the `list_entries` row loop (`service.py:187`), set
`route_of_administration = variant.route_of_administration`,
`leaflet_url = variant.leaflet_url`,
`specification_url = variant.specification_url`. The existing
`crud.list_entries` join already returns the full `MedicationRegistry` row, so no
crud change is needed.

### Success Criteria:

#### Automated Verification:

- Linting passes: `cd backend && uv run ruff check . && uv run ruff format --check .`
- Backend tests pass: `cd backend && uv run pytest`
- Existing `list_entries` service test updated to assert the three new fields.

#### Manual Verification:

- In Swagger (`/docs`), `GET /cabinet/entries` shows the three new fields on each
  item, populated for a real entry.

**Implementation Note**: After completing this phase and all automated
verification passes, pause for manual confirmation before proceeding.

---

## Phase 2: Frontend — render entry display fields

### Overview

Show the route of administration and leaflet/specification links per
entry, consuming the still-bare list. Keeps the table scannable on mobile by
revealing details in an expandable row.

### Changes Required:

#### 1. API types

**File**: `frontend/src/features/cabinet/api/cabinet-api.ts`

**Intent**: Mirror the three new backend fields on the TS `CabinetEntryOut`.

**Contract**: Add `route_of_administration: string | null`,
`leaflet_url: string | null`, `specification_url: string | null` to the
`CabinetEntryOut` interface. `listEntries()` is otherwise unchanged this phase.

#### 2. List row with expandable detail

**File**: `frontend/src/features/cabinet/components/cabinet-list.tsx`

**Intent**: Add a per-row expand affordance that reveals a detail panel with
Droga podania and links to Ulotka / Charakterystyka. Links open in a
new tab; missing values show "—"; missing links are omitted (no dead link).

**Contract**: Each entry row gains a toggle (chevron) controlling a collapsible
detail sub-row. Detail labels (Polish): `Droga podania`, `Ulotka`,
`Charakterystyka`. `leaflet_url` / `specification_url` render as
`<a target="_blank" rel="noopener noreferrer">`; render the link only when the
URL is non-null. Expansion state is local component state (not URL).

### Success Criteria:

#### Automated Verification:

- Type-check + build passes: `cd frontend && npm run build`
- Lint passes: `cd frontend && npm run lint`
- Format passes: `cd frontend && npx prettier --check src/`

#### Manual Verification:

- Expanding a row shows the route of administration and working leaflet/specification
  links (open the correct official pages in a new tab).
- A row whose registry data lacks a route or a link shows "—" / omits the link
  without layout breakage.
- Layout is usable on a narrow (mobile) viewport.

**Implementation Note**: Pause for manual confirmation before proceeding.

---

## Phase 3: Backend — filtering, search, sort, pagination

### Overview

Add query parameters to the list endpoint, push status filtering into SQL,
reuse the registry full-text search, sort by name, and paginate in the database
with an accurate total. Change the response to a paginated envelope.

### Changes Required:

#### 1. Promote the tsquery builder

**File**: `backend/app/api/v1/medicines/service.py`

**Intent**: Make the injection-safe prefix-tsquery builder reusable by the
cabinet facade (cross-domain reuse goes through the facade per AGENTS.md).

**Contract**: Rename `_build_tsquery` → public `build_tsquery(query: str) -> str | None`
(keep behaviour identical); update the internal caller. Returns None when the
query has < 2 effective characters.

#### 2. Paginated envelope schema

**File**: `backend/app/api/v1/cabinet/schemas.py`

**Intent**: Define the paginated response wrapper.

**Contract**: Add `CabinetPageOut(BaseModel)` with `items: list[CabinetEntryOut]`,
`total: int`, `page: int`, `page_size: int`.

#### 3. List query with filters, search, sort, pagination

**File**: `backend/app/api/v1/cabinet/crud.py`

**Intent**: Replace the all-rows `list_entries` query with a filtered, searched,
sorted, paginated one plus a matching count, so the service can build an accurate
envelope.

**Contract**: Provide a crud function (or pair) that accepts `user_id`,
`today: date`, `threshold: int`, `status: str | None`, `tsquery: str | None`,
`order: "asc" | "desc"`, `limit: int`, `offset: int` and returns the page rows
`list[tuple[CabinetEntry, MedicationRegistry]]` **and** the total count under the
same filters. Build on the existing `select(CabinetEntry, MedicationRegistry)`
join (`crud.py:132`):
- status → date predicates on `CabinetEntry.expiry_date` per the parity rule in
  Critical Implementation Details;
- search → `text("medication_registry.search_vector @@ to_tsquery('simple', :tsquery)")`
  with `tsquery` bound (never interpolated);
- sort → `ORDER BY lower(medication_registry.name) <asc|desc>, cabinet_entries.id ASC`
  — the `id` tiebreaker makes paging deterministic when names collide; the
  asc/desc toggle flips only the name key, not the tiebreaker. The COUNT query
  needs no ORDER BY.
- pagination → `LIMIT/OFFSET`; total → `select(func.count())` over the same
  filtered join (no limit/offset).

Wrap every `await session.execute(...)` in `try/except SQLAlchemyError` →
`CabinetDatabaseError` (lessons L-004). Session stays typed
`sqlalchemy.ext.asyncio.AsyncSession` (L-002).

#### 4. Service orchestration

**File**: `backend/app/api/v1/cabinet/service.py`

**Intent**: Accept the new parameters, call the filtered crud, map rows to
`CabinetEntryOut` (status still via `classify_status` for the badge), and assemble
`CabinetPageOut`.

**Contract**: Extend `list_entries(...)` with `status`, `tsquery`, `order`,
`page`, `page_size`; compute `offset = (page-1)*page_size`; return
`CabinetPageOut(items=..., total=..., page=page, page_size=page_size)`. Reuse the
existing per-row mapping (including Phase 1 display fields and the
`_tablet_capacity_invalid` guard).

#### 5. Facade wiring

**File**: `backend/app/api/v1/cabinet/facade.py`

**Intent**: Fetch the user's expiry threshold (as today) and turn the raw search
string into a safe tsquery via the medicines builder, then delegate.

**Contract**: Extend `list_entries(...)` to accept the raw params; call
`medicines_service.build_tsquery(q)` when `q` is provided; pass `tsquery`,
`status`, `order`, `page`, `page_size`, and the resolved `threshold` to
`cabinet_service.list_entries`. Returns `CabinetPageOut`.

#### 6. Shared `NonEmptyStr` alias

**File**: `backend/app/utilities/types.py` (new),
`backend/app/api/v1/medicines/router.py`

**Intent**: Give the stripped, non-empty query-string alias a shared home so the
cabinet router reuses it instead of importing a sibling router's private alias or
redefining it.

**Contract**: Create `app/utilities/types.py` defining
`NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]`
(move the existing L-003 comment from `medicines/router.py:17-23` with it).
Update `medicines/router.py` to import `NonEmptyStr` from `app.utilities.types`
and delete its local definition (behaviour identical; existing
`Annotated[NonEmptyStr, Query(...)]` call sites unchanged).

#### 7. Router params + envelope

**File**: `backend/app/api/v1/cabinet/router.py`

**Intent**: Expose the query parameters with validation and return the envelope.

**Contract**: `GET /cabinet/entries` `response_model=CabinetPageOut`; import
`NonEmptyStr` from `app.utilities.types`. Params (all `Query()` **inside**
`Annotated`, L-003):
- `status: Literal["valid","expiring","expired"] | None = None`
- `q: Annotated[NonEmptyStr, Query(description=...)] | None = None` (stripped;
  None when absent — `Query()` stays inside `Annotated` so the OpenAPI
  description is preserved and the L-003 convention holds)
- `sort: Literal["name"] = "name"`
- `order: Literal["asc","desc"] = "asc"`
- `page: int = Query(1, ge=1)`
- `page_size: Literal[20,50,100] = 20`

Keep the existing error→HTTP mapping (`CabinetDatabaseError`/`UserDatabaseError`
→ 503, `CabinetError` → 400, catch-all → 500).

### Success Criteria:

#### Automated Verification:

- Lint + format: `cd backend && uv run ruff check . && uv run ruff format --check .`
- Tests pass: `cd backend && uv run pytest`
- **Parity test**: SQL status filter and `classify_status` agree on boundary
  dates (`today`, `today+threshold`, `today+threshold+1`) for each status.
- Search test: a `q` matching name and a `q` matching active ingredient each
  return the expected entries; a `q` < 2 effective chars returns all entries
  (no filter).
- Pagination test: `total` reflects the full filtered set; `items` length and
  contents match `page`/`page_size`; `order=desc` reverses name order.
- Validation test: `page_size=25` → 422; `status=foo` → 422.

#### Manual Verification:

- In Swagger, combining `status` + `q` + `order` + `page` + `page_size` returns a
  correct envelope; totals look right against a seeded cabinet.

**Implementation Note**: Pause for manual confirmation before proceeding.

---

## Phase 4: Frontend — controls + URL-driven state

### Overview

Consume the paginated envelope and add the search, status filter, name-sort
toggle, page-size selector, and pagination controls, all backed by URL query
params so views are shareable and S-07-deep-linkable. Add distinct empty states.

### Changes Required:

#### 1. API + query layer

**File**: `frontend/src/features/cabinet/api/cabinet-api.ts`,
`frontend/src/features/cabinet/api/cabinet-queries.ts`

**Intent**: Send the new params and consume the envelope; key the query by params
so each view caches independently while staying invalidatable as a group.

**Contract**: Add a `CabinetListParams` type (`status?`, `q?`, `sort`, `order`,
`page`, `page_size`) and `CabinetPageOut` (`items`, `total`, `page`,
`page_size`); `listEntries(params)` serializes params to the query string and
returns `CabinetPageOut`. `cabinetKeys.entries(params)` includes the params;
`useAddEntry`'s invalidation targets the `["cabinet","entries"]` prefix so it
still clears all variants. `useCabinetEntries(params)` passes them through.

#### 2. URL-state controls

**File**: `frontend/src/features/cabinet/components/cabinet-page.tsx` (and small
control pieces under `cabinet/components/`)

**Intent**: Drive list state from the URL via `useSearchParams`; render the
controls; reset to page 1 when a filter/search/sort/page-size changes.

**Contract**: Read/write `status`, `q`, `sort`, `order`, `page`, `page_size` from
`useSearchParams` (sensible defaults when absent: `sort=name`, `order=asc`,
`page=1`, `page_size=20`). Controls: a debounced search input (writes `q` to the
URL via the existing `use-debounce` hook), a status filter (All / Ważny / Bliski
termin / Przeterminowany), a page-size selector (20/50/100), and prev/next
pagination showing current page and total page count derived from `total`.
Changing any filter/search/sort/page-size resets `page` to 1.

#### 3. List rendering + empty states

**File**: `frontend/src/features/cabinet/components/cabinet-list.tsx`

**Intent**: Render `items` from the envelope and distinguish an empty cabinet
from a no-match result.

**Contract**: Accept the page data (items + total). When `total === 0` and no
filter/search is active → existing "Apteczka jest pusta. Dodaj pierwszy lek."
When `total === 0` **with** an active filter/search → a distinct message (e.g.
"Brak leków spełniających kryteria.") plus a "Wyczyść filtry" action that clears
the URL params. Preserve loading/error states. Keep the Phase 2 expandable detail.

### Success Criteria:

#### Automated Verification:

- Build passes: `cd frontend && npm run build`
- Lint passes: `cd frontend && npm run lint`
- Format passes: `cd frontend && npx prettier --check src/`

#### Manual Verification:

- Typing in search narrows the list (debounced) and updates the URL `q`.
- Selecting a status filter shows only matching entries; combined with search it
  intersects; clearing returns all.
- Name sort toggle reverses order; page-size selector changes rows-per-page;
  prev/next pages through with a correct page count.
- Reloading the page preserves all filter/sort/search/page state from the URL;
  pasting a filtered URL into a new tab reproduces the same view.
- Empty cabinet vs. no-match show different messages; "Wyczyść filtry" resets.
- Usable on a narrow (mobile) viewport.

**Implementation Note**: Final phase — confirm the end-to-end flow with the human.

---

## Testing Strategy

### Unit Tests (backend, pytest):

- `classify_status` ↔ SQL status-filter parity at boundary dates (per status).
- `build_tsquery` behaviour unchanged after promotion (move/extend existing
  medicines test as needed).

### Integration Tests (backend, httpx AsyncClient):

- `GET /cabinet/entries` with `status`, `q` (name and active-ingredient matches),
  `order=desc`, and `page`/`page_size` returns the correct envelope and totals.
- Param validation: `page_size=25` → 422; `status=foo` → 422; blank/whitespace
  `q` rejected or treated as absent per the `NonEmptyStr` contract.
- Reuse `authed_client`, `mock_session`, `fake_user` fixtures from
  `backend/tests/conftest.py`; pass `spec=` on any new mocks (AGENTS.md).

### Manual Testing Steps:

1. Seed a cabinet with several entries across valid/expiring/expired and varied
   names/active ingredients.
2. Exercise each control individually, then in combination, watching the URL.
3. Reload and paste-into-new-tab to confirm URL state restoration.
4. Confirm leaflet/specification links open the correct official pages.
5. Verify both empty states and "Wyczyść filtry".
6. Check a narrow mobile viewport.

## Performance Considerations

Status/search/sort/pagination all run in a single indexed query; search reuses
the existing `search_vector` GIN index, keeping within the < 500ms p95 NFR. DB
-side `LIMIT/OFFSET` + `COUNT` avoids loading the whole cabinet per request.

## Migration Notes

None — every column used already exists (`CabinetEntry`, `MedicationRegistry`).
No Alembic migration. Any DB-touching verification commands must run from native
PowerShell, not the agent Bash tool (lessons L-001) — but this slice needs no
schema change.

## References

- Roadmap slice S-02: `context/foundation/roadmap.md:137`
- PRD: US-03, FR-004, FR-006, FR-011, FR-012 (`context/foundation/prd.md`)
- Lessons: L-002 (session typing), L-003 (Query in Annotated), L-004 (SQLAlchemyError wrap)
- Full-text search pattern: `backend/app/api/v1/medicines/{service,crud,queries}.py`
- Existing list path: `backend/app/api/v1/cabinet/{router,service,crud,facade}.py`
- Producer-field origin: `context/changes/registry-import/plan-brief.md:38`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Backend — entry display fields

#### Automated

- [x] 1.1 Lint + format pass (`ruff check` / `ruff format --check`) — ae5ad12
- [x] 1.2 Backend tests pass (`uv run pytest`) — ae5ad12
- [x] 1.3 `list_entries` test asserts the three new fields — ae5ad12

#### Manual

- [x] 1.4 Swagger shows the three new fields populated on a real entry — ae5ad12

### Phase 2: Frontend — render entry display fields

#### Automated

- [ ] 2.1 Build passes (`npm run build`)
- [ ] 2.2 Lint passes (`npm run lint`)
- [ ] 2.3 Format passes (`prettier --check src/`)

#### Manual

- [ ] 2.4 Expanding a row shows route of administration and working leaflet/spec links
- [ ] 2.5 Missing route/link degrades gracefully ("—" / omitted link)
- [ ] 2.6 Usable on a narrow (mobile) viewport

### Phase 3: Backend — filtering, search, sort, pagination

#### Automated

- [ ] 3.1 Lint + format pass
- [ ] 3.2 Backend tests pass (`uv run pytest`)
- [ ] 3.3 Parity test: SQL status filter ↔ `classify_status` at boundary dates
- [ ] 3.4 Search test: name match and active-ingredient match; < 2 chars = no filter
- [ ] 3.5 Pagination test: correct `total`, page slicing, and `order=desc`
- [ ] 3.6 Validation test: `page_size=25` → 422; `status=foo` → 422

#### Manual

- [ ] 3.7 Swagger: combined status + q + order + page + page_size returns a correct envelope

### Phase 4: Frontend — controls + URL-driven state

#### Automated

- [ ] 4.1 Build passes (`npm run build`)
- [ ] 4.2 Lint passes (`npm run lint`)
- [ ] 4.3 Format passes (`prettier --check src/`)

#### Manual

- [ ] 4.4 Search narrows the list (debounced) and updates URL `q`
- [ ] 4.5 Status filter + search intersect; clearing returns all
- [ ] 4.6 Sort toggle, page-size selector, and prev/next pagination work with correct page count
- [ ] 4.7 Reload and paste-into-new-tab restore full state from the URL
- [ ] 4.8 Distinct empty states + "Wyczyść filtry" reset
- [ ] 4.9 Usable on a narrow (mobile) viewport

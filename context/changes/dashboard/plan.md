# Dashboard Implementation Plan

## Overview

Build the authenticated landing screen at `/` (S-07, FR-009) as a five-count
navigation hub. A new backend `GET /cabinet/summary` endpoint returns the five
counts; the frontend renders them as tinted stat cards, each a clickable link to
the cabinet list pre-filtered to the matching status. Also add a dashboard entry
to the sidebar menu and confirm login/register land on the dashboard.

## Current State Analysis

- **Dashboard is a stub.** `frontend/src/features/dashboard/components/dashboard-page.tsx`
  renders a single "Moja apteczka" link inside `AppLayout`;
  `dashboard-placeholder.tsx` is unused. The route `/` → `DashboardPage` is
  already wired in `frontend/src/app/router.tsx`.
- **Login already lands on `/`.** `login-form.tsx:22` and `register-form.tsx:27`
  both `navigate("/")` on success; `/` maps to `DashboardPage`. This requirement
  is already satisfied — the plan verifies and preserves it, it does not change
  the redirect.
- **Cabinet filtering is fully URL-driven.** `frontend/src/features/cabinet/components/cabinet-page.tsx`
  parses `?status=valid|expiring|expired`, `?below_minimum=true`, `?sufficiency=…`,
  `?category=…`. So each dashboard card only needs a `<Link>` to the right query
  string — no new filter plumbing.
- **All classification/aggregation logic already exists on the backend.**
  `backend/app/api/v1/cabinet/crud.py::_build_base_query` builds the filtered
  join query for status / below_minimum / sufficiency; `list_entries` already
  runs `select(func.count()).select_from(base.subquery())` for its total.
  `cabinet/facade.py::_resolve_prefs` resolves the user's `expiry_threshold_days`
  and `min_package_count` (falling back to `DEFAULT_EXPIRY_THRESHOLD_DAYS` /
  `DEFAULT_MIN_PACKAGE_COUNT`). The S-06 badge rule `is_below_minimum` lives in
  `cabinet/service.py`.
- **Status categories partition the cabinet by expiry** (expired `< today`;
  expiring `today..today+threshold`; valid `> today+threshold`) — mutually
  exclusive and exhaustive, so `total == valid + expiring + expired`.
- **Sidebar menu has no dashboard entry.** `app-sidebar.tsx` `TOP_NAV` = `[/cabinet]`,
  `BOTTOM_NAV` = `[/settings]`. Nav icons are `<img>` assets (`capsule.png`,
  `gear.png`); no home/dashboard icon asset exists.
- **Conventions to follow:** per-feature `api/` (typed fetchers + TanStack Query
  hooks + query-key factory, no barrel files); facade-for-cross-domain; L-004
  (wrap every `session.execute` in `try/except SQLAlchemyError` → domain error);
  L-006 (imports at top); Google docstrings with typed sections; all UI text in
  Polish.

## Desired End State

Logging in (or registering) lands the user on `/`, which shows a centered title
(**Panel główny**) over five tinted stat cards — Łącznie leków, Aktualne, Bliski
termin, Przeterminowane, Brak zapasu — laid out in a row on desktop and stacked
on mobile. Each card shows a count fetched from `GET /cabinet/summary` and links
to the cabinet list pre-filtered to that status; the count and the resulting list
always agree because both derive from the same query. An empty cabinet shows a
friendly "add your first medication" call-to-action instead of five zeros;
loading shows skeleton cards; a failed request shows a Polish error with a retry
button. The sidebar menu includes a "Panel główny" link to `/`, active only on
the exact `/` route.

Verify: log in → land on `/` showing five cards with correct numbers → click each
card → cabinet list is pre-filtered to the matching status with a matching count →
sidebar "Panel główny" link navigates back to `/`.

### Key Discoveries:

- `cabinet/crud.py::_build_base_query` (backend/app/api/v1/cabinet/crud.py:263)
  is the reusable filtered query; a count is `select(func.count()).select_from(base.subquery())`
  as already done at crud.py:392.
- `cabinet/facade.py::_resolve_prefs` (backend/app/api/v1/cabinet/facade.py:24)
  is the established way to get `expiry_threshold_days` + `min_package_count`.
- `cabinet-page.tsx` already applies all needed URL filters (frontend/src/features/cabinet/components/cabinet-page.tsx:52),
  so card links need no cabinet-side changes.
- `NavLink to="/"` matches every route unless given `end`; the sidebar link must
  set `end` to avoid always-active styling.

## What We're NOT Doing

- No notifications/alert preview, charts, recent-activity feed, "quick action"
  buttons, or the bottom "Leki bliskie terminu" list from the `dashboard-v1.jpg`
  mockup. Scope is FR-009's five counts only.
- No "Ważne leki" (important) card — the FR-009 set uses "Aktualne" (valid), not
  the mockup's important card.
- No change to the login/register redirect logic (already targets `/`).
- No new cabinet filters, no changes to `GET /cabinet/entries`.
- No new backend domain — the summary endpoint lives in the existing `cabinet`
  domain (it is a cabinet aggregation).
- No Playwright E2E in this slice (routed through `/10x-e2e` separately per
  CLAUDE.md).

## Implementation Approach

Backend first: add a thin count path to the cabinet domain that reuses the
existing filtered query, exposed as `GET /cabinet/summary`. Then build the
frontend dashboard feature's data layer (fetcher + query hook), then its UI
(cards + states), then wire navigation. Each phase is independently verifiable;
the frontend phases can be developed against the real endpoint from Phase 1.

## Critical Implementation Details

- **Counts derive from one conditional-aggregation query over `_build_base_query`.**
  The whole point of the backend endpoint (vs client-side derivation) is that the
  counts and the list agree. `count_summary` builds the *unfiltered*
  `_build_base_query` subquery (all of the user's joined entries — the same row
  shape `list_entries` uses) and sums per-bucket `CASE` expressions in a single
  query rather than issuing one filtered count per bucket. The expiry-status
  boundaries mirror `_build_base_query`'s status branches and
  `service.classify_status`; the below-minimum bucket mirrors
  `service.is_below_minimum` and the crud `below_minimum` clause (`is_important
  AND package_count < minimum`). This trades the single-shared-query guarantee for
  a single round-trip: the status boundaries and below-minimum rule now live in
  three copies kept in sync by hand, so a parity test (each `summary` status count
  == `GET /cabinet/entries?status=…` total) guards the status seam against drift.
- **"Brak zapasu" is deliberately narrowed to below-minimum only — needs product
  sign-off.** FR-020 fires the out-of-stock badge on an important entry when
  EITHER (a) it is close-to-expiry/expired OR (b) its package count is below
  minimum. This card's count uses `below_minimum=True`, which is condition (b)
  ONLY — an important, well-stocked but expiring entry shows the badge yet is not
  counted here. This is intentional: the cabinet exposes `status` and
  `below_minimum` as separate filters with no single "(a) OR (b)" filter, so
  matching the full badge would require either a new combined cabinet filter
  (violating "No new cabinet filters" scope) or breaking the count↔list invariant
  that the whole endpoint is built around. **Product sign-off obtained
  (2026-07-10): "Brak zapasu" is confirmed as below-minimum-only. Gate closed —
  Phase 3 may ship this count.**
- **`NavLink to="/"` needs `end`.** Without it the dashboard link renders active
  on `/cabinet`, `/settings`, etc.

## Phase 1: Backend summary endpoint

### Overview

Add a cabinet count aggregation exposed as `GET /cabinet/summary`, reusing the
existing filtered query and preference resolution.

### Changes Required:

#### 1. Count helper in cabinet crud

**File**: `backend/app/api/v1/cabinet/crud.py`

**Intent**: Add a single-query aggregation over `_build_base_query` that returns
all five counts at once, so a dashboard load is one round-trip. Follows L-004
(wrap `session.execute` in `try/except SQLAlchemyError` → `CabinetDatabaseError`).

**Contract**: `async def count_summary(session, user_id, today, threshold, min_package_count) -> SummaryCounts`
(a `NamedTuple` of `total`, `valid`, `expiring`, `expired`, `out_of_stock`). Body
builds the *unfiltered* `_build_base_query(...).subquery()` and selects
`func.count()` plus per-bucket `sum(case(...))` expressions: valid/expiring/expired
by the same expiry boundaries as `_build_base_query`'s status branches, and
out_of_stock by `is_important AND package_count < min_package_count`. Search/
category/sufficiency are not applied.

#### 2. Summary computation in cabinet service

**File**: `backend/app/api/v1/cabinet/service.py`

**Intent**: Add a service function that computes today (UTC) and issues the five
counts via `crud.count_summary`, returning a `CabinetSummaryOut`. Pure
orchestration over this domain's crud — no cross-domain calls here.

**Contract**: `async def summarize_cabinet(session, user_id, expiry_threshold_days, min_package_count) -> CabinetSummaryOut`.
Calls `crud.count_summary` once and maps its `SummaryCounts` onto
`CabinetSummaryOut`. `out_of_stock` is deliberately below-minimum-only, not the
full FR-020 badge; see the "Brak zapasu" narrowing note in Critical
Implementation Details. Uses the same `today`/UTC convention as `list_entries`.

#### 3. `CabinetSummaryOut` schema

**File**: `backend/app/api/v1/cabinet/schemas.py`

**Intent**: Response model for the endpoint.

**Contract**: `class CabinetSummaryOut(BaseModel)` with int fields `total`,
`valid`, `expiring`, `expired`, `out_of_stock`.

#### 4. Facade orchestration

**File**: `backend/app/api/v1/cabinet/facade.py`

**Intent**: Resolve user prefs (reusing `_resolve_prefs`) and delegate to
`service.summarize_cabinet`, mirroring `list_entries`.

**Contract**: `async def get_summary(session, user_id) -> CabinetSummaryOut`.

#### 5. Route

**File**: `backend/app/api/v1/cabinet/router.py`

**Intent**: Add `GET /cabinet/summary` guarded like the rest of the cabinet
router, calling `cabinet_facade.get_summary`, with the same error-mapping pattern
as `list_entries` (`CabinetDatabaseError`/`UserDatabaseError` → 503, `CabinetError`
→ 400, unexpected → 500).

**Contract**: `@router.get("/summary", response_model=CabinetSummaryOut)`; handler
signature mirrors `list_entries` (current_user + session deps). No new router
registration needed — `cabinet_router` is already included in
`app/api/v1/router.py`.

### Success Criteria:

#### Automated Verification:

- Lint/format passes: `cd backend && uv run ruff check . && uv run ruff format --check .`
- Backend unit tests pass: `cd backend && uv run pytest tests/cabinet`
- Backend typecheck passes: `cd backend && uv run pyright` (or the project's configured type checker)
- Integration test: authed `GET /cabinet/summary` returns the five int fields; counts match a seeded fixture across empty cabinet, expiry-threshold boundaries (exactly-today, exactly-threshold-day), and a below-minimum important entry.
- Parity: for a seeded user, `summary.total == valid + expiring + expired`, and each status count equals `GET /cabinet/entries?status=<s>`'s `total`.

#### Manual Verification:

- `GET /cabinet/summary` in the OpenAPI docs returns sensible counts for a real account.

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation before proceeding.

---

## Phase 2: Frontend dashboard data layer

### Overview

Add the dashboard feature's typed fetcher and TanStack Query hook, and ensure the
summary refetches when cabinet entries change.

### Changes Required:

#### 1. API fetcher + type

**File**: `frontend/src/features/dashboard/api/dashboard-api.ts`

**Intent**: Typed fetcher for the summary, mirroring `cabinet-api.ts` style
(`apiJson`).

**Contract**: `interface CabinetSummaryOut { total; valid; expiring; expired; out_of_stock: number }`
and `export function getCabinetSummary(): Promise<CabinetSummaryOut>` hitting
`/cabinet/summary`.

#### 2. Query hook + key factory

**File**: `frontend/src/features/dashboard/api/dashboard-queries.ts`

**Intent**: `useCabinetSummary()` query hook plus a `dashboardKeys` factory,
following `cabinet-queries.ts`.

**Contract**: `dashboardKeys.summary = () => ["cabinet", "summary"] as const`;
`useCabinetSummary()` wraps `useQuery` on that key. Keying under the `["cabinet", …]`
namespace lets the existing cabinet mutations' `invalidateQueries({ queryKey: ["cabinet","entries"] })` stay narrow while a summary-specific invalidation is added next.

#### 3. Invalidate summary on cabinet mutations

**File**: `frontend/src/features/cabinet/api/cabinet-queries.ts`

**Intent**: The five cabinet mutations (`useAddEntry`, `useToggleImportant`,
`useSetUsage`, `useDeleteEntry`, `useUpdateQuantity`) currently invalidate
`cabinetKeys.entriesAll()`. Extend each `onSuccess` to also invalidate the
dashboard summary so counts stay live after add/delete/quantity/importance/usage
changes.

**Contract**: add `queryClient.invalidateQueries({ queryKey: ["cabinet", "summary"] })`
alongside the existing entries invalidation in each mutation's `onSuccess`.
Invalidate the **literal** key here (do not import `dashboardKeys` from the
dashboard feature): dashboard depends on cabinet, so a cabinet→dashboard import
would invert the dependency direction. Add a short comment at this invalidation
noting that `["cabinet","summary"]` must stay in sync with
`dashboardKeys.summary()` (dashboard-queries.ts), which is the source of truth
for the key, so the two literal copies don't silently drift.

### Success Criteria:

#### Automated Verification:

- Lint passes: `cd frontend && npm run lint`
- Typecheck passes: `cd frontend && npx tsc -b`
- Data-seam tests pass: `cd frontend && npx vitest run src/features/dashboard/api` — `getCabinetSummary` calls the right path and parses the response; `useCabinetSummary` returns data on success and surfaces error state.

#### Manual Verification:

- With the dev server running, the dashboard query fires once on load and refetches after adding/deleting a cabinet entry.

**Implementation Note**: Pause for manual confirmation before proceeding.

---

## Phase 3: Frontend dashboard UI

### Overview

Replace the stub with the five-card hub, wire each card to its pre-filtered
cabinet link, and handle loading / empty / error states.

### Changes Required:

#### 1. Stat card component

**File**: `frontend/src/features/dashboard/components/summary-card.tsx`

**Intent**: A single tinted card rendering a Polish label + count, wrapped in a
`react-router-dom` `<Link>` to its target; styled after `dashboard-v1.jpg` on the
existing dark slate theme, reusing the app's status color language (valid/expiring/
expired accents consistent with the cabinet status badges).

**Contract**: props `{ label: string; count: number; to: string; accent: <status token> }`.
The whole card is the link. Full-width when stacked.

#### 2. Card configuration (count → label → link)

**File**: `frontend/src/features/dashboard/components/summary-cards.config.ts`

**Intent**: Single source mapping each summary field to its Polish label and
cabinet link target, so the card→filter contract is declared in one place and is
directly testable.

**Contract**: ordered array:
`{ key: "total", label: "Łącznie leków", to: "/cabinet" }`,
`{ key: "valid", label: "Aktualne", to: "/cabinet?status=valid" }`,
`{ key: "expiring", label: "Bliski termin", to: "/cabinet?status=expiring" }`,
`{ key: "expired", label: "Przeterminowane", to: "/cabinet?status=expired" }`,
`{ key: "out_of_stock", label: "Brak zapasu", to: "/cabinet?below_minimum=true" }`.

#### 3. Loading skeleton + empty state

**File**: `frontend/src/features/dashboard/components/dashboard-skeleton.tsx` and
`frontend/src/features/dashboard/components/dashboard-empty.tsx`

**Intent**: Skeleton renders five placeholder cards matching the real layout so
there's no layout shift. Empty state (shown when `total === 0`) renders a Polish
prompt + a `<Link to="/cabinet/add">` CTA instead of five zeros.

**Contract**: presentational components, no data fetching.

#### 4. Dashboard page

**File**: `frontend/src/features/dashboard/components/dashboard-page.tsx`

**Intent**: Rewrite the stub to call `useCabinetSummary()` and render, inside
`AppLayout`, a centered title (**Panel główny**) over the responsive card grid
(row on desktop via grid/flex, `flex-col` stacked on mobile). Branch on query
state: loading → skeleton; error → Polish message + retry button (calls
`refetch`); `data.total === 0` → empty state; else → the five cards from the
config, reading counts from `data`.

**Contract**: uses `useCabinetSummary`; grid is responsive (1 column on mobile,
five across on desktop). Remove/retire `dashboard-placeholder.tsx` (unused).

### Success Criteria:

#### Automated Verification:

- Lint passes: `cd frontend && npm run lint`
- Typecheck passes: `cd frontend && npx tsc -b`
- Prettier passes: `cd frontend && npx prettier --check src/features/dashboard`
- Component tests pass: `cd frontend && npx vitest run src/features/dashboard/components` covering: loading renders skeleton; error renders retry; `total===0` renders the add-CTA empty state; populated data renders five cards whose counts and `href`s match the config (asserting each card links to the correct pre-filtered `/cabinet?...`).

#### Manual Verification:

- Dashboard shows five cards with correct numbers matching the cabinet list.
- Clicking each card lands on the cabinet list pre-filtered to that status, with a matching total.
- Empty cabinet shows the add-CTA, not five zeros.
- On mobile width the cards stack vertically; on desktop they sit in a row.
- Slow/failed backend shows skeleton then an error+retry (test against a cold Render backend if possible).

**Implementation Note**: Pause for manual confirmation before proceeding.

---

## Phase 4: Navigation & landing wiring

### Overview

Add the dashboard to the sidebar menu and confirm login/register land on the real
dashboard.

### Changes Required:

#### 1. Sidebar dashboard link

**File**: `frontend/src/app/components/app-sidebar.tsx`

**Intent**: Add a "Panel główny" item pointing at `/` to `TOP_NAV` (above
"Apteczka"). Because `/` is the index route, the link must use `end` so it is
active only on the exact path. Provide a home/grid icon; since no home icon asset
exists and nav icons are currently `<img>`, extend `SidebarLink` to accept an
inline-SVG icon node (matching the hamburger SVG style in `app-layout.tsx`) and
use it for the dashboard item, leaving the existing `<img>` items unchanged.

**Contract**: new nav entry `{ to: "/", label: "Panel główny", end: true, icon: <home svg> }`;
`SidebarLink` gains support for an optional `end` prop (passed to `NavLink`) and a
ReactNode icon; existing image-based entries keep working.

#### 2. Login-landing verification (no code change)

**File**: `frontend/src/features/auth/components/login-form.tsx`,
`frontend/src/features/auth/components/register-form.tsx`

**Intent**: Confirm both already `navigate("/")` and that `/` now renders the real
dashboard. No change unless a test reveals a regression.

**Contract**: verification only.

### Success Criteria:

#### Automated Verification:

- Lint passes: `cd frontend && npm run lint`
- Typecheck passes: `cd frontend && npx tsc -b`
- Sidebar test passes: `cd frontend && npx vitest run` for a test asserting the sidebar renders a "Panel główny" link to `/` and it is not marked active when rendered at another route.

#### Manual Verification:

- Logging in redirects to `/` and shows the dashboard cards.
- Registering redirects to `/` and shows the dashboard cards.
- Sidebar shows "Panel główny"; it is highlighted only on `/`, not on `/cabinet` or `/settings`.
- Clicking "Panel główny" from another page returns to the dashboard.

**Implementation Note**: Final phase — confirm the full flow end-to-end.

---

## Testing Strategy

### Unit Tests:

- Backend: `count_entries` / `summarize_cabinet` counts for empty cabinet,
  expiry-threshold boundaries (today, today+threshold), below-minimum important
  entry; `total == valid + expiring + expired`.
- Frontend: `getCabinetSummary` path + parse; `useCabinetSummary` success/error;
  card config → link targets.

### Integration Tests:

- `GET /cabinet/summary` (authed) returns five ints; each status count matches the
  corresponding `GET /cabinet/entries?status=…` total for the same seeded user.

### Manual Testing Steps:

1. Log in → land on `/` with five cards.
2. Note each count; click each card; confirm the cabinet list is filtered and its
   total matches the card.
3. Add/delete an entry; return to dashboard; confirm counts updated.
4. Empty account → add-CTA shown.
5. Resize to mobile → cards stack.
6. Sidebar "Panel główny" active only on `/`.

## Performance Considerations

Five count queries per dashboard load, each a single indexed aggregate over the
user's entries — negligible for MVP cabinet sizes. TanStack Query caches the
result; cabinet mutations invalidate it. No pagination or full-list transfer
(the reason a backend summary beats client-side derivation).

## Migration Notes

No schema changes, no migrations. Purely additive endpoint + frontend feature.

## References

- Roadmap S-07: `context/foundation/roadmap.md:247`
- PRD FR-009: `context/foundation/prd.md:136`
- Design reference: `reference/dashboard-v1.jpg` (visual style only; five FR-009 counts, no bottom list)
- Reusable filtered query: `backend/app/api/v1/cabinet/crud.py:263`
- Pref resolution: `backend/app/api/v1/cabinet/facade.py:24`
- URL-driven cabinet filters: `frontend/src/features/cabinet/components/cabinet-page.tsx:52`
- Query-key/hook pattern: `frontend/src/features/cabinet/api/cabinet-queries.ts:25`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles.

### Phase 1: Backend summary endpoint

#### Automated

- [x] 1.1 Lint/format passes (ruff check + format) — d8b08c0
- [x] 1.2 Backend unit tests pass (tests/cabinet) — d8b08c0
- [x] 1.3 Backend typecheck passes — d8b08c0
- [x] 1.4 Integration test: GET /cabinet/summary returns five int fields; counts match seeded fixture across empty / threshold boundaries / below-minimum — d8b08c0
- [x] 1.5 Parity: total == valid+expiring+expired and each status count matches GET /cabinet/entries?status=<s> total — d8b08c0

#### Manual

- [x] 1.6 GET /cabinet/summary returns sensible counts for a real account — d8b08c0

### Phase 2: Frontend dashboard data layer

#### Automated

- [x] 2.1 Lint passes — 54708f3
- [x] 2.2 Typecheck passes — 54708f3
- [x] 2.3 Data-seam tests pass (dashboard/api: fetcher path/parse + hook success/error) — 54708f3

#### Manual

- [ ] 2.4 Summary query fires on load and refetches after cabinet add/delete

### Phase 3: Frontend dashboard UI

#### Automated

- [ ] 3.1 Lint passes
- [ ] 3.2 Typecheck passes
- [ ] 3.3 Prettier passes (src/features/dashboard)
- [ ] 3.4 Component tests: loading→skeleton, error→retry, total===0→add-CTA, populated→five cards with counts and correct pre-filtered hrefs

#### Manual

- [ ] 3.5 Five cards show correct numbers matching the cabinet list
- [ ] 3.6 Clicking each card lands on correctly pre-filtered cabinet list with matching total
- [ ] 3.7 Empty cabinet shows add-CTA, not five zeros
- [ ] 3.8 Cards stack on mobile, row on desktop
- [ ] 3.9 Slow/failed backend shows skeleton then error+retry

### Phase 4: Navigation & landing wiring

#### Automated

- [ ] 4.1 Lint passes
- [ ] 4.2 Typecheck passes
- [ ] 4.3 Sidebar test: renders "Panel główny" link to `/`, not active on another route

#### Manual

- [ ] 4.4 Login redirects to `/` showing dashboard cards
- [ ] 4.5 Register redirects to `/` showing dashboard cards
- [ ] 4.6 Sidebar "Panel główny" highlighted only on `/`
- [ ] 4.7 Clicking "Panel główny" from another page returns to the dashboard

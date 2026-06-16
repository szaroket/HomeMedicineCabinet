# Important Category Implementation Plan

## Overview

Deliver roadmap slice **S-04: Important category** (FR-013, FR-014, FR-020 partial). Users can mark a cabinet entry as **important** — both at add time and via an inline star toggle in the list — set a **global minimum package count** (1–10, default 1) on a new settings screen, filter the cabinet to **important** entries, and see an **out-of-stock** signal (a colored row plus a "Brak w apteczce" label) on important entries whose package count is below the configured minimum.

The data model already exists from the F-02 scaffold (`CabinetEntry.is_important`, `UserPreferences.min_package_count`) and is already present in the initial-schema migration — **no new migration is required**. The work is therefore: expose two preferences endpoints, enhance three cabinet endpoints, and build the two frontend surfaces that consume them.

## Current State Analysis

- **Data model is in place.** `CabinetEntry.is_important: bool = False` (`backend/app/api/v1/cabinet/models.py:25`) and `UserPreferences.min_package_count: int` (default 1, `backend/app/api/v1/users/models.py:34`) both exist; the columns are created in `migrations/versions/0e56afa1e4b6_initial_schema.py` (lines 72, 88). No schema change needed.
- **Users domain is a stub.** `users/router.py` is an empty `APIRouter` guarded by `Security(get_current_user)`; `users/service.py` and `users/crud.py` expose only a read-only `get_user_preferences` that returns `None` when no row exists. There is **no** `users/schemas.py` and no write path.
- **Cabinet read path is the integration point.** `cabinet/service.list_entries` already receives `expiry_threshold_days`, and `_map_row_to_entry_out` (`service.py:170`) builds `CabinetEntryOut` with a computed `status` — but no `is_important` and no out-of-stock signal. The facade already fetches `UserPreferences` to resolve the expiry threshold (`facade.py:43`), so `min_package_count` can be read in the same place.
- **No category filter yet.** `CabinetListParams` (`schemas.py:13`) has `status`, `search`, `order`, `page`, `page_size` but no `category`; `crud._build_base_query` (`crud.py:132`) filters on status/search only. S-02 promised category filtering but deferred it (no category existed).
- **POST add flow** (`service.add_entry`) inserts/merges entries but does not accept `is_important`. The merge math (FR-010) lives in `_merge_and_commit` / `crud.update_entry_counts`.
- **Frontend has no settings surface.** Features are `auth`, `cabinet`, `dashboard`; `router.tsx` has `/`, `/cabinet`, `/cabinet/add`. `cabinet-list.tsx` renders 5 columns (name, packages, tablets, expiry, status) with click-to-expand details; the Status column already uses color-coded text (green/orange/red via `STATUS_LABEL`). `cabinet-page.tsx` drives filters through URL search params. `add-medication-form.tsx` + `cabinet-schemas.ts` define the add flow.

### Key Discoveries:

- `is_important` / `min_package_count` columns already exist — **no migration** (`migrations/versions/0e56afa1e4b6_initial_schema.py:72,88`).
- The facade is the only place allowed to read another domain's data; `cabinet/facade.py:43` already calls `users_service.get_user_preferences` — extend it to also pass `min_package_count`.
- Status column already encodes expiry via color (`cabinet-list.tsx:26-30`); the out-of-stock row color must be a **distinct** treatment reserved for the below-minimum case so the two signals stay separable.
- `L-001`: any TLS-DB command must run from PowerShell, not the Bash tool. The endpoint tests here use `authed_client` with dependency-overridden mock sessions (`tests/conftest.py`), so `uv run pytest` runs fine from Bash — no real DB connection.
- `L-004`: every `session.execute`/`flush`/`refresh` in crud must be wrapped in `try/except SQLAlchemyError`, logged with `exc_info=True`, and re-raised as the domain `*DatabaseError`. The users write path must define/raise `UserDatabaseError` (already exists in `errors.py:147`).
- `L-003`: keep `Query()`/`Path()` inside `Annotated` when the type carries Pydantic constraints.

## Desired End State

A logged-in user can:
1. Open **/settings**, see the current global minimum, change it to a value in 1–10, and have it persist across sessions/devices.
2. Mark any cabinet entry important via an inline star in the list, or via a checkbox in the add-medication form; the star reflects current state and toggles back off.
3. Filter the cabinet list to **Ważne** (important) entries.
4. See important entries whose package count is below the global minimum rendered with a colored row and a **"Brak w apteczce"** label; the signal clears automatically when the count rises to or above the minimum. Expiry continues to be shown (unchanged) in the Status column.

Verification: the four behaviors above work end-to-end against the running app, and the automated suites (`uv run pytest`, `uv run ruff check`, `npm run build`, `npm run lint`) pass.

## What We're NOT Doing

- No DB migration (columns already exist).
- No "used" category, dosage, or finish-date logic (S-05); the category filter is built to extend to "used" later but only **important** is wired now.
- No notifications, notification center, or below-minimum/expiry alerts (S-06) — this slice surfaces the badge state in the list only.
- No expiry-driven row color — FR-020's expiry condition stays in the existing Status column; the new row color is reserved for below-minimum.
- No per-entry minimum override (v2 non-goal); a single global minimum applies to all important entries.
- No decrement-to-zero / delete behavior (S-03).
- No editing of expiry/close-to-finish thresholds on the settings screen yet (S-06) — the screen is created now but only the minimum field is exposed.

## Implementation Approach

Build bottom-up, **one backend endpoint per phase** so each phase is an independently reviewable and testable diff, then layer the two frontend surfaces on top. Preferences endpoints (Phases 1–2) come first because the cabinet badge (Phase 3) depends on `min_package_count`. The frontend settings screen (Phase 6) consumes Phases 1–2; the cabinet UI (Phase 7) consumes Phases 3–5.

Cross-domain reads (cabinet needing `min_package_count` from the users domain) go through `cabinet/facade.py` — the only layer permitted to call another domain. Pure domain logic (the below-minimum computation) lives in `cabinet/service.py` alongside the existing `classify_status` helper, not in a separate module.

## Critical Implementation Details

- **Out-of-stock semantics.** The below-minimum signal is `is_important AND package_count < min_package_count` (strictly below, per FR-020 wording and US-05). Non-important entries are always `false`. With the default minimum of 1 this fires only at 0 packages; with a minimum of 2 it fires at 1. Compute it once as a pure function and surface it as a single boolean field on `CabinetEntryOut` so the frontend owns the color + copy.
- **Merge importance (FR-010).** When an add request marks an entry important but it dedup-merges into an existing entry, the result is important if **either** side is (`existing.is_important OR incoming.is_important`). The add flow can set importance on but never silently clears it — un-importing is done via the star toggle.

---

## Phase 1: `GET /users/preferences`

### Overview

Expose the authenticated user's preferences. When no `user_preferences` row exists yet, return the effective defaults (do not persist) so the settings screen always has values to render.

### Changes Required:

#### 1. Users response schema

**File**: `backend/app/api/v1/users/schemas.py` (new)

**Intent**: Define the read shape returned to clients.

**Contract**: `UserPreferencesOut(BaseModel)` with `expiry_threshold_days: int`, `close_to_finish_threshold_days: int`, `min_package_count: int`. (All three are returned for forward-compatibility with S-06; only `min_package_count` is editable this slice.)

#### 2. Service: effective preferences

**File**: `backend/app/api/v1/users/service.py`

**Intent**: Add a function that returns the user's preferences as a `UserPreferencesOut`, falling back to the `DEFAULT_*` constants when `get_user_preferences` returns `None`.

**Contract**: `async def get_effective_preferences(session, user_id) -> UserPreferencesOut`. Reuses existing `crud.get_user_preferences`; maps the `DEFAULT_EXPIRY_THRESHOLD_DAYS` / `DEFAULT_CLOSE_TO_FINISH_THRESHOLD_DAYS` / `DEFAULT_MIN_PACKAGE_COUNT` constants from `app/utilities/const.py` on the `None` path.

#### 3. Router endpoint

**File**: `backend/app/api/v1/users/router.py`

**Intent**: Add the GET route on the already-guarded users router, mapping `UserDatabaseError → 503` and unexpected errors → 500, following the cabinet router's exception pattern.

**Contract**: `GET /users/preferences` → `200 UserPreferencesOut`; injects `CurrentUser` via `Security(get_current_user)` and `session` via `Depends(get_session)`.

### Success Criteria:

#### Automated Verification:

- Backend tests pass: `uv run pytest`
- Lint + format pass: `uv run ruff check . && uv run ruff format --check .`
- New test: `GET /users/preferences` returns defaults when no row exists, and stored values when a row exists (uses `authed_client` + mocked session/crud).

#### Manual Verification:

- Hitting `GET /api/v1/users/preferences` as a logged-in user returns the expected JSON with `min_package_count`.

**Implementation Note**: After automated verification passes, pause for human confirmation of the manual check before proceeding.

---

## Phase 2: `PATCH /users/preferences`

### Overview

Let the user update `min_package_count` (1–10). Provision the row on first write (upsert): update when present, insert with defaults + the new value when absent.

### Changes Required:

#### 1. Update request schema

**File**: `backend/app/api/v1/users/schemas.py`

**Intent**: Validate the partial update; only the minimum is editable this slice.

**Contract**: `UpdatePreferencesRequest(BaseModel)` with `min_package_count: int = Field(ge=1, le=10)`. Pydantic raises 422 on out-of-range values.

#### 2. CRUD upsert

**File**: `backend/app/api/v1/users/crud.py`

**Intent**: Add a write that updates an existing `UserPreferences` row or inserts a new one with defaults plus the provided field.

**Contract**: `async def upsert_min_package_count(session, user_id, min_package_count) -> UserPreferences`. Follows `L-004`: wrap `execute`/`flush`/`refresh` in `try/except SQLAlchemyError`, log with `exc_info=True`, raise `UserDatabaseError` chained `from exc`. Reuse the `persist(...)` context manager pattern used in `cabinet/crud.py`.

> **Addendum (impl review, 2026-06-16)**: shipped as two thin CRUD functions — `update_min_package_count(session, prefs, ...)` + `insert_preferences(session, prefs)` — with the get-existing → branch → construct-new orchestration kept in `service.update_preferences`. Behavior is equivalent to the single-`upsert` contract above; the split keeps CRUD thin and orchestration in the service.

#### 3. Service + router

**File**: `backend/app/api/v1/users/service.py`, `backend/app/api/v1/users/router.py`

**Intent**: Service orchestrates the upsert and returns the effective preferences; router adds the PATCH route mapping `UserDatabaseError → 503`.

**Contract**: `async def update_preferences(session, user_id, min_package_count) -> UserPreferencesOut`; `PATCH /users/preferences` body `UpdatePreferencesRequest` → `200 UserPreferencesOut`.

### Success Criteria:

#### Automated Verification:

- Backend tests pass: `uv run pytest`
- Lint + format pass: `uv run ruff check . && uv run ruff format --check .`
- New tests: PATCH updates an existing row; PATCH provisions a row when none exists; `min_package_count` of 0 and 11 each return 422.

#### Manual Verification:

- `PATCH /api/v1/users/preferences` with `{"min_package_count": 3}` returns the updated value and persists across a subsequent GET.

**Implementation Note**: After automated verification passes, pause for human confirmation before proceeding.

---

## Phase 3: `GET /cabinet/entries` — importance field, out-of-stock signal, category filter

### Overview

Surface `is_important` and a computed below-minimum out-of-stock boolean on each entry, and add an `important` category filter. The facade passes `min_package_count` (read alongside the expiry threshold) into the service.

### Changes Required:

#### 1. Pure below-minimum function

**File**: `backend/app/api/v1/cabinet/service.py`

**Intent**: Single source of truth for the out-of-stock signal, placed beside `classify_status`.

**Contract**: `def is_below_minimum(is_important: bool, package_count: int, min_package_count: int) -> bool` returning `is_important and package_count < min_package_count`. Pure; covered by parametrized unit tests.

#### 2. Response schema fields

**File**: `backend/app/api/v1/cabinet/schemas.py`

**Intent**: Add the two new fields to the list response.

**Contract**: `CabinetEntryOut` gains `is_important: bool` and `below_minimum: bool`.

#### 3. List params + filter

**File**: `backend/app/api/v1/cabinet/schemas.py`, `backend/app/api/v1/cabinet/crud.py`

**Intent**: Accept a category filter and apply it in the query.

**Contract**: `CabinetListParams` gains `category: Literal["important"] | None = None`. `_build_base_query` adds `WHERE cabinet_entries.is_important IS TRUE` when `category == "important"`. The param threads through `crud.list_entries`, `service.list_entries`, and `facade.list_entries`.

> **Addendum (impl review, 2026-06-16)**: shipped with three `StrEnum` classes (`CabinetStatus`, `CabinetOrder`, `CabinetCategory`) and the pre-existing `status`/`order` params converted from `Literal[...]` to those enums; `category` is `CabinetCategory` rather than the planned `Literal`. Behavior is unchanged (StrEnum serializes to identical strings, `== "important"`/`== "expired"` comparisons still hold, invalid values still 422). Benign EXTRA scope beyond the planned category addition; kept for the type-safety improvement.

#### 4. Service mapping + facade min wiring

**File**: `backend/app/api/v1/cabinet/service.py`, `backend/app/api/v1/cabinet/facade.py`

**Intent**: Populate the new fields when mapping rows, and have the facade resolve `min_package_count`.

**Contract**: `service.list_entries` accepts `min_package_count: int`; `_map_row_to_entry_out` gains a `min_package_count: int` parameter (it currently takes only `entry, variant, today, expiry_threshold_days` — `service.py:170`) and sets `is_important=entry.is_important` and `below_minimum=is_below_minimum(...)`. `facade.list_entries` reads `prefs.min_package_count` (falling back to `DEFAULT_MIN_PACKAGE_COUNT`) and passes it down, alongside the existing `expiry_threshold_days` and the new `category` param.

#### 5. Router param pass-through

**File**: `backend/app/api/v1/cabinet/router.py`

**Intent**: Forward `params.category` to the facade.

**Contract**: `list_entries` route passes `category=params.category`; no new error mappings (existing `CabinetDatabaseError`/`UserDatabaseError`/`CabinetError` handling covers it).

#### 6. Update existing tests broken by the schema/signature change

**File**: `backend/tests/cabinet/test_router.py`, `backend/tests/cabinet/test_service.py`, `backend/tests/cabinet/test_facade.py`

**Intent**: Keep the suite green — the two new required `CabinetEntryOut` fields and the new `min_package_count`/`category` params break existing fixtures and assertions.

**Contract**:
- `test_router.py` — extend the `_make_cabinet_entry_out` factory (`test_router.py:215`) defaults dict with `is_important` and `below_minimum` so every test using it still constructs a valid `CabinetEntryOut`.
- `test_service.py` — update the ~8 `service.list_entries(...)` call sites (`test_service.py:545–689`) to pass `min_package_count`; add assertions that the mapped output carries `is_important` / `below_minimum`.
- `test_facade.py` — update the `service.list_entries.call_args.kwargs` assertions (`test_facade.py:40,51,69`) to include the new `category` and `min_package_count` kwargs.
- To minimize churn, thread the new service/facade params as **keyword args with sane defaults** (e.g. `min_package_count` last, `category=None`).

### Success Criteria:

#### Automated Verification:

- Backend tests pass: `uv run pytest`
- Lint + format pass: `uv run ruff check . && uv run ruff format --check .`
- Parametrized unit tests for `is_below_minimum` (important+below, important+at-min, important+above, non-important).
- Endpoint tests: response includes `is_important` and `below_minimum`; `?category=important` returns only important entries; an invalid category value is rejected (422).

#### Manual Verification:

- `GET /api/v1/cabinet/entries?category=important` returns only important entries with correct `below_minimum` values for known fixtures.

**Implementation Note**: After automated verification passes, pause for human confirmation before proceeding.

---

## Phase 4: `PATCH /cabinet/entries/{entry_id}` — toggle importance

### Overview

Add an endpoint to set `is_important` on a single entry owned by the current user. Returns the updated entry as `CabinetEntryOut` (recomputed status + below-minimum), consistent with the list shape.

### Changes Required:

#### 1. CRUD: fetch-by-id (owned) + update flag

**File**: `backend/app/api/v1/cabinet/crud.py`

**Intent**: Look up an entry scoped to the user and update its importance flag.

**Contract**: `async def find_entry_by_id(session, user_id, entry_id) -> CabinetEntry | None` (filters on `id` AND `user_id`); `async def update_entry_importance(session, entry, is_important) -> CabinetEntry`. Both follow `L-004` error wrapping. Reuse `get_registry_by_id` to load the variant for the response mapping.

#### 2. Request schema + service

**File**: `backend/app/api/v1/cabinet/schemas.py`, `backend/app/api/v1/cabinet/service.py`

**Intent**: Validate the body and orchestrate the update + response mapping.

**Contract**: `SetImportantRequest(BaseModel)` with `is_important: bool`. `async def set_entry_importance(session, user_id, entry_id, is_important, expiry_threshold_days, min_package_count) -> CabinetEntryOut`; raises `MedicationNotFoundError`-style not-found when the entry is absent/not owned (add an `EntryNotFoundError(CabinetError)` to `errors.py` mapped to 404).

#### 3. Facade + router

**File**: `backend/app/api/v1/cabinet/facade.py`, `backend/app/api/v1/cabinet/router.py`

**Intent**: Facade resolves prefs (cross-domain) and delegates; router adds the PATCH route mapping not-found → 404 and reusing existing 503/400/500 handlers. Since `EntryNotFoundError` subclasses `CabinetError`, the `except EntryNotFoundError → 404` branch **must precede** the generic `except CabinetError → 400` catch-all, or a missing entry returns 400 (mirror the `MedicationNotFoundError`-before-`CabinetError` ordering in `add_entry`, `router.py:96`).

**Contract**: `PATCH /cabinet/entries/{entry_id}` body `SetImportantRequest` → `200 CabinetEntryOut`. `entry_id: uuid.UUID` as a path param.

#### 4. Update existing tests for the new PATCH route

**File**: `backend/tests/cabinet/test_router.py`, `backend/tests/cabinet/test_facade.py`

**Intent**: Cover the new route and keep shared fixtures consistent.

**Contract**: Add router tests for toggle-on/off and the 404 path (reuse the `_make_cabinet_entry_out` factory updated in Phase 3). If `facade.set_entry_importance` reuses the prefs-resolution helper, extend any `call_args` assertions that newly receive `min_package_count`.

### Success Criteria:

#### Automated Verification:

- Backend tests pass: `uv run pytest`
- Lint + format pass: `uv run ruff check . && uv run ruff format --check .`
- Endpoint tests: toggling important on returns `is_important=true`; toggling off returns `false`; a non-existent or other-user entry returns 404.

#### Manual Verification:

- `PATCH /api/v1/cabinet/entries/{id}` flips importance and the change is reflected in a subsequent list call.

**Implementation Note**: After automated verification passes, pause for human confirmation before proceeding.

**Addendum (impl, 2026-06-16)**: The prefs-resolution logic was extracted into a `_ResolvedPrefs` NamedTuple + `_resolve_prefs` helper in `facade.py`, now shared by both `list_entries` (Phase 3) and `set_entry_importance`. This DRYs the cross-domain prefs read across the two facade paths; the Phase 3 `list_entries` path was rewired to consume the helper with no behavior change (all cabinet tests pass).

---

## Phase 5: `POST /cabinet/entries` — mark important at add time

### Overview

Accept `is_important` in the add request. On a fresh insert, persist it; on a dedup-merge, OR it with the existing entry's flag.

### Changes Required:

#### 1. Request/response schema

**File**: `backend/app/api/v1/cabinet/schemas.py`

**Intent**: Carry importance in and back out of the add flow.

**Contract**: `AddEntryRequest` gains `is_important: bool = False`; `AddEntryOut` gains `is_important: bool`.

#### 2. CRUD insert + importance update

**File**: `backend/app/api/v1/cabinet/crud.py`

**Intent**: Persist importance on insert; update it on the merge path when it must flip on.

**Contract**: `insert_entry(...)` gains an `is_important: bool` parameter (set on the `CabinetEntry`). `update_entry_counts` extends to also accept/write `is_important` (or the merge calls `update_entry_importance` from Phase 4) — choose the single-write approach to avoid a second flush.

#### 3. Service add/merge flow

**File**: `backend/app/api/v1/cabinet/service.py`

**Intent**: Thread `is_important` through `add_entry` → `_dedup_or_insert` → insert/merge; apply OR semantics on merge.

**Contract**: `add_entry(...)` gains `is_important: bool`. Fresh insert sets the flag; `_merge_and_commit` computes `merged_important = existing.is_important or is_important` and writes it. `_build_add_entry_out` includes `is_important`.

#### 4. Router pass-through

**File**: `backend/app/api/v1/cabinet/router.py`

**Intent**: Forward `data.is_important` to the service.

**Contract**: `add_entry` route passes `is_important=data.is_important`; no new error mappings.

#### 5. Update existing add-flow tests

**File**: `backend/tests/cabinet/test_service.py`, `backend/tests/cabinet/test_router.py`

**Intent**: Existing `add_entry`/merge tests break when the new `is_important` param and `AddEntryOut.is_important` field land.

**Contract**: Update existing `service.add_entry(...)` call sites and `AddEntryOut` assertions to account for `is_important` (default `False`); add the OR-merge assertions named in the Success Criteria below. Thread `is_important` as a defaulted keyword arg to minimize churn at existing call sites.

### Success Criteria:

#### Automated Verification:

- Backend tests pass: `uv run pytest`
- Lint + format pass: `uv run ruff check . && uv run ruff format --check .`
- Endpoint tests: adding with `is_important=true` creates an important entry; merging an important add into a non-important existing entry yields `is_important=true` (OR); merging a non-important add into an important existing entry keeps `is_important=true`.

#### Manual Verification:

- Adding a medication with the important flag set produces an important cabinet entry; re-adding the same drug/expiry merges and preserves importance.

**Implementation Note**: After automated verification passes, pause for human confirmation before proceeding.

---

## Phase 6: Frontend — settings feature

### Overview

Create a `settings` feature with a `/settings` route and a form to view/edit the global minimum (1–10), consuming the Phase 1–2 endpoints.

### Changes Required:

#### 1. Settings API + types

**File**: `frontend/src/features/settings/api/settings-api.ts` (new)

**Intent**: Typed fetchers for the preferences resource.

**Contract**: `interface UserPreferences { expiry_threshold_days: number; close_to_finish_threshold_days: number; min_package_count: number }`; `getPreferences(): Promise<UserPreferences>` (GET); `updatePreferences(payload: { min_package_count: number }): Promise<UserPreferences>` (PATCH). Uses `apiJson` from `@/lib/api-client`.

#### 2. Query/mutation hooks

**File**: `frontend/src/features/settings/api/settings-queries.ts` (new)

**Intent**: TanStack Query cache layer with a query-key factory.

**Contract**: `settingsKeys.preferences()`; `usePreferences()`; `useUpdatePreferences()` (invalidates `settingsKeys.preferences()` on success).

#### 3. Validation schema

**File**: `frontend/src/features/settings/schemas/settings-schemas.ts` (new)

**Intent**: Mirror the backend 1–10 bound client-side with Polish messages.

**Contract**: `z.object({ min_package_count: z.number().int(...).min(1, ...).max(10, ...) })`.

#### 4. Settings page

**File**: `frontend/src/features/settings/components/settings-page.tsx` (new)

**Intent**: Render the minimum-packages field, load current value, submit updates, show success/error states in Polish. Follows the layout/header pattern used by `cabinet-page.tsx` (AppHeader/LogoutButton/AppFooter).

**Contract**: Default export-free named `export function SettingsPage()`; kebab-case filename per AGENTS.md.

#### 5. Route + navigation

**File**: `frontend/src/app/router.tsx`, app header/nav component

**Intent**: Add a protected `/settings` route and a nav link to reach it.

**Contract**: New child route `{ path: "/settings", element: <SettingsPage /> }` under `ProtectedLayout`; a "Ustawienia" link in the shared header.

> **Addendum (impl review, 2026-06-16)**: navigation shipped as a full responsive sidebar instead of the planned header link. New `app/components/app-sidebar.tsx` (mobile hamburger drawer) + `app/components/app-layout.tsx` (shared chrome wrapper) plus two icon assets; `cabinet-page.tsx` and `add-medication-page.tsx` were migrated onto `AppLayout`. The page migrations are layout-only (no behavioral regression — build + lint pass). Materially larger than the "Ustawienia link in the shared header" phrasing but kept for the better nav UX. Note: the dashboard page was **not** migrated to `AppLayout` (see F5 — confirm asymmetry is intentional).

> **Addendum (impl review, 2026-06-16)**: `backend/app/main.py:43` CORS `allow_methods` was broadened to add `PATCH` (explicit allowlist, not `*`). Required for the browser preflight to reach `PATCH /users/preferences` (Phase 2) and `PATCH /cabinet/entries/{entry_id}` (Phase 4) — those endpoints were not browser-reachable until this landed. Documented here retroactively; the code change is correct and minimal.

### Success Criteria:

#### Automated Verification:

- Production build passes: `npm run build`
- Lint passes: `npm run lint` (the project's only style/format gate — eslint; there is no prettier config, dependency, or script)

#### Manual Verification:

- `/settings` loads the current minimum, accepts a value 1–10, rejects out-of-range input, and the saved value persists after reload.

**Implementation Note**: After automated verification passes, pause for human confirmation before proceeding.

---

## Phase 7: Frontend — cabinet importance UI

### Overview

Wire the cabinet list and add form to the Phase 3–5 endpoints: inline star toggle, add-form important checkbox, colored row + "Brak w apteczce" label for below-minimum important entries, and the important category filter.

### Changes Required:

#### 1. API + types

**File**: `frontend/src/features/cabinet/api/cabinet-api.ts`

**Intent**: Extend the cabinet contract for importance.

**Contract**: `CabinetEntryOut` gains `is_important: boolean` and `below_minimum: boolean`; `CabinetListParams` gains `category?: "important"` (threaded into `listEntries`' query string); `AddEntryPayload` gains `is_important?: boolean`; new `toggleImportant(id: string, is_important: boolean): Promise<CabinetEntryOut>` (PATCH `/cabinet/entries/{id}`).

#### 2. Toggle mutation

**File**: `frontend/src/features/cabinet/api/cabinet-queries.ts`

**Intent**: Mutation hook for the star, invalidating the list.

**Contract**: `useToggleImportant()` calls `toggleImportant` and invalidates `cabinetKeys.entriesAll()` on success.

#### 3. List row: star + out-of-stock styling

**File**: `frontend/src/features/cabinet/components/cabinet-list.tsx`

**Intent**: Add a star button per row (toggles importance, `stopPropagation` so it doesn't trigger expand), apply a distinct row color when `below_minimum`, and render a "Brak w apteczce" label. Keep expiry in the existing Status column unchanged.

**Contract**: Star control reflects `entry.is_important`; row receives an out-of-stock background/accent class when `entry.below_minimum`; the "Brak w apteczce" copy is defined as a single constant for easy retuning. Color must be visually distinct from the Status text colors and meet the accessibility decision (color + text label together).

#### 4. Category filter control

**File**: `frontend/src/features/cabinet/components/cabinet-page.tsx`

**Intent**: Add a category select ("Wszystkie" / "Ważne") wired to a URL param, included in the query params and in `hasFilters`/`clearFilters`.

**Contract**: New `category` URL param parsed to `"important" | undefined`; added to the `CabinetListParams` object; resets pagination on change; cleared by `clearFilters`.

#### 5. Add-form important checkbox

**File**: `frontend/src/features/cabinet/components/add-medication-form.tsx`, `frontend/src/features/cabinet/schemas/cabinet-schemas.ts`

**Intent**: Let the user mark important while adding.

**Contract**: `addEntrySchema` gains `is_important: z.boolean().optional()` (default false); the form renders a "Oznacz jako ważny" checkbox; the submit payload includes `is_important`.

### Success Criteria:

#### Automated Verification:

- Production build passes: `npm run build`
- Lint passes: `npm run lint` (the project's only style/format gate — eslint; there is no prettier config, dependency, or script)

#### Manual Verification:

- Clicking the star marks/unmarks an entry important and the state survives a reload.
- An important entry below the global minimum shows the colored row + "Brak w apteczce" label; raising it to/above the minimum clears the signal.
- The "Ważne" category filter shows only important entries.
- Adding a medication with the important checkbox produces an important entry.

**Implementation Note**: After automated verification passes, pause for human confirmation. This is the final phase — confirm the full slice end-to-end.

---

## Testing Strategy

### Unit Tests:

- `is_below_minimum` — parametrized over important×below / important×at-minimum / important×above / non-important; boundary at `package_count == min_package_count` (no signal) and `== min - 1` (signal).
- Users `get_effective_preferences` — defaults path (no row) vs stored-values path.

### Integration / Endpoint Tests (httpx `AsyncClient` via `authed_client`, mocked sessions/crud from `tests/conftest.py`):

- `GET /users/preferences` defaults vs stored; `PATCH` update vs provision; 422 on 0 and 11.
- `GET /cabinet/entries` returns new fields; `?category=important` filters; invalid category → 422.
- `PATCH /cabinet/entries/{id}` toggles on/off; 404 for missing/other-user entry.
- `POST /cabinet/entries` with `is_important=true`; OR-merge in both directions.

Follow project test conventions: reuse shared conftest fixtures (no duplicate mocks), pass `spec=` to `MagicMock`/`AsyncMock`, `autospec=True` for `mocker.patch`, `pytest.mark.parametrize` for multi-input cases, named args for 3+ argument calls.

### Manual Testing Steps:

1. Set the global minimum to 2 in `/settings`.
2. Add a medication marked important with 1 package → list shows colored row + "Brak w apteczce".
3. Increment is out of scope (S-03); instead add the same drug/expiry again to merge to 2 packages and confirm the signal clears.
4. Toggle the star off → entry leaves the "Ważne" filter and loses any out-of-stock styling.
5. Reload to confirm persistence; verify expiry status still shows independently in the Status column.

## Performance Considerations

Negligible: the category filter adds a single boolean `WHERE` clause to an already-paginated query; the below-minimum computation is in-memory per row. No new N+1 — the list join already loads the registry variant, and `min_package_count` is fetched once per request in the facade.

## Migration Notes

None — `is_important` and `min_package_count` columns already exist in the initial-schema migration; no data backfill required (defaults are correct).

## References

- Roadmap slice: `context/foundation/roadmap.md` (S-04)
- PRD: `context/foundation/prd.md` (FR-013, FR-014, FR-020, US-05)
- Backend layer rules: `AGENTS.md` (facade for cross-domain; crud/service/router responsibilities)
- Lessons: `context/foundation/lessons.md` (L-001 TLS-DB, L-003 Annotated Query, L-004 SQLAlchemyError wrapping)
- Existing patterns: `backend/app/api/v1/cabinet/facade.py:43` (cross-domain prefs read), `backend/app/api/v1/cabinet/service.py:129` (`classify_status` pure fn), `frontend/src/features/cabinet/components/cabinet-page.tsx` (URL-param filters)

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: GET /users/preferences

#### Automated

- [x] 1.1 Backend tests pass: `uv run pytest` — 8c84893
- [x] 1.2 Lint + format pass: `uv run ruff check . && uv run ruff format --check .` — 8c84893
- [x] 1.3 GET returns defaults when no row, stored values when present — 8c84893

#### Manual

- [x] 1.4 GET /api/v1/users/preferences returns expected JSON for a logged-in user — 8c84893

### Phase 2: PATCH /users/preferences

#### Automated

- [x] 2.1 Backend tests pass: `uv run pytest` — 3b738a4
- [x] 2.2 Lint + format pass: `uv run ruff check . && uv run ruff format --check .` — 3b738a4
- [x] 2.3 PATCH updates existing row, provisions when absent, rejects 0 and 11 (422) — 3b738a4

#### Manual

- [x] 2.4 PATCH min_package_count persists across a subsequent GET — 3b738a4

### Phase 3: GET /cabinet/entries — importance field, out-of-stock signal, category filter

#### Automated

- [x] 3.1 Backend tests pass: `uv run pytest` — 3ba2461
- [x] 3.2 Lint + format pass: `uv run ruff check . && uv run ruff format --check .` — 3ba2461
- [x] 3.3 Parametrized unit tests for `is_below_minimum` — 3ba2461
- [x] 3.4 Endpoint tests: new fields present; `?category=important` filters; invalid category → 422 — 3ba2461

#### Manual

- [x] 3.5 `?category=important` returns only important entries with correct `below_minimum`

### Phase 4: PATCH /cabinet/entries/{entry_id} — toggle importance

#### Automated

- [x] 4.1 Backend tests pass: `uv run pytest` — af2e2a6
- [x] 4.2 Lint + format pass: `uv run ruff check . && uv run ruff format --check .` — af2e2a6
- [x] 4.3 Endpoint tests: toggle on/off; 404 for missing/other-user entry — af2e2a6

#### Manual

- [x] 4.4 PATCH flips importance and is reflected in a subsequent list call — af2e2a6

### Phase 5: POST /cabinet/entries — mark important at add time

#### Automated

- [x] 5.1 Backend tests pass: `uv run pytest` — 42cbb9c
- [x] 5.2 Lint + format pass: `uv run ruff check . && uv run ruff format --check .` — 42cbb9c
- [x] 5.3 Endpoint tests: add with `is_important=true`; OR-merge in both directions — 42cbb9c

#### Manual

- [x] 5.4 Adding with the important flag produces an important entry; re-add merges and preserves importance — 42cbb9c

### Phase 6: Frontend — settings feature

#### Automated

- [x] 6.1 Production build passes: `npm run build` — af71b43
- [x] 6.2 Lint passes: `npm run lint` — af71b43
- [x] 6.3 ~~Format check passes: `npx prettier --check src/`~~ — dropped (impl review 2026-06-16: prettier is not used in this project; eslint via 6.2 is the real gate)

#### Manual

- [x] 6.4 `/settings` loads, edits (1–10), rejects out-of-range, and persists across reload — af71b43

### Phase 7: Frontend — cabinet importance UI

#### Automated

- [ ] 7.1 Production build passes: `npm run build`
- [ ] 7.2 Lint passes: `npm run lint`
- [x] 7.3 ~~Format check passes: `npx prettier --check src/`~~ — dropped (impl review 2026-06-16: prettier is not used in this project; eslint via 7.2 is the real gate)

#### Manual

- [ ] 7.4 Star marks/unmarks importance; survives reload
- [ ] 7.5 Below-minimum important entry shows colored row + "Brak w apteczce"; clears when restocked to/above minimum
- [ ] 7.6 "Ważne" filter shows only important entries
- [ ] 7.7 Add-form important checkbox produces an important entry

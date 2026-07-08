# Notifications and Badges (S-06) Implementation Plan

## Overview

Deliver the S-06 vertical slice: an in-app notification center (bell + unread count + dropdown panel) that surfaces three alert types — a medication entering the expiry window, an "important" medication below its minimum package count, and a "used" medication with an end date at risk of running out before the course ends — plus the two threshold settings (expiry, close-to-finish) that govern them. Notifications are **computed on page load** from live cabinet + preference data (no background queue). The only persisted state is a `dismissed_notifications` table that records individual dismissals so a dismissed alert does not re-fire until its condition clears and re-triggers.

## Current State Analysis

- **Preferences already exist.** `user_preferences` (`backend/app/api/v1/users/models.py:25-42`) stores all three thresholds — `expiry_threshold_days` (default 30), `close_to_finish_threshold_days` (default 7), `min_package_count` (default 1). Defaults live in `backend/app/utilities/const.py:3-5`. The `GET /users/preferences` endpoint already returns all three via `users_service.get_effective_preferences` (`users/service.py:94-121`), but `PATCH /users/preferences` only accepts `min_package_count` (`users/schemas.py:14-17`, `users/router.py:80-105`). `close_to_finish_threshold_days` is **stored but consumed by nothing** — this slice is its first consumer.
- **Reusable pure functions** live in `backend/app/api/v1/cabinet/service.py`: `classify_status(expiry_date, today, expiry_threshold_days) -> Status` (`:162`), `is_below_minimum(is_important, package_count, min_package_count) -> bool` (`:144`), and `compute_usage_view(entry, tablets_per_package, today) -> UsageView(days_of_supply, days_until_end, is_sufficient)` (`:221`). `cabinet_service.list_entries` already composes these into fully-computed `CabinetEntryOut` rows (with medication name, status, `below_minimum`, and the usage view).
- **No `dismissed_notifications` table.** Deferred from data-layer-scaffold; no migration creates it. Confirmed by inspection of `backend/migrations/versions/`.
- **Delete-account (S-09)** deletes `cabinet_entries` then `user_preferences` + `users` in one transaction (`users/facade.py:42-44`); it explicitly skipped notifications because the table did not exist. Test-plan Risk #7 flags orphaned-dismissal risk on account delete.
- **Frontend** has `features/{auth,cabinet,dashboard,settings}/`. The header is `app/components/app-layout.tsx:19-44` (`<LogoutButton />` at `:43`). No icon library — icons are inline SVGs (`cabinet/components/entry-icons.tsx`). No popover/dropdown primitive — only `components/ui/confirm-dialog.tsx` (portal + backdrop + escape). `StatusBadge` (`cabinet/components/status-badge.tsx`) is a reusable pill. The settings form (`settings/components/settings-page.tsx`) exposes only the min-package field. Polish strings are inline literals.

## Desired End State

A logged-in user sees a bell in the header. When any of the three conditions holds for one of their cabinet entries, the bell shows an unread count (the number of currently-active, non-dismissed alerts; hidden at 0, capped at `9+`). Clicking the bell opens a dropdown panel listing the alerts most-urgent-first, each showing the medication name and a type-specific Polish line. Dismissing one removes it and it does not return until its condition clears and re-triggers. The settings screen lets the user edit the expiry threshold (7–90 days) and close-to-finish threshold (≥1 day) alongside the existing minimum. Deleting an account or a cabinet entry leaves no orphaned dismissal rows.

Verify: `GET /api/v1/notifications` returns the correct active set for seeded fixtures; dismiss → refetch omits it; clearing the condition and refetching re-fires it; editing thresholds changes which alerts appear; the bell/panel render and behave in the browser.

### Key Discoveries:

- Reuse the three pure functions in `cabinet/service.py` (`:144`, `:162`, `:221`) — do not re-implement the classification/finish-date math.
- `users_service.get_effective_preferences` (`users/service.py:94`) returns all three thresholds with defaults filled in — the notifications facade's preference source.
- The `cabinet_entry_id` FK with `ON DELETE CASCADE` covers **both** entry deletion and (transitively, because account delete removes all the user's entries) account deletion — see Critical Implementation Details.
- No frontend popover primitive — the panel is hand-built following the `ConfirmDialog` portal/escape pattern (`components/ui/confirm-dialog.tsx`).

## What We're NOT Doing

- No stored notification records and no background job/cron — notifications are derived on each request (tech-stack constraint `has_background_jobs: false`).
- No email/push notifications (PRD Non-Goals) — in-app only.
- No change to the shipped cabinet badges — FR-020 is treated as satisfied (status badge covers expiring/expired; the "Brak w apteczce" pill covers below-minimum). No new unified badge.
- No client-side dismissal storage — persistence is server-side to satisfy cross-device + isolation NFRs.
- No read/seen state distinct from dismissal — the unread count is simply the active, non-dismissed count.
- No dashboard (that is S-07).

## Implementation Approach

A new `notifications` backend domain owns the derivation and the dismissal table. Its facade reads the user's cabinet entries (with registry join) and effective preferences cross-domain, applies the three pure predicates per entry to build the active set, garbage-collects stale dismissals, filters the active set against remaining dismissals, orders by urgency, and returns the list. A `POST /notifications/dismiss` records a dismissal. On the frontend, a new `features/notifications/` feature provides the API layer, a bell with an unread-count badge, and a dropdown panel; the settings feature gains two threshold fields. Work proceeds backend-first (evaluation → dismiss → thresholds → cascade) then frontend (bell/panel → settings) so each phase is independently verifiable.

## Critical Implementation Details

- **`GET /notifications` has a conditional write side-effect (GC).** Because dismissal clearance is only observed at request time, the GET path deletes dismissal rows whose condition is no longer active before returning. The delete is **gated**: the facade computes the stale set in memory from the dismissals it already read and issues the `DELETE` only when that set is non-empty (see Phase 3 §2), so the common case — a load with no newly-cleared dismissals — is read-only. This matters because the endpoint is high-frequency (bell mounts on every page load, per-mutation invalidation, and the 5-min `refetchInterval`). When a delete does run, do the read + GC delete inside a single `persist(session)` transaction so a partial failure rolls back; the operation must be idempotent (re-running yields the same result). Accepted limitation: if a condition clears and re-triggers entirely between two loads, the stale dismissal keeps suppressing it — acceptable for a web-only app the user checks regularly.
- **Cascade is transitive.** With `ON DELETE CASCADE` on `dismissed_notifications.cabinet_entry_id`, deleting a cabinet entry removes its dismissals at the DB level (fires on bulk SQL delete, not just ORM). Since S-09 deletes all of a user's `cabinet_entries`, account deletion is transitively covered. Phase 5 still adds an **explicit** `delete_by_user` call in the account-deletion flow as belt-and-suspenders (documents intent and survives any future reordering of the S-09 entry-delete), and proves no-orphans with an integration test.
- **Dismissal identity is `(user_id, cabinet_entry_id, trigger_type)`.** A single entry can hold multiple simultaneous alerts (e.g. expiring AND below-minimum), so `trigger_type` is part of the key; dismissing one does not dismiss the other.

## Phase 1: Migration + `dismissed_notifications` model

### Overview

Create the persistence for dismissals: a new table and its SQLModel model. No API surface yet.

### Changes Required:

#### 1. Notifications domain package + model

**File**: `backend/app/api/v1/notifications/__init__.py`, `backend/app/api/v1/notifications/models.py`

**Intent**: Introduce the notifications domain and define the `DismissedNotification` SQLModel table that records one dismissal per `(user, entry, trigger type)`.

**Contract**: `DismissedNotification(SQLModel, table=True)`, `__tablename__ = "dismissed_notifications"`. Fields: `id: uuid.UUID` (pk, default `uuid4`); `user_id: uuid.UUID` (FK `users.id`); `cabinet_entry_id: uuid.UUID` (FK `cabinet_entries.id`); `trigger_type: str` (stored as `sa.Text`, wrapped at the boundary by a `TriggerType` StrEnum — see Phase 2 — with values `expiry`, `below_minimum`, `run_out`); `dismissed_at: datetime` (tz-aware, default now). `__table_args__`: `UniqueConstraint("user_id", "cabinet_entry_id", "trigger_type", name="uq_dismissed_user_entry_trigger")`. Mirror the field/typing style of `CabinetEntry` (`cabinet/models.py:8-40`).

#### 2. Alembic migration

**File**: `backend/migrations/versions/<rev>_add_dismissed_notifications.py`

**Intent**: Create the `dismissed_notifications` table with the FK that guarantees entry-scoped (and transitively account-scoped) cleanup.

**Contract**: `create_table("dismissed_notifications", ...)` with the columns above. FK on `cabinet_entry_id` → `cabinet_entries.id` with `ondelete="CASCADE"`; FK on `user_id` → `users.id`. The unique constraint from the model. Follow the existing migration style in `backend/migrations/versions/0e56afa1e4b6_initial_schema.py`. Downgrade drops the table.

### Success Criteria:

#### Automated Verification:

- Model imports without error: `uv run python -c "import app.api.v1.notifications.models"`
- Lint/format pass: `uv run ruff check . && uv run ruff format --check .`
- Migration applies and rolls back cleanly (run from native PowerShell per L-001): `uv run alembic upgrade head` then `uv run alembic downgrade -1`

#### Manual Verification:

- Table exists in Supabase with the FK cascade and unique constraint as specified.

**Implementation Note**: After completing this phase and all automated verification passes, pause for manual confirmation before proceeding.

---

## Phase 2: Notifications domain — trigger evaluation + `GET /notifications`

### Overview

Build the read path: evaluate the three triggers per entry, order by urgency, filter out already-dismissed alerts, and expose `GET /api/v1/notifications`. No dismiss write or GC yet (that is Phase 3).

### Changes Required:

#### 1. Domain errors

**File**: `backend/app/utilities/errors.py`

**Intent**: Add the notifications error pair mirroring the cabinet pattern so the router can map DB failures to 503.

**Contract**: `NotificationsError(Exception)` base storing `self.message`, plus `NotificationsDatabaseError(NotificationsError)` — mirror `CabinetError`/`CabinetDatabaseError` (`errors.py:220-237`, `:329-345`).

#### 2. Trigger types + response schema

**File**: `backend/app/api/v1/notifications/schemas.py`, and a `TriggerType` StrEnum (colocated in `schemas.py` or `app/utilities/types.py` next to `DosagePeriod`)

**Intent**: Define the wire contract for a notification and the closed set of trigger types.

**Contract**: `TriggerType(StrEnum)` = `EXPIRY="expiry"`, `BELOW_MINIMUM="below_minimum"`, `RUN_OUT="run_out"`. `NotificationOut(BaseModel)`: `trigger_type: TriggerType`, `cabinet_entry_id: uuid.UUID`, `medication_name: str`, `days_remaining: int | None` (days-to-expiry for `expiry`; `days_of_supply` for `run_out`; `None` for `below_minimum`). `NotificationListOut(BaseModel)`: `items: list[NotificationOut]` (the frontend derives the unread count from `items` length).

#### 3. Pure trigger predicates + ordering

**File**: `backend/app/api/v1/notifications/service.py`

**Intent**: Given a computed cabinet entry view and the effective thresholds, decide which of the three alerts are active, and provide the urgency comparator. Reuse the cabinet pure functions — do not re-derive expiry/finish math.

**Contract**: Pure functions operating on an entry's already-computed fields (status, `below_minimum`, `days_of_supply`, `days_until_end`, `is_sufficient`) plus `today` and thresholds:
- expiry active when `status in {EXPIRING, EXPIRED}` (i.e. `classify_status` result).
- below-minimum active when `is_below_minimum(...)` is true.
- run-out active when the entry is used + tablet-based with an end date, `is_sufficient` is `False` (finish before end date), and `days_of_supply <= close_to_finish_threshold_days` (per FR-019).
- an `order_notifications(items) -> list[NotificationOut]` comparator: most-urgent-first, using the deterministic sort key `(expired_bucket, effective_days, trigger_type_rank, cabinet_entry_id)` where: `expired_bucket = 0` if `days_remaining is not None and days_remaining < 0` else `1` (already-expired items sort ahead of everything); `effective_days = days_remaining if days_remaining is not None else 0` (so a `below_minimum` alert — `days_remaining = None` — sorts as `0`, ahead of any positive-days `expiry`/`run_out` item but after expired ones, reflecting "the important med is already unusable/out now"); `trigger_type_rank` breaks same-day ties in a fixed order (`expiry`, `below_minimum`, `run_out`); `cabinet_entry_id` is the final stable tie-breaker so ordering is fully reproducible. (This below-minimum-before-positive-days placement is a chosen default; the intended UX priority of below-minimum vs. expiring is a product call and can be re-tuned by swapping the `effective_days`/`trigger_type_rank` weighting — the comparator is the single place to change it.) Cover the ordering with a parametrized unit test asserting this exact key.

Follow test-style conventions (parametrize, named args for 3+ params) and NamedTuple returns where a function returns multiple values.

#### 4. CRUD (read side) + cabinet read reuse

**File**: `backend/app/api/v1/notifications/crud.py`; possibly a thin unpaginated read on the cabinet layer

**Intent**: Read the user's dismissal rows (for filtering). Obtain the user's cabinet entries with registry data via the cabinet layer (all entries, unpaginated) so the facade can evaluate every entry.

**Contract**: `notifications/crud.get_dismissals(session, user_id) -> list[DismissedNotification]` wrapped in `try/except SQLAlchemyError` → `NotificationsDatabaseError` (L-004). For the cabinet data, prefer reusing an existing cabinet read that returns computed `CabinetEntryOut` rows for a user without pagination; if none exists, add a minimal `cabinet_service.list_all_for_user(session, user_id, expiry_threshold_days, min_package_count) -> list[CabinetEntryOut]` reusing the current base-query builder without the page slice. Keep all raw SQL in the cabinet layer; notifications never issues cabinet SQL directly.

#### 5. Facade + router

**File**: `backend/app/api/v1/notifications/facade.py`, `backend/app/api/v1/notifications/router.py`, and register in `backend/app/api/v1/router.py`

**Intent**: Orchestrate the read: fetch effective preferences (all three thresholds) and the computed cabinet entries cross-domain, build the active set via the predicates, filter out dismissed alerts, order, and return. Expose the endpoint.

**Contract**: `facade.list_notifications(session, user_id) -> NotificationListOut` — calls `users_service.get_effective_preferences` and the cabinet read, applies the Phase 2 predicates + `order_notifications`, and filters against `crud.get_dismissals`. When assembling each `NotificationOut`, the facade sets `days_remaining` per type from the `CabinetEntryOut` row: for `expiry`, compute `(entry.expiry_date - today).days` from `CabinetEntryOut.expiry_date` (the predicates operate on the pre-computed status/usage fields and do **not** receive `expiry_date`, so this day-count is derived here at assembly time); for `run_out`, use `days_of_supply`; for `below_minimum`, `None`. Router: `APIRouter(prefix="/notifications", tags=["notifications"], dependencies=[Security(get_current_user)])`; `GET "/"` → `list_notifications`, `response_model=NotificationListOut`, injecting `current_user` + `session`, with the standard `try/except` ladder (`NotificationsDatabaseError` → 503, catch-all → 500) mirroring `users/router.py:27-50`. Register `notifications_router` in `app/api/v1/router.py:11-15`.

### Success Criteria:

#### Automated Verification:

- Unit tests for the three predicates + `order_notifications` pass: `uv run pytest backend/tests/notifications`
- Integration test: seeded expiring / below-minimum / run-out fixtures each appear in `GET /notifications`; a valid, well-stocked entry produces none.
- Lint/format + typecheck pass: `uv run ruff check . && uv run ruff format --check .`

#### Manual Verification:

- Hitting `GET /api/v1/notifications` for a user with mixed inventory returns the expected alerts in urgency order.

**Implementation Note**: Pause for manual confirmation after automated verification passes.

---

## Phase 3: Dismiss endpoint + load-time garbage collection

### Overview

Add the write path: record a dismissal, suppress it on subsequent loads, and garbage-collect dismissals whose condition has cleared so they re-fire fresh.

### Changes Required:

#### 1. CRUD (write side)

**File**: `backend/app/api/v1/notifications/crud.py`

**Intent**: Insert a dismissal idempotently and delete stale dismissals in bulk.

**Contract**: `insert_dismissal(session, user_id, cabinet_entry_id, trigger_type)` using `async with persist(session, row): session.add(row)`; on the unique-constraint race, treat an existing row as success (catch `IntegrityError` and no-op, mirroring the cabinet insert race-guard at `cabinet/crud.py:140-146`). `delete_stale_dismissals(session, user_id, stale_keys: set[tuple[uuid, str]])` — delete the user's rows whose `(cabinet_entry_id, trigger_type)` is in `stale_keys` (an explicit set of already-identified stale keys, not "everything not active"). The caller passes only the keys it has determined are stale; when the set is empty the caller skips the call entirely (see §2), so the GET read path issues no DELETE when nothing is stale. Both wrapped per L-004.

#### 2. Wire GC into the read + add dismiss to facade/router

**File**: `backend/app/api/v1/notifications/facade.py`, `backend/app/api/v1/notifications/router.py`, `backend/app/api/v1/notifications/schemas.py`

**Intent**: Run GC as part of `list_notifications` (compute active set → delete stale dismissals → filter → return), all in one transaction. Add the dismiss endpoint.

**Contract**: In `list_notifications`, after building the active set and reading the user's dismissals (already fetched for filtering), compute the stale set in memory — `stale_keys = {(d.cabinet_entry_id, d.trigger_type) for d in dismissals if (d.cabinet_entry_id, d.trigger_type) not in active_keys}`. **Only when `stale_keys` is non-empty**, call `delete_stale_dismissals(session, user_id, stale_keys)` inside a `persist(session)` block; when it is empty, skip the write so the GET stays read-only (addresses the high-frequency write concern — the endpoint is called on every page load, per-mutation invalidation, and the 5-min `refetchInterval`). Then filter the active set against the surviving dismissals (the in-memory list minus `stale_keys`). `DismissRequest(BaseModel)`: `cabinet_entry_id: uuid.UUID`, `trigger_type: TriggerType`. `facade.dismiss(session, user_id, request)` → `crud.insert_dismissal`. Router `POST "/dismiss"` → `status_code=204`, standard error ladder.

### Success Criteria:

#### Automated Verification:

- Integration test — the full lifecycle: fire → `POST /dismiss` → alert absent from `GET` → change data so the condition clears → alert absent (still) and dismissal row GC'd → condition re-triggers → alert present again: `uv run pytest backend/tests/notifications`
- Idempotent dismiss: dismissing twice returns 204 both times and creates one row.
- Lint/format + typecheck pass.

#### Manual Verification:

- Dismiss an alert via the API, reload — it stays gone; restock/adjust so the condition flips off then on, reload — it returns.

**Implementation Note**: Pause for manual confirmation after automated verification passes.

---

## Phase 4: Backend — editable thresholds

### Overview

Make `expiry_threshold_days` and `close_to_finish_threshold_days` writable through the preferences PATCH, so the settings UI (Phase 7) can change what fires.

### Changes Required:

#### 1. Extend the request schema

**File**: `backend/app/api/v1/users/schemas.py`

**Intent**: Accept the two thresholds alongside the minimum, with PRD-bounded validation.

**Contract**: Add to `UpdatePreferencesRequest`: `expiry_threshold_days: int = Field(ge=7, le=90)` (FR-007), `close_to_finish_threshold_days: int = Field(ge=1)`. Keep `min_package_count: int = Field(ge=1, le=10)`. All three required in the body (the form always submits the full set seeded from GET).

#### 2. Extend the upsert

**File**: `backend/app/api/v1/users/service.py`, `backend/app/api/v1/users/crud.py`, `backend/app/api/v1/users/router.py`

**Intent**: Persist all three fields on update/insert rather than only `min_package_count`.

**Contract**: Widen `users_service.update_preferences` to take and write `expiry_threshold_days` and `close_to_finish_threshold_days` (update the existing-row path — currently `crud.update_min_package_count` at `users/crud.py` — to a `update_preferences` that sets all three; and the new-row path already constructs all three). `patch_preferences` (`users/router.py:80-105`) passes the three fields through. Returned `UserPreferencesOut` already carries all three.

### Success Criteria:

#### Automated Verification:

- Integration tests: PATCH with all three fields persists and GET reflects them; out-of-range values (expiry 6 or 91, close-to-finish 0) return 422: `uv run pytest backend/tests/users`
- Lint/format + typecheck pass.

#### Manual Verification:

- PATCH `/users/preferences` with new thresholds, then confirm a borderline entry's expiry alert appears/disappears accordingly.

**Implementation Note**: Pause for manual confirmation after automated verification passes.

---

## Phase 5: Backend — account-delete cascade extension

### Overview

Guarantee no orphaned dismissal rows on account deletion, closing test-plan Risk #7. (Entry-delete is already covered by the Phase 1 FK cascade.)

### Changes Required:

#### 1. Explicit delete-by-user for dismissals

**File**: `backend/app/api/v1/notifications/service.py`, `backend/app/api/v1/notifications/crud.py`

**Intent**: Provide a domain-owned bulk delete of a user's dismissals for the account-deletion flow.

**Contract**: `notifications_service.delete_by_user(session, user_id)` → `crud.delete_by_user(session, user_id)` (bulk `DELETE ... WHERE user_id = :user_id`), wrapped per L-004, on the shared session (no commit — the caller's `persist` owns the transaction), mirroring `cabinet_service.delete_by_user` used at `users/facade.py:43`.

#### 2. Call it from the account-deletion flow

**File**: `backend/app/api/v1/users/facade.py`

**Intent**: Delete the user's dismissals within the existing atomic delete block, before/with the cabinet-entry delete, as explicit intent alongside the FK cascade.

**Contract**: In `delete_account` (`users/facade.py:42-44`), add `await notifications_service.delete_by_user(session=session, user_id=user_id)` inside the `async with persist(session)` block. Import the notifications service (cross-domain call from a facade is permitted).

### Success Criteria:

#### Automated Verification:

- Integration test: a user with dismissal rows is deleted → zero `dismissed_notifications` rows remain for that user (no orphans): `uv run pytest backend/tests/users`
- Lint/format + typecheck pass.

#### Manual Verification:

- Delete a test account that had dismissals; confirm the table has no rows for that user.

**Implementation Note**: Pause for manual confirmation after automated verification passes.

---

## Phase 6: Frontend — notification bell & center panel

### Overview

Add the `features/notifications/` feature: API layer, the header bell with an unread-count badge, and the bell-anchored dropdown panel with dismiss.

### Changes Required:

#### 1. API layer

**File**: `frontend/src/features/notifications/api/notifications-api.ts`, `frontend/src/features/notifications/api/notifications-queries.ts`

**Intent**: Typed fetchers + TanStack Query hooks + key factory mirroring the cabinet/settings conventions.

**Contract**: `notifications-api.ts` — `interface NotificationItem { trigger_type: "expiry" | "below_minimum" | "run_out"; cabinet_entry_id: string; medication_name: string; days_remaining: number | null }`; `getNotifications(): Promise<{ items: NotificationItem[] }>` via `apiJson`; `dismissNotification(payload: { cabinet_entry_id: string; trigger_type: string }): Promise<void>` via `apiFetch` POST to `/notifications/dismiss` (throw `res` on `!res.ok`). `notifications-queries.ts` — `notificationKeys = { all: () => ["notifications"] as const }`; `useNotifications()` (`useQuery`) with `refetchInterval: 5 * 60 * 1000` (5 min) so alerts that become active purely from the passage of time (an entry crossing into the expiry window, a course end date nearing) surface in a long-lived tab without a reload; `useDismissNotification()` (`useMutation`, `onSuccess` invalidates `notificationKeys.all()`). Follow `cabinet-queries.ts:25-77`. Refresh policy rationale: the global `queryClient` (`lib/query-client.ts`) leaves TanStack's default `refetchOnWindowFocus: true` in place, which already covers tab-away→return; cabinet mutations invalidate this key (§2); the `refetchInterval` closes the remaining mid-session, no-focus gap. Accepted cost: each such refetch is a `GET /notifications`, which carries the GC write side-effect (see Critical Implementation Details / F3) — negligible at the PRD target scale; revisit the interval only if read volume grows.

#### 2. Cross-feature invalidation

**File**: `frontend/src/features/cabinet/api/cabinet-queries.ts`

**Intent**: Keep the bell fresh after in-app inventory changes (add/edit/restock/delete) that alter alert conditions.

**Contract**: In each cabinet mutation's `onSuccess`, also `invalidateQueries({ queryKey: notificationKeys.all() })` alongside the existing cabinet invalidation.

#### 3. Bell + unread badge

**File**: `frontend/src/features/notifications/components/notification-bell.tsx`, `frontend/src/app/components/app-layout.tsx`

**Intent**: Render an inline-SVG bell in the header with an overlaid unread-count badge, opening the panel on click.

**Contract**: `NotificationBell` reads `useNotifications()`, computes `count = items.length`, renders an inline-SVG bell (following `entry-icons.tsx`) with an absolutely-positioned `rounded-full ... text-xs` badge shown only when `count > 0`, displaying `count > 9 ? "9+" : count`. Polish `aria-label` (e.g. `Powiadomienia`). Place inside the header at `app-layout.tsx:43`, wrapping the bell + `<LogoutButton />` in a `flex items-center gap-2` div.

#### 4. Dropdown panel

**File**: `frontend/src/features/notifications/components/notification-panel.tsx`, and a label/copy map (colocated hook or module)

**Intent**: A bell-anchored dropdown listing alerts most-urgent-first (backend order preserved), each with medication name + a type-specific Polish line, and a dismiss control per row; closes on outside-click and Escape.

**Contract**: Panel opens from the bell; built as an overlay following the `ConfirmDialog` portal/escape pattern (`components/ui/confirm-dialog.tsx`) but anchored under the bell (not a centered modal). Row copy by `trigger_type` (Polish, inline constants): `expiry` → `Wygasa za {days_remaining} dni` (and an expired variant when `days_remaining < 0`), `below_minimum` → `Poniżej minimum`, `run_out` → `Zabraknie za {days_remaining} dni`. Each row has a dismiss button (Polish `aria-label`) calling `useDismissNotification().mutate({ cabinet_entry_id, trigger_type })`. Empty state: `Brak powiadomień`. Reuse `StatusBadge` for the type pill where useful.

### Success Criteria:

#### Automated Verification:

- Component tests (per the repo `*.test.ts(x)` convention): badge hidden at 0, shows `9+` above 9; panel lists rows with correct Polish copy per type; dismiss invokes the mutation: `npm run test`
- Build + lint + format pass: `npm run build && npm run lint && npx prettier --check src/`

#### Manual Verification:

- Bell shows the correct count; clicking opens the panel; dismissing removes a row and decrements the badge; outside-click and Escape close the panel; layout holds on mobile width.

**Implementation Note**: Pause for manual confirmation after automated verification passes.

---

## Phase 7: Frontend — settings threshold controls

### Overview

Surface the two new thresholds in the settings form so the user can tune what fires.

### Changes Required:

#### 1. Schema + payload

**File**: `frontend/src/features/settings/schemas/settings-schemas.ts`, `frontend/src/features/settings/api/settings-api.ts`

**Intent**: Extend validation and the PATCH payload to include all three fields.

**Contract**: Add to `updatePreferencesSchema`: `expiry_threshold_days` (int, `min(7)`, `max(90)`, Polish messages) and `close_to_finish_threshold_days` (int, `min(1)`, Polish message). Extend `UpdatePreferencesPayload` (`settings-api.ts:13`) with both fields; `updatePreferences` already sends the whole payload.

#### 2. Form fields

**File**: `frontend/src/features/settings/components/settings-page.tsx`

**Intent**: Add two number inputs mirroring the existing min-package field, seeded from `usePreferences()` and submitted together.

**Contract**: Extend `defaultValues` and the `useEffect` `reset(...)` (`:28-35`) to include both thresholds from `prefs`; submit all three in `onSubmit` (`:40-42`). Add two `<label>` + help-text + `<input type="number">` blocks (Polish copy) with `min`/`max` matching the schema, following the min-package block at `:75-99`. Wire `errors.*` messages the same way.

### Success Criteria:

#### Automated Verification:

- Component test: form seeds all three values from prefs, rejects out-of-range thresholds with Polish messages, submits the full payload: `npm run test`
- Build + lint + format pass.

#### Manual Verification:

- Change both thresholds, save, reload — values persist; a borderline entry's expiry/run-out alert appears or disappears to match the new thresholds.

**Implementation Note**: Pause for manual confirmation after automated verification passes.

---

## Testing Strategy

### Unit Tests:

- The three trigger predicates (expiry / below-minimum / run-out) across boundary inputs (at threshold, one day inside/outside, expired, exactly-sufficient vs insufficient, no-end-date → no run-out alert), parametrized.
- `order_notifications` — urgency ordering across mixed types including expired-first.

### Integration Tests:

- `GET /notifications` active-set correctness for seeded mixed inventory.
- Dismiss lifecycle: fire → dismiss → suppressed → condition clears (GC) → re-fires.
- Idempotent dismiss (unique-constraint race).
- Preferences PATCH: all three fields persist; out-of-range → 422.
- Account delete leaves zero dismissal rows.

### Manual Testing Steps:

1. Seed one entry per trigger type; open the app — bell count = 3, panel lists them most-urgent-first with correct Polish copy.
2. Dismiss the expiry alert; reload — it stays gone; the other two remain.
3. Restock the below-minimum entry above the minimum; reload — that alert clears and its dismissal (if any) is GC'd.
4. Drop it back below minimum; reload — the alert fires fresh (not suppressed by the old dismissal).
5. In settings, lower the expiry threshold so a valid entry falls inside the window; reload — a new expiry alert appears.
6. Delete a cabinet entry that had a dismissal; confirm no orphaned rows and no errors.

## Performance Considerations

Notifications recompute per request over the user's full cabinet (small data volume per PRD `target_scale`). Reuse the cabinet computation rather than issuing extra queries; the GC delete is a single bulk statement scoped by `user_id`. No pagination needed — cabinets are small.

## Migration Notes

One additive migration (`dismissed_notifications`). No backfill — the table starts empty; absence of a dismissal row means "not dismissed." Downgrade drops the table. Run migration commands from native PowerShell (L-001), not the Bash tool.

## References

- Roadmap slice: `context/foundation/roadmap.md:235-245` (S-06)
- PRD: FR-007, FR-008, FR-019, FR-020; US-02, US-05 (`context/foundation/prd.md`)
- Reused pure functions: `backend/app/api/v1/cabinet/service.py:144,162,221`
- Preferences source: `backend/app/api/v1/users/service.py:94`
- Account-delete flow to extend: `backend/app/api/v1/users/facade.py:21-48`
- Frontend patterns: `frontend/src/features/cabinet/api/cabinet-queries.ts:25-77`, `frontend/src/components/ui/confirm-dialog.tsx`, `frontend/src/app/components/app-layout.tsx:43`
- Lessons: L-001 (PowerShell for DB), L-004 (crud try/except), L-006 (imports at top)

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Migration + dismissed_notifications model

#### Automated

- [x] 1.1 Model imports without error — f8d2cda
- [x] 1.2 Lint/format pass — f8d2cda
- [x] 1.3 Migration applies and rolls back cleanly — f8d2cda

#### Manual

- [x] 1.4 Table exists in Supabase with FK cascade and unique constraint — f8d2cda

### Phase 2: Notifications domain — trigger evaluation + GET /notifications

#### Automated

- [x] 2.1 Unit tests for the three predicates + order_notifications pass — e29ae20
- [x] 2.2 Integration test: seeded triggers appear; healthy entry produces none — e29ae20
- [x] 2.3 Lint/format + typecheck pass — e29ae20

#### Manual

- [x] 2.4 GET /notifications returns expected alerts in urgency order — e29ae20

### Phase 3: Dismiss endpoint + load-time garbage collection

#### Automated

- [x] 3.1 Integration test: full fire → dismiss → clear (GC) → re-fire lifecycle — 549dc03
- [x] 3.2 Idempotent dismiss: twice → 204 each, one row — 549dc03
- [x] 3.3 Lint/format + typecheck pass — 549dc03

#### Manual

- [x] 3.4 Dismiss persists across reload; re-fires after condition flips off then on — 549dc03

### Phase 4: Backend — editable thresholds

#### Automated

- [x] 4.1 PATCH persists all three fields; GET reflects them — 4fe5bf1
- [x] 4.2 Out-of-range threshold values return 422 — 4fe5bf1
- [x] 4.3 Lint/format + typecheck pass — 4fe5bf1

#### Manual

- [x] 4.4 New thresholds change which borderline alerts fire — 4fe5bf1

### Phase 5: Backend — account-delete cascade extension

#### Automated

- [x] 5.1 Account delete leaves zero dismissal rows for the user
- [x] 5.2 Lint/format + typecheck pass

#### Manual

- [x] 5.3 Deleting a test account with dismissals leaves no rows

### Phase 6: Frontend — notification bell & center panel

#### Automated

- [ ] 6.1 Component tests: badge edges, panel copy per type, dismiss invokes mutation
- [ ] 6.2 Build + lint + format pass

#### Manual

- [ ] 6.3 Bell count, panel open, dismiss decrements, outside-click/Escape close, mobile layout holds

### Phase 7: Frontend — settings threshold controls

#### Automated

- [ ] 7.1 Form seeds all three values, rejects out-of-range with Polish messages, submits full payload
- [ ] 7.2 Build + lint + format pass

#### Manual

- [ ] 7.3 Thresholds persist across reload and change which alerts appear

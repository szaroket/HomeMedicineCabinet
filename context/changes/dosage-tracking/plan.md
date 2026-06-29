# Dosage Tracking (S-05) Implementation Plan

## Overview

Let a user assign a cabinet entry to the **"used"** category with a dosage schedule
(times × tablets, per day or per week) and an optional end date — both when adding a
medication (`POST /cabinet/entries`) and afterwards via a dedicated
`PATCH /cabinet/entries/{id}/usage`. The cabinet then surfaces, per "used" entry:

- with **no end date** → an estimated **finish date** (FR-016/FR-018);
- with an **end date** → **days of supply vs days until end** plus a
  *sufficient / short* badge (FR-017).

Non-tablet medications can be marked "used" for **start/end date tracking only** — no
dosage fields, no finish calculation (FR-015/FR-016).

The backend owns the quantitative calc (daily rate, floored days-of-supply,
days-until-end, sufficiency) in UTC so S-06 notifications can reuse one calc path; the
frontend converts the result to the **browser's local timezone** for display.

## Current State Analysis

- **Schema already exists — no migration.** The initial migration `0e56afa1e4b6` and
  `backend/app/api/v1/cabinet/models.py:26-31` already define `is_used`, `dosage_times`,
  `dosage_period` (Text, with a DB `CHECK (dosage_period IN ('day','week'))`),
  `dosage_amount`, `dosage_start_date`, `dosage_end_date`. They are currently never read
  or written by any code path.
- **Near-perfect analog:** S-04's importance flow is the template — `PATCH /entries/{id}`
  → `router` → `facade.set_entry_importance` (resolves prefs) → `service.set_entry_importance`
  → `crud.update_entry_importance` → `_map_row_to_entry_out` → `CabinetEntryOut`
  (`backend/app/api/v1/cabinet/router.py:131`, `facade.py:92`, `service.py:587`,
  `crud.py:332`).
- **Pure stock math exists:** `service.total_tablets(package_count, partial_tablet_count,
  tablets_per_package)` (`service.py:50`) already computes available stock; the
  finish-date calc is a new pure function beside it.
- **`close_to_finish_threshold_days`** already exists on `UserPreferences`
  (`users/models.py`, default 7) — it drives the S-06 *notification*, **not** S-05's
  display. Out of scope here.
- **Response/UI gaps:** `CabinetEntryOut` (`schemas.py:134`) and its TS twin
  (`cabinet-api.ts:50`) carry no usage/finish fields; `CabinetCard` (`cabinet-card.tsx`)
  shows the star toggle and expand area but no usage UI; the category filter
  (`filter-options.ts:11`) offers only `important`, while the backend list query already
  has a generic `category` param branch (`crud.py:185`).
- **Risk #6** in `context/foundation/test-plan.md` ("Dosage finish-date / sufficiency
  miscalc", High impact) targets exactly this slice — the calc functions need explicit
  unit tests.

## Desired End State

A user can, from the add form or an entry's expanded card, mark a tablet-based medication
as "used", enter `3 × 2 tablets per day` and an optional end date, and immediately see —
in their local timezone — either an estimated finish date or a sufficiency verdict against
the end date. Non-tablet meds can be marked used with dates only. "Used" entries are
filterable. Verify via: `uv run pytest` (backend calc + endpoint tests green),
`npm run build` + `npm run lint` (frontend), and manual UI walk-through per phase.

### Key Discoveries:

- DB `CHECK` constraint already restricts `dosage_period` to `'day'`/`'week'` —
  the Pydantic enum must match exactly (`day`/`week`), or inserts raise `IntegrityError`.
- `add_entry` already OR-merges importance on dedup (`service.py:660`); usage merge follows
  the same "incoming wins" shape but **overwrites** the usage fields rather than OR-ing —
  and only when the POST actually carried a usage block, so a restock that omits usage
  preserves the existing schedule (importance-OR can never lose state; usage-overwrite can,
  hence the conditional).
- `_map_row_to_entry_out` is the single read-path mapper (`service.py:191`) used by both
  list and the importance PATCH — extend it once and both endpoints gain usage fields.
- The list query's `category` filter is centralised in `_build_base_query` (`crud.py:135`)
  — adding `used` is a one-branch change mirroring the existing `important` branch.

## What We're NOT Doing

- **No notifications.** FR-019 close-to-finish notification + the `close_to_finish_threshold`
  wiring belong to S-06. We compute `days_until_end`/sufficiency for *display* only.
- **No package/partial-count editing** beyond what add/merge already does — that is S-03
  (`manage-cabinet-entry`).
- **No new migration / schema change** — columns already exist.
- **No variable/PRN dosing** — fixed `times × amount` per day/week only (PRD non-goal).
- **No finish-date calc for non-tablet meds** — date-only tracking (FR-016).
- **No changes to the importance PATCH contract** — usage gets its own sub-resource route.

## Implementation Approach

Phases are split **per endpoint, backend then frontend**, ordered `POST → GET → PATCH`
(the granularity and ordering you requested). POST persists usage (no calc needed); GET
adds the calc + response fields + the `used` filter; PATCH adds update/unassign. Shared
pieces are built where first needed and reused: dosage **validation** lands in Phase 1
(POST backend) and is reused by Phase 5 (PATCH backend); the **dosage form fields**
component is built in Phase 2 (add form) and reused by Phase 6 (card), per the codebase's
"colocate first, extract later" rule.

## Critical Implementation Details

- **Timezone seam.** Backend computes everything in UTC (`datetime.now(timezone.utc).date()`,
  as `classify_status` already does) and returns **numbers, not a finish calendar date**:
  `days_of_supply` (int, floored), `days_until_end` (int), `is_sufficient` (bool), plus the
  raw stored dosage dates. The frontend computes `finish_date = localToday + days_of_supply`
  and formats all dates in the browser timezone. Document the assumption on-screen
  ("na podstawie bieżącego stanu"). Accepted: backend UTC-today vs frontend local-today may
  differ by one day at midnight (single user, PL timezone — negligible).
- **Floor, never overstate.** `days_of_supply = floor(total_tablets / daily_rate)` — serves
  the PRD guardrail and Risk #6. Guard `daily_rate <= 0` (return `None`, never divide).
- **DB CHECK parity.** The `dosage_period` Pydantic enum values must be exactly `day`/`week`.

## Phase 1: POST backend — persist usage on add

### Overview

Extend the add flow so a `POST /cabinet/entries` body may carry usage/dosage fields, persist
them, and on a dedup merge let the **incoming usage overwrite** the existing entry's usage.
Introduce the shared dosage-validation helper and the `used`-related schema/enum/error.

### Changes Required:

#### 1. Usage schema, enum, and error

**File**: `backend/app/api/v1/cabinet/schemas.py`, `backend/app/utilities/errors.py`

**Intent**: Define the request-side usage contract once so both POST and PATCH reuse it, and
a domain error for invalid dosage that the router maps to 422.

**Contract**:
- `DosagePeriod(StrEnum)` with members `day = "day"`, `week = "week"` (must match the DB CHECK).
- A `UsageFields` model (or mixin) with: `is_used: bool = False`, `dosage_times: int | None`,
  `dosage_period: DosagePeriod | None`, `dosage_amount: int | None`,
  `dosage_start_date: date | None`, `dosage_end_date: date | None`. `is_used` **must default to
  `False`** so the existing `POST /cabinet/entries` contract is not broken (current clients/tests
  don't send it). `AddEntryRequest` carries usage as an **optional nested block** —
  `usage: UsageFields | None = None` — so "usage omitted" (the restock case) is distinguishable
  from "usage explicitly provided"; this is the sentinel the merge path relies on (see §3).
  `AddEntryOut` echoes the stored usage fields back (no computed finish — the existing
  "fetch GET for computed values" note already applies).
- `InvalidDosageError(CabinetError)` in `errors.py`, default English message, mirroring
  `InvalidPartialTabletCountError`.

#### 2. Dosage validation helper

**File**: `backend/app/api/v1/cabinet/service.py`

**Intent**: One pure validator both write paths call, enforcing the FR-015 field rules so
invalid combinations never reach the DB.

**Contract**: `validate_usage(variant, is_used, dosage_times, dosage_period, dosage_amount,
dosage_start_date, dosage_end_date, today: date) -> ResolvedUsage` (NamedTuple of the cleaned
values). `today` is **passed in** (the caller in `service.py` computes
`datetime.now(timezone.utc).date()`) so the validator stays pure and its parametrized tests
pin a deterministic today without patching the clock — matching the injected-`today` style of
`compute_usage_view` (Phase 3 §1). Rules: when `is_used` is False → all dosage/date fields must
be None (or are cleared). When `is_used` is True and the variant is **tablet-based** →
`dosage_times`, `dosage_period`, `dosage_amount` are all required and ≥ 1; `dosage_start_date`
defaults to `today` when omitted; `dosage_end_date` optional but, if set, must be ≥ start date. When `is_used` is True
and the variant is **non-tablet** → dosage_* must be None; only start/end dates allowed (end
≥ start). Raise `InvalidDosageError` with a specific message otherwise. Use descriptive
names (no single letters — L-005).

#### 3. Persist usage in add / merge-overwrite

**File**: `backend/app/api/v1/cabinet/service.py`, `backend/app/api/v1/cabinet/crud.py`

**Intent**: Carry the validated usage through `add_entry` into both the insert and the merge
path; on merge the incoming usage overwrites the existing entry's usage **only when the POST
actually provided usage** — a restock that omits usage must preserve the existing schedule.

**Contract**: `add_entry` accepts the optional `usage` block. When `usage is None` it threads
no usage into the flow (insert uses column defaults; merge leaves the existing entry's usage
untouched). When `usage` is provided it calls `validate_usage`, then threads the resolved
values into `_dedup_or_insert`. The fresh-insert path is `_dedup_or_insert` →
`_insert_with_race_guard` (service.py:406) → `crud.insert_entry`, so
`_insert_with_race_guard` must also **forward the usage params** to `crud.insert_entry` —
otherwise usage never reaches a brand-new insert. `crud.insert_entry` gains usage params; a
`crud.update_entry_usage(session, entry, resolved_usage)` (or extend `update_entry_counts`)
writes the usage columns inside the existing `persist(...)` / `try/except SQLAlchemyError`
pattern (L-004). `_merge_and_commit` overwrites the entry's usage fields from the incoming
resolved usage **only when usage was provided** (conditional overwrite — restock without usage
keeps the schedule), independent of the tablet-pool sum; this mirrors the non-destructive
spirit of the importance-OR merge while keeping "incoming wins" when the caller expresses
usage intent. An explicit `is_used: false` in a provided usage block still clears the schedule.
`_build_add_entry_out` includes the usage fields.

#### 4. Router error mapping

**File**: `backend/app/api/v1/cabinet/router.py`

**Intent**: Map the new error to 422 alongside the existing partial-count error.

**Contract**: Add `InvalidDosageError` to the `(InvalidPackageCountError,
InvalidPartialTabletCountError)` → 422 except-group in `add_entry`. HTTPException stays at the
router layer only.

### Success Criteria:

#### Automated Verification:

- Lint/format pass: `cd backend && uv run ruff check . && uv run ruff format --check .`
- Type check passes: `uv run pyright`
- Unit tests pass: `cd backend && uv run pytest tests/cabinet/test_service.py tests/cabinet/test_router.py`
- New tests cover: usage persisted on insert; merge overwrites usage when provided; merge
  **preserves** existing usage when the POST omits the usage block (restock); `validate_usage`
  rejects each invalid combination (tablet missing dosage, non-tablet with dosage, end < start);
  invalid dosage → 422.

#### Manual Verification:

- `POST /cabinet/entries` with valid tablet usage persists `is_used` + dosage columns. GET does
  not expose usage until Phase 3, so verify by DB inspection here — e.g.
  `SELECT is_used, dosage_times, dosage_period, dosage_amount, dosage_start_date, dosage_end_date
  FROM cabinet_entries WHERE id = :id;` — or defer this sign-off until Phase 3's GET lands. (Not
  a gap — the read path is intentionally built in Phase 3.)
- A second POST of the same drug+expiry **with** a usage block overwrites the stored schedule;
  a second POST that **omits** usage (restock) adds packages and preserves the existing schedule.

---

## Phase 2: POST frontend — usage fields in the add form

### Overview

Add optional usage controls to the add-medication form so a user can mark a new entry "used"
and enter a dosage schedule + dates at creation time. Build the reusable dosage-fields
sub-component here.

### Changes Required:

#### 1. Add-flow types + zod

**File**: `frontend/src/features/cabinet/api/cabinet-api.ts`,
`frontend/src/features/cabinet/schemas/cabinet-schemas.ts`

**Intent**: Extend the POST payload and validation with the usage fields.

**Contract**: `AddEntryPayload` gains optional `is_used`, `dosage_times`, `dosage_period:
"day" | "week"`, `dosage_amount`, `dosage_start_date`, `dosage_end_date`. `addEntrySchema`
gains the same with cross-field zod refinement matching the backend rules (tablet-based +
used ⇒ dosage required; non-tablet ⇒ no dosage; end ≥ start). Polish error messages.

#### 2. Dosage fields component

**File**: `frontend/src/features/cabinet/components/dosage-fields.tsx` (new),
`frontend/src/features/cabinet/components/add-medication-form.tsx`

**Intent**: A reusable block rendering the "used" toggle, dosage inputs (hidden/disabled for
non-tablet variants per `is_tablet_based`), and start/end date inputs; embed it in the add
form gated on a selected variant.

**Contract**: `DosageFields` takes the current values, `isTabletBased`, and change handlers;
renders Polish labels (times / okres [dzień|tydzień] / dawka / data rozpoczęcia / data
zakończenia). The add form wires it into its existing form state and includes the values in
the `useAddEntry` payload. No finish-date display here (that is Phase 4).

### Success Criteria:

#### Automated Verification:

- Build passes: `cd frontend && npm run build`
- Lint passes: `npm run lint`
- Format check passes: `npx prettier --check src/`

#### Manual Verification:

- Selecting a tablet-based variant reveals dosage fields; a non-tablet variant hides them and
  shows only date fields.
- Submitting with usage creates the entry; submitting tablet "used" without dosage shows a
  validation error before the request.

---

## Phase 3: GET backend — finish/sufficiency calc + response + filter

### Overview

Add the pure dosage calc functions, surface usage + computed numbers on `CabinetEntryOut` via
the shared mapper, and add the `used` branch to the list category filter.

### Changes Required:

#### 1. Pure calc functions

**File**: `backend/app/api/v1/cabinet/service.py`

**Intent**: Compute the daily rate and floored days-of-supply, plus the end-date comparison,
as pure functions (per project convention pure domain logic lives in `service.py`).

**Contract**:
- `daily_consumption_rate(dosage_times, dosage_amount, dosage_period) -> float` — `(times ×
  amount) / period_days`, `period_days = 1` for `day`, `7` for `week`.
- `days_of_supply(total_tablets, daily_rate) -> int | None` — `floor(total / rate)`; returns
  `None` when `daily_rate <= 0`.
- `compute_usage_view(entry, tablets_per_package, today) -> UsageView` (NamedTuple:
  `days_of_supply: int | None`, `days_until_end: int | None`, `is_sufficient: bool | None`).
  Returns all-None when the entry is not "used", is non-tablet, **or `total_tablets` is None**
  (tpp unavailable — the tablet variant has invalid/None capacity, the same guard
  `_map_row_to_entry_out` already applies at service.py:210-221; never call
  `days_of_supply(None, rate)`). `days_until_end = (end_date
  - today).days` when an end date is set, else None. `is_sufficient = days_of_supply >=
  days_until_end` when both present, else None.

#### 2. Response schema + mapper

**File**: `backend/app/api/v1/cabinet/schemas.py`, `backend/app/api/v1/cabinet/service.py`

**Intent**: Add usage + computed fields to the read model and populate them once in the shared
mapper.

**Contract**: `CabinetEntryOut` gains `is_used: bool`, the four stored dosage fields +
`dosage_start_date`/`dosage_end_date`, and computed `days_of_supply: int | None`,
`days_until_end: int | None`, `is_sufficient: bool | None`. `_map_row_to_entry_out` calls
`compute_usage_view` (it already derives `tpp`) and fills these; both list and the importance
PATCH inherit the fields automatically.

#### 3. `used` category filter

**File**: `backend/app/api/v1/cabinet/crud.py`, `backend/app/api/v1/cabinet/schemas.py`

**Intent**: Allow filtering the list to "used" entries.

**Contract**: Add `used` to `CabinetCategory` enum. In `_build_base_query`, add a branch
`if category == "used": where is_used is True` mirroring the existing `important` branch.

### Success Criteria:

#### Automated Verification:

- Lint/format + type check pass: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run pyright`
- Unit tests pass: `cd backend && uv run pytest tests/cabinet/`
- Calc tests (Risk #6) cover, via `pytest.mark.parametrize`: per-day vs per-week rate; partial
  package included in total; floor boundary (e.g. 10 tablets ÷ 3/day = 3); `daily_rate <= 0`
  guard returns None; non-tablet "used" ⇒ all-None; not-used ⇒ all-None; tablet "used" with
  `total_tablets` None (invalid capacity) ⇒ all-None; end date in the
  future (sufficient / short both ways); end date in the past (`days_until_end <= 0`).
- `GET /cabinet/entries?category=used` returns only used entries (router/crud test).

#### Manual Verification:

- `GET /cabinet/entries` returns the new usage + computed numeric fields for a used entry.

---

## Phase 4: GET frontend — local finish date, sufficiency, filter UI

### Overview

Render the usage state on the expanded card — the locally-computed finish date (no end date)
or days-of-supply-vs-end + a sufficient/short badge (end date set) — and add a "used" option
to the category filter.

### Changes Required:

#### 1. Response types + local date helpers

**File**: `frontend/src/features/cabinet/api/cabinet-api.ts`,
`frontend/src/features/cabinet/hooks/use-cabinet-entry.ts`

**Intent**: Mirror the new backend fields and compute the finish date in the browser timezone.

**Contract**: `CabinetEntryOut` (TS) gains `is_used`, the stored dosage fields, and
`days_of_supply`, `days_until_end`, `is_sufficient`. Add a helper computing
`finishDate = startOfLocalToday + days_of_supply days` and formatting via the existing
`pl-PL` `formatDate`. `useCabinetEntry` exposes the derived usage view (finish date string,
day counts, sufficiency verdict) to the card.

#### 2. Card usage display

**File**: `frontend/src/features/cabinet/components/cabinet-card.tsx`

**Intent**: Show the usage summary in the expanded detail area, with assumptions visible.

**Contract**: When `is_used`: show the schedule (`{times} × {amount} tabl. / {okres}`) as the
stated assumption; if `days_until_end == null` show "Szacowany koniec: {finishDate}"; else
show days-of-supply vs days-until-end plus a badge **Wystarczy** / **Zabraknie** driven by
`is_sufficient`. Non-tablet used entries show only the start/end dates. Reuse `StatusBadge`
styling conventions.

#### 3. Filter UI

**File**: `frontend/src/features/cabinet/components/filter-options.ts`,
`frontend/src/features/cabinet/components/filter-sheet.tsx`,
`frontend/src/features/cabinet/api/cabinet-api.ts`

**Intent**: Expose the "used" category filter.

**Contract**: Add `used` to `CategoryFilter` type, `CATEGORY_OPTIONS` (`{ value: "used",
label: "W użyciu" }`), and the `category` param union in `CabinetListParams`. `filter-sheet`
renders the new option.

> **Addendum (post-impl review, 2026-06-26).** Two items not enumerated above were
> implemented and accepted during review:
>
> - **Table/page wiring.** `cabinet-list.tsx` (desktop table view) and `cabinet-page.tsx`
>   (page wiring) also surface the usage display and the stock filter — they share the
>   same `useCabinetEntry` view the card uses, so the table needs the same columns/badges.
> - **Server-side `sufficiency` filter.** A `sufficiency=insufficient|sufficient` query
>   param was added (schemas/service/facade/router/`crud._sufficiency_clauses`) so the
>   Wystarczy/Zabraknie filter works across all pages, not just the current one. The SQL
>   duplicates the Python `compute_usage_view` arithmetic (SQL can't call per-row Python);
>   the two paths are pinned together by parity tests in `tests/cabinet/test_crud.py`
>   (`TestBuildBaseQuerySufficiency`) and a "change both together" note on the builder —
>   the same documented-duplication pattern as `is_below_minimum` (Risk #6).
> - **Sufficiency badge.** Rendered via the shared `StatusBadge` (descriptor
>   `sufficiencyInfo` in `use-cabinet-entry.ts`) rather than hand-rolled spans, satisfying
>   the "Reuse `StatusBadge` styling conventions" intent above.

### Success Criteria:

#### Automated Verification:

- Build + lint + format pass: `cd frontend && npm run build && npm run lint && npx prettier --check src/`

#### Manual Verification:

- A used entry with no end date shows a finish date that matches the browser's local date math.
- A used entry with an end date shows day counts + a Wystarczy/Zabraknie badge consistent with
  the numbers.
- The category filter "W użyciu" returns only used entries.
- Changing the browser timezone shifts the displayed finish date accordingly.

---

## Phase 5: PATCH backend — update / unassign usage

### Overview

Add `PATCH /cabinet/entries/{id}/usage` to set, change, or clear a used assignment on an
existing entry, reusing the Phase 1 validator. Unassign clears all dosage/date columns.

### Changes Required:

#### 1. Request schema + crud clear/update

**File**: `backend/app/api/v1/cabinet/schemas.py`, `backend/app/api/v1/cabinet/crud.py`

**Intent**: A focused usage update body and a crud write that sets or nulls the usage columns.

**Contract**: `UsageRequest` reusing the `UsageFields` shape from Phase 1.
`crud.update_entry_usage(session, entry, resolved_usage)` writes the usage columns (setting all
to None when `is_used` is False) inside `persist(...)` + `try/except SQLAlchemyError` (L-004).

#### 2. Service + facade

**File**: `backend/app/api/v1/cabinet/service.py`, `backend/app/api/v1/cabinet/facade.py`

**Intent**: Orchestrate ownership lookup, validation, persistence, and recomputed response —
mirroring `set_entry_importance`.

**Contract**: `service.set_entry_usage(session, user_id, entry_id, usage, expiry_threshold_days,
min_package_count)` — `find_entry_by_id` or `EntryNotFoundError`; fetch variant;
`validate_usage`; `crud.update_entry_usage`; return `_map_row_to_entry_out(...)`.
`facade.set_entry_usage` resolves prefs via `_resolve_prefs` then delegates (same shape as the
importance facade method).

#### 3. Router

**File**: `backend/app/api/v1/cabinet/router.py`

**Intent**: Expose the sub-resource route with the established error mapping.

**Contract**: `@router.patch("/entries/{entry_id}/usage", response_model=CabinetEntryOut)` →
`facade.set_entry_usage`. Map `EntryNotFoundError`→404, `InvalidDosageError`→422,
`MedicationNotFoundError`→404, `CabinetDatabaseError`→503, `CabinetError`→400, else 500 —
mirroring the existing handlers.

> **Addendum (post-impl review, 2026-06-26).** One item not enumerated above was
> implemented and accepted during review:
>
> - **Shared dosage value caps.** Bound constraints were added to the *shared* `UsageFields`
>   (`dosage_times: Field(None, ge=1, le=24)`, `dosage_amount: Field(None, ge=1, le=100)`) with
>   matching `.max(24)`/`.max(100)` in the frontend zod schema (`cabinet-schemas.ts`). Because
>   `UsageFields` is reused by the Phase 1 POST path, this also tightens the POST contract — both
>   paths now reject out-of-range dosages with parametrized 422 coverage (times 0/25, amount
>   0/101). The frontend `.max()` parity keeps client and server validation in sync.

### Success Criteria:

#### Automated Verification:

- Lint/format + type check pass: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run pyright`
- Tests pass: `cd backend && uv run pytest tests/cabinet/`
- Tests cover: set usage on an existing entry; edit dosage; unassign (`is_used=false`) nulls all
  dosage/date columns; 404 for another user's entry (ownership); 422 for invalid dosage.

#### Manual Verification:

- `PATCH /cabinet/entries/{id}/usage` sets, then edits, then clears usage; cleared rows have NULL
  dosage/date columns.

---

## Phase 6: PATCH frontend — inline usage form on the card

### Overview

Let the user set, edit, and unassign usage directly in the expanded card, reusing the
`DosageFields` component and a new mutation hook.

### Changes Required:

#### 1. API fn + mutation hook

**File**: `frontend/src/features/cabinet/api/cabinet-api.ts`,
`frontend/src/features/cabinet/api/cabinet-queries.ts`

**Intent**: Wire the PATCH endpoint into a TanStack mutation that invalidates the entries list.

**Contract**: `setUsage(id, payload): Promise<CabinetEntryOut>` (PATCH `/cabinet/entries/{id}/usage`).
`useSetUsage()` mutation mirroring `useToggleImportant` — `onSuccess` invalidates
`cabinetKeys.entriesAll()`.

#### 2. Inline edit on the card

**File**: `frontend/src/features/cabinet/components/cabinet-card.tsx`,
`frontend/src/features/cabinet/hooks/use-cabinet-entry.ts`

**Intent**: Add an edit affordance in the expanded area that reveals `DosageFields`
pre-filled from the entry, Save (calls `useSetUsage`) and an unassign control.

**Contract**: Expanded card gets a "Zmień dawkowanie" toggle revealing `DosageFields` seeded
from the entry's current usage; Save submits via `useSetUsage`; an unassign action submits
`is_used: false`. Reuse the same zod refinement from Phase 2. Stop click propagation so the
card's expand toggle is not triggered (existing `ev.stopPropagation()` pattern).

### Success Criteria:

#### Automated Verification:

- Build + lint + format pass: `cd frontend && npm run build && npm run lint && npx prettier --check src/`

#### Manual Verification:

- Set dosage on an existing entry from the card → finish date/sufficiency appears after save.
- Edit dosage → display updates; unassign → usage block disappears and the entry is no longer
  returned by the "W użyciu" filter.

---

## Testing Strategy

### Unit Tests (backend — primary defense for Risk #6):

- `validate_usage`: every accept/reject combination (tablet missing dosage; non-tablet with
  dosage; end < start; unassign with stray dosage; start-date default).
- `daily_consumption_rate` / `days_of_supply` / `compute_usage_view`: parametrized over
  per-day/per-week, partial package, floor boundary, zero-rate guard, non-tablet/not-used
  all-None, end-date future (sufficient & short), end-date past.
- Merge-overwrites-usage in `add_entry`; usage persisted on insert.
- Ownership: PATCH usage on another user's entry → `EntryNotFoundError`/404.

Follow project test conventions: `pytest.mark.parametrize` for multiple inputs, named args for
3+ argument calls, `spec=`/`autospec=True` mocks, and reuse `conftest.py` fixtures
(`mock_session`, `fake_user`, `authed_client`).

### Integration / Router Tests:

- `POST` with usage, `GET ?category=used`, `PATCH .../usage` happy + error paths via
  `httpx.AsyncClient`.

### Manual Testing Steps:

1. Add a tablet med marked "used", `3 × 2 / day`, no end date → finish date shows in local tz.
2. Add an end date via the card → days counts + Wystarczy/Zabraknie badge appears.
3. Mark a non-tablet med "used" → only dates, no dosage/finish.
4. Unassign → usage block gone, dropped from "W użyciu" filter.
5. Switch browser timezone → finish date shifts.

## Performance Considerations

Negligible — calc is O(1) per row over an already-paginated list; no new queries beyond the
existing single list query (the `used` filter is one extra WHERE clause). Target scale is a
single user, low qps.

## Migration Notes

None — the dosage columns and the `dosage_period` CHECK constraint already exist in migration
`0e56afa1e4b6`.

## References

- Roadmap slice: `context/foundation/roadmap.md` (S-05)
- PRD: FR-015, FR-016, FR-017, FR-018 (`context/foundation/prd.md`)
- Risk #6: `context/foundation/test-plan.md`
- Analog implementation: `backend/app/api/v1/cabinet/service.py:587` (`set_entry_importance`),
  `crud.py:332`, `facade.py:92`, `router.py:131`
- Lessons applied: L-004 (crud try/except), L-005 (no single-letter names)

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: POST backend — persist usage on add

#### Automated

- [x] 1.1 Lint/format pass (ruff check + format --check) — 27a2675
- [x] 1.2 Type check passes (pyright) — 27a2675
- [x] 1.3 Unit tests pass (test_service.py + test_router.py) — 27a2675
- [x] 1.4 New tests cover usage persisted, merge overwrites, validate_usage rejects, invalid→422 — 27a2675

#### Manual

- [x] 1.5 POST with valid tablet usage persists is_used + dosage columns — 27a2675
- [x] 1.6 Second POST same drug+expiry overwrites the stored schedule — 27a2675

### Phase 2: POST frontend — usage fields in the add form

#### Automated

- [x] 2.1 Build passes (npm run build) — 54a05f8
- [x] 2.2 Lint passes (npm run lint) — 54a05f8
- [x] 2.3 Format check passes (prettier --check) — 54a05f8

#### Manual

- [x] 2.4 Tablet variant reveals dosage fields; non-tablet hides them, dates only — 54a05f8
- [x] 2.5 Submitting tablet "used" without dosage shows validation error pre-request — 54a05f8

### Phase 3: GET backend — finish/sufficiency calc + response + filter

#### Automated

- [x] 3.1 Lint/format + type check pass — 86a8c28
- [x] 3.2 Unit tests pass (tests/cabinet/) — 86a8c28
- [x] 3.3 Calc tests (Risk #6) cover parametrized rate/floor/guard/non-tablet/end-date cases — 86a8c28
- [x] 3.4 GET ?category=used returns only used entries — 86a8c28

#### Manual

- [x] 3.5 GET /cabinet/entries returns usage + computed numeric fields for a used entry — 86a8c28

### Phase 4: GET frontend — local finish date, sufficiency, filter UI

#### Automated

- [x] 4.1 Build + lint + format pass — 1ecd9f8

#### Manual

- [x] 4.2 No-end-date entry shows finish date matching local date math — 1ecd9f8
- [x] 4.3 End-date entry shows day counts + Wystarczy/Zabraknie badge — 1ecd9f8
- [x] 4.4 "W użyciu" filter returns only used entries — 1ecd9f8
- [x] 4.5 Changing browser timezone shifts the finish date — 1ecd9f8

### Phase 5: PATCH backend — update / unassign usage

#### Automated

- [x] 5.1 Lint/format + type check pass — 737007f
- [x] 5.2 Tests pass (tests/cabinet/) — 737007f
- [x] 5.3 Tests cover set, edit, unassign-nulls-columns, ownership 404, invalid 422 — 737007f

#### Manual

- [x] 5.4 PATCH sets, edits, then clears usage; cleared rows have NULL columns — 737007f

### Phase 6: PATCH frontend — inline usage form on the card

#### Automated

- [x] 6.1 Build + lint + format pass — e7c4b15

#### Manual

- [x] 6.2 Set dosage from card → finish/sufficiency appears after save — e7c4b15
- [x] 6.3 Edit updates display; unassign removes usage block and drops from filter — e7c4b15

# Add Medication from Registry (S-01) Implementation Plan

## Overview

Deliver the north-star slice: a logged-in user searches the Polish medicines registry, picks a product and then a pack size (two-step), enters package count, an optional partial-package tablet count, and an expiry date, and the entry appears in their cabinet with a computed status (valid / expiring / expired). Re-adding the same `(drug + tablet count + expiry date)` merges into the existing entry per FR-010, with an explicit merge notice. This fills the stubbed `medicines/` and `cabinet/` backend domains and adds a new `cabinet` frontend feature.

## Current State Analysis

Foundations F-01/F-02/F-03 are complete:

- **Auth** — `get_current_user` JWT guard (`app/core/jwt_security.py`) and `provision_user` (`app/api/v1/auth/crud.py:21`) which creates a `User` + `UserPreferences` row (defaults: `expiry_threshold_days=30`, `close_to_finish_threshold_days=7`, `min_package_count=1`).
- **Data layer** — all tables migrated. `CabinetEntry` (`app/api/v1/cabinet/models.py:8`) already carries the full schema (package_count, partial_tablet_count, expiry_date, is_important, is_used, dosage fields) with a unique constraint `uq_cabinet_entries_user_med_expiry` on `(user_id, medication_registry_id, expiry_date)`.
- **Registry** — imported. `MedicationRegistry` (`app/api/v1/medicines/models.py:8`) carries `name` (indexed), `active_ingredient`, `capacity` (Numeric = tablets-per-package for pills), `capacity_unit`, `is_tablet_based`, plus a `search_vector` tsvector + GIN index (`ix_medication_registry_search_vector`, built in migration `0e56afa1e4b6` and rebuilt in `2c7067ce3f56`) over name + active ingredient.
- **Domain stubs** — `cabinet/router.py` and `medicines/router.py` contain only the prefixed, auth-guarded `APIRouter`; `crud.py`/`service.py` are empty; no `schemas.py`. Both routers are already included in `app/api/v1/router.py`.

Frontend: auth feature complete; TanStack Query, react-hook-form, zod, react-router-dom 7 installed; routes are `/login`, `/register`, `/` (placeholder `DashboardPage`). No `cabinet` feature, **no `components/ui/` primitives**, **Vitest not configured**. `lib/api-client.ts` exposes `apiJson<T>` / `apiFetch` with bearer-token + refresh handling.

### Key Discoveries:

- **The DB unique constraint already encodes the FR-010 dedup key.** Each registry row is one `(drug + pack-size)` variant and "tablet count" = `capacity`. So "same drug + tablet count" == "same `medication_registry_id`", and `(user_id, medication_registry_id, expiry_date)` covers both the tablet dedup key `(drug + tablet count + expiry)` and the non-tablet key `(drug + expiry)`. No schema change is needed.
- **`capacity` is `Decimal`.** For tablet-based meds it must be coerced to an `int` (`tablets_per_package`) for the merge math. Verified invariant (DB query, 2026-06-09): zero `is_tablet_based=true` rows have NULL/non-integer `capacity`, and this slice does not change registry data — so `int(capacity)` cannot fail in practice. Keep only a cheap defensive `assert`/log (not a domain-error path) so a future re-import that breaks the invariant surfaces loudly rather than silently miscomputing.
  > **Addendum (Phase 4 impl):** The impl raises a typed `CabinetInvariantError` (→ 500) instead of a bare `assert`/log. Accepted as an improvement — the violation is loud, router-mapped, and unit-testable — superseding the "not a domain-error path" instruction above for this invariant.
- **Status is computed, never stored** — it depends on the user-configurable `expiry_threshold_days`, so it is derived on read from `expiry_date` + the user's preference.
- **Full-text search infra already exists** — query the `search_vector` GIN index with a prefix `to_tsquery('simple', '<term>:*')`; no new index/extension needed.
- **Error conventions** (per repo memory): English-only error messages; `HTTPException` only at the router layer; domain errors live in `app/utilities/errors.py`. Google-style docstrings throughout (`Args`/`Returns`/`Raises`).
- **L-001** — any DB-touching command (running the server, hitting endpoints against Supabase) must be run from native PowerShell, not the agent's Bash tool. Pure pytest (no DB) and `ruff` run fine in Bash.

## Desired End State

A logged-in user can:
1. Type ≥ 2 characters into a search field and see matching **products** (name + strength + form) from the registry within ~500ms.
2. Select a product and then choose a **pack size** (capacity) from that product's variants.
3. For tablet-based variants, optionally enter a partial-package tablet count (`1…capacity−1`); for non-tablet variants those fields are hidden.
4. Enter package count (≥ 1) and an expiry date (any date, incl. past), and submit.
5. See a success popup: either "added" or, on a `(drug + tablet count + expiry)` collision, an **explicit merge notice** with before/after totals; the popup asks whether to add another (yes → form resets & stays; no → navigates to the cabinet list).
6. See the entry in a minimal read-only cabinet list with a status badge (valid / expiring / expired).

Verified by: pytest unit suite green for the FR-010 logic; `ruff` + `npm run build` + `npm run lint` clean; manual endpoint + UI walkthrough (DB-touching steps run from PowerShell).

## What We're NOT Doing

- No rich cabinet list (filter / sort / paginate) or registry detail fields (producer, route, leaflet/spec links) — that is **S-02**. The list here is minimal and read-only.
- No category assignment (important / used), dosage, finish-date, notifications, badges, dashboard counts — S-04/S-05/S-06/S-07.
- No edit/increment/decrement/delete of entries — S-03.
- No cabinet free-text search — S-02.
- No backend endpoint integration tests, no Vitest setup, no Playwright E2E (per the agreed test-depth decision — unit tests on the merge math only).
- No new migrations, no trigram/`pg_trgm`, no registry data changes.
- No `components/ui` design-system build-out beyond the minimal elements this feature needs (follow the existing auth-form styling).

## Implementation Approach

Backend-first, one endpoint per phase for small reviewable PRs. The riskiest, consumer-independent logic (FR-010 merge/normalization + status classification) lands first as pure, DB-free functions with full unit coverage (Phase 1). The two `medicines` read endpoints power the two-step picker (Phases 2–3). The cabinet write + read endpoints follow (Phases 4–5), with the add endpoint consuming Phase 1's logic. The frontend feature (Phase 6) wires it all together. Every layer follows the established router→service→crud split and the auth domain's conventions.

## Critical Implementation Details

- **FR-010 merge math (load-bearing — Phases 1 & 4 depend on this contract).** Let `tpp = int(capacity)` (tablets per package). For an entry with package count `P` and partial `T` (`T` may be `None`):
  `total = (P - 1) * tpp + T` when `T is not None`, else `total = P * tpp`.
  Merge: `merged_total = total_existing + total_new`. Normalize back:
  if `merged_total % tpp == 0` → `P' = merged_total // tpp`, `T' = None`;
  else → `P' = merged_total // tpp + 1`, `T' = merged_total % tpp`.
  For **non-tablet** meds there is no `tpp`: merging simply sums `package_count`, `partial_tablet_count` stays `None`, no normalization.
- **Status classification.** With `today` (UTC date) and the user's `expiry_threshold_days`: `expired` if `expiry_date < today`; `expiring` if `today <= expiry_date <= today + threshold`; else `valid`.
- **Timezone policy (F4).** The backend and database operate entirely in UTC: `today` is the UTC date, status is computed UTC-relative, and `expiry_date` is stored/returned as a plain calendar date. The frontend owns timezone presentation — it converts/interprets dates against the user's **browser** timezone for display. Consequence accepted for MVP: because status is computed UTC-side, the `valid↔expiring↔expired` boundary follows the UTC day, which can differ by one day from the Warsaw local day right around midnight. This is a deliberate trade (no per-user timezone passed to the backend this slice), not an oversight. **S-02 (filterable list) should pass the browser's IANA timezone (e.g. `?tz=Europe/Warsaw`) so status-based filtering computes `today` in the user's local zone; `classify_status` already accepts `today` as a parameter, so no refactor is needed.**
- **Safe tsquery construction.** User input must never be interpolated raw into `to_tsquery`. Split the query on whitespace, keep alphanumeric tokens, append `:*` to each, and join with ` & ` — bind as a parameter. An empty/all-stripped query returns no rows (or is rejected before hitting the DB).
- **Null variant attributes.** `strength` and `pharmaceutical_form` can be `NULL`; the variants lookup must match `NULL` to `NULL` (use `IS NOT DISTINCT FROM`), not `=`.
- **Case-folded product key (cross-phase, Phases 2 & 3).** The source registry stores the same product under inconsistent casing (e.g. "Apap" vs "APAP"). Phase 2's `/products` endpoint groups case-insensitively (`DISTINCT ON (lower(name), lower(coalesce(strength,'')), lower(coalesce(form,'')))`) and returns one representative row per case-folded group. Phase 3's `/variants` lookup **must** therefore match the product key case-insensitively (`lower(...)` on both sides, NULL-safe), or selecting a product would miss pack-size variants stored under a different casing.

## Phase 1: FR-010 merge/normalization + status logic (with unit tests)

### Overview

Implement the pure, DB-free domain logic for the tablet-pool merge/normalization and the expiry status classification, plus their unit tests. This is the slice's top risk; it lands fully covered before any endpoint or UI consumes it.

### Changes Required:

#### 1. Cabinet domain logic module

**File**: `backend/app/api/v1/cabinet/service.py` (new)

**Intent**: House the pure functions for FR-010 so they are unit-testable without a DB and reusable by the service layer. Keep them free of SQLModel/session types.

**Contract**: Pure functions, no I/O:
- `total_tablets(package_count: int, partial_tablet_count: int | None, tablets_per_package: int) -> int`
- `normalize_tablet_pool(total: int, tablets_per_package: int) -> tuple[int, int | None]` → `(package_count, partial_tablet_count)`
- `merge_tablet_entry(existing, new, tablets_per_package) -> tuple[int, int | None]` (composes the two above per the Critical Implementation Details contract)
- `merge_non_tablet_entry(existing_packages: int, new_packages: int) -> int`
- `classify_status(expiry_date: date, today: date, expiry_threshold_days: int) -> str` returning one of `"valid" | "expiring" | "expired"`.
A `Status` `StrEnum` (or module-level constants) defines the three values. Google-style docstrings on each.

#### 2. Unit tests

**File**: `backend/tests/cabinet/__init__.py`, `backend/tests/cabinet/test_service.py` (new)

**Intent**: Exhaustively cover the merge/normalization and status logic, including the edge cases the roadmap flagged.

**Contract**: Cases must include — even divide (no remainder → partial cleared); remainder (→ one partial, rest full); partial set on both sides; partial on one side only; single-package and multi-package; non-tablet increment; and status boundaries (day before expiry, exactly today, exactly at threshold edge, one day past threshold). Mirror the existing `tests/auth/` layout; no DB, no fixtures requiring a connection.

### Success Criteria:

#### Automated Verification:

- [ ] Lint/format clean: `cd backend && uv run ruff check . && uv run ruff format --check .`
- [ ] Unit tests pass: `cd backend && uv run pytest tests/cabinet/test_service.py`

#### Manual Verification:

- [ ] Spot-check a worked FR-010 example by hand (e.g. existing 1 pkg of 20 + new 1 pkg with partial 5 → 25 → 2 pkg, partial 5) matches a test case.

**Implementation Note**: After automated verification passes, pause for human confirmation before Phase 2.

---

## Phase 2: Backend — `GET /api/v1/medicines/products`

### Overview

Step-1 of the picker: full-text prefix search returning distinct products (name + strength + form) matching name or active ingredient. Establishes the `medicines` schemas/crud/service skeleton.

### Changes Required:

#### 1. Medicines response schemas

**File**: `backend/app/api/v1/medicines/schemas.py` (new)

**Intent**: Typed response model for a distinct product result.

**Contract**: `ProductOut` with `name: str`, `strength: str | None`, `pharmaceutical_form: str | None`, `active_ingredient: str | None`.

#### 2. Product search query

**File**: `backend/app/api/v1/medicines/crud.py`

**Intent**: Run the indexed full-text prefix query and return distinct product tuples.

**Contract**: `async def search_products(session, tsquery: str, limit: int) -> list[...]` — `SELECT DISTINCT name, strength, pharmaceutical_form, active_ingredient ... WHERE search_vector @@ to_tsquery('simple', :tsquery)`, ordered by `name`, capped at `limit`. The crud receives an already-built, parameter-bound tsquery string.

#### 3. Product search service

**File**: `backend/app/api/v1/medicines/service.py`

**Intent**: Build the safe tsquery from raw user input, enforce min length, default/clamp the limit, call crud.

**Contract**: `async def search_products(session, q: str, limit: int = 20) -> list[ProductOut]`. Builds tsquery per the "Safe tsquery construction" detail; returns `[]` for queries under 2 effective characters.

#### 4. Route

**File**: `backend/app/api/v1/medicines/router.py`

**Intent**: Expose the endpoint on the already-guarded router.

**Contract**: `GET /products?query=<str>&limit=<int>` → `list[ProductOut]`. `query` is a required query param.

### Success Criteria:

#### Automated Verification:

- [ ] Lint/format clean: `cd backend && uv run ruff check . && uv run ruff format --check .`
- [ ] Existing tests still pass: `cd backend && uv run pytest`

#### Manual Verification:

- [ ] From PowerShell (per L-001): start the server and `GET /api/v1/medicines/products?query=apa` with a valid bearer token returns distinct products within ~500ms; a 1-char query returns `[]`; an unauthenticated request is rejected.

**Implementation Note**: Pause for human confirmation before Phase 3.

---

## Phase 3: Backend — `GET /api/v1/medicines/variants`

### Overview

Step-2 of the picker: return all pack-size variants of a selected product, so the user can pick a specific tablet count / capacity.

### Changes Required:

#### 1. Variant schema

**File**: `backend/app/api/v1/medicines/schemas.py`

**Intent**: Typed response for a concrete registry row (a pack-size variant) the add flow will reference by `id`.

**Contract**: `VariantOut` with `id: UUID`, `name`, `strength`, `pharmaceutical_form`, `capacity: Decimal | None`, `capacity_unit: str | None`, `is_tablet_based: bool`, `active_ingredient`, `route_of_administration`. (Producer/leaflet/spec deferred to S-02.)

#### 2. Variants query

**File**: `backend/app/api/v1/medicines/crud.py`

**Intent**: Fetch all registry rows for an exact `(name, strength, form)` product, NULL-safe.

**Contract**: `async def list_variants(session, name, strength, pharmaceutical_form) -> list[MedicationRegistry]` — **case-insensitive** match on the product key, ordered by `capacity`. Phase 2's products endpoint returns a case-folded representative of `(name, strength, form)` (the source registry holds the same product under inconsistent casing, e.g. "Apap" vs "APAP"), so this lookup must match the same case-folded key or it will miss variants stored under a different casing. Use `lower(name) = lower(:name)` for the name, and a NULL-safe case-insensitive comparison for `strength`/`pharmaceutical_form` — `lower(strength) IS NOT DISTINCT FROM lower(:strength)` (so `NULL` still matches `NULL`), not a plain `=`.

#### 3. Variants service + route

**File**: `backend/app/api/v1/medicines/service.py`, `backend/app/api/v1/medicines/router.py`

**Intent**: Thin orchestration + endpoint.

**Contract**: `GET /variants?name=<str>&strength=<str|null>&form=<str|null>` → `list[VariantOut]`. `name` required; `strength`/`form` optional (absent ⇒ match `NULL`).

### Success Criteria:

#### Automated Verification:

- [ ] Lint/format clean: `cd backend && uv run ruff check . && uv run ruff format --check .`
- [ ] Existing tests still pass: `cd backend && uv run pytest`

#### Manual Verification:

- [ ] From PowerShell: selecting a product from Phase 2 and calling `/variants` returns its pack sizes ordered by capacity, with `is_tablet_based` correct for tablet vs non-tablet products; a product with NULL strength matches correctly.

**Implementation Note**: Pause for human confirmation before Phase 4.

> **Addendum (Phase 3 impl):** A registry-import parser fix also landed in this phase's commit (`scripts/registry_import/parser.py` `_clean()` now maps the `"-"` sentinel to `None`, plus a `TestClean` suite). It is forward-only (affects future imports, not the rows `/variants` serves today) and is unrelated to the variants endpoint, so it falls outside this slice's "no registry data changes" guardrail — recorded here so it isn't re-flagged as drift.
>
> **Addendum (Phase 3 impl):** Raw SQL was extracted into a new `backend/app/api/v1/medicines/queries.py` module (`SEARCH_PRODUCTS`, `LIST_VARIANTS` as `text(...)` constants) rather than kept inline in `crud.py` as the plan implied; `crud.py` imports `queries` and owns execution. This is now a repo convention — see AGENTS.md "Backend layer rules" (`queries.py`).

---

## Phase 4: Backend — `POST /api/v1/cabinet/entries` (add with FR-010 merge)

### Overview

The write path. Validates input, looks up the registry variant, applies the FR-010 dedup/merge (Phase 1 logic) against the user's existing entries, persists, and returns the resulting entry with a computed status, a `merged` flag, and before/after totals.

### Changes Required:

#### 1. Cabinet domain errors

**File**: `backend/app/utilities/errors.py`

**Intent**: Domain exceptions the router maps to HTTP status codes (English messages, per conventions).

> **Addendum (Phase 2 review):** A sibling `MedicinesError(Exception)` base + `MedicineSearchError` and a crud `SQLAlchemyError → MedicineSearchError → 503` guard already landed in Phase 2 (`errors.py`, `medicines/{crud,router}.py`), mirroring `AuthError`'s shape (separate base, English messages, `HTTPException` at the router only). `CabinetError` below follows the same independent-per-domain pattern — do not fold the medicines errors into it.

**Contract**: Add a new per-domain base class `CabinetError(Exception)` mirroring `AuthError`'s shape exactly (a `message: str` attribute set in `__init__`, English-only). Do **not** extend `AuthError` — that base is auth-specific and reusing it for cabinet/medicine errors would muddy the taxonomy. The new errors extend `CabinetError`, each with a default message: `MedicationNotFoundError` (→ 404, default e.g. "Medication not found."), `InvalidPackageCountError` / `InvalidPartialTabletCountError` (→ 422, with descriptive defaults). The router catches `CabinetError` subclasses and maps them to HTTP, exactly as `auth/router.py` catches `AuthError` subclasses.

#### 2. Request/response schemas

**File**: `backend/app/api/v1/cabinet/schemas.py` (new)

**Intent**: Validated add request and the add result envelope.

**Contract**:
- `AddEntryRequest`: `medication_registry_id: UUID`, `package_count: int` (≥ 1), `expiry_date: date`, `partial_tablet_count: int | None`. Field validators enforce `package_count ≥ 1` and, when `partial_tablet_count` is provided, `≥ 1` (the per-variant upper-bound `< capacity` and the tablet-based-only rule are enforced in the service, which knows the variant).
- `CabinetEntryOut`: `id`, registry display fields (`name`, `strength`, `pharmaceutical_form`, `capacity`, `capacity_unit`, `is_tablet_based`), `package_count`, `partial_tablet_count`, `expiry_date`, `total_tablets: int | None`, `status: str`.
- `MergeSummary`: `previous_package_count`, `previous_partial_tablet_count`, `previous_total_tablets`, `added_total_tablets`, `new_total_tablets` (tablet meds); package-count before/after for non-tablet.
- `AddEntryResult`: `merged: bool`, `entry: CabinetEntryOut`, `merge_summary: MergeSummary | None`.

> **Addendum (Phase 4 impl):** The add path returns a new `AddEntryOut` schema that intentionally **omits `status`** — status is date-derived (depends on the user's expiry preferences) and is served fresh by `GET /api/v1/cabinet/entries`, so the impl does not fetch preferences / run `classify_status` on the write path. `CabinetEntryOut` (with `status`) remains the GET contract. Recorded here so the contract diff isn't re-flagged as drift. **Phase 6 (frontend) must read status from GET, not from the add response.**

#### 3. Cabinet crud

**File**: `backend/app/api/v1/cabinet/crud.py`

**Intent**: Raw DB ops only.

**Contract**: `get_registry_by_id`; `get_user_preferences(user_id)`; `find_entry(user_id, registry_id, expiry_date)` (the dedup lookup); `insert_entry(...)`; `update_entry_counts(entry, package_count, partial_tablet_count)`.

#### 4. Cabinet service

**File**: `backend/app/api/v1/cabinet/service.py`

**Intent**: Orchestrate add: validate against the variant, branch tablet vs non-tablet, dedup, merge (Phase 1 logic) or insert, compute status, assemble `AddEntryResult`.

**Contract**: `async def add_entry(session, user_id, data: AddEntryRequest) -> AddEntryResult`. Raises `MedicationNotFoundError` if the variant is missing; `InvalidPartialTabletCountError` if a partial is supplied for a non-tablet variant or is outside `1…tpp−1`. Tablet `tpp = int(capacity)` — the registry data is verified to hold integer capacities for tablet-based rows (see Critical Implementation Details), so a cheap `assert`/log suffices here rather than a domain-error path. On a `find_entry` hit, merge and update; otherwise insert. Status from `classify_status` using the user's `expiry_threshold_days`.

**Concurrent-add race (F2).** Two simultaneous POSTs for the same `(user_id, registry_id, expiry_date)` can both miss `find_entry` and both attempt `insert`; the second violates `uq_cabinet_entries_user_med_expiry`. Handle it as a merge, not a 500: wrap the insert so that on `IntegrityError` the service rolls back the failed insert (`await session.rollback()`), re-runs `find_entry` (the row now exists, committed by the winning request), and applies the same merge path used for the `find_entry`-hit case — returning `merged=true`. Verify the async session's post-rollback state allows the follow-up read+update in the same request (asyncpg/SQLModel). This is defense-in-depth behind the frontend submit guard (Phase 6).

#### 5. Route

**File**: `backend/app/api/v1/cabinet/router.py`

**Intent**: Endpoint + error→HTTP mapping (only place `HTTPException` is raised).

**Contract**: `POST /entries` with `current_user` from `Security(get_current_user)` → `AddEntryResult`, `201`. Maps domain errors to 404/422.

### Success Criteria:

#### Automated Verification:

- [ ] Lint/format clean: `cd backend && uv run ruff check . && uv run ruff format --check .`
- [ ] Existing tests still pass: `cd backend && uv run pytest`

#### Manual Verification:

- [ ] From PowerShell: adding a new tablet-based entry returns `merged=false` and correct `total_tablets`/`status`; re-adding the same `(variant + expiry)` returns `merged=true` with a correct `merge_summary` and re-normalized package/partial counts; a different expiry creates a separate entry; a non-tablet variant ignores tablet fields and increments package count on re-add; `package_count=0` and an out-of-range partial are rejected with 422; an unknown `medication_registry_id` returns 404.

**Implementation Note**: Pause for human confirmation before Phase 5.

---

## Phase 5: Backend — `GET /api/v1/cabinet/entries` (list)

### Overview

Read path for the minimal cabinet list: the current user's entries joined to registry display fields, each with a computed status.

### Changes Required:

#### 1. List crud

**File**: `backend/app/api/v1/cabinet/crud.py`

**Intent**: Fetch the user's entries joined to `MedicationRegistry`.

**Contract**: `async def list_entries(session, user_id) -> list[...]` joining `CabinetEntry` to `MedicationRegistry`, ordered by registry `name`.

#### 2. List service + route

**File**: `backend/app/api/v1/cabinet/service.py`, `backend/app/api/v1/cabinet/router.py`

**Intent**: Map rows to `CabinetEntryOut` (reusing `total_tablets` + `classify_status`) and expose the endpoint.

**Contract**: `GET /entries` → `list[CabinetEntryOut]`, scoped to `current_user.id` (strict per-account isolation). Reuses the user's `expiry_threshold_days` for status.

### Success Criteria:

#### Automated Verification:

- [ ] Lint/format clean: `cd backend && uv run ruff check . && uv run ruff format --check .`
- [ ] Existing tests still pass: `cd backend && uv run pytest`

#### Manual Verification:

- [ ] From PowerShell: the list returns only the authenticated user's entries with correct `status` per entry; a second user sees none of the first user's entries; an entry with a past expiry shows `expired`, one within 30 days shows `expiring`, one beyond shows `valid`.

**Implementation Note**: Pause for human confirmation before Phase 6.

---

## Phase 6: Frontend — `cabinet` feature (add flow + minimal list)

### Overview

A single `features/cabinet/` feature: a debounced two-step add form, conditional tablet fields, a success/merge popup that asks whether to add another, a minimal read-only list, and routing. All user-facing text in Polish.

### Changes Required:

#### 1. Generic debounce hook

**File**: `frontend/src/hooks/use-debounce.ts` (new)

**Intent**: Reusable value debounce for the autocomplete (genuinely cross-feature → shared `hooks/`).

**Contract**: `useDebounce<T>(value: T, delayMs: number): T`.

#### 2. Zod schemas

**File**: `frontend/src/features/cabinet/schemas/cabinet-schemas.ts` (new)

**Intent**: Validate the add form with Polish messages.

**Contract**: `addEntrySchema` — selected variant id required, `package_count` integer ≥ 1, `expiry_date` required (any date allowed), `partial_tablet_count` optional integer `1…capacity−1` (upper bound derived from the selected variant; tablet-based only). Export inferred types.

#### 3. Typed API + Query hooks

**File**: `frontend/src/features/cabinet/api/cabinet-api.ts`, `frontend/src/features/cabinet/api/cabinet-queries.ts` (new)

**Intent**: REST contract + cache layer mirroring `features/auth/api/`.

**Contract**: fetchers `searchProducts(q)`, `listVariants(name, strength, form)`, `addEntry(payload)` (returns `AddEntryResult`), `listEntries()`; matching response interfaces. A `cabinetKeys` query-key factory; `useProductSearch(debouncedQ)` (enabled when `q.length >= 2`), `useVariants(product)`, `useCabinetEntries()`, and `useAddEntry()` (invalidates the entries key on success).

#### 4. Add-medication form (two-step)

**File**: `frontend/src/features/cabinet/components/add-medication-form.tsx` (new) + small subcomponents (`product-autocomplete.tsx`, `variant-select.tsx`) as needed.

**Intent**: Drive the flow — debounced product search (min 2 chars, 250ms) → product select → variant (pack-size) select → conditional tablet fields → package count + expiry → submit.

**Contract**: react-hook-form + zod resolver (pattern from `features/auth/components/login-form.tsx`). Tablet-count/partial fields render only when the selected variant `is_tablet_based`. Submit calls `useAddEntry`. **Disable the submit button while the add mutation is in flight** (`useMutation` `isPending`) so a double-click cannot fire two concurrent POSTs (the frontend half of the F2 race guard; the backend insert→IntegrityError→merge path is the other half). Styling follows the existing auth forms (no new design system).

#### 5. Success / merge popup

**File**: `frontend/src/features/cabinet/components/add-result-dialog.tsx` (new)

**Intent**: Show the add outcome and ask whether to continue.

**Contract**: Given `AddEntryResult` — if `merged`, show "Połączono z istniejącym wpisem" with before/after totals from `merge_summary`; else "Dodano lek". Prompt "Czy chcesz dodać kolejny lek?" — confirm resets the form and stays; decline navigates to the cabinet list. All copy in Polish.

#### 6. Minimal cabinet list

**File**: `frontend/src/features/cabinet/components/cabinet-list.tsx` (new)

**Intent**: Read-only verification view.

**Contract**: Renders `useCabinetEntries()` as a simple list/table: name, strength/form, tablet count (capacity), package count, partial, expiry date, and a status badge mapped to Polish (`valid → ważny`, `expiring → wkrótce wygaśnie`, `expired → przeterminowany`). Expiry dates are displayed in the user's browser timezone (per the F4 timezone policy — backend/DB are UTC, the frontend handles local presentation). No filter/sort/paginate.

#### 7. Pages + routing

**File**: `frontend/src/features/cabinet/components/cabinet-page.tsx`, `add-medication-page.tsx` (new); `frontend/src/app/router.tsx`

**Intent**: Compose the feature into routes under `ProtectedLayout`.

**Contract**: Add `/cabinet` (list page) and `/cabinet/add` (add-form page) as children of the existing `ProtectedLayout` block. The decline action in the result dialog navigates to `/cabinet`. Add a link to `/cabinet/add` from the dashboard (or cabinet page) so the flow is reachable.

### Success Criteria:

#### Automated Verification:

- [ ] Type-check + build clean: `cd frontend && npm run build`
- [ ] Lint clean: `cd frontend && npm run lint`
- [ ] Format clean: `cd frontend && npx prettier --check src/`

#### Manual Verification:

- [ ] Logged in, navigating to `/cabinet/add`, typing ≥ 2 chars shows product suggestions; selecting a product lists its pack sizes; a tablet variant shows tablet/partial fields, a non-tablet variant hides them.
- [ ] Submitting a valid entry shows the success popup; choosing "add another" resets and stays; choosing "no" lands on `/cabinet` with the entry visible and the correct status badge.
- [ ] Re-adding the same product + pack size + expiry shows the explicit merge notice with before/after totals; the list reflects the merged counts.
- [ ] All visible text is Polish; the flow is usable at mobile width.

**Implementation Note**: After automated verification passes, pause for human confirmation that manual testing succeeded.

---

## Testing Strategy

### Unit Tests:

- FR-010 `total_tablets`, `normalize_tablet_pool`, `merge_tablet_entry`, `merge_non_tablet_entry` — even-divide, remainder, partial on both/one side, single/multi package, non-tablet increment.
- `classify_status` — boundaries at today, threshold edge, and one day past.

### Integration Tests:

- Out of scope for this slice (agreed test-depth: unit tests on merge math only). Endpoint behavior is covered by the per-phase manual PowerShell checks.

### Manual Testing Steps:

1. (PowerShell) Start backend; with a valid token, exercise `/medicines/products`, `/medicines/variants`, `POST /cabinet/entries` (new, merge, different-expiry, non-tablet, validation errors), `GET /cabinet/entries` (isolation, status).
2. (Frontend) Walk the full add flow incl. merge notice and minimal list, at desktop and mobile widths.

## Performance Considerations

Autocomplete uses the existing `search_vector` GIN index with prefix `to_tsquery`, a 2-char minimum, 250ms debounce, and a result cap (~20) with TanStack Query caching per term — protecting the < 500ms p95 NFR and limiting query volume.

## Migration Notes

None — the schema from F-02 already supports this slice; no new migrations.

## References

- Roadmap slice: `context/foundation/roadmap.md` (S-01)
- PRD: FR-003, FR-010, FR-022, US-01, NFR (data isolation, < 500ms p95)
- Pattern to follow (router→service→crud, error mapping): `backend/app/api/v1/auth/`
- Frontend feature pattern: `frontend/src/features/auth/` (api, queries, schemas, react-hook-form)
- Lesson L-001 (DB commands from PowerShell): `context/foundation/lessons.md`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles.

### Phase 1: FR-010 merge/normalization + status logic (with unit tests)

#### Automated

- [x] 1.1 Lint/format clean (ruff check + format --check) — fe03838
- [x] 1.2 Unit tests pass (pytest tests/cabinet/test_service.py) — fe03838

#### Manual

- [x] 1.3 Worked FR-010 example matches a test case — fe03838

### Phase 2: Backend — `GET /api/v1/medicines/products`

#### Automated

- [x] 2.1 Lint/format clean — a8a25a3
- [x] 2.2 Existing tests still pass (pytest) — a8a25a3

#### Manual

- [x] 2.3 PowerShell: product search returns distinct products < ~500ms; 1-char ⇒ []; unauthenticated rejected — a8a25a3

### Phase 3: Backend — `GET /api/v1/medicines/variants`

#### Automated

- [x] 3.1 Lint/format clean — c29d1ec
- [x] 3.2 Existing tests still pass (pytest) — c29d1ec

#### Manual

- [x] 3.3 PowerShell: variants ordered by capacity; is_tablet_based correct; NULL strength matches — c29d1ec

### Phase 4: Backend — `POST /api/v1/cabinet/entries` (add with FR-010 merge)

#### Automated

- [x] 4.1 Lint/format clean — 813312b
- [x] 4.2 Existing tests still pass (pytest) — 813312b

#### Manual

- [x] 4.3 PowerShell: new add, merge with summary, different-expiry new entry, non-tablet increment, 422 validation, 404 unknown id — 813312b

### Phase 5: Backend — `GET /api/v1/cabinet/entries` (list)

#### Automated

- [ ] 5.1 Lint/format clean
- [ ] 5.2 Existing tests still pass (pytest)

#### Manual

- [ ] 5.3 PowerShell: per-user isolation; status correct for past / within-30d / beyond expiry

### Phase 6: Frontend — `cabinet` feature (add flow + minimal list)

#### Automated

- [ ] 6.1 Build clean (npm run build)
- [ ] 6.2 Lint clean (npm run lint)
- [ ] 6.3 Format clean (prettier --check src/)

#### Manual

- [ ] 6.4 Two-step add flow: product → variant → conditional tablet fields
- [ ] 6.5 Success popup add-another vs navigate-to-list; entry visible with status badge
- [ ] 6.6 Merge notice with before/after on duplicate add
- [ ] 6.7 All text Polish; usable at mobile width

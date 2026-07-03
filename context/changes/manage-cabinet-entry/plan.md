# Manage Cabinet Entry (FR-005) Implementation Plan

## Overview

Add the missing edit/delete surface for a cabinet entry so a user can adjust how much of a medication they hold and remove entries they no longer have. This closes roadmap slice **S-03** and implements **FR-005**: increase/decrease package count, update (or clear) the partial-tablet count of an opened package, and delete an entry with explicit confirmation — including the category-aware zero behaviour (decrementing an uncategorised entry to zero deletes it after confirmation; important/used entries stay at zero for restock).

## Current State Analysis

The `cabinet` domain today supports **Create** (`POST /cabinet/entries`, with FR-010 dedup/merge), **Read** (`GET /cabinet/entries`), and two narrow partial updates — `PATCH /cabinet/entries/{id}` (importance flag only) and `PATCH /cabinet/entries/{id}/usage` (dosage only). There is **no DELETE endpoint anywhere**, and `package_count` / `partial_tablet_count` can only change today via the merge branch of `POST`. The frontend has no delete/edit affordance, no delete/update mutation, and no shared UI primitives (modals are hand-rolled).

Key facts that shape the work:

- `cabinet_entries.package_count` already carries a DB CHECK `>= 0` (`migrations/versions/0e56afa1e4b6_initial_schema.py`) — **0 is already a legal stored value, so no migration is needed.**
- `crud.update_entry_counts` (`backend/app/api/v1/cabinet/crud.py:503`) already updates `package_count` + `partial_tablet_count` (used by the merge path) — the quantity endpoint reuses it directly.
- `crud.find_entry_by_id` (`crud.py:433`) is the owner-scoped lookup that yields `EntryNotFoundError` → 404; every write path uses it.
- Service methods `set_entry_importance` / `set_entry_usage` (`service.py:850`, `:897`) are the exact template for a new `set_entry_quantity`: `find_entry_by_id` → `_get_variant_or_raise` → validate → crud update → `_map_row_to_entry_out`.
- The facade resolves user prefs (`_resolve_prefs`) so `_map_row_to_entry_out` can compute `status` / `below_minimum`. Any endpoint returning `CabinetEntryOut` must route through the facade; delete (204, no body) does not.
- Partial-tablet validation against variant capacity already exists in the add path (`_validate_and_get_tpp`, `_tablet_capacity_invalid` in `service.py`) and is reused, not reinvented.
- All needed error classes already exist in `app/utilities/errors.py`: `EntryNotFoundError`, `InvalidPackageCountError`, `InvalidPartialTabletCountError`, `CabinetDatabaseError`.

## Desired End State

A logged-in user, on the cabinet list (desktop table or mobile card), can:

- Press **−/+** on an entry to decrement/increment its package count; the list refetches and status/badge update.
- Edit the partial-tablet count of a tablet-based entry, or clear it to mark the package full.
- Press a **delete** (trash) action to remove an entry after a Polish confirmation dialog; if the entry shows an out-of-stock badge, the dialog states the badge will also be cleared.
- Decrement an **uncategorised** entry to 0 → a confirmation dialog warns the entry will be deleted; on confirm it is removed. Decrement an **important or used** entry to 0 → it stays at 0 (visible for restock), no delete.

Verified by: new backend unit + integration tests pass; `npm run build` + lint + prettier clean; and a Playwright spec drives delete + decrement-to-zero end to end (also giving the e2e suite its first real teardown path).

### Key Discoveries:

- No migration required — `package_count >= 0` CHECK already present (`0e56afa1e4b6_initial_schema.py`).
- `crud.update_entry_counts` (`crud.py:503`) and `find_entry_by_id` (`crud.py:433`) are directly reusable; only `delete_entry` is net-new crud.
- The quantity request must allow `package_count >= 0`, unlike `AddEntryRequest` which enforces `>= 1` (`schemas.py:97`) — a distinct request schema is needed.
- Frontend mutations all follow invalidate-`entriesAll()`-on-success (`cabinet-queries.ts:64-99`); the two dialog patterns to clone are `add-result-dialog.tsx` (centred overlay) and `filter-sheet.tsx` (Escape-to-close).
- L-001: integration/e2e that opens a TLS DB connection must be run from **native PowerShell**, not the agent Bash tool.

## What We're NOT Doing

- **Editing `expiry_date`** — excluded by FR-005 (Socrates note); a different expiry batch is a separate entry via the add flow, and expiry is part of the unique dedup key.
- **Changing the medication / variant** of an existing entry — that is a delete + re-add.
- **Undo / soft-delete / trash recovery** — hard delete with confirmation only; no soft-delete column exists.
- **Bulk / multi-select delete** — FR-005 is strictly per-entry.
- **Server-enforced zero invariant** — the "uncategorised entry cannot sit at 0" rule is orchestrated client-side (confirm → DELETE); the backend PATCH allows 0 for all entries. (See Implementation Approach.)
- **Optimistic UI updates** — list stays authoritative via invalidate + refetch, so server-computed status/badge/sufficiency never flash stale.

## Implementation Approach

Two endpoints, each split into a backend phase and a frontend phase, ordered **delete-first** so the quantity phase can reuse the delete flow for its decrement-to-zero branch rather than stubbing it:

1. Backend DELETE → 2. Frontend delete (builds the reusable `ConfirmDialog` primitive) → 3. Backend quantity PATCH → 4. Frontend quantity steppers + zero rule (reuses phase-2 dialog + delete mutation) → 5. E2E.

The **decrement-to-zero-deletes-uncategorised** rule lives in the client: the list response already carries `is_important` / `is_used`, so the stepper handler decides — at `package_count === 1` with neither flag set, a decrement opens the confirm dialog and calls `DELETE`; otherwise it PATCHes the new count (0 is accepted by the backend, and important/used entries persist at 0). This keeps the backend surface minimal (PATCH allows `>= 0`, DELETE removes) and puts the confirmation, which is inherently a UI concern, where it belongs.

Every write endpoint returning a body routes router → facade → service (to resolve prefs for computed fields); delete returns 204 and goes router → service directly (thin pass-through, no cross-domain data needed).

## Critical Implementation Details

- **Timing & lifecycle**: The quantity request schema must allow `package_count >= 0` (decrement to zero is valid), diverging from `AddEntryRequest`'s `>= 1` rule. Do not reuse `AddEntryRequest` or its validator for this path.
- **State sequencing**: In the frontend stepper handler, evaluate the zero-delete branch **before** issuing any request — decide DELETE vs PATCH from the current `package_count` + category flags, then act; do not PATCH to 0 first and delete after.
- **Debug & observability**: Integration and Playwright specs that open a TLS DB connection must be run from native PowerShell, not the agent Bash tool (L-001). Hand these commands to the user to run when DB-touching.

---

## Phase 1: Backend — DELETE endpoint

### Overview

Add `DELETE /cabinet/entries/{entry_id}` returning 204, owner-scoped, with a new `delete_entry` crud function.

### Changes Required:

#### 1. Delete crud

**File**: `backend/app/api/v1/cabinet/crud.py`

**Intent**: Add `delete_entry` that removes a `CabinetEntry` row and commits, following the domain's DB-error discipline.

**Contract**: `async def delete_entry(session: AsyncSession, entry: CabinetEntry) -> None`. Wrap the `session.delete(entry)` + commit in `try/except SQLAlchemyError` → `logger.error(..., exc_info=True)` → raise `CabinetDatabaseError() from exc` (L-004). Use the existing `persist`/commit idiom already imported in this module.

#### 2. Delete service

**File**: `backend/app/api/v1/cabinet/service.py`

**Intent**: Add `delete_entry` that resolves the owner-scoped entry then deletes it, mirroring the guard clause used by `set_entry_importance`.

**Contract**: `async def delete_entry(session, user_id, entry_id) -> None`. `find_entry_by_id` → `None` ⇒ raise `EntryNotFoundError()`; otherwise call `crud.delete_entry`. No variant lookup, no prefs, no return body. Google-style docstring with `Raises: EntryNotFoundError, CabinetDatabaseError`.

#### 3. Delete route

**File**: `backend/app/api/v1/cabinet/router.py`

**Intent**: Add the `DELETE` route calling the service directly (no facade — 204, no computed body), with error mapping consistent with the other handlers.

**Contract**: `@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)`; params `entry_id: uuid.UUID`, `current_user: Security(get_current_user)`, `session: Depends(get_session)`; returns `None`. Map `EntryNotFoundError` → 404, `CabinetDatabaseError`/`UserDatabaseError` → 503, `CabinetError` → 400, unexpected → 500 (mirror the `set_entry_importance` except-ladder).

### Success Criteria:

#### Automated Verification:

- Unit tests pass: `cd backend && uv run pytest tests/cabinet`
- Integration tests pass (run from native PowerShell, L-001): `cd backend; uv run pytest tests/integration/cabinet`
- Lint + format clean: `cd backend && uv run ruff check . && uv run ruff format --check .`

#### Manual Verification:

- `DELETE /cabinet/entries/{id}` on an owned entry returns 204 and the entry disappears from `GET /cabinet/entries`.
- `DELETE` on a non-existent or foreign entry returns 404 (cross-account isolation holds).
- OpenAPI docs show the lock icon on the new route (router-level `Security` guard applies).

**Implementation Note**: After automated verification passes, pause for manual confirmation before Phase 2.

---

## Phase 2: Frontend — delete action

### Overview

Add the delete data layer, the project's first shared `ConfirmDialog` primitive, and a delete (trash) affordance on the desktop row and mobile card with adaptive Polish copy.

### Changes Required:

#### 1. Delete fetcher + mutation hook

**File**: `frontend/src/features/cabinet/api/cabinet-api.ts`, `.../api/cabinet-queries.ts`

**Intent**: Add `deleteEntry(id)` calling `DELETE /cabinet/entries/{id}`, and `useDeleteEntry` invalidating `entriesAll()` on success — mirroring `toggleImportant` / `useToggleImportant`.

**Contract**: `deleteEntry(id: string): Promise<void>` via `apiJson` with `method: "DELETE"` (no body; tolerate a 204/empty response). `useDeleteEntry()` returns a mutation keyed on `{ id }` that invalidates `cabinetKeys.entriesAll()`.

#### 2. ConfirmDialog primitive

**File**: `frontend/src/components/ui/confirm-dialog.tsx` (new `components/ui/` directory)

**Intent**: A reusable, domain-agnostic confirmation modal — the project's first shared UI primitive — cloned from the `add-result-dialog` centred-overlay pattern plus `filter-sheet`'s Escape-to-close, styled to the dark-slate theme with a destructive (red) confirm variant.

**Contract**: Props `{ open, title, message, confirmLabel, cancelLabel, onConfirm, onCancel, destructive?, pending? }`. Renders a fixed overlay + centred panel; Escape and backdrop click call `onCancel`; confirm button disabled while `pending`. All caller-supplied text is Polish (the component ships no hardcoded domain copy beyond generic fallbacks).

#### 3. Delete affordance on row + card

**File**: `frontend/src/features/cabinet/components/cabinet-list.tsx` (EntryRow), `.../cabinet-card.tsx`

**Intent**: Add a trash-icon action that opens `ConfirmDialog`; on confirm, call `useDeleteEntry`. Confirmation copy adapts: when the entry carries the out-of-stock badge (`below_minimum` or expiring/expired status per existing `OUT_OF_STOCK_LABEL` logic in `use-cabinet-entry.ts`), the message states the badge will also be cleared.

**Contract**: Local `confirming` state per row/card toggles the shared `ConfirmDialog`. Delete button uses the destructive style. Polish strings, e.g. title `Usuń lek` / message `Czy na pewno chcesz usunąć „{name}" z apteczki?` (+ badge-cleared sentence when applicable). A trash icon is added to `entry-icons.tsx`.

### Success Criteria:

#### Automated Verification:

- Build passes: `cd frontend && npm run build`
- Lint passes: `cd frontend && npm run lint`
- Format clean: `cd frontend && npx prettier --check src/`

#### Manual Verification:

- Trash action opens a Polish confirm dialog; Anuluj/Escape/backdrop cancels; Usuń removes the entry and the list refetches.
- An out-of-stock entry's dialog states the badge will be cleared.
- Dialog and delete work on both the desktop table row and the mobile card.

**Implementation Note**: After automated verification passes, pause for manual confirmation before Phase 3.

---

## Phase 3: Backend — quantity PATCH endpoint

### Overview

Add `PATCH /cabinet/entries/{entry_id}/quantity` accepting absolute `package_count` (≥ 0) and `partial_tablet_count`, returning the recomputed `CabinetEntryOut`.

### Changes Required:

#### 1. Quantity request schema

**File**: `backend/app/api/v1/cabinet/schemas.py`

**Intent**: Add `UpdateQuantityRequest` allowing `package_count >= 0` (decrement to zero is valid) plus an optional `partial_tablet_count`.

**Contract**: `UpdateQuantityRequest(BaseModel)` with `package_count: int` (validator: `>= 0`, raising for negatives) and `partial_tablet_count: int | None = None` (`>= 1` when provided, matching `AddEntryRequest`'s partial validator). Do **not** reuse `AddEntryRequest` (its `>= 1` package rule is wrong here).

#### 2. Quantity service

**File**: `backend/app/api/v1/cabinet/service.py`

**Intent**: Add `set_entry_quantity` mirroring `set_entry_usage`: resolve owner-scoped entry, load variant, validate the partial-tablet count against variant capacity using the existing helpers, persist via `update_entry_counts`, and map to `CabinetEntryOut`.

**Contract**: `async def set_entry_quantity(session, user_id, entry_id, package_count, partial_tablet_count, expiry_threshold_days, min_package_count) -> CabinetEntryOut`. `find_entry_by_id` → `None` ⇒ `EntryNotFoundError`; `_get_variant_or_raise`; validate `partial_tablet_count` against the variant (reuse `_validate_and_get_tpp` / `_tablet_capacity_invalid` — non-tablet variant must have `partial_tablet_count is None`; tablet variant range `1 … tpp-1`) raising `InvalidPartialTabletCountError`; `crud.update_entry_counts(package_count=..., partial_tablet_count=...)`; return `_map_row_to_entry_out(...)`. Google-style docstring with the full `Raises:` set.

#### 3. Quantity facade passthrough

**File**: `backend/app/api/v1/cabinet/facade.py`

**Intent**: Add `set_entry_quantity` that resolves prefs then delegates to the service — identical shape to `set_entry_importance`.

**Contract**: `async def set_entry_quantity(session, user_id, entry_id, package_count, partial_tablet_count) -> CabinetEntryOut`; `_resolve_prefs` → `cabinet_service.set_entry_quantity(..., expiry_threshold_days=..., min_package_count=...)`.

#### 4. Quantity route

**File**: `backend/app/api/v1/cabinet/router.py`

**Intent**: Add the `PATCH .../quantity` route calling the facade, with the same except-ladder as the other PATCH handlers plus the 422 mapping for count validation.

**Contract**: `@router.patch("/entries/{entry_id}/quantity", response_model=CabinetEntryOut)`; body `UpdateQuantityRequest`. Map `EntryNotFoundError`/`MedicationNotFoundError` → 404, `(InvalidPackageCountError, InvalidPartialTabletCountError)` → 422, `CabinetDatabaseError`/`UserDatabaseError` → 503, `CabinetError` → 400, unexpected → 500.

### Success Criteria:

#### Automated Verification:

- Unit tests pass: `cd backend && uv run pytest tests/cabinet`
- Integration tests pass (native PowerShell, L-001): `cd backend; uv run pytest tests/integration/cabinet`
- Lint + format clean: `cd backend && uv run ruff check . && uv run ruff format --check .`

#### Manual Verification:

- PATCH with `package_count: 0` succeeds (entry persists at 0) — the CHECK ≥ 0 is honoured.
- PATCH with a negative count → 422; an out-of-range `partial_tablet_count` (≥ capacity, or set on a non-tablet variant) → 422.
- Returned `CabinetEntryOut` reflects recomputed `status` / `below_minimum` / `total_tablets`.
- PATCH on a foreign/non-existent entry → 404.

**Implementation Note**: After automated verification passes, pause for manual confirmation before Phase 4.

---

## Phase 4: Frontend — quantity steppers + zero rule

### Overview

Add the quantity data layer and inline −/+ steppers plus partial-tablet editing on row and card, with the client-orchestrated decrement-to-zero rule reusing Phase 2's `ConfirmDialog` and `useDeleteEntry`.

### Changes Required:

#### 1. Quantity fetcher + mutation hook

**File**: `frontend/src/features/cabinet/api/cabinet-api.ts`, `.../api/cabinet-queries.ts`

**Intent**: Add `updateQuantity(id, payload)` calling `PATCH /cabinet/entries/{id}/quantity`, and `useUpdateQuantity` invalidating `entriesAll()` on success.

**Contract**: `updateQuantity(id: string, payload: { package_count: number; partial_tablet_count?: number | null }): Promise<CabinetEntryOut>`. Hook mirrors `useSetUsage`.

#### 2. Inline steppers + partial-tablet edit + zero rule

**File**: `frontend/src/features/cabinet/components/cabinet-list.tsx` (EntryRow), `.../cabinet-card.tsx`, and a shared handler in `.../hooks/use-cabinet-entry.ts`

**Intent**: Render a −/+ stepper bound to `package_count` and an editable partial-tablet field (tablet-based entries only; clearing it sends `null` = full package). The decrement handler evaluates the zero rule before issuing a request: at `package_count === 1` with `!is_important && !is_used`, open the `ConfirmDialog` and call `useDeleteEntry` on confirm; otherwise call `useUpdateQuantity` with the new count. Increment and partial edits always call `useUpdateQuantity`.

**Contract**: Decrement/increment/partial logic centralised in `use-cabinet-entry.ts` (returns handlers + a `pendingDelete`/`confirming` flag) so the desktop row and mobile card share one implementation. Partial-tablet input validates client-side `1 … capacity-1` (reuse the add-form cross-check pattern) and hides for non-tablet entries. Polish confirm copy for the zero-delete case, e.g. title `Usuń lek` / message `Zmniejszenie liczby opakowań do zera usunie „{name}" z apteczki. Kontynuować?`. No optimistic updates — rely on invalidate + refetch.

### Success Criteria:

#### Automated Verification:

- Build passes: `cd frontend && npm run build`
- Lint passes: `cd frontend && npm run lint`
- Format clean: `cd frontend && npx prettier --check src/`

#### Manual Verification:

- −/+ adjusts package count; list refetches; status/out-of-stock badge update accordingly.
- Editing/clearing the partial-tablet count works for tablet-based entries and is hidden for non-tablet entries; out-of-range values are rejected client-side.
- Decrementing an uncategorised entry from 1 → confirm dialog → confirm deletes it; cancel leaves it at 1.
- Decrementing an important or used entry to 0 leaves it at 0 (visible for restock), no dialog.
- Behaviour is consistent on desktop row and mobile card.

**Implementation Note**: After automated verification passes, pause for manual confirmation before Phase 5.

---

## Phase 5: E2E — manage/delete spec + teardown

### Overview

Add a Playwright spec exercising delete and decrement-to-zero end to end, and use the new `DELETE` to give the suite a real teardown path.

### Changes Required:

#### 1. Manage-entry e2e spec

**File**: `frontend/e2e/manage-cabinet-entry.spec.ts` (new)

**Intent**: Drive the golden path for FR-005 through the browser using role/label/text locators and state-based waits (per the `/10x-e2e` rules and `seed.spec.ts` precedent): log in (reuse `auth.setup.ts` storage state), add a fresh entry (unique expiry to dodge the dedup constraint), increment/decrement its package count, then delete it via the confirm dialog and assert it is gone.

**Contract**: Locators via `getByRole` / `getByText` (never CSS/XPath); waits via `toBeVisible()` / `waitForResponse()` on the quantity PATCH and DELETE / `waitForURL()` — never `waitForTimeout()`. Cover both a plain delete and a decrement-to-zero delete of an uncategorised entry. Unique per-run identifiers (timestamp-suffixed expiry) so parallel runs and re-runs don't collide.

#### 2. Teardown via DELETE

**File**: `frontend/e2e/manage-cabinet-entry.spec.ts` (afterEach/afterAll) and, if applicable, the existing seed/teardown helpers

**Intent**: Now that a DELETE endpoint exists, remove entries created by the spec in teardown rather than leaking them (addressing the documented gap in `seed.spec.ts:33`).

**Contract**: Teardown calls the cabinet DELETE for any entry ids created during the run; failures in teardown do not mask test assertions.

### Success Criteria:

#### Automated Verification:

- E2E spec passes (native PowerShell, hits real DB — L-001): `cd frontend; npx playwright test manage-cabinet-entry`
- Full e2e suite still green: `cd frontend; npx playwright test`
- Lint + format clean on the new spec: `cd frontend && npm run lint && npx prettier --check e2e/`

#### Manual Verification:

- Playwright report shows the manage/delete journey passing.
- After a run, no orphaned test entries remain in the cabinet (teardown worked).

**Implementation Note**: This phase completes the slice; after it passes, the change is ready for `/10x-impl-review` and archival.

---

## Testing Strategy

### Unit Tests:

- `tests/cabinet/test_service.py`: `set_entry_quantity` (package 0 allowed, partial validation for tablet vs non-tablet variants, `EntryNotFoundError`, recomputed output); `delete_entry` (not-found raises, happy path calls crud).
- `tests/cabinet/test_crud.py`: `delete_entry` (happy path + `SQLAlchemyError` → `CabinetDatabaseError`); `update_entry_counts` reuse for the quantity path.
- `tests/cabinet/test_router.py`: DELETE 204 + 404 mapping; quantity PATCH success + 422 (negative count / bad partial) + 404 + 503 mapping.
- `tests/cabinet/test_facade.py`: `set_entry_quantity` forwards resolved prefs to the service.
- Reuse shared fixtures (`mock_session`, `fake_user`, `client`, `authed_client`) with `spec=` / `autospec=True` — no duplicate mocks.

### Integration Tests:

- `tests/integration/cabinet/`: DELETE removes the row and enforces cross-account 404 (extend `test_ownership.py`); quantity PATCH persists counts, allows 0, honours the CHECK ≥ 0, and recomputes status/below_minimum.

### Manual Testing Steps:

1. Add an entry, use −/+ to change package count, confirm the badge/status update.
2. Edit and clear the partial-tablet count on a tablet-based entry.
3. Delete an entry via the trash action; verify the confirm dialog and badge-clearing copy.
4. Decrement an uncategorised entry to 0 (confirm → deleted) and an important/used entry to 0 (stays at 0).
5. Repeat on a mobile-width viewport.

## Performance Considerations

Small scale (PRD `target_scale: low`). Invalidate + refetch on each mutation is acceptable; rapid −/+ clicks each trigger a refetch, softened by `keepPreviousData` already set on `useCabinetEntries`. No optimistic updates, so server-computed classification is never shown stale.

## Migration Notes

No schema migration required — `cabinet_entries.package_count` already has the `>= 0` CHECK, and no columns are added or changed. Delete is a hard delete (no soft-delete column).

## References

- Roadmap slice: `context/foundation/roadmap.md` (S-03), PRD **FR-005**, FR-022, FR-020 (badge), FR-013/FR-015 (category flags).
- Backend templates: `backend/app/api/v1/cabinet/service.py:850` (`set_entry_importance`), `:897` (`set_entry_usage`); `crud.py:433` (`find_entry_by_id`), `:503` (`update_entry_counts`); `facade.py:95`.
- Frontend patterns: `cabinet-queries.ts:74-99` (mutation hooks), `add-result-dialog.tsx` / `filter-sheet.tsx` (modal patterns), `usage-edit-form.tsx` (inline edit), `use-cabinet-entry.ts` (per-row state + `OUT_OF_STOCK_LABEL`).
- E2E precedent: `frontend/e2e/seed.spec.ts` (add → verify golden path; teardown gap note at `:33`).
- Lessons: L-001 (PowerShell for TLS DB), L-004 (SQLAlchemyError wrapping), L-005 (no single-letter names), L-006 (imports at top).

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Backend — DELETE endpoint

#### Automated

- [ ] 1.1 Unit tests pass: `cd backend && uv run pytest tests/cabinet`
- [ ] 1.2 Integration tests pass (native PowerShell): `cd backend; uv run pytest tests/integration/cabinet`
- [ ] 1.3 Lint + format clean: `cd backend && uv run ruff check . && uv run ruff format --check .`

#### Manual

- [ ] 1.4 DELETE on owned entry returns 204 and the entry disappears from the list
- [ ] 1.5 DELETE on non-existent/foreign entry returns 404 (isolation holds)
- [ ] 1.6 OpenAPI shows the lock icon on the new route

### Phase 2: Frontend — delete action

#### Automated

- [ ] 2.1 Build passes: `cd frontend && npm run build`
- [ ] 2.2 Lint passes: `cd frontend && npm run lint`
- [ ] 2.3 Format clean: `cd frontend && npx prettier --check src/`

#### Manual

- [ ] 2.4 Trash action opens a Polish confirm dialog; cancel paths work; confirm removes the entry
- [ ] 2.5 Out-of-stock entry's dialog states the badge will be cleared
- [ ] 2.6 Works on both desktop row and mobile card

### Phase 3: Backend — quantity PATCH endpoint

#### Automated

- [ ] 3.1 Unit tests pass: `cd backend && uv run pytest tests/cabinet`
- [ ] 3.2 Integration tests pass (native PowerShell): `cd backend; uv run pytest tests/integration/cabinet`
- [ ] 3.3 Lint + format clean: `cd backend && uv run ruff check . && uv run ruff format --check .`

#### Manual

- [ ] 3.4 PATCH package_count: 0 succeeds and persists at 0
- [ ] 3.5 Negative count → 422; out-of-range/non-tablet partial → 422
- [ ] 3.6 Response reflects recomputed status/below_minimum/total_tablets
- [ ] 3.7 PATCH on foreign/non-existent entry → 404

### Phase 4: Frontend — quantity steppers + zero rule

#### Automated

- [ ] 4.1 Build passes: `cd frontend && npm run build`
- [ ] 4.2 Lint passes: `cd frontend && npm run lint`
- [ ] 4.3 Format clean: `cd frontend && npx prettier --check src/`

#### Manual

- [ ] 4.4 −/+ adjusts package count; list refetches; badge/status update
- [ ] 4.5 Partial-tablet edit/clear works for tablet entries, hidden for non-tablet
- [ ] 4.6 Uncategorised entry 1 → 0 confirms then deletes; cancel leaves at 1
- [ ] 4.7 Important/used entry decrements to 0 and stays (no dialog)
- [ ] 4.8 Consistent on desktop row and mobile card

### Phase 5: E2E — manage/delete spec + teardown

#### Automated

- [ ] 5.1 Manage/delete spec passes (native PowerShell): `cd frontend; npx playwright test manage-cabinet-entry`
- [ ] 5.2 Full e2e suite still green: `cd frontend; npx playwright test`
- [ ] 5.3 Lint + format clean on the new spec: `cd frontend && npm run lint && npx prettier --check e2e/`

#### Manual

- [ ] 5.4 Playwright report shows the manage/delete journey passing
- [ ] 5.5 No orphaned test entries remain after a run (teardown worked)

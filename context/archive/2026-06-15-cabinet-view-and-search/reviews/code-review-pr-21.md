<!-- CODE-REVIEW-REPORT -->
# Code Review: Cabinet View and Search (PR #21)

- **Target**: PR #21 (`feature/s02-cabinet-view-and-search` → `develop`)
- **Scope**: full diff excluding `context/` (backend + frontend, 20 files)
- **Date**: 2026-06-16
- **Effort**: high (recall-biased)
- **Findings**: 6 (1 visible-state bug, 1 UX regression, 4 lower-severity)
- **Status**: all 6 resolved on 2026-06-16 (see per-finding **Resolution** notes)

## Resolution summary

| # | Finding | Fix | Tests |
|---|---------|-----|-------|
| 1 | Out-of-range `page` → blank table | Clamp effect redirects to last valid page once `total` is known; `totalPages` floored at 1 | frontend (manual) |
| 2 | Table flickers to spinner on page/filter change | `placeholderData: keepPreviousData` on `useCabinetEntries` | frontend (manual) |
| 3 | 1-char search leaks `?search=a` into URL | `effectiveSearch` (≥ `MIN_SEARCH_LEN`) drives URL, `hasFilters`, and query params | frontend (manual) |
| 4 | Dropped `CabinetError → 400` branch | Restored `except CabinetError → 400` before generic `Exception → 500` | `test_router.py::test_cabinet_error_returns_400` |
| 5 | `clearFilters` wiped `order`/`page_size` | Deletes only `status`/`search`/`page`, preserving sort + page size | frontend (manual) |
| 6 | `_tablet_capacity_invalid` computed twice | Hoisted into a single `capacity_invalid` local | `test_service.py::test_tablet_variant_with_invalid_capacity_yields_none_total_and_warns` |

Backend suite: 226 passed (the live-DB `tests/db/test_connection.py` requires a
database and is excluded locally). Frontend `tsc -b` and `eslint` clean. Per the
request, automated tests were added for backend findings only (#4, #6); the
frontend fixes were verified manually.

Verified against source: table name `medication_registry` is correct for the raw
`search_vector @@ to_tsquery` clause; `classify_status` matches the SQL date
predicates in `_build_base_query` exactly; table header/cell counts align (5/5,
`colSpan={5}`).

## Findings (ranked most-severe first)

### 1. Out-of-range `page` is never clamped → blank table

- **File**: `frontend/src/features/cabinet/components/cabinet-page.tsx:50` (`parsePage`)
- **Severity**: bug (visible broken state, reachable from a plain URL)

Open `/cabinet?page=999` (or hit Back to a page that no longer exists after
results shrink). `parsePage` returns 999, the request sends
`offset=(999-1)*pageSize`, backend returns `items=[]` but `total>0`.
`CabinetList`'s empty-state guard checks `total === 0`, which is false, so it
renders the table headers with an empty `<tbody>`, and pagination shows
`Strona 999 z 1`.

**Fix**: clamp `page` to `totalPages` once `pageData` is known (or redirect to
the last valid page).

### 2. No `placeholderData`/`keepPreviousData` → table flickers on every page/filter change

- **File**: `frontend/src/features/cabinet/api/cabinet-queries.ts:48` (`useCabinetEntries`)
- **Severity**: UX regression

Clicking `Następna` or changing a filter switches the query key to an uncached
key, so `isLoading` is true and `CabinetList` returns the `Ładowanie…` text
instead of the previous rows — the table disappears and the layout jumps on
every navigation.

**Fix**: add `placeholderData: keepPreviousData` so the prior page stays visible
while the next one fetches.

### 3. 1-character search writes `?search=a` but is ignored by the query

- **File**: `frontend/src/features/cabinet/components/cabinet-page.tsx:70` (debounce effect)
- **Severity**: minor correctness / inconsistent state

Typing a single character writes `?search=a` to the URL (the delete branch only
fires on `""`), but `params` omits `search` (length < 2) and `hasFilters` stays
`false`. The list shows all entries / "Apteczka jest pusta" while the URL claims
an active search, and reloading keeps the orphaned param.

**Fix**: only write `search` to the URL when it is effective (length ≥ 2), or
delete it below that threshold.

### 4. `list_entries` dropped the `except CabinetError → 400` branch

- **File**: `backend/app/api/v1/cabinet/router.py:57`
- **Severity**: low (narrowed contract; near-dead path for this endpoint)

The rewrite catches only `(CabinetDatabaseError, UserDatabaseError) → 503` then
generic `Exception → 500`. The previous `except CabinetError → 400` branch was
removed, so any non-DB `CabinetError` from the read path would now surface as
500 instead of 400. Currently unreachable for the list path, but the contract
narrowed silently.

**Resolution** (2026-06-16): Restored the `except CabinetError → 400` handler
between the 503 and the generic 500 branches in `router.py`. Regression test
`tests/cabinet/test_router.py::TestListEntriesErrorMapping::test_cabinet_error_returns_400`
asserts a raised `CabinetError` maps to 400 with its message in `detail`.

### 5. `clearFilters` wipes non-filter UI state

- **File**: `frontend/src/features/cabinet/components/cabinet-page.tsx:88`
- **Severity**: low (UX)

`clearFilters` does `setSearchParams({})`, which also removes `order` and
`page_size` — not just the filters. Setting sort to Z→A and page size to 100,
then clicking "Wyczyść filtry", silently reverts both to defaults.

**Fix**: delete only `status`/`search`/`page`, preserving `order` and
`page_size`.

### 6. `_tablet_capacity_invalid(variant)` computed twice per row

- **File**: `backend/app/api/v1/cabinet/service.py:169` (`_map_row_to_entry_out`)
- **Severity**: cleanup

The predicate is evaluated once for the warning check and again for the `tpp`
ternary — redundant work and a duplicated branch that can drift.

**Fix**: compute once into a local (`invalid = _tablet_capacity_invalid(variant)`)
and reuse it.

**Resolution** (2026-06-16): Hoisted into a single `capacity_invalid` local that
drives both the warning log and the `tpp` ternary. Parametrized regression test
`tests/cabinet/test_service.py::TestListEntries::test_tablet_variant_with_invalid_capacity_yields_none_total_and_warns`
covers `None`/`0`/negative capacity on a tablet-based variant, asserting
`total_tablets is None` and that `logger.warning` is called exactly once.

## Notes

- Backend status SQL/Python parity is covered by `TestStatusSQLParity` — good.
- The `text(...)` clause qualifies `medication_registry.search_vector`, required
  here (unlike the single-table medicines query) because of the join — correct.
- Shared `build_tsquery` / `NonEmptyStr` extraction into `app/utilities/` removes
  the prior duplication cleanly.

# Registry Import (F-03) Implementation Plan

## Overview

Reshape the `medication_registry` table so it mirrors the official Polish medicines
XML at **one row per package unit (`jednostkaOpakowania`)**, then build a one-off
Python import script that streams the official XML dataset, normalizes it, and
bulk-loads it into that table. After this change the registry holds real,
queryable data so S-01's autocomplete can be built on clean, registry-backed
records.

## Current State Analysis

- The `medication_registry` table already exists (shipped in F-02, migration head
  `2c7067ce3f56`). Its columns: `id, name, active_ingredient, tablet_count,
  producer, route_of_administration, leaflet_url, specification_url` plus a
  generated `search_vector` (tsvector over `name` + `active_ingredient`) with a
  GIN index `ix_medication_registry_search_vector`.
- The table is **empty of registry data** — nothing has been imported yet, so a
  reshape is safe.
- `cabinet_entries.medication_registry_id` is an FK → `medication_registry.id`.
  Reshaping the table's *columns* (keeping `id` as the uuid PK) does not disturb
  this FK, so cabinet schema stays untouched.
- The SQLModel class lives at `backend/app/api/v1/medicines/models.py`
  (`MedicationRegistry`); `crud.py`/`service.py` in that domain are empty stubs.
- Alembic is wired (`backend/migrations/`, async `env.py`); migrations run against
  the Supabase **direct** connection (port 5432), not the transaction pooler.
- No `backend/scripts/` directory exists yet. Tests live in `backend/tests/`
  (pytest + pytest-asyncio, `asyncio_mode = "auto"`).
- `httpx` is already an installed dependency (via `fastapi[standard]`).

### XML structure (confirmed from `docs/reference/rejestr_lekow_sample_20260603.xml`)

Root `<produktyLecznicze>` (namespace
`http://rejestry.ezdrowie.gov.pl/rpl/eksport-danych-v6.0.0`) → many
`<produktLeczniczy>` entries. Each product:

- **Attributes**: `nazwaProduktu` (name), `nazwaPowszechnieStosowana` (common
  name), `moc` (strength), `nazwaPostaciFarmaceutycznej` (form),
  `podmiotOdpowiedzialny` (MA holder), `rodzajPreparatu` (`ludzki` = human),
  `ulotka` (leaflet URL, absolute), `charakterystyka` (specification URL,
  absolute), `id` (source product id).
- `<kodyATC>/<kodATC>` — ATC code.
- `<drogiPodania>/<drogaPodania @drogaPodaniaNazwa>` — **multiple** routes
  (e.g. Gensulin R: `domięśniowa, dożylna, podskórna`).
- `<substancjeCzynne>/<substancjaCzynna @nazwaSubstancji>` — **multiple** active
  substances.
- `<daneOWytworcy>/<wytworcy @nazwaWytworcyImportera>` — manufacturer(s).
- `<opakowania>/<opakowanie @kodGTIN @kategoriaDostepnosci @skasowane>` —
  **multiple** packages. Each `<opakowanie>` contains
  `<jednostkiOpakowania>/<jednostkaOpakowania @pojemnosc @jednostkaPojemnosci>` —
  **one or more** units. `pojemnosc` is the count/volume (e.g. `6`, `100`, or
  empty); `jednostkaPojemnosci` is the unit (`tabl.`, `ml`, `g`, …).

## Desired End State

- `medication_registry` is reshaped to a package-unit grain with XML-mirroring,
  English-named columns (see Phase 1) and the existing `search_vector` + GIN index
  preserved.
- A one-off script `uv run python -m scripts.registry_import` (run from
  `backend/`) downloads the official XML, parses it, and loads it; re-running it
  is safe (truncate-and-reload, guarded).
- The registry holds one row per imported `jednostkaOpakowania` for **human,
  non-withdrawn** products, each carrying name, active ingredient, strength, form,
  MA holder, manufacturer, routes, ATC, availability, capacity, capacity unit,
  pill flag, and leaflet/specification URLs.
- Parser logic is covered by unit tests using the committed sample as a fixture —
  no DB or network needed to run them.

### Key Discoveries

- **Migration head is `2c7067ce3f56`** (`backend/migrations/versions/`); the new
  revision must set `down_revision = "2c7067ce3f56"`.
- The `search_vector` generated column depends only on `name` + `active_ingredient`
  (both retained), so the reshape **does not need to drop or recreate** it
  (`2c7067ce3f56_varchar_to_text.py:30-41`).
- Keeping `id` as the uuid PK means the `cabinet_entries` FK is untouched — the
  reshape is column-level (`add_column`/`drop_column`), not a table drop.
- One `<opakowanie>` may hold **multiple** `<jednostkaOpakowania>` (composite
  packs, e.g. FANHDI: powder vial + solvent syringe). Per decision, each
  `jednostkaOpakowania` becomes its own row → `gtin` repeats across those rows
  (store it **non-unique**).
- `pojemnosc` can be empty (FANHDI's powder vial) → `capacity` NULL,
  `is_tablet_based` False; the parser must not crash on this.
- The XML namespace means ElementTree tags arrive fully qualified
  (`{http://…v6.0.0}produktLeczniczy`); lookups must be namespace-aware.

## What We're NOT Doing

- No autocomplete API, search endpoint, or any `/api/v1/medicines` routes — that
  is S-01/S-02.
- No frontend.
- No daily/scheduled dataset refresh (parked to v2); this is a one-off script.
- No normalized multi-table schema (products/packages/routes/substances) — a
  single flat table at package-unit grain was chosen.
- No new columns for fields outside the agreed set (e.g. `liczbaOpakowan`,
  `rodzajOpakowania`, `informacjeDodatkowe`, `numerPozwolenia`, `zgodyPrezesa`,
  educational-material flags are not imported).
- No change to `cabinet_entries`, `users`, or `user_preferences`.
- No upsert/merge-on-re-run keyed by GTIN — re-runs truncate and reload.

## Implementation Approach

Four sequential phases, each leaving the repo runnable. Phase 1 reshapes the
schema (model + migration) with no data. Phase 2 builds the parser as pure,
fixture-tested functions so normalization correctness is proven before any DB or
network is involved (directly mitigating the roadmap's stated F-03 risk). Phase 3
wraps the parser in a streaming downloader + batched async bulk loader with a
truncate-and-reload guard. Phase 4 runs the real import against Supabase and
verifies the loaded data.

## Critical Implementation Details

**Streaming parse (memory + namespace).** The real dataset is hundreds of MB; a
full DOM load is not viable. Use `xml.etree.ElementTree.iterparse` over the file,
match the namespace-qualified `produktLeczniczy` end-event, yield rows, then call
`elem.clear()` (and drop processed siblings from the root) so memory stays flat.
Tags are namespace-qualified, e.g.:

```python
NS = "{http://rejestry.ezdrowie.gov.pl/rpl/eksport-danych-v6.0.0}"
context = ET.iterparse(source, events=("start", "end"))
_event, root = next(context)  # capture the <produktyLecznicze> root
for event, elem in context:
    if event == "end" and elem.tag == f"{NS}produktLeczniczy":
        yield from _rows_for_product(elem)
        elem.clear()
        root.clear()  # drop the processed product from root so memory stays flat
```

**Pill detection is a curated, tested allowlist.** `is_tablet_based` is computed at
import from `jednostkaPojemnosci` against a centralized set of countable units
(`{"tabl.", "kaps.", …}`, extensible). Volume/mass units (`ml`, `g`, …) and
unknown units → `False`. Keeping the allowlist in one constant makes it testable
and easy to extend without touching query code in S-01/S-05.

**Generated column must never be written.** `search_vector` is computed by
PostgreSQL; the bulk insert must list only the real columns. Including
`search_vector` in an INSERT raises a "cannot insert into generated column" error.

**Migrations use the direct connection.** Run `alembic upgrade head` against the
Supabase direct connection (port 5432); DDL through the transaction pooler (6543)
fails on asyncpg prepared statements (carried over from F-02).

---

## Phase 1: Reshape `medication_registry`

### Overview

Update the `MedicationRegistry` SQLModel and add a new Alembic migration that
transforms the table from the F-02 shape to the package-unit grain. No data is
involved; `search_vector` and the cabinet FK are left intact.

### Changes Required

#### 1. MedicationRegistry model

**File**: `backend/app/api/v1/medicines/models.py`

**Intent**: Redefine the registry row as one package unit mirroring the XML, with
English column names. Drop the lossy `tablet_count` and the single `producer`;
add the package-grain and product-metadata fields. Keep `id` as the uuid PK so the
cabinet FK is undisturbed.

**Contract**: `class MedicationRegistry(SQLModel, table=True)`,
`__tablename__ = "medication_registry"`, all string columns `sa.Text()`,
all nullable except `id` and `name`:
- `id: uuid.UUID` — PK, default `uuid4` (unchanged)
- `source_product_id: str | None` — `produktLeczniczy@id`
- `gtin: str | None` — `opakowanie@kodGTIN` (NOT unique — repeats for composite packs)
- `name: str` — `nazwaProduktu`, indexed (unchanged)
- `active_ingredient: str | None` — joined `substancjeCzynne` substance names
- `strength: str | None` — `moc`
- `pharmaceutical_form: str | None` — `nazwaPostaciFarmaceutycznej`
- `marketing_authorization_holder: str | None` — `podmiotOdpowiedzialny`
- `manufacturer: str | None` — joined `wytworcy` names
- `route_of_administration: str | None` — joined `drogaPodania` names (retained column)
- `atc_code: str | None` — `kodATC`
- `availability_category: str | None` — `kategoriaDostepnosci`
- `capacity: Decimal | None` — parsed `pojemnosc` (`sa_type=sa.Numeric()`)
- `capacity_unit: str | None` — `jednostkaPojemnosci`
- `is_tablet_based: bool` — derived from `capacity_unit`; default `False`
- `leaflet_url: str | None` — `ulotka` (unchanged)
- `specification_url: str | None` — `charakterystyka` (unchanged)

`search_vector` remains DB-only (not a model field), as in F-02.

#### 2. Reshape migration

**File**: `backend/migrations/versions/<hash>_reshape_medication_registry.py`
(generate with `uv run alembic revision -m "reshape medication registry"` from
`backend/` — write the body by hand; do not autogenerate, to keep the
`search_vector` column from being dropped/re-added unnecessarily).

**Intent**: Move the live table from the F-02 shape to the new shape with
column-level `add_column`/`drop_column` operations. Leave `search_vector`, the GIN
index, `name`'s index, and the cabinet FK in place.

**Contract**:
- `down_revision = "2c7067ce3f56"`.
- `upgrade()`: `op.drop_column` for `tablet_count` and `producer`; `op.add_column`
  for `source_product_id, gtin, strength, pharmaceutical_form,
  marketing_authorization_holder, manufacturer, atc_code, availability_category,
  capacity (sa.Numeric), capacity_unit, is_tablet_based (sa.Boolean,
  server_default false)`. All new text columns `sa.Text()`, nullable.
- `downgrade()`: drop the added columns; re-add `tablet_count` (`sa.Integer`,
  nullable) and `producer` (`sa.Text`, nullable).
- Do **not** touch `search_vector`, `ix_medication_registry_search_vector`,
  `ix_medication_registry_name`, or any FK.

### Success Criteria

#### Automated Verification

- `uv run alembic upgrade head` completes cleanly against Supabase (direct conn)
- `uv run alembic downgrade -1` rolls back cleanly
- `uv run alembic upgrade head` succeeds again (idempotency)
- `python -c "from app.api.v1.medicines.models import MedicationRegistry"` exits 0
- `uv run ruff check . && uv run ruff format --check .` passes

#### Manual Verification

- In Supabase, `medication_registry` shows the new columns and no longer shows
  `tablet_count`/`producer`
- `search_vector` (tsvector) column and `ix_medication_registry_search_vector` GIN
  index are still present
- `cabinet_entries` FK to `medication_registry` is intact

**Implementation Note**: After completing this phase and all automated
verification passes, pause for manual confirmation before proceeding.

---

## Phase 2: XML Parser (pure, fixture-tested)

### Overview

Build the normalization logic as pure functions that turn the XML into row dicts,
with no DB or network dependency, and cover them with unit tests against the
committed sample. This is where correctness is proven before bulk loading.

### Changes Required

#### 1. Scripts package

**Files**: `backend/scripts/__init__.py`,
`backend/scripts/registry_import/__init__.py`

**Intent**: Establish a `scripts` package so `python -m scripts.registry_import`
runs from `backend/` and can import `app.*`.

**Contract**: Empty `__init__.py` files.

#### 2. Parser module

**File**: `backend/scripts/registry_import/parser.py`

**Intent**: Stream-parse the XML and yield one normalized row per
`jednostkaOpakowania`, applying the human-only and non-withdrawn filters and all
field normalization.

**Contract**:
- `TABLET_UNITS: frozenset[str]` — centralized countable-unit allowlist
  (at minimum `{"tabl.", "kaps."}`; extend conservatively).
- `parse_registry(source) -> Iterator[dict]` — `source` is a path or file object;
  uses namespace-aware `iterparse` with `elem.clear()`; skips products where
  `rodzajPreparatu != "ludzki"`; skips `opakowanie` with `skasowane == "TAK"`;
  emits one dict per `jednostkaOpakowania` of the surviving packages.
- Helper functions, each unit-testable:
    The three join helpers dedupe in **document order** (e.g. `dict.fromkeys`), not
    via `set()`, so the joined string is deterministic and the exact-string tests
    below are stable:
  - `_join_routes(product) -> str | None` — distinct `drogaPodaniaNazwa`,
    order-preserving, joined `", "`.
  - `_join_substances(product) -> str | None` — distinct `nazwaSubstancji`,
    order-preserving, joined `" + "`; `None` if none.
  - `_join_manufacturers(product) -> str | None` — distinct
    `nazwaWytworcyImportera`, order-preserving, joined `", "`.
  - `_parse_capacity(pojemnosc) -> Decimal | None` — trims, accepts comma or dot
    decimals, returns `None` for empty/non-numeric.
  - `_is_tablet_based(unit) -> bool` — membership test against `TABLET_UNITS`.
- Each yielded dict's keys match the non-generated `MedicationRegistry` columns.

**Contract (snippet — the non-obvious streaming + namespace core)**:

```python
NS = "{http://rejestry.ezdrowie.gov.pl/rpl/eksport-danych-v6.0.0}"

def parse_registry(source) -> Iterator[dict]:
    context = ET.iterparse(source, events=("start", "end"))
    _event, root = next(context)  # capture the <produktyLecznicze> root
    for event, elem in context:
        if event != "end" or elem.tag != f"{NS}produktLeczniczy":
            continue
        if elem.get("rodzajPreparatu") == "ludzki":
            yield from _rows_for_product(elem)
        elem.clear()
        root.clear()  # drop the processed product from root so memory stays flat
```

#### 3. Test fixture

**File**: `backend/tests/fixtures/registry_sample.xml`

**Intent**: A committed, offline fixture for parser tests.

**Contract**: Copy of `docs/reference/rejestr_lekow_sample_20260603.xml` (or a
trimmed representative subset covering Apap, Acodin Duo, Gensulin R, Edelan, FANHDI).

#### 4. Parser unit tests

**File**: `backend/tests/test_registry_parser.py`

**Intent**: Lock down the normalization rules against the known sample so future
edits can't silently regress field mapping.

**Contract**: Tests asserting, at minimum:
- Apap yields one row per non-withdrawn tablet package (the `skasowane="TAK"`
  500-tabl. package is excluded), each with `is_tablet_based=True` and the correct
  `capacity` (e.g. 6, 12, 24, …, 60).
- Acodin Duo yields non-tablet rows (`is_tablet_based=False`, `capacity_unit="ml"`)
  and the withdrawn 100 ml package is excluded; `active_ingredient` is the joined
  substances.
- Gensulin R's `route_of_administration == "domięśniowa, dożylna, podskórna"`.
- FANHDI's composite `opakowanie` yields **two** rows (one per
  `jednostkaOpakowania`); the empty-`pojemnosc` unit yields `capacity is None`
  without error.
- A synthetic `rodzajPreparatu="weterynaryjny"` product yields no rows.

### Success Criteria

#### Automated Verification

- `uv run pytest tests/test_registry_parser.py -v` passes
- `uv run ruff check . && uv run ruff format --check .` passes

#### Manual Verification

- Spot-read a handful of yielded dicts and confirm field mapping matches the XML

**Implementation Note**: After this phase and all automated verification passes,
pause for manual confirmation before proceeding.

---

## Phase 3: Loader + CLI

### Overview

Add the download + async batched bulk-insert layer and a CLI entrypoint, reusing
the app's engine and the Phase 2 parser. Re-running is safe via delete-and-reload
in a single all-or-none transaction, with a guard against orphaning existing
cabinet entries.

### Changes Required

#### 1. Loader module

**File**: `backend/scripts/registry_import/loader.py`

**Intent**: Consume the parser's row stream and bulk-insert into
`medication_registry` in batches within a transaction, after clearing existing
registry rows.

**Contract**:
- `async def load_registry(rows, *, batch_size=1000, force=False) -> int` —
  returns the number of inserted rows.
- Before inserting, if `force` is False and `cabinet_entries` has any row, abort
  with a clear error (deleting registry rows would orphan cabinet FKs).
- The whole load runs in **one transaction (all-or-none)**: open a session,
  `DELETE FROM medication_registry`, insert every batch, then a **single commit at
  the end**. If any batch fails, the transaction rolls back and the previous
  registry contents are left untouched — never a half-populated table. (No
  per-batch commit, no checkpoint/resume; a failed run is simply re-run.)
- Use `DELETE`, **not** `TRUNCATE` — the `cabinet_entries` FK makes Postgres reject
  `TRUNCATE medication_registry` with "cannot truncate a table referenced in a
  foreign key constraint", even when `cabinet_entries` is empty.
- Insert in chunks of `batch_size` (default 1000) rows per `session.execute(stmt,
  batch)` call using SQLAlchemy core `insert(MedicationRegistry)` — batching bounds
  per-statement memory, but all batches share the one transaction above. The insert
  lists only real columns (never `search_vector`).
- Uses `app.db.connector` (`engine` / `async_session_factory`).

#### 2. Downloader + CLI entrypoint

**File**: `backend/scripts/registry_import/__main__.py`

**Intent**: Tie download → parse → load together with argparse, so the import runs
as `uv run python -m scripts.registry_import` from `backend/`.

**Contract**:
- Args: `--source` (default the official dataset URL; also accepts a local file
  path), `--batch-size` (default 1000), `--force` (bypass the cabinet guard),
  `--dry-run` (parse + count, no DB writes).
- When `--source` is a URL, stream-download to a temp file (httpx streaming) before
  parsing; when it is a local path, parse it directly. **Windows note**: a
  `NamedTemporaryFile` cannot be reopened by path while still open on Windows (this
  project's dev OS), so passing `.name` to `iterparse` raises `PermissionError`. Use
  `NamedTemporaryFile(delete=False)`, close it after the download, parse it by path,
  and `os.unlink` it in a `finally` block (or pass the open file object directly to
  `iterparse`).
- Runs the async load via `asyncio.run(...)`; logs total parsed and inserted
  counts. `--dry-run` prints counts and a few sample rows without touching the DB.

### Success Criteria

#### Automated Verification

- `uv run python -m scripts.registry_import --source tests/fixtures/registry_sample.xml --dry-run`
  prints the expected non-zero parsed-row count and exits 0 (no DB/network)
- `uv run ruff check . && uv run ruff format --check .` passes
- `python -c "import scripts.registry_import.loader, scripts.registry_import.parser"`
  exits 0

#### Manual Verification

- `--dry-run` sample output looks correct for the fixture
- Running without `--force` against a DB with existing cabinet entries aborts with
  a clear message

**Implementation Note**: After this phase and all automated verification passes,
pause for manual confirmation before proceeding.

---

## Phase 4: Production Import Run + Verification

### Overview

Run the script against the real dataset into Supabase and verify the loaded data
is complete and correctly shaped.

### Changes Required

#### 1. Execute the import

**File**: (no code change) — operational run

**Intent**: Populate `medication_registry` from the live dataset.

**Contract**: With `DATABASE_URL` pointing at Supabase (direct connection), run
`uv run python -m scripts.registry_import` from `backend/`. Confirm the logged
inserted-row count is in the expected order of magnitude (tens to hundreds of
thousands of package-unit rows).

### Success Criteria

#### Automated Verification

- The script exits 0 and logs a non-zero inserted-row count

#### Manual Verification

- `SELECT count(*) FROM medication_registry` returns a plausible large count
- Spot-check rows: `SELECT * FROM medication_registry WHERE name = 'Apap'` shows
  one row per non-withdrawn tablet package with correct `capacity`/`capacity_unit`
- A tablet product has `is_tablet_based = true`; a syrup/cream has `false`
- `leaflet_url` / `specification_url` resolve to the official site
- A `to_tsvector` search via the existing GIN index returns matches (sanity check
  that `search_vector` populated for the new rows)

**Implementation Note**: This phase is operational; confirm the data looks correct
in Supabase before marking F-03 done.

---

## Testing Strategy

### Unit Tests

- `test_registry_parser.py` covers all normalization rules against the committed
  fixture: pill detection, capacity parsing (incl. empty), route/substance/
  manufacturer joins, human-only + non-withdrawn filtering, composite-pack
  row explosion.

### Integration Tests

- None required for F-03. The loader is exercised manually via `--dry-run`
  (offline) and the Phase 4 production run. A DB-backed loader test is deferred
  (test-DB strategy is a Module 3 concern).

### Manual Testing Steps

1. Apply migrations: `uv run alembic upgrade head` (from `backend/`).
2. Dry-run the parser over the fixture and eyeball counts.
3. Run the full import against Supabase.
4. In Supabase, verify row counts and spot-check Apap, a syrup, and a
   multi-route product.

## Performance Considerations

- Streaming `iterparse` + `elem.clear()` keeps memory flat regardless of file size.
- Batched bulk inserts (default 1000/commit) keep the load efficient over a
  large row count; asyncpg handles the throughput.
- The `search_vector` generated column is computed by PostgreSQL on insert; no
  application-side cost, but it does add per-row work during the bulk load
  (acceptable for a one-off script).

## Migration Notes

- The new revision chains from `2c7067ce3f56`; set `down_revision` accordingly.
- The reshape is column-level and leaves `search_vector`, its GIN index, and the
  `cabinet_entries` FK intact — no FK drop/recreate needed.
- Run migrations against the Supabase **direct** connection (port 5432), not the
  transaction pooler.
- Re-running the import clears `medication_registry` with `DELETE FROM` (not
  `TRUNCATE`, which the `cabinet_entries` FK would reject); the loader guards against
  doing this when `cabinet_entries` is non-empty unless `--force` is passed.

## References

- Roadmap: `context/foundation/roadmap.md` § F-03
- F-02 plan (schema origin): `context/changes/data-layer-scaffold/plan.md`
- Current model: `backend/app/api/v1/medicines/models.py`
- Migration head: `backend/migrations/versions/2c7067ce3f56_varchar_to_text.py`
- Backend structure rules: `docs/reference/backend-structure.md`
- Sample fixture: `docs/reference/rejestr_lekow_sample_20260603.xml`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step
> lands. Do not rename step titles.

### Phase 1: Reshape `medication_registry`

#### Automated

- [x] 1.1 `uv run alembic upgrade head` completes cleanly against Supabase — 2c2736c
- [x] 1.2 `uv run alembic downgrade -1` rolls back cleanly — 2c2736c
- [x] 1.3 `uv run alembic upgrade head` succeeds again (idempotency) — 2c2736c
- [x] 1.4 `MedicationRegistry` imports without error — 2c2736c
- [x] 1.5 `uv run ruff check . && uv run ruff format --check .` passes — 2c2736c

#### Manual

- [x] 1.6 New columns present, `tablet_count`/`producer` gone in Supabase — 2c2736c
- [x] 1.7 `search_vector` tsvector column + GIN index still present — 2c2736c
- [x] 1.8 `cabinet_entries` FK to `medication_registry` intact — 2c2736c

### Phase 2: XML Parser (pure, fixture-tested)

#### Automated

- [x] 2.1 `uv run pytest tests/test_registry_parser.py -v` passes
- [x] 2.2 `uv run ruff check . && uv run ruff format --check .` passes

#### Manual

- [x] 2.3 Spot-read yielded dicts confirm field mapping matches the XML

### Phase 3: Loader + CLI

#### Automated

- [ ] 3.1 `--dry-run` over the fixture prints expected counts and exits 0
- [ ] 3.2 `uv run ruff check . && uv run ruff format --check .` passes
- [ ] 3.3 loader + parser modules import without error

#### Manual

- [ ] 3.4 `--dry-run` sample output looks correct
- [ ] 3.5 Run without `--force` against non-empty cabinet aborts clearly

### Phase 4: Production Import Run + Verification

#### Automated

- [ ] 4.1 Script exits 0 and logs a non-zero inserted-row count

#### Manual

- [ ] 4.2 `count(*)` returns a plausible large number
- [ ] 4.3 Apap spot-check: one row per non-withdrawn tablet package, correct capacity
- [ ] 4.4 Tablet vs syrup/cream `is_tablet_based` correct
- [ ] 4.5 Leaflet/specification URLs resolve
- [ ] 4.6 tsvector/GIN search returns matches for new rows

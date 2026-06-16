# Registry Import (F-03) — Plan Brief

> Full plan: `context/changes/registry-import/plan.md`

## What & Why

Reshape `medication_registry` to mirror the official Polish medicines XML at one
row per package unit, then build a one-off script that streams, normalizes, and
bulk-loads the dataset. Without real registry data, S-01 (the north-star
add-from-registry flow) cannot be built — and the F-02 schema's single
`tablet_count` column can't represent a product's many package sizes, which is the
data-quality problem the whole product exists to solve.

## Starting Point

F-02 shipped an empty `medication_registry` table (migration head `2c7067ce3f56`)
with a lossy `tablet_count`/`producer` shape and a `search_vector` GIN index.
Alembic + async engine are wired; `cabinet_entries` FKs into the registry. No
import script exists. The real XML structure is confirmed from a committed sample.

## Desired End State

`medication_registry` holds one row per package unit for every human, non-withdrawn
product in the registry — name, active ingredient, strength, form, MA holder,
manufacturer, routes, ATC, availability, capacity + unit, a pill flag, and
leaflet/specification URLs — queryable via the existing full-text index. A
guarded, re-runnable script produces this from the official dataset.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Row granularity | One row per `jednostkaOpakowania` | User wants the model to mirror the XML at package-unit grain | Plan |
| Schema shape | Single flat denormalized table | Keeps cabinet FK + queries simple; registry is read-only | Plan |
| Migration strategy | New revision, column-level alter | Respects immutability; `search_vector` + FK untouched | Plan |
| Composite packs | One row per sub-unit (`gtin` repeats, non-unique) | No data loss for multi-unit packs | Plan |
| Filtering | Human + non-withdrawn only | Matches PRD persona; cleaner autocomplete | Plan |
| Producer | Store both MA holder **and** manufacturer | No information lost; UI chooses later | Plan |
| Active ingredient | Joined `substancjeCzynne` names | Present even when common name is blank | Plan |
| Extra columns | strength, form, source_product_id, gtin, atc_code, availability_category, route | Disambiguation + traceability, cheap on a read-only table | Plan |
| Pill detection | Curated `capacity_unit` allowlist → `is_tablet_based` | Explicit, testable, extensible | Plan |
| Re-run safety | Truncate-and-reload, guarded by cabinet-not-empty check | Simple for a one-off; avoids orphaning FKs | Plan |

## Scope

**In scope:** schema reshape (model + migration), streaming XML parser with unit
tests, download + batched async loader, CLI with dry-run, production import run.

**Out of scope:** any medicines API/autocomplete (S-01/S-02), frontend, scheduled
refresh (v2), normalized multi-table schema, changes to non-registry tables,
GTIN-keyed upsert.

## Architecture / Approach

`scripts/registry_import/`: `parser.py` (pure, fixture-tested streaming
normalization) → `loader.py` (async batched bulk insert, truncate-and-reload) →
`__main__.py` (download + argparse CLI). Reuses `app.db.connector` and the
`MedicationRegistry` model. `search_vector` stays DB-computed and is never written.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Schema reshape | Reshaped model + new migration | Disturbing `search_vector`/FK during alter |
| 2. XML parser | Pure normalization + unit tests on fixture | Mis-mapping XML fields / namespace handling |
| 3. Loader + CLI | Download + batched load + dry-run guard | Memory/throughput on the large file |
| 4. Production run | Registry populated in Supabase | Row count or field mapping off in real data |

**Prerequisites:** F-02 applied (done); `DATABASE_URL` to Supabase direct
connection; sample fixture committed.
**Estimated effort:** ~2 sessions across 4 phases.

## Open Risks & Assumptions

- The tablet-unit allowlist starts small (`tabl.`, `kaps.`); real data may surface
  other countable units to add — caught by spot checks in Phase 4.
- Real-data field variants (unexpected `pojemnosc` formats, missing attributes)
  may surface only at the production run; the parser is written defensively.
- The dataset URL must be reachable at import time (large download).

## Success Criteria (Summary)

- `medication_registry` holds one well-formed row per human, non-withdrawn package
  unit, queryable by the existing full-text index.
- Parser unit tests pass offline against the committed fixture.
- Apap (and other) spot-checks in Supabase match the XML after the production run.

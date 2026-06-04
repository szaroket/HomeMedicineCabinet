---
change_id: registry-import
roadmap_id: F-03
title: "Registry import: Polish medicines XML → PostgreSQL"
status: impl_reviewed
created: 2026-06-04
updated: 2026-06-04
---

## What

Reshape the `medication_registry` table to mirror the Polish medicines XML at one
row per package unit (`jednostkaOpakowania`), then build a one-off Python import
script that streams the official XML dataset, normalizes it, and bulk-loads it so
S-01's autocomplete has clean, registry-backed data to query.

## Why

The whole product hypothesis is that registry-backed data eliminates the
inconsistent free-text records that erode trust. S-01 (the north star) cannot be
built until the registry table holds real, queryable data. The F-02 schema's
single lossy `tablet_count` column can't represent a product's many package sizes;
reshaping to a package-grain table that mirrors the XML fixes this at the root.

## Scope constraints

- **Human-use medicines only** — only products whose `rodzajPreparatu` is `ludzki`
  (human) are imported; veterinary products are skipped (`parser.py`, covered by
  the `weterynaryjny` fixture row). Animal/veterinary medicines are out of MVP
  scope (PRD §Non-Goals).
- **Import once, no updates** — registry records are created once at MVP via this
  one-off script and are not updated thereafter. Incremental/periodic refresh is
  deferred to v2 (PRD §Non-Goals; roadmap Parking Lot "Daily dataset update").

## Links

- Roadmap entry: `context/foundation/roadmap.md` § F-03
- PRD refs: FR-003, FR-011, FR-012
- Plan: `context/changes/registry-import/plan.md`
- Plan brief: `context/changes/registry-import/plan-brief.md`
- Dataset: `https://rejestry.ezdrowie.gov.pl/api/rpl/medicinal-products/public-pl-report/6.0.0/overall.xml`
- Sample fixture: `docs/reference/rejestr_lekow_sample_20260603.xml`

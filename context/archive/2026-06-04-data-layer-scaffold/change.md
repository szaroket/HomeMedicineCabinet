---
change_id: data-layer-scaffold
roadmap_id: F-02
title: "Data layer: SQLModel models + Alembic migrations + Supabase PostgreSQL"
status: archived
created: 2026-06-04
updated: 2026-06-15
archived_at: 2026-06-15T16:48:13Z
---

## What

Wire SQLModel + asyncpg + Alembic into the existing FastAPI skeleton. Define the full MVP schema (four tables: users, medication_registry, cabinet_entries, user_preferences). Prove the connection works with a smoke test.

## Why

Every downstream slice (F-03, S-01 and beyond) requires DB models and a working connection. Schema design decisions here — especially the deduplication key and full-text index — ripple through all slices and are expensive to change mid-build.

## Links

- Roadmap entry: `context/foundation/roadmap.md` § F-02
- PRD refs: FR-003, FR-010, NFR (per-account data isolation), NFR (data persists across sessions and devices)
- Plan: `context/changes/data-layer-scaffold/plan.md`

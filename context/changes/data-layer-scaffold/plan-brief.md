# Data Layer Scaffold — Plan Brief

> Full plan: `context/changes/data-layer-scaffold/plan.md`

## What & Why

Wire SQLModel + asyncpg + Alembic into the FastAPI skeleton and define the full MVP PostgreSQL schema. This foundation is required before F-03 (registry import) and S-01 (add medication) can be built — without it, every downstream slice has no tables to read or write.

## Starting Point

`backend/pyproject.toml` has only `fastapi[standard]`; no ORM, driver, or migration tool is installed. The `medicines/`, `auth/`, and `health/` domain directories exist as stubs with no models or DB access.

## Desired End State

Four tables exist in Supabase PostgreSQL (`users`, `medication_registry`, `cabinet_entries`, `user_preferences`), a GIN tsvector index on `medication_registry` is in place for autocomplete, `alembic upgrade head` applies cleanly, and a smoke test confirms the live DB session works.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) |
|---|---|---|
| DB driver | asyncpg | Best performance + first-class SQLAlchemy async support for FastAPI |
| DB connector location | `backend/app/db/connector.py` | Single shared import path for all domain crud.py files |
| Alembic location | `backend/alembic.ini` + `backend/migrations/` | Standard placement alongside pyproject.toml; works with `uv run alembic` |
| Full-text index | GIN on stored tsvector column | Fastest autocomplete query path; satisfies <500ms p95 NFR for registry search |
| Schema scope | Full MVP (all fields through S-03) | Avoids ALTER TABLE mid-build; dosage + category fields included upfront |
| user_preferences | Included in F-02 | Both S-04 and S-06 depend on it — deferring creates a blocking bottleneck |
| Alembic generation | Autogenerate + hand-edit | Autogenerate handles 90%; GIN index, tsvector, and CHECK constraints added manually |
| Testing scope | Smoke test only | Proves infrastructure works; model-level tests belong to CRUD slices (F-03, S-01) |
| User identity | Local `users` table as FK anchor | Proper referential integrity; F-01 populates it on registration using Supabase Auth UUID |
| Config loading | Pydantic `BaseSettings` (`app/config.py`) | One validated source of truth for `DATABASE_URL`, shared by connector + Alembic env.py |
| Table names | Explicit `__tablename__` on every model | SQLModel defaults to `medicationregistry`/`user`; explicit snake_case plural keeps SQL, FKs, and index consistent and avoids the `user` reserved word |
| Schema authority | Alembic only — no `create_all` | Avoids schema drift; `create_all` would build tables missing the tsvector column, GIN index, and CHECK constraints |

## Scope

**In scope:**
- `sqlmodel`, `alembic`, `asyncpg` dependencies
- `backend/app/db/connector.py` — engine, session factory, `get_session` dependency
- FastAPI async lifespan in `main.py`
- Four SQLModel models: `User`, `UserPreferences`, `MedicationRegistry`, `CabinetEntry`
- New domain stubs: `cabinet/`, `users/` (empty routers, service, crud)
- Alembic init + `env.py` async config + initial migration
- Hand-edited migration additions: tsvector generated column + GIN index, CHECK constraints
- `backend/tests/` smoke test

**Out of scope:**
- Auth routes, JWT validation, supabase Python library (F-01)
- Registry import script (F-03)
- `dismissed_notifications` table (S-06)
- Any CRUD operations or API endpoints
- Row Level Security policies

## Architecture / Approach

All DB access flows through `backend/app/db/connector.py`. Each request gets an `AsyncSession` via FastAPI's `Depends(get_session)` injected into route handlers. SQLModel models live in `backend/app/v1/<domain>/models.py` per AGENTS.md convention. Alembic owns schema migrations; SQLModel metadata is the source of truth for autogenerate. The `search_vector` tsvector column is a PostgreSQL generated column — invisible to SQLModel, added via raw SQL in the migration.

## Phases at a Glance

| Phase | What it delivers | Key risk |
|---|---|---|
| 1. Dependencies + DB connector | Engine, session factory, lifespan wired | `DATABASE_URL` scheme must be `postgresql+asyncpg://` |
| 2. SQLModel models + domain stubs | All four table models defined; cabinet/ and users/ scaffolded | FK relationships must be consistent across all four models |
| 3. Alembic + first migration | Migration applies and rolls back cleanly; GIN index in place | Async env.py pattern required — default sync template fails with asyncpg |
| 4. Smoke test | Live DB session confirmed via pytest | Requires real `DATABASE_URL` — no test DB mock |

**Prerequisites:** Supabase project created with PostgreSQL enabled; `DATABASE_URL` available as an env var.
**Estimated effort:** ~1 session across 4 phases.

## Open Risks & Assumptions

- `DATABASE_URL` must be set before Phase 3 and 4 can be verified — local `.env` file required (never committed; AGENTS.md hard rule). Use the Supabase **direct** connection (port 5432) for Alembic migrations; the transaction pooler (6543) breaks asyncpg prepared statements unless `statement_cache_size=0` is set on the runtime engine.
- Alembic autogenerate may miss some SQLModel relationship declarations; migration must be visually reviewed before running `upgrade head`
- tsvector `GENERATED ALWAYS AS` syntax requires PostgreSQL 12+ — Supabase free tier runs PostgreSQL 15, so this is safe

## Success Criteria (Summary)

- `uv run alembic upgrade head` applies cleanly and all four tables appear in Supabase dashboard
- GIN index on `medication_registry.search_vector` is in place
- `uv run pytest backend/tests/test_db.py -v` passes against the live Supabase DB

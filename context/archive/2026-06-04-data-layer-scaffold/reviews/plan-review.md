<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Data Layer Scaffold

- **Plan**: `context/changes/data-layer-scaffold/plan.md`
- **Mode**: Deep
- **Date**: 2026-06-04
- **Verdict**: REVISE → SOUND (after triage)
- **Findings**: 2 critical · 2 warnings · 1 observation (all fixed)

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | WARNING |
| Architectural Fitness | PASS |
| Blind Spots | WARNING |
| Plan Completeness | FAIL |

## Grounding

3/3 existing paths ✓ (`pyproject.toml`, `main.py`, `v1/router.py`), 4/4 new paths correctly absent ✓ (`cabinet/`, `users/`, `db/`, `tests/`), brief↔plan ✓. `lessons.md` and `contract-surfaces.md` not present — those checks skipped.

## Findings

### F1 — Migration SQL references table names the models won't produce

- **Severity**: ❌ CRITICAL
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Plan Completeness
- **Location**: Phase 2 (models) + Phase 3 (hand-edited migration SQL)
- **Detail**: No model set `__tablename__`, so SQLModel would produce `medicationregistry`/`cabinetentry`/`userpreferences`/`user` (lowercased class name, no snake_casing or pluralization). The Phase 3 hand-edited SQL, FK strings, and GIN index all assumed `medication_registry`/`cabinet_entries`/`user_preferences`/`users`, so the ALTER TABLE / CREATE INDEX statements and FK resolution would fail. Secondary: `user` is a PostgreSQL reserved word. The plan's own Phase 3 manual check mixed both conventions.
- **Fix**: Set explicit `__tablename__` on every model to snake_case plural names; align the Phase 3 manual-verification bullet; add a Critical Implementation Details note.
- **Decision**: FIXED (Fix in plan)

### F2 — Phase 1 Manual criterion missing from Progress section

- **Severity**: ❌ CRITICAL (mechanical Progress contract)
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 1 Manual Verification ↔ Progress § Phase 1
- **Detail**: Phase 1 Manual Verification had two bullets (connector.py exists + main.py references the lifespan) but Progress listed only 1.4 (connector.py). Every Success Criteria bullet must map to a Progress checkbox.
- **Fix**: Added `- [ ] 1.5 backend/app/main.py references the lifespan` under Progress § Phase 1 § Manual.
- **Decision**: FIXED (Fix in plan)

### F3 — init_db() create_all() collides with Alembic as authority

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Lean Execution
- **Location**: Phase 1 — DB connector (init_db)
- **Detail**: `init_db()` was specced to run `SQLModel.metadata.create_all` as a fallback. On a fresh DB this builds bare tables without the tsvector generated column, GIN index, and CHECK constraints, then Alembic collides with the already-existing tables — contradicting the plan's "Alembic is authoritative" decision and risking silent schema drift.
- **Fix**: Drop `create_all`; make `init_db()` a connectivity-check-only (`SELECT 1`).
- **Decision**: FIXED (Fix in plan)

### F4 — Supabase pooler + asyncpg prepared-statement gotcha unaddressed

- **Severity**: ⚠️ WARNING
- **Impact**: 🔬 HIGH — architectural stakes; think carefully before deciding
- **Dimension**: Blind Spots
- **Location**: Phase 1 (engine) + Phase 3 (alembic upgrade)
- **Detail**: Supabase exposes a direct endpoint (5432) and a transaction-mode pgbouncer pooler (6543). asyncpg uses server-side prepared statements by default, which the transaction pooler breaks; DDL migrations must not run through it. The plan noted only the URL scheme, not the endpoint choice or prepared-statement cache, so the implementer would likely hit this at `alembic upgrade head` or first query.
- **Fix A ⭐ Recommended**: Document endpoint split — direct (5432) for Alembic; runtime engine on pooler with `statement_cache_size=0` via `connect_args`. Added to Critical Implementation Details, connector contract, and Migration Notes.
  - Strength: Pre-empts the most common Supabase+asyncpg failure; cheap now, expensive to debug mid-build.
  - Tradeoff: Two URL shapes to manage (migrate vs runtime).
  - Confidence: HIGH — documented, frequently-hit incompatibility.
  - Blind spot: Exact Supabase pooler config for this project assumed standard.
- **Fix B**: Use the direct connection (5432) everywhere for MVP.
  - Strength: One URL; no workaround needed.
  - Tradeoff: Fewer connections; not the recommended serverless path.
  - Confidence: MED — adequate at this app's low qps.
  - Blind spot: Render free tier vs Supabase direct connection caps not measured.
- **Decision**: FIXED (Fix A)

### F5 — Alembic env-var URL won't interpolate from os.environ

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 3 — alembic.ini / env.py
- **Detail**: The contract set `sqlalchemy.url = %(DATABASE_URL)s` in alembic.ini, but configparser resolves `%(...)s` from config sections, NOT `os.environ` — raising `InterpolationMissingOptionError`. Same eager-read risk if the connector did `os.environ["DATABASE_URL"]` at import (KeyError contradicts the "starts without import errors" criterion).
- **Fix**: Resolved differently per user — introduce a Pydantic `BaseSettings` module (`backend/app/config.py`) as the single validated source of truth for `DATABASE_URL`, read from `.env`, imported by both the connector and Alembic `env.py`. `pydantic-settings` added as a dependency; `alembic.ini` no longer relies on configparser interpolation; `env.py` injects the URL via `config.set_main_option(...)`.
- **Decision**: FIXED (Fix differently — Pydantic BaseSettings)

## Triage Summary

- Fixed: F1, F2, F3, F4 (Fix A), F5 (Pydantic BaseSettings) — 5
- Skipped / Accepted / Dismissed: none
- Verdict after fixes: SOUND

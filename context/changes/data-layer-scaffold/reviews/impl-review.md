<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Data Layer Scaffold

- **Plan**: context/changes/data-layer-scaffold/plan.md
- **Scope**: Phases 1–4 of 4 (full plan)
- **Date**: 2026-06-04
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 2 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | WARNING |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

Automated checks re-run during review: `ruff check .` clean, `ruff format --check .` clean (36 files), all four models import. DB-dependent criteria (alembic upgrade/downgrade/idempotency, pytest smoke) verified by author with commit shas (33a9adc, 589d27c) and manual Supabase-dashboard checks; not independently re-run (no live DATABASE_URL in review env).

## Findings

### F1 — Redundant second migration `varchar_to_text`

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Scope Discipline
- **Location**: backend/migrations/versions/2c7067ce3f56_varchar_to_text.py
- **Detail**: Plan Phase 3 specified exactly one migration ("initial schema"). A second migration (committed in same commit 33a9adc) converts varchar→text, but the committed initial migration 0e56afa1e4b6 already creates every affected column as `sa.Text()` (git confirms it was never varchar in committed history). For a fresh DB this migration is a no-op type change that additionally DROPs and re-CREATEs the search_vector generated column and GIN index for no reason (lines 40-54), and makes history misleading.
- **Fix A ⭐ Recommended**: Keep it — do not edit/squash applied migrations.
  - Strength: If 0e56afa1e4b6 was applied to the shared Supabase DB as varchar before the committed version was cleaned to Text, this migration is what fixed that DB; removing it would desync prod from the chain. Migrations are append-only once applied.
  - Tradeoff: Leaves a confusing, mostly-redundant step + needless index rebuild on fresh upgrades.
  - Confidence: MED — depends on whether already applied to a shared DB; Progress shows upgrade/downgrade ran green.
  - Blind spot: Live Supabase migration state not visible.
- **Fix B**: Squash into the initial migration and delete this file.
  - Strength: Clean single-migration chain matching the plan; no wasted index rebuild on fresh installs.
  - Tradeoff: Only safe if NO shared DB has applied 2c7067ce3f56; otherwise breaks `alembic upgrade` there.
  - Confidence: LOW — requires confirming nothing has it applied.
  - Blind spot: Same — live DB state unknown.
- **Decision**: FIXED via Fix A + comment — live DB confirmed stamped at 2c7067ce3f56 (tables recreated through it), so migration is append-only/load-bearing. Kept as-is and added a header NOTE in 2c7067ce3f56 explaining why it exists and must not be squashed.

### F2 — Cabinet unique constraint lives only in the migration, not the model

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Pattern Consistency
- **Location**: backend/app/api/v1/cabinet/models.py:8
- **Detail**: Plan's CabinetEntry contract lists the unique constraint on (user_id, medication_registry_id, expiry_date) — the FR-010 dedup key. It is in the migration (uq_cabinet_entries_user_med_expiry, initial migration lines 100-105) but the SQLModel class has no `__table_args__` declaring it. Since env.py sets `target_metadata = SQLModel.metadata`, the next `alembic revision --autogenerate` (F-03/S-01) will see the model lacks the constraint and emit a spurious DROP CONSTRAINT. The tsvector column and CHECK constraints are correctly migration-only (autogenerate doesn't detect them); unique constraints ARE detected — that's the asymmetry. UserPreferences handles uniqueness correctly via Field(unique=True).
- **Fix**: Add to CabinetEntry: `__table_args__ = (UniqueConstraint("user_id", "medication_registry_id", "expiry_date", name="uq_cabinet_entries_user_med_expiry"),)` so model metadata matches the DB and autogenerate stays stable.
- **Decision**: FIXED — added `__table_args__` with `sa.UniqueConstraint(...)` to CabinetEntry. Verified: ruff check + format clean; constraint now present in `CabinetEntry.__table__.constraints`.

### F3 — Engine omits asyncpg pooler guard (statement_cache_size=0)

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality (reliability)
- **Location**: backend/app/db/connector.py:13
- **Detail**: Plan flagged that Supabase's transaction pooler (port 6543) breaks asyncpg server-side prepared statements and made `connect_args={"statement_cache_size": 0}` conditional on using the pooler. The engine omits it. .env.structure ships DATABASE_URL= empty, so the runtime endpoint is unknown. If runtime points at the pooler, the app fails with DuplicatePreparedStatementError; if it uses the direct connection (5432), this is correct as-is.
- **Fix**: If/when the runtime URL uses the 6543 pooler, add `connect_args={"statement_cache_size": 0}` to create_async_engine.
- **Decision**: FIXED — added a conditional guard: `statement_cache_size=0` is applied via `connect_args` only when `:6543` is in the URL (pooler), leaving direct 5432 connections untouched. ruff check + format clean.

### F4 — Plan paths (app/v1, app/config.py) don't match implementation

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: context/changes/data-layer-scaffold/plan.md (throughout)
- **Detail**: Plan references app/v1/<domain>/, app/config.py, and imports from app.config. Implementation correctly uses app/api/v1/, app/core/config.py, and app.core.config — matching AGENTS.md (authoritative structure). The CODE is right; the PLAN is stale. Old app/v1/ tree and app/config.py were cleanly removed (verified — no stray files). Flagged only so the plan isn't trusted verbatim by a later reader.
- **Fix**: Optional — note in plan that paths were superseded by the AGENTS.md app/api/v1 layout. Code requires no change.
- **Decision**: FIXED (addendum only) — added a dated addendum block at the top of plan.md mapping stale paths (app/v1 → app/api/v1, app/config.py → app/core/config.py) to the AGENTS.md layout and noting the code is authoritative. No code change; no full plan rewrite.

<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Notifications and Badges (S-06)

- **Plan**: context/changes/notifications-and-badges/plan.md
- **Scope**: Phase 1 of 7
- **Date**: 2026-07-07
- **Verdict**: APPROVED
- **Findings**: 0 critical, 0 warnings, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

## What Was Verified

- **Model** (`backend/app/api/v1/notifications/models.py`) matches the plan contract field-for-field: `id` (uuid pk, `default_factory=uuid4`), `user_id` FK to `users.id`, `cabinet_entry_id` FK to `cabinet_entries.id` with `ondelete="CASCADE"`, `trigger_type` as `sa.Text`, tz-aware `dismissed_at`, and the `uq_dismissed_user_entry_trigger` unique constraint on `(user_id, cabinet_entry_id, trigger_type)`. Mirrors `CabinetEntry` style; the verbose `sa_column` on `cabinet_entry_id` is required because SQLModel's `foreign_key=` shorthand can't express `ondelete`.
- **Migration** (`backend/migrations/versions/7726318333b6_add_dismissed_notifications.py`): `create_table` with both FKs (cascade on entry, plain on user), the unique constraint, and a downgrade dropping the table. Revision chain is linear and single-headed (`…dc9619b00abd → 7726318333b6`). Column style (`sa.Uuid()`, `sa.DateTime(timezone=True)`) matches the initial schema migration.
- **Automated criteria**: model imports OK; `ruff check` and `ruff format --check` both pass (re-run at review time). Migration apply/rollback (1.3) and the Supabase table check (1.4) require the DB via native PowerShell per L-001 — not independently re-run here; marked done in Progress and 1.4 confirmed manually.
- **Scope**: only the two planned source files plus change.md/plan.md progress stamps. No creep.

## Findings

### F1 — Cascade FK column `cabinet_entry_id` has no index

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency / Performance
- **Location**: backend/migrations/versions/7726318333b6_add_dismissed_notifications.py:29
- **Detail**: `cabinet_entry_id` carries `ON DELETE CASCADE` but has no standalone index. The unique constraint `(user_id, cabinet_entry_id, trigger_type)` indexes `user_id` as its leftmost column (covering `get_dismissals` / `delete_by_user`) but not `cabinet_entry_id`, which is not the leftmost prefix. Postgres does not auto-index the referencing side of an FK, so an entry-delete's cascade `DELETE ... WHERE cabinet_entry_id = ?` can fall back to a sequential scan — the classic "unindexed FK → slow cascade" footgun. Not a defect for this phase: consistent with the existing project convention (`cabinet_entries.user_id` and `medication_registry_id` are likewise unindexed), and the plan's Performance Considerations explicitly scope this to small per-user data volume. Flagged only as a known trade-off if scale grows.
- **Fix**: (optional) add `sa.Index` on `cabinet_entry_id` in this migration + `index=True` on the model field. Skip to stay consistent with the current no-FK-index convention.
- **Decision**: FIXED — added `index=True` on the `cabinet_entry_id` column and `op.create_index`/`op.drop_index` (`ix_dismissed_notifications_cabinet_entry_id`) in the migration. `ruff check` + `ruff format --check` pass.

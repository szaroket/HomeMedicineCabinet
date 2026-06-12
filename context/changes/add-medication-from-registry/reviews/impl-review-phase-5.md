<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Add Medication from Registry (S-01)

- **Plan**: context/changes/add-medication-from-registry/plan.md
- **Scope**: Phase 5 of 6
- **Date**: 2026-06-12
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 2 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | WARNING |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

Automated verification re-run during review: `ruff check` + `ruff format --check` clean; `pytest` 192 passed (DB-backed `tests/db` excluded per L-001).

**Triage outcome (2026-06-12):** all 4 findings FIXED — F1 (Fix A, tz-aware columns across cabinet + users), F2 (UTC `today`), F3 (plan addendum), F4 (warning log on NULL capacity). Re-verified after fixes: ruff clean, 192 passed.

## Findings

### F1 — Naive UTC written into a timestamptz column (+ users domain left inconsistent)

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality (data correctness)
- **Location**: backend/app/api/v1/cabinet/models.py:32-40
- **Detail**: The migration defines `cabinet_entries.created_at`/`updated_at` as `sa.DateTime(timezone=True)` (timestamptz — `0e56afa1e4b6_initial_schema.py:95-96`). This phase changed the model defaults from tz-aware `datetime.now(timezone.utc)` to NAIVE `datetime.now(timezone.utc).replace(tzinfo=None)`. Writing a naive datetime into a timestamptz column makes the stored instant depend on the DB session TimeZone setting rather than being unambiguous UTC; the prior tz-aware value was correct. Likely root cause: the SQLModel fields never declare the column as timezone-aware, so ORM/DB types disagree and the coercion papers over the symptom. The same timestamptz columns on `users`/`user_preferences` (users/models.py) were NOT changed and still store tz-aware — the two domains now disagree. Unrelated to phase 5's GET endpoint and unverified by phase 5's success criteria (which never read these columns). Committed as a "timezone bug fix" but points the wrong way for a timestamptz column.
- **Fix A ⭐ Recommended**: Fix at the source — declare the model timestamp columns as tz-aware (`sa_column`/`sa_type=DateTime(timezone=True)`) and revert to tz-aware `datetime.now(timezone.utc)` values, consistently across cabinet + users.
  - Strength: Addresses the ORM/DB type mismatch directly; stored instants stay unambiguous UTC; one consistent rule across domains; matches the F4 "DB is UTC" policy.
  - Tradeoff: Slightly more code on each timestamp field.
  - Confidence: HIGH — matches the timestamptz schema and F4 policy.
  - Blind spot: Original error the naive coercion was meant to fix is unreproduced; confirm it disappears.
- **Fix B**: If naive-write is intentional, apply it to `users`/`user_preferences` too and document why in a model comment.
  - Strength: Restores cross-domain consistency with minimal churn.
  - Tradeoff: Keeps ambiguous-instant behavior on a timestamptz column; fragile if the DB session TZ ever differs from UTC.
  - Confidence: MEDIUM — depends on the unconfirmed original error.
  - Blind spot: Why naive was needed at all is undocumented.
- **Decision**: FIXED via Fix A — declared sa_type=DateTime(timezone=True) + tz-aware UTC values on cabinet_entries and users/user_preferences timestamps. Root cause confirmed by user's asyncpg DataError ($14::TIMESTAMP WITHOUT TIME ZONE): all 3 tables are timestamptz in migration 0e56afa1e4b6 but no model declared timezone=True.

### F2 — Status uses local `date.today()`, contradicting the F4 UTC policy

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: backend/app/api/v1/cabinet/service.py:164
- **Detail**: `list_entries` computes `today = date.today()` to feed `classify_status`. The plan's Critical Implementation Details / F4 timezone policy states "today is the UTC date ... status is computed UTC-relative". `date.today()` returns the server's LOCAL date, not the UTC date — on a non-UTC host the valid/expiring/expired boundary shifts by a day. This is the first read path that computes status, so it sets the precedent.
- **Fix**: Use `datetime.now(timezone.utc).date()` instead of `date.today()`.
- **Decision**: FIXED — replaced `date.today()` with `datetime.now(timezone.utc).date()` in `list_entries` (service.py).

### F3 — Large unplanned cross-domain refactor in a "list endpoint" phase

- **Severity**: ⚠️ WARNING (benign / justified)
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: backend/app/api/v1/cabinet/facade.py (new), backend/app/api/v1/users/{crud,service}.py (new), backend/app/utilities/const.py (new), AGENTS.md
- **Detail**: Phase 5 was scoped as `crud.list_entries` + service + route. It also added `facade.py`, extracted `get_user_preferences` into a new `users` domain, added `const.py`, a `UserError`/`UserDatabaseError` taxonomy, and amended AGENTS.md. Real scope creep — but it correctly satisfies the standing facade rule (cross-domain calls go through `facade.py`, not service→other-domain), the cabinet→users preference lookup genuinely needed it, AGENTS.md was updated to formalize the layer, and tests were added for the moved code. Net architecture improvement; flagged only so the scope expansion is acknowledged.
- **Fix**: No code change. Optionally add a one-line addendum to the plan's Phase 5 noting the facade + users-domain extraction landed here.
- **Decision**: FIXED — added a Phase 5 impl addendum to plan.md documenting the facade + users-domain extraction.

### F4 — Read path silently tolerates NULL capacity; write path raises

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/app/api/v1/cabinet/service.py:169-173
- **Detail**: In `list_entries`, a tablet-based variant with NULL capacity yields `tpp=None` → `total_tablets=None`, silently. The phase-4 write path raises `CabinetInvariantError` (→500) on the same invariant violation. The divergence is arguably fine for a read (don't fail the whole list for one bad row), but it's an undocumented inconsistency.
- **Fix**: Either log a warning when a tablet-based row has NULL capacity in the list path, or accept the divergence with a brief comment.
- **Decision**: FIXED — `list_entries` now emits a `logger.warning` (with a clarifying comment) when a tablet-based row has NULL capacity, while still serving the row.

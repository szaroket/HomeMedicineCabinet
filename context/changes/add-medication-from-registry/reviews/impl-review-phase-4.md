<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Add Medication from Registry (S-01)

- **Plan**: context/changes/add-medication-from-registry/plan.md
- **Scope**: Phase 4 of 6 — `POST /api/v1/cabinet/entries` (add with FR-010 merge)
- **Date**: 2026-06-10
- **Verdict**: REJECTED
- **Findings**: 1 critical, 3 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | WARNING |
| Safety & Quality | FAIL |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

Automated gates verified: `ruff check` clean, `ruff format --check` clean, 187 unit tests pass (the lone stalled test is `tests/db/test_connection.py`, a real-DB test that requires PowerShell per L-001 — not a Phase 4 file).

## Findings

### F1 — F2 concurrent-add race guard is dead code; race returns 503, not merge

- **Severity**: ❌ CRITICAL
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/app/api/v1/cabinet/crud.py:148; backend/app/api/v1/cabinet/service.py:277
- **Detail**: The plan's F2 requirement is: on a duplicate-key IntegrityError from a concurrent POST, roll back, re-read, and merge → return `merged=true`. `_insert_with_race_guard` (service.py:277) does `except IntegrityError: return None` to trigger the merge fallthrough. But `crud.insert_entry` (crud.py:148) catches `except SQLAlchemyError` and re-raises `CabinetDatabaseError`. `IntegrityError` is a subclass of `SQLAlchemyError`, so the duplicate-key error is converted inside crud before the service ever sees it. The `except IntegrityError` branch and the merge-fallthrough at service.py:336-344 are unreachable; a real two-POST race returns 503 instead of merging. Compounding: the test `test_integrity_error_falls_through_to_merge` (test_service.py) mocks `crud.insert_entry` to raise IntegrityError directly, bypassing the real wrapper — so it passes green while the production path is broken (false confidence). This is defense-in-depth behind the Phase 6 frontend submit guard, so real-world hit rate is low, but it's an explicit plan requirement that silently doesn't work.
- **Fix**: In `insert_entry`, add `except IntegrityError: raise` *before* the `except SQLAlchemyError` block so the duplicate-key error propagates untouched to the service-layer race guard. Then add a service test that calls the real `insert_entry` (mock only the session/persist) so the conversion path is actually exercised.
  - Strength: Minimal, localized to one crud function; restores the documented merge-on-race contract; no cross-domain ripple (medicines/crud has no equivalent race).
  - Tradeoff: Slightly widens crud's exception surface (one error type now escapes the SQLAlchemyError funnel by design).
  - Confidence: HIGH — exception subclassing confirmed by reading both handlers; `persist()` already rolls back on any exception so the session is clean for the re-read.
  - Blind spot: Haven't run a live two-request race (needs PowerShell/DB per L-001); asyncpg post-rollback re-read should be fine but is unverified against a real connection.
- **Decision**: PENDING

### F2 — `updated_at` never bumped on FR-010 merge-update

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/api/v1/cabinet/crud.py:174-183; backend/app/api/v1/cabinet/models.py:35-37
- **Detail**: `update_entry_counts` mutates package_count/partial_tablet_count but never touches `updated_at`. The model sets `updated_at` only via `default_factory` at construction, with no `onupdate`, and the DB column has no server-side default/trigger. After a merge, `updated_at` still shows creation time. Nothing in this slice consumes `updated_at` yet, so impact is latent — but any future audit/sync/"recently changed" logic will be wrong, and a merge is exactly the event you'd want timestamped.
- **Fix**: Set `entry.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)` in `update_entry_counts`, or add `sa_column_kwargs={"onupdate": ...}` to the column so every UPDATE bumps it.
- **Decision**: PENDING

### F3 — Unplanned: tz-naive datetime written into a TIMESTAMPTZ column

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality / Pattern Consistency
- **Location**: backend/app/api/v1/cabinet/models.py:32-37
- **Detail**: Unplanned change: created_at/updated_at now use `datetime.now(timezone.utc).replace(tzinfo=None)` (timezone-naive) while the column is `DateTime(timezone=True)` (Postgres TIMESTAMPTZ, migration 0e56afa1e4b6). This is NOT a column-type fix (the column was already tz-aware); most likely added to dodge a naive-vs-aware comparison TypeError during manual testing. Postgres accepts the naive value (interprets it in session TZ), so it works — but it's a UTC-correctness smell and is inconsistent with the sibling `users` models, which store aware UTC into the same column type. The project is already split (auth/crud also uses naive), so this is a "pick one" decision.
- **Fix A ⭐ Recommended**: Store aware UTC — drop `.replace(tzinfo=None)` so it matches the TIMESTAMPTZ column and the users models.
  - Strength: Aligns value with column type and the stated "backend/DB operate entirely in UTC" policy; removes drift risk if the DB session TZ ever differs from UTC.
  - Tradeoff: Must confirm the original naive/aware TypeError doesn't resurface elsewhere (likely a comparison that should also be made aware).
  - Confidence: MED — fixes the smell, but the exact bug the naive change papered over isn't documented.
  - Blind spot: Why naive was introduced isn't recorded; reverting blind could reintroduce that error.
- **Fix B**: Keep naive, but make it a documented project-wide convention and align the `users` models to match.
  - Strength: Internally consistent; least churn to working code.
  - Tradeoff: Entrenches naive-UTC against a TIMESTAMPTZ column — the weaker convention; relies on DB session TZ always = UTC.
  - Confidence: MED.
  - Blind spot: Supabase session TZ assumption unverified.
- **Decision**: PENDING

### F4 — POST response drops `status`; diverges from the plan's contract

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: backend/app/api/v1/cabinet/schemas.py (AddEntryOut vs CabinetEntryOut)
- **Detail**: The plan (lines 244, 283) specifies the add result's entry carries `status: str`. The implementation returns a new `AddEntryOut` that omits status (docstring: callers should read GET /cabinet/entries), leaving `CabinetEntryOut` (which has status) defined but unused by this endpoint. Defensible — status is date-derived and arguably better read fresh — but it contradicts the written contract, and get_user_preferences/classify_status are imported but never called in the add path.
- **Fix A ⭐ Recommended**: Document the deviation as a plan addendum (POST intentionally omits status; status is served by GET).
  - Strength: Preserves a reasonable design choice; keeps the plan truthful before Phase 5/6 build on it.
  - Tradeoff: Plan becomes a slightly moving target.
  - Confidence: HIGH — matches how Phase 3 recorded its own addenda.
  - Blind spot: Phase 6 frontend must not rely on status from the add response.
- **Fix B**: Honor the contract — return CabinetEntryOut with computed status.
  - Strength: No plan drift; one round-trip gives the client everything.
  - Tradeoff: Re-introduces the preferences fetch + classify on the write path that the impl deliberately removed.
  - Confidence: HIGH.
  - Blind spot: None significant.
- **Decision**: PENDING

### F5 — `tpp` NULL-capacity invariant is a 500 domain-error path

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: backend/app/api/v1/cabinet/service.py (_validate_and_get_tpp) + new CabinetInvariantError in errors.py
- **Detail**: The plan called for `tpp = int(capacity)` guarded by a "cheap assert/log (NOT a domain-error path)". The impl instead raises a typed `CabinetInvariantError` → 500. Arguably better (loud, mapped, testable) but contradicts the explicit instruction. No action needed beyond acknowledging; the typed error is the stronger choice.
- **Fix**: Accept as-is (improvement over the plan), optionally note the deviation in the plan.
- **Decision**: PENDING

### F6 — Minor mock-spec gaps in new tests

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/tests/cabinet/test_crud.py:120,138,151,176,190; backend/tests/db/test_connector.py:11
- **Detail**: `patch("...persist")` calls omit `autospec=True`, and test_connector's `_make_session()` returns a bare `AsyncMock()` with no `spec=`. Project rule: always pass spec=/autospec=. (The landed test_crud/test_router/test_connector are legitimate pure-unit tests with mocked sessions — they do NOT hit a DB, so the "no integration tests" guardrail is respected.)
- **Fix**: Add `autospec=True` to the persist patches; `spec=AsyncSession` to the connector test's mock session.
- **Decision**: PENDING

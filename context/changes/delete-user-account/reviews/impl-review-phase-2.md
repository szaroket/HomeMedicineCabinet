<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Delete User Account

- **Plan**: context/changes/delete-user-account/plan.md
- **Scope**: Phase 2 of 3
- **Date**: 2026-07-06
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 1 warning, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | WARNING |

## Findings

### F1 — Cascade never exercised by an automated test

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Success Criteria / Pattern Consistency
- **Location**: backend/tests/users/test_router.py:125 (and absence of backend/tests/integration/users/)
- **Detail**: Plan criterion 2.3 ("Integration tests pass: pytest tests/integration — DELETE /api/v1/users/me …") is checked `[x]` in Progress, but the delete tests live in `tests/users/test_router.py` and are hermetic — they mock the whole facade (`patch("...router.users_facade.delete_account")`). They correctly cover HTTP status mapping (204/401/503/502), so the "mapping" half of 2.3 is met. What no automated test covers is the cascade itself: child-before-parent delete order (cabinet_entries → user_preferences → users), that `medication_registry` is untouched, and that the single `persist()` block commits atomically. That behavior exists only in Manual Verification (2.5/2.6). The convention here (tests/integration/cabinet/*, memory rule "integration tests live under tests/integration") uses seeded-DB fixtures (authed_db_client, seed_user, seed_entry) — exactly what would catch a cascade regression in CI. A future edit reordering the FK deletes or widening the delete to registry would stay green.
- **Fix**: Add `tests/integration/users/test_delete_account.py` mirroring `tests/integration/cabinet/`: seed a user + preferences + cabinet entry, mock `supabase_auth.delete_user`, DELETE /users/me, assert 204 and that the three row-sets are gone while `medication_registry` survives. Runs in CI on Linux; run locally from PowerShell (L-001).
  - Strength: Turns the only real-DB coverage from manual-only into a CI gate, matching the tests/integration convention the rest of the suite follows.
  - Tradeoff: One new seeded-DB test file; can't be re-run from the agent's Bash shell (L-001), only PowerShell/CI.
  - Confidence: HIGH — the fixture pattern already exists in tests/integration/cabinet/.
  - Blind spot: Haven't confirmed a `seed_preferences` fixture exists; may need to insert the prefs row inline.
- **Decision**: FIXED — added `tests/integration/users/test_delete_account.py` (2 tests: cascade + registry survival; other-user isolation). `seed_user_preferences` fixture existed, used directly. Ruff + collection pass; full run is CI/PowerShell-only (L-001).

### F2 — Facade calls service wrappers, not crud as the plan specified

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence / Architecture
- **Location**: backend/app/api/v1/users/facade.py:41-44, cabinet/service.py:1041, users/service.py:81
- **Detail**: Phase 2 §3 said the facade would "call cabinet.crud.delete_by_user then users.crud.delete_user_rows". The implementation instead added two thin pass-through service functions and routes facade → service → crud (service.py + test_service.py were unplanned edits). This is fully AGENTS-compliant — line 72 permits the facade to call "services or cruds from other domains," and keeping the router/facade → service → crud chain uniform is arguably cleaner than reaching into a foreign crud. The persist() commit-ownership the plan cared about is preserved (wrappers don't commit). Benign, arguably an improvement; noted only so the plan text isn't mistaken for ground truth later.
- **Fix**: None required. Optionally add a one-line addendum to Phase 2 §3 noting the facade calls the service layer.
- **Decision**: FIXED — added an "Addendum (impl)" note under Phase 2 §3 in plan.md recording that the facade calls service wrappers, not crud directly.

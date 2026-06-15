<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Auth Scaffold (F-01)

- **Plan**: context/changes/auth-scaffold/plan.md
- **Mode**: Deep
- **Date**: 2026-06-05
- **Verdict**: REVISE → SOUND (all 3 findings fixed in plan, 2026-06-05)
- **Findings**: 0 critical · 2 warnings · 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | WARNING |
| Plan Completeness | WARNING |

## Grounding

5/5 paths ✓, 3/3 symbols ✓ (users.id = uuid4 default in `users/models.py:11`; CORS missing `allow_credentials` in `main.py:30`; no `@/` alias in `vite.config.ts`/`tsconfig.app.json` — all confirmed), brief↔plan ✓. ⚠ 1 flag: `backend/tests/conftest.py` already exists (plan labels it "new" — see F1). Progress block well-formed (4 phases match, all Success-Criteria bullets mapped to `- [ ] N.M` items).

## Findings

### F1 — Auth tests have no DB-isolation strategy (hits live Supabase + L-001 abort)

- **Severity**: ⚠️ WARNING
- **Impact**: 🔬 HIGH — architectural stakes; think carefully before deciding
- **Dimension**: Blind Spots
- **Location**: Phase 2 §5 (Tests) + Success Criteria "uv run pytest"
- **Detail**: The plan mocks the Supabase client but says nothing about the DB session. `register`/`login` call `provision_user(session, …)`, which writes `users` + `user_preferences` through the app's real `get_session` → live Supabase Postgres. Consequences: (1) tests aren't hermetic — they need a live `DATABASE_URL` and mutate real rows; the `ON CONFLICT DO NOTHING` upsert hides re-run drift in "register provisions a row" assertions. (2) lessons.md **L-001**: any TLS DB connection hard-aborts under the agent's Bash tool (`OPENSSL_Uplink … no OPENSSL_Applink`), so the Phase 2 automated gate `uv run pytest` cannot be run by the agent — it aborts during collection — and must be handed to PowerShell. The "pause after automated verification passes" note assumes a gate the agent can't execute. Also: `backend/tests/conftest.py` already exists (with a live-DB `db_session` fixture); the plan marks it "(new)" and would clobber it — it should extend it.
- **Fix A ⭐ Recommended**: Override `get_session` in tests (mock / in-memory), keep the suite hermetic
  - Strength: `app.dependency_overrides[get_session]` with an AsyncMock makes guard + endpoint tests pure — they run from the Bash tool, no live DB, no L-001 abort. Matches "without hitting real Supabase" intent and the existing JWKS monkeypatch approach.
  - Tradeoff: provisioning SQL (`ON CONFLICT`) isn't exercised against real Postgres — that moves to the Phase 2 manual gate, which already verifies rows in the Supabase editor.
  - Confidence: HIGH — `dependency_overrides` is the standard FastAPI test seam; conftest already uses fixtures.
  - Blind spot: aiosqlite won't honor PG-specific `ON CONFLICT` syntax — prefer mocking the session/crud over SQLite.
- **Fix B**: Keep live-DB tests, but move pytest off the agent to PowerShell
  - Strength: real provisioning SQL is exercised end-to-end.
  - Tradeoff: agent can't self-verify Phase 2 (must hand commands to the user per L-001); tests are stateful and need cleanup.
  - Confidence: MED — works, but contradicts the "mock the Supabase client" framing and slows the implement loop.
  - Blind spot: concurrent test runs against shared rows are flaky.
- **Decision**: FIXED via Fix A — plan Phase 2 §5 now overrides `get_session` (AsyncMock), keeps the suite hermetic, and extends (not clobbers) the existing `conftest.py`; provisioning SQL moved to the Phase 2 manual gate.

### F2 — Phase 1 guard verification targets a route that doesn't exist yet

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Plan Completeness
- **Location**: Phase 1 §6 + Manual Verification 1.4 / 1.5
- **Detail**: Phase 1 applies `dependencies=[Depends(get_current_user)]` to the medicines / cabinet / users routers — but all three are empty (`APIRouter(prefix=…)` with zero path operations; confirmed in code). FastAPI runs router-level dependencies only after a path matches, so a request to `/api/v1/medicines/` returns 404, not 401. The first route the guard actually protects is `GET /auth/me`, which lands in Phase 2. Result: the Phase 1 manual gates "invalid token → 401" (1.4) and "valid token passes" (1.5) are not testable at the Phase 1 boundary — the implementer hits 404 and either gets confused or marks a gate green that proved nothing.
- **Fix**: Reword the Phase 1 manual gate to state that no protected route exists yet, and move the real-route 401/200 check to Phase 2 (after `/auth/me`), relying on the monkeypatched guard unit test for Phase 1 confidence. (Alternatively, pull `/auth/me` into Phase 1 so there's a live guarded route to curl — heavier reorder.)
- **Decision**: FIXED via Fix — Phase 1 Manual Verification + Progress 1.4/1.5 reworded (no live guarded route yet; confidence from guard unit test); real-route 401/200 check added to Phase 2 Manual Verification + Progress 2.6.

### F3 — Access token in localStorage: XSS exposure not acknowledged

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 3 §4 (Auth store) + brief "Key Decisions"
- **Detail**: Storing the access JWT in localStorage is a deliberate, documented choice — but the plan pairs it with the security-careful httpOnly refresh-cookie design without noting that localStorage is readable by any injected script (XSS), which is exactly what httpOnly avoids for the refresh token. Worth one line so it's a known, accepted risk rather than an oversight.
- **Fix**: Add a one-line note: access token in localStorage is XSS-exposed; mitigated by short token lifetime + strict input handling; revisit (in-memory + silent refresh) if the threat model tightens.
- **Decision**: FIXED via Fix — added a "Security note (accepted risk)" line to the Phase 3 §4 Auth store contract.

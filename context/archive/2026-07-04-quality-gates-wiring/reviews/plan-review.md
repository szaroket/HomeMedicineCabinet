<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Quality-Gates Wiring Implementation Plan

- **Plan**: context/changes/quality-gates-wiring/plan.md
- **Mode**: Deep
- **Date**: 2026-07-04
- **Verdict**: REVISE → SOUND (after triage: all 4 findings fixed 2026-07-04)
- **Findings**: 0 critical, 2 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | WARNING |
| Architectural Fitness | PASS |
| Blind Spots | WARNING |
| Plan Completeness | WARNING |

## Grounding

8/8 paths ✓ (ci-cd.yml, playwright.config.ts, package.json, config.py,
tests/integration/conftest.py, integration README, AGENTS.md, test-plan.md),
5/5 symbols ✓ (`test:run` script present; `typecheck` script absent as the plan
claims; `testcontainers[postgres]` dep present in backend/pyproject.toml;
deploy.needs currently lists 5 jobs; e2e env refs E2E_TEST_PASSWORD /
E2E_DATABASE_URL confirmed in auth.setup.ts / cleanup-test-users.ts), brief↔plan ✓.

The plan's mechanical claims all check out against the code: Playwright's
`webServer` array boots both servers (playwright.config.ts:50-68); `Settings()`
requires database_url/supabase_url/supabase_anon_key at import (config.py:28-30);
integration conftest self-provisions `postgres:17-alpine` via testcontainers
(conftest.py:38-40); pre-commit does not run `tsc`; the e2e env-inheritance
reasoning is correct.

## Findings

### F1 — E2E job has no concurrency control against the shared Supabase account

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Phase 2 — E2E job wiring
- **Detail**: The plan triggers frontend-e2e on every PR *and* every push to main/develop, all runs sharing one confirmed account (e2e-hmc@example.com) in one shared Supabase project. The suite's only cleanup is `globalTeardown` (cleanup-test-users.ts:64), which runs `DELETE FROM cabinet_entries WHERE user_id = (account)` — deleting *all* of that account's rows, not just the current run's. seed.spec.ts "leans on the globalTeardown sweep alone" (e2e/CLAUDE.md), so two overlapping CI runs (push-to-main + an open PR, or two PRs) share state: run B's teardown can delete rows run A created, and run A's list/empty-state assertions can see run B's rows. The critical-path-e2e suite was designed for serial local runs; CI is exactly what introduces automatic concurrency. The brief attributes e2e flakiness only to live-DB latency, not cross-run interference — and `retries: 2` does not fix a data race.
- **Fix**: Add a `concurrency:` group to the frontend-e2e job (e.g. `group: e2e-shared-supabase`, `cancel-in-progress: false`) so runs serialize on the shared account instead of racing.
  - Strength: Removes the whole class of cross-run interference with one workflow-level key; matches the suite's actual (serial) design assumption.
  - Tradeoff: E2E runs no longer overlap; a second push waits. On a low-traffic single-maintainer repo this is invisible.
  - Confidence: MED — the race is real given globalTeardown's account-wide DELETE and seed.spec's teardown-only cleanup; whether it actually flakes depends on how tightly journey assertions scope their locators (unverified).
  - Blind spot: Did not trace every seed.spec assertion to confirm it filters to its own unique row vs. counting entries.
- **Decision**: FIXED (concurrency group added to Phase 2 §1 contract)

### F2 — "Eight jobs" is a miscount; the change produces nine gates

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Desired End State (l.58-62); Testing Strategy step 5 (l.370); Phase-2 manual verification 2.6
- **Detail**: deploy.needs currently lists 5 jobs (ci-cd.yml:185-190). Phase 1 §4 appends 3 (frontend-unit, frontend-typecheck, backend-integration) → 8. Phase 2 §4 appends frontend-e2e → 9. So the end state is *nine* gate jobs and nine deploy.needs entries, but the plan says "eight parallel gate jobs" and "all eight are listed in deploy.needs" throughout, and manual step 5 asks to "Confirm deploy.needs lists all eight gate jobs." An implementer verifying against "eight" will find nine and either distrust their work or remove a job. The per-phase contracts (which append specific named jobs) are individually correct — only the summary count is wrong.
- **Fix**: Replace "eight" with "nine" in Desired End State, Success Criteria, and manual verification step 5 (and 2.6's framing). 5 existing + frontend-unit + frontend-typecheck + backend-integration + frontend-e2e = 9.
- **Decision**: FIXED (5 references corrected: eight→nine ×4, "other seven"→"other eight")

### F3 — frontend-typecheck is scope beyond the Phase 4 mandate

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Lean Execution
- **Location**: Phase 1 §2; Phase 3 §1
- **Detail**: test-plan §3 Phase 4 and change.md scope this change to "the frontend-unit and e2e jobs." backend-integration is a defensible addition (README + §5 say it's excluded "until Phase 4," so Phase 4 is when it un-ignores). frontend-typecheck is weaker: a brand-new gate no upstream doc calls for, re-running the `tsc -b` already inside frontend-build (build = `tsc -b && vite build`, package.json:8). The plan pre-justifies it (discrete/faster gate symmetric with backend-typecheck) — a keep-or-drop call, not a defect. One consistency gap if kept: Phase 3 §1's doc edits flip the frontend-unit / e2e / integration rows in test-plan §5 to enforced but add no §5 gate row for frontend-typecheck, so "Docs reflect that CI now enforces these gates" would be incomplete.
- **Fix**: Decide keep-or-drop. If keeping, add a frontend-typecheck row to test-plan §5 in Phase 3 §1's contract. If dropping, remove the job + the package.json `typecheck` script from Phase 1 (and the count in F2 becomes eight).
- **Decision**: FIXED (kept; Phase 3 §1 contract now flips a `frontend typecheck` §5 row too — count stays nine)

### F4 — Phase 1 title differs between body and Progress

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 1 heading (l.112) vs Progress (l.400)
- **Detail**: Body heading is "## Phase 1: Secret-free CI jobs (frontend-unit, frontend-typecheck, backend-integration)"; the Progress subsection is "### Phase 1: Secret-free CI jobs". The N.M ↔ criteria mapping is otherwise complete and correct (all 12 Progress items match their verification bullets). Only the parenthetical suffix differs, which /10x-implement's phase-number match tolerates — flagged for exactness, not because it will fail to parse.
- **Fix**: Drop the parenthetical from the body heading (or append it to the Progress heading) so the two match verbatim.
- **Decision**: FIXED (parenthetical dropped from Phase 1 body heading)

<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Playwright Critical-Path E2E Bootstrap

- **Plan**: context/changes/critical-path-e2e/plan.md
- **Scope**: Phase 2 of 4
- **Date**: 2026-07-01
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 1 warning, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

Success-criteria notes: 2.2 (`npm run build`) and 2.3 (`npm run lint`) ran and
passed. 2.4 verified — `frontend/e2e/.auth/user.json` (1353 B) contains an
`auth_token` entry and is gitignored + untracked. 2.1
(`npx playwright test --project=setup`) was NOT re-run from the agent Bash tool
per L-001 (backend boot opens TLS to Supabase → `OPENSSL_Uplink` abort); the
populated `user.json` artifact is direct evidence the setup project ran.

## Findings

### F1 — register→login pivot breaks Phase 3/4 uniqueness & teardown assumptions

- **Severity**: ⚠️ WARNING
- **Impact**: 🔬 HIGH — architectural stakes; think carefully before deciding
- **Dimension**: Plan Adherence (cross-phase)
- **Location**: frontend/e2e/auth.setup.ts:32,50
- **Detail**: Phase 2 planned to REGISTER a brand-new throwaway user per run
  (timestamp-suffixed `e2e-<timestamp>@example.com`). The implementation instead
  LOGS IN a single fixed shared account (`e2e-hmc@example.com`, password from
  env). The pivot is well-justified and documented (Supabase email confirmation
  → `sign_up` returns no session, so a fresh registration can't authenticate).
  The problem is the blast radius wasn't propagated to later phases, which still
  assume the per-run-user model:
  - Phase 3 §"Per-run uniqueness" relies on "a new user_id every run" so
    `uq_cabinet_entries_user_med_expiry (user_id, med_id, expiry_date)` "can
    never collide," and on that basis DROPS per-run variation of medicine/expiry.
    With a fixed user_id this is false — two consecutive runs with the same
    medicine+expiry hit the constraint, threatening criteria 3.6 / 4.5.
  - Phase 4 teardown filters `e2e-*` emails and deletes the user row.
    `e2e-hmc@example.com` matches `e2e-*`, so a naive teardown deletes the one
    shared confirmed account — which can't be re-registered (email confirmation),
    breaking every subsequent run.
- **Fix A ⭐ Recommended**: Realign Phase 3 & Phase 4 plan sections to the
  fixed-account model — Phase 3 derives per-run uniqueness from a
  timestamp-suffixed `expiry_date` (or `package_count`), not user_id; Phase 4
  teardown deletes only `cabinet_entries` for the shared user_id, never the
  user / user_preferences / account rows.
  - Strength: Keeps the sound login decision; fixes the source of truth before
    Phase 3 is driven, so /10x-e2e doesn't inherit a broken uniqueness rationale.
  - Tradeoff: Plan edits to two not-yet-implemented phases.
  - Confidence: HIGH — the constraint columns and teardown filter are spelled out
    in the plan; the conflict is mechanical.
  - Blind spot: Haven't confirmed `expiry_date` alone gives enough variation
    headroom for very rapid (same-second) re-runs.
- **Fix B**: Restore per-run registration by giving test users a real session
  despite confirmation (admin-provision / disable confirmation on a test
  project).
  - Strength: Preserves the original per-run isolation model unchanged.
  - Tradeoff: Needs test-Supabase infra — collides with the plan's "NOT
    provisioning a dedicated test project" guardrail.
  - Confidence: MED — depends on Supabase admin access not yet set up.
  - Blind spot: Effort/infra cost not scoped anywhere in this change.
- **Decision**: FIXED via Fix A — realigned Phase 3 (uniqueness now from per-run
  `expiry_date`, not `user_id`) and Phase 4 (teardown deletes only the shared
  account's `cabinet_entries`, never the user/account rows), plus the top-level
  Desired End State and "What We're NOT Doing" isolation note.

### F2 — Stale config comment: "registers a throwaway user"

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence (doc accuracy)
- **Location**: frontend/playwright.config.ts:23
- **Detail**: The `setup` project comment says "registers a throwaway user and
  saves the session," but `auth.setup.ts` logs in a shared account.
  `auth.setup.ts`'s own docstring is correct; only this config comment is stale.
- **Fix**: Change the comment to "logs in the shared test account and saves the
  session to e2e/.auth/user.json".
- **Decision**: FIXED — updated the setup-project comment in playwright.config.ts:25.

## Positives

`auth.setup.ts` is a clean quality-lever exemplar: `getByLabel`/`getByRole`
locators, `waitForResponse` + explicit status assertion (fails fast on 401),
`waitForURL` + protected-element check, no `waitForTimeout`, password from env
(never committed), storageState gitignored and untracked.

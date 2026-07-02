<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Playwright Critical-Path E2E Bootstrap

- **Plan**: context/changes/critical-path-e2e/plan.md
- **Scope**: Phase 4 of 4 (Direct-DB Teardown Script)
- **Date**: 2026-07-02
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

## Notes

Verified: `npm run build` and `npm run lint` both pass (criteria 4.2, 4.3).
Criteria 4.1/4.4/4.5 (`npx playwright test` + post-run DB query) are DB-touching
and cannot be run from the agent's Bash tool per lessons.md L-001; marked done in
Progress at commit 88c64d5, to be re-confirmed from native PowerShell.

Plan deviations that are improvements (not findings):
- Config loads env via `loadEnv({ path: ['.env.local', '.env'] })` instead of the
  plan's `import 'dotenv/config'` — necessary, since the vars live in `.env.local`
  which the plan's form would not load.
- `globalTeardown` wired as a plain path string rather than `require.resolve(...)`;
  both valid, string is the more common idiom.

The `ssl: { rejectUnauthorized: false }` on the `pg` client is plan-sanctioned and
is NOT an L-001 violation — that lesson prohibits weakening SSL in the backend
`connector.py`/`migrations/env.py`, whereas this is a separate test-only Node
cleanup connection the plan explicitly permitted.

## Findings

### F1 — TEST_EMAIL default duplicated across two e2e files

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: frontend/e2e/teardown/cleanup-test-users.ts:32; frontend/e2e/auth.setup.ts:29
- **Detail**: Both files hardcode the same fallback default
  `process.env.E2E_TEST_EMAIL ?? "e2e-hmc@example.com"`. Runtime overrides stay in
  sync automatically (same env var name); the only risk is the literal default
  drifting if one file is edited without the other, which would make setup log in
  one account while teardown sweeps a different one, silently leaving rows behind.
  Low likelihood, low blast radius (Phase 3's per-run `expiry_date` uniqueness still
  prevents collisions), but a genuine two-places-to-edit hazard.
- **Fix**: Extract the shared `TEST_EMAIL` (env read + default) into a small
  `e2e/test-account.ts` module and import it in both files, so the default lives in
  exactly one place. Or accept as-is — the existing comment documents the coupling.
- **Decision**: FIXED — extracted shared `TEST_EMAIL` into `frontend/e2e/test-account.ts`, imported by both `auth.setup.ts` and `teardown/cleanup-test-users.ts`.

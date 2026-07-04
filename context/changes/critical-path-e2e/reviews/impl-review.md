<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Playwright Critical-Path E2E Bootstrap

- **Plan**: context/changes/critical-path-e2e/plan.md
- **Scope**: Full plan (Phases 1–4, all complete)
- **Date**: 2026-07-02
- **Verdict**: APPROVED
- **Findings**: 0 critical, 0 warnings, 2 observations

This full-plan sweep follows the four per-phase reviews
(`impl-review-phase-1..4.md`, all APPROVED). It confirms the phases compose
cleanly across boundaries and re-verifies the non-DB success criteria.

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS (1 minor note) |
| Success Criteria | PASS |

## Cross-phase verification

- **storageState safety** — `frontend/e2e/.auth/user.json` is gitignored (root
  `.gitignore` → `frontend/e2e/.auth/`) and not tracked; the captured
  `auth_token` never enters version control. `git check-ignore` confirms
  `user.json`, `playwright-report`, `test-results` all ignored.
- **No secrets committed** — `E2E_TEST_PASSWORD` / `E2E_DATABASE_URL` documented
  empty in `.env.structure`, read only at runtime; `TEST_EMAIL` default deduped
  into `test-account.ts` (phase-4 F1 fix, commit `ced13e1`).
- **Teardown blast radius** — `DELETE FROM cabinet_entries WHERE user_id =
  (SELECT id FROM users WHERE email = $1)` is exact-email-scoped and
  parameterized; a missing account yields NULL → matches nothing; cannot touch
  `users` / `auth.users`.
- **Success Criteria** — `npm run build` (tsc -b incl. e2e project reference)
  and `npm run lint` both exit 0 (re-run during this review; the 2 pre-existing
  React-Compiler warnings noted in the phase-3 review were fixed in `af8f8e1`).
  The `npx playwright test` criteria (1.5, 2.1, 3.1, 3.5–3.6, 4.1, 4.4–4.5) are
  DB-touching and cannot run from the agent's Git Bash tool per lessons.md
  L-001 — recorded `[x]` at their commits, driven through /10x-e2e, treated as
  verified-by-prior-run.

## Findings

### F1 — Playwright-artifact gitignore landed in root, not the planned frontend/.gitignore

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency / Plan Adherence
- **Location**: frontend/.gitignore (empty); .gitignore "Playwright E2E artifacts" block
- **Detail**: Phase 1 §4 planned to add `playwright-report/`, `test-results/`,
  `.playwright/` to `frontend/.gitignore`. Instead they were merged into the
  ROOT `.gitignore` (with `frontend/e2e/.auth/` correctly added there too). This
  is functionally correct — `git check-ignore` confirms all artifacts and the
  storageState token are ignored and untracked. The only residue is that
  `frontend/.gitignore` now exists as a 0-byte dead file and the plan's stated
  target diverged silently.
- **Fix**: Delete the empty `frontend/.gitignore`, or add a one-line addendum to
  the Phase 1 block noting the rules consolidated into root `.gitignore`. No
  behavior change either way.
- **Decision**: FIXED (no-op) — chose "delete the empty file"; on inspection
  `frontend/.gitignore` no longer exists (`ls` → No such file), so the desired
  end state already held. Re-confirmed root `.gitignore:225-229` carries the
  Playwright block and `git check-ignore` ignores `user.json` /
  `playwright-report` / `test-results`. No edit needed.

### F2 — Parallel-run uniqueness is latent-fragile in the seed exemplar

- **Severity**: 📝 OBSERVATION
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: frontend/playwright.config.ts:24 (fullyParallel); frontend/e2e/seed.spec.ts:77-81 (uniqueFutureExpiryIso)
- **Detail**: `fullyParallel: true` + a single shared fixed account (constant
  `user_id`) means the only isolation axis for `uq_cabinet_entries_user_med_expiry`
  is `Date.now() % 3650`. Today there is exactly one spec/one test, so nothing
  runs concurrently and there is no live risk. But seed.spec.ts is explicitly
  the exemplar future specs are modeled on (e2e/CLAUDE.md, "what you show is what
  you get"). Once a second cabinet-creating spec exists, two parallel workers
  hitting the same product within a same-millisecond bucket collide, and
  `retries: 0` locally means no self-heal. This is phase-3's F3 accepted risk
  extended into the parallelism dimension — flagged now because the exemplar
  propagates the pattern.
- **Fix**: When the second cabinet-creating spec is added, fold worker/entropy
  into the offset (e.g. mix in `process.env.TEST_WORKER_INDEX` and/or
  `package_count`) so uniqueness doesn't ride on wall-clock alone. Not required
  while only the seed exists.
- **Decision**: FIXED — hardened the exemplar now (chose to fix ahead of the
  second spec). `uniqueFutureExpiryIso` gives each parallel worker a DISJOINT
  365-day band (`workerIndex * bandDays + Date.now() % bandDays`), so two workers
  in the same millisecond can never collide regardless of wall-clock; time still
  spreads re-runs within a band. Updated the function + its comment and the
  file-header cleanup rationale (seed.spec.ts). `npm run build` (tsc -b incl. e2e
  ref) and `npm run lint` re-run green.

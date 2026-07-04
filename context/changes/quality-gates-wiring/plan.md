# Quality-Gates Wiring Implementation Plan

## Overview

Close the remaining CI gaps in `.github/workflows/ci-cd.yml` (test-plan.md §3
Phase 4). Five gates already ship via F-04 (`2026-06-29-ci-cd-wiring`):
vulnerability-scan, pre-commit, backend unit tests, frontend build, and backend
type-check (pyright). This change wires in the jobs that are still missing or
stubbed:

1. **frontend-unit** — Vitest suite (landed in `frontend-data-seam-tests`); no CI job exists.
2. **frontend-typecheck** — a discrete `tsc -b` gate; today TypeScript is only checked implicitly inside `frontend-build`.
3. **backend-integration** — DB-backed testcontainers suite (`tests/integration/`), currently `--ignore`'d in CI "until test-plan Phase 4".
4. **frontend-e2e** — Playwright suite (landed in `critical-path-e2e`); the CI job is an `if: false` TODO stub that is also wired incorrectly.

All four new/fixed jobs are added to `deploy.needs` so they gate the release.

## Current State Analysis

- `.github/workflows/ci-cd.yml` has jobs: `vulnerability-scan`, `pre-commit`,
  `backend-tests` (runs `pytest --ignore=tests/db --ignore=tests/integration`),
  `frontend-build` (`npm run build` = `tsc -b && vite build`), `backend-typecheck`
  (pyright), a `frontend-e2e` stub (`if: false`, lines 146-179), and `deploy`
  (`needs`: the five real jobs; runs only on `release`).
- **The e2e stub is wrong, not merely disabled** (`ci-cd.yml:169-175`): it starts
  the backend and frontend manually with `&`, but `frontend/playwright.config.ts`
  already boots both via its `webServer` array. It also runs only `npm ci` — the
  webServer's `uv run uvicorn` (cwd `../backend`) needs backend deps installed via
  `uv sync`, which the stub never does.
- **E2E needs live infrastructure.** The backend boots for real, so `Settings`
  requires real `database_url`, `supabase_url`, `supabase_anon_key`
  (`backend/app/core/config.py:28-30`). `auth.setup.ts` logs a confirmed account
  in through the UI and needs `E2E_TEST_PASSWORD` (`e2e/auth.setup.ts:49`); the
  `globalTeardown` sweeps that account's rows via a direct `pg` connection and
  needs `E2E_DATABASE_URL` (`e2e/teardown/cleanup-test-users.ts:36`). The
  `critical-path-e2e` plan-brief already decided to **use the existing Supabase
  project** (swappable later via env), and the registry data the journey searches
  already lives there. `AUTH_COOKIE_SECURE=False` is already injected by the
  Playwright `webServer` env block.
- `VITE_API_URL` defaults to `http://localhost:8000` (`frontend/src/lib/api-client.ts:4`),
  so the Vite dev server needs no extra env in CI (backend is on :8000).
- **Backend integration** (`backend/tests/integration/`) uses **testcontainers**
  (`PostgresContainer("postgres:17-alpine")`, `conftest.py:38-40`). It provisions
  and tears down its own Postgres via Docker — so it needs the Docker daemon
  (present on `ubuntu-latest`) but **no** GitHub `services:` container and **no
  external secrets**. `Settings()` still instantiates at import, so placeholder
  `DATABASE_URL`/`SUPABASE_URL`/`SUPABASE_ANON_KEY` env are needed exactly as the
  existing `backend-tests` job supplies them; testcontainers overrides
  `DATABASE_URL` at runtime for the real container.
- **Frontend typecheck is a real gap.** `.pre-commit-config.yaml` runs ruff
  (backend), eslint, and prettier — **not** `tsc`. All three tsconfigs
  (`tsconfig.app.json`, `.node.json`, `.e2e.json`) set `noEmit: true` and are
  referenced from the root `tsconfig.json`, so `tsc -b` type-checks src + config +
  e2e specs without emitting.

## Desired End State

`.github/workflows/ci-cd.yml` runs nine parallel gate jobs on every PR and push
to `main`/`develop`: the five existing ones plus `frontend-unit`,
`frontend-typecheck`, `backend-integration`, and a working `frontend-e2e`. All
nine are listed in `deploy.needs`, so a `release` deploy proceeds only when every
gate is green. The e2e job fails fast with a clear message if any required GitHub
secret is missing. Docs (`test-plan.md`, integration `README.md`, `AGENTS.md`,
`change.md`) reflect that CI now enforces these gates.

Verify: open a PR from a branch → all nine jobs run; `frontend-unit`,
`frontend-typecheck`, `backend-integration` pass without any secret config; the
`frontend-e2e` job passes once the secrets are present (or fails fast, naming the
missing secret, when they are not).

### Key Discoveries:

- The e2e stub duplicates Playwright's own `webServer` boot and lacks `uv sync` — both must be corrected, not just `if: false` removed (`ci-cd.yml:146-179`, `playwright.config.ts:50-68`).
- Backend integration self-provisions Postgres via testcontainers — no `services: postgres` needed (`backend/tests/integration/conftest.py:38`, `README.md` "CI status").
- Backend `Settings()` requires `database_url`/`supabase_url`/`supabase_anon_key` at import even when the DB is unused → placeholder env for non-live jobs (`config.py:28-30`, existing `backend-tests` env block `ci-cd.yml:92-96`).
- Pre-commit does not run `tsc`; a standalone typecheck gate is not redundant with any existing job except the implicit `tsc -b` inside `frontend-build` (`.pre-commit-config.yaml`).
- GitHub Actions sets `CI=true` automatically, which activates `forbidOnly`, `retries: 2`, and `reuseExistingServer: false` in `playwright.config.ts` — no extra config needed.

## What We're NOT Doing

- **Not authoring new tests.** This is the gate layer; the Vitest, Playwright, and integration suites already exist.
- **Not creating a dedicated test Supabase project.** Reuse the existing project (decision inherited from `critical-path-e2e`); swappable later via secrets only.
- **Not provisioning the GitHub secrets or the confirmed test account for you.** The plan adds a preflight *check* and documents the required set; creating the secrets/account in the GitHub UI is a manual prerequisite.
- **Not adding a `services: postgres` container** — testcontainers handles Postgres for the integration job.
- **Not changing `frontend-build`** (it keeps `tsc -b && vite build`); the new typecheck job overlaps its `tsc -b` step deliberately, for a discrete/faster gate symmetric with `backend-typecheck`.
- **Not touching pre-commit hooks, branch-protection rules, or the deploy hooks** (RENDER_* secrets) themselves.

## Implementation Approach

Two functional phases plus a docs phase. Phase 1 adds the three **secret-free**
jobs — they are verifiable on any branch push with zero external configuration,
giving a clean checkpoint before the live-infra work. Phase 2 fixes the e2e job,
which is the only one needing secrets and a live backend. Phase 3 reconciles the
documentation and status trackers. Each job phase also adds its jobs to
`deploy.needs` so the deploy gate stays consistent as work lands.

## Critical Implementation Details

- **E2E env must be job-level, not step-level.** The backend is booted by
  Playwright's `webServer` (`uv run uvicorn` as a child of `npx playwright test`),
  so `DATABASE_URL`/`SUPABASE_URL`/`SUPABASE_ANON_KEY` must be exported at the job
  (or the test step) level to be inherited by that child process, not scoped to an
  install step.
- **Secrets can't be read in `if:` conditions.** GitHub blocks `secrets.*` in job
  `if:` expressions. The preflight must map secrets to `env:` in a `run` step and
  test the env vars there, failing with `exit 1` — this is why it's a step, per
  the chosen "verify secrets exist" approach.
- **Preflight ordering.** The secrets check must run *before* `npx playwright
  install --with-deps` (the slowest step) so a misconfigured run fails in seconds,
  not minutes.

## Phase 1: Secret-free CI jobs

### Overview

Add three parallel gate jobs that need no secrets and no live services (Docker
for testcontainers is provided by the runner), and add all three to `deploy.needs`.

### Changes Required:

#### 1. `frontend-unit` job

**File**: `.github/workflows/ci-cd.yml`

**Intent**: Run the Vitest data-seam suite as a discrete CI gate.

**Contract**: New job `frontend-unit` (`runs-on: ubuntu-latest`): checkout →
`setup-node@v6` (node 22, npm cache keyed on `frontend/package-lock.json`) →
`npm ci` (working-directory `frontend`) → `npm run test:run`. Mirror the existing
`frontend-build` job's setup block.

#### 2. `frontend-typecheck` job + `typecheck` npm script

**File**: `.github/workflows/ci-cd.yml`, `frontend/package.json`

**Intent**: Give TypeScript type errors a discrete, fast gate symmetric with
`backend-typecheck` (pyright), instead of only surfacing them inside the build.

**Contract**: Add `"typecheck": "tsc -b"` to `frontend/package.json` `scripts`.
New job `frontend-typecheck`: same node setup + `npm ci` → `npm run typecheck`.

#### 3. `backend-integration` job

**File**: `.github/workflows/ci-cd.yml`

**Intent**: Run the DB-backed integration suite (`tests/integration/`) that CI has
been skipping, now that Phase 4 wires it in. Testcontainers supplies Postgres.

**Contract**: New job `backend-integration`: checkout → `setup-python@v6` (3.13) →
`setup-uv` (SHA-pinned, same pin as sibling jobs) → `uv sync --all-groups`
(working-directory `backend`) → `uv run pytest tests/integration`. Supply the same
placeholder `env` block the `backend-tests` job uses (`DATABASE_URL`,
`SUPABASE_URL`, `SUPABASE_ANON_KEY`) so `Settings()` imports; testcontainers
overrides `DATABASE_URL` at runtime. No `services:` block.

#### 4. Add the three jobs to the deploy gate

**File**: `.github/workflows/ci-cd.yml`

**Intent**: Ensure a release deploy waits on the new gates.

**Contract**: Append `frontend-unit`, `frontend-typecheck`, `backend-integration`
to `deploy.needs`.

### Success Criteria:

#### Automated Verification:

- Workflow YAML is valid: `npx --prefix frontend --yes yaml-lint .github/workflows/ci-cd.yml` (or any YAML validator) parses without error.
- `frontend/package.json` contains a `typecheck` script: `npm run typecheck` succeeds locally in `frontend/`.
- `npm run test:run` passes locally in `frontend/`.
- Backend integration suite passes locally with Docker running: `cd backend && uv run pytest tests/integration`.

#### Manual Verification:

- On a pushed branch / PR, `frontend-unit`, `frontend-typecheck`, and `backend-integration` all appear and pass with no secret configuration.
- The `backend-integration` job's log shows testcontainers pulling/starting `postgres:17-alpine` and tearing it down.
- The three jobs run in parallel with the existing gates (not serialized).

**Implementation Note**: After completing this phase and all automated
verification passes, pause for manual confirmation that the three jobs run green
in CI before proceeding to Phase 2.

---

## Phase 2: E2E job wiring

### Overview

Turn the `frontend-e2e` TODO stub into a correct, enabled job: remove the wrong
manual server-start steps, install backend deps so Playwright's `webServer` can
boot uvicorn, add a secrets-preflight step, install the Chromium browser, inject
the live env from secrets, run the suite, upload the report on failure, and add
the job to `deploy.needs`.

### Changes Required:

#### 1. Enable and correct the `frontend-e2e` job

**File**: `.github/workflows/ci-cd.yml`

**Intent**: Replace the broken stub body with a job that lets Playwright manage
the servers and runs the suite against the live Supabase project.

**Contract**: In job `frontend-e2e`: remove `if: false`; delete the manual
"Start backend" and "Start frontend" `&` steps (Playwright's `webServer` boots
both). Add: `setup-python@v6` (3.13) + `setup-uv` (SHA-pinned) + `uv sync
--all-groups` (working-directory `backend`) so `uv run uvicorn` resolves; keep
node setup + `npm ci`; `npx playwright install --with-deps chromium`; run the
suite via `npx playwright test` (working-directory `frontend`). Backend + e2e env
(`DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `E2E_TEST_PASSWORD`,
`E2E_DATABASE_URL`) are provided from `secrets.*` at the level inherited by the
Playwright child process (see Critical Implementation Details).

Add a job-level `concurrency` group so runs serialize on the shared Supabase
account instead of racing:

```yaml
concurrency:
  group: e2e-shared-supabase
  cancel-in-progress: false
```

This is required, not cosmetic: `globalTeardown` (`e2e/teardown/cleanup-test-users.ts`)
`DELETE`s **all** of `e2e-hmc@example.com`'s rows — not just the current run's —
and `seed.spec.ts` relies on that account-wide sweep alone. Without serialization,
two overlapping CI runs (a push to `main` plus an open PR, or two PRs) share the
account's state: run B's teardown can delete run A's rows mid-suite, and run A's
list/empty-state assertions can observe run B's rows. `cancel-in-progress: false`
lets each run finish (rather than a newer run killing an in-flight one and leaving
half-swept state). `retries: 2` cannot fix this data race.

#### 2. Secrets-preflight step

**File**: `.github/workflows/ci-cd.yml`

**Intent**: Fail fast with a clear message if any required secret is missing,
before the expensive browser install (the "verify secrets exist" decision).

**Contract**: A `run` step placed first among the e2e steps (after checkout),
mapping each required secret to `env` and checking each is non-empty, exiting
non-zero and naming every missing secret via `::error::`. Required set:
`DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `E2E_TEST_PASSWORD`,
`E2E_DATABASE_URL`.

```yaml
- name: Verify required E2E secrets are present
  env:
    DATABASE_URL: ${{ secrets.DATABASE_URL }}
    SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
    SUPABASE_ANON_KEY: ${{ secrets.SUPABASE_ANON_KEY }}
    E2E_TEST_PASSWORD: ${{ secrets.E2E_TEST_PASSWORD }}
    E2E_DATABASE_URL: ${{ secrets.E2E_DATABASE_URL }}
  run: |
    missing=()
    for name in DATABASE_URL SUPABASE_URL SUPABASE_ANON_KEY E2E_TEST_PASSWORD E2E_DATABASE_URL; do
      [ -z "${!name}" ] && missing+=("$name")
    done
    if [ ${#missing[@]} -ne 0 ]; then
      echo "::error::Missing required E2E secret(s): ${missing[*]}"
      exit 1
    fi
```

#### 3. Upload Playwright report on failure

**File**: `.github/workflows/ci-cd.yml`

**Intent**: Preserve the HTML report + traces when e2e fails, for debugging.

**Contract**: `actions/upload-artifact@v4` step with `if: failure()`, uploading
`frontend/playwright-report/` (and `frontend/test-results/` for `on-first-retry`
traces).

#### 4. Add e2e to the deploy gate

**File**: `.github/workflows/ci-cd.yml`

**Intent**: e2e is fully blocking — a broken critical journey must stop a release.

**Contract**: Append `frontend-e2e` to `deploy.needs`.

### Success Criteria:

#### Automated Verification:

- Workflow YAML parses without error after the edits.
- The preflight step's shell logic is valid `bash` (e.g. `bash -n` on the extracted script) — no syntax error.

#### Manual Verification:

- With all five secrets configured in the GitHub repo, the `frontend-e2e` job runs, Playwright boots backend + frontend itself (log shows both `webServer` URLs becoming ready), the suite passes, and the account's rows are swept by `globalTeardown`.
- With a secret deliberately unset, the job fails within seconds at the preflight step, naming the missing secret — not later at browser install or a 30s login timeout.
- On an induced failure, the Playwright report artifact is uploaded and downloadable from the run.
- The `deploy` job (on a `release`) waits on `frontend-e2e` and does not start until it is green.

**Implementation Note**: This phase requires the five GitHub secrets and the
confirmed `e2e-hmc@example.com` test account to exist in the shared Supabase
project. After automated verification, pause for manual confirmation that the e2e
job runs green in CI (secrets present) before proceeding to Phase 3.

---

## Phase 3: Docs & status reconciliation

### Overview

Update the trackers and reference docs so they match the now-enforced gates.

### Changes Required:

#### 1. `test-plan.md` status + gate rows

**File**: `context/foundation/test-plan.md`

**Intent**: Reflect that Phase 4 is complete and the gates are enforced.

**Contract**: §3 Phase 4 row Status → `complete`, add the change folder
`context/changes/quality-gates-wiring/`. §4 "CI gates" row: drop "Frontend-unit
job absent; e2e job is a TODO stub" and the `tests/integration` exclusion caveat.
§5: flip the `frontend unit`, `frontend typecheck`, `e2e`, and integration gate
rows to enforced (add a `frontend typecheck` row if §5 has none). §6.2:
update the "Excluded from CI … until test-plan Phase 4" line to note integration
now runs in CI via testcontainers.

#### 2. Integration README CI status

**File**: `backend/tests/integration/README.md`

**Intent**: The "CI status" section says integration is excluded until Phase 4
wires a "Postgres service container" — now wired, and via testcontainers, not a
service container.

**Contract**: Update the "CI status" section to state integration runs in the
`backend-integration` CI job, Postgres supplied by testcontainers (no `services:`
container).

#### 3. `AGENTS.md` stale CI note

**File**: `AGENTS.md`

**Intent**: The "Commit & Pull Request Guidelines" section says "No CI workflow
exists yet — no automated gate on PRs," which is stale since F-04.

**Contract**: Replace that clause to state CI runs on PRs (lint/typecheck, backend
+ frontend unit, backend integration, build, and e2e gates) via
`.github/workflows/ci-cd.yml`; keep the local pre-PR guidance.

#### 4. `change.md` status

**File**: `context/changes/quality-gates-wiring/change.md`

**Intent**: Mark the change progressed.

**Contract**: `status: complete`, `updated:` to the implementation date.

### Success Criteria:

#### Automated Verification:

- No dangling "TODO stub" / "job absent" / "until test-plan Phase 4" strings remain: `rg -n "TODO stub|Frontend-unit job absent|until test-plan Phase 4|No CI workflow exists yet" context/foundation/test-plan.md backend/tests/integration/README.md AGENTS.md` returns nothing.

#### Manual Verification:

- test-plan.md §3/§4/§5 read consistently with the shipped workflow.
- AGENTS.md no longer claims CI is absent.

**Implementation Note**: Docs-only phase; no CI run required beyond confirming the
strings are gone.

---

## Testing Strategy

### Unit Tests:

- No new unit tests — this change wires existing suites. The suites themselves are the artifacts under test.

### Integration Tests:

- The `backend-integration` job *is* the integration test runner being wired; its green run in CI is the acceptance signal.

### Manual Testing Steps:

1. Push the branch; confirm the three secret-free jobs (`frontend-unit`, `frontend-typecheck`, `backend-integration`) appear and pass with no secret config.
2. Configure the five secrets; confirm `frontend-e2e` runs green and Playwright boots both servers.
3. Temporarily unset one secret; confirm the preflight fails fast, naming it.
4. Induce an e2e failure; confirm the report artifact uploads.
5. Confirm `deploy.needs` lists all nine gate jobs.

## Performance Considerations

- The e2e job is the slow one: `uv sync` + `npm ci` + `playwright install` + `webServer` boot (~5-15s) + `retries: 2`. It runs in parallel with the other gates, so it sets the pipeline's critical-path length but does not serialize other jobs.
- `backend-integration` pulls `postgres:17-alpine` once per run; acceptable for a Phase-4 gate.
- `frontend-typecheck` re-runs `tsc -b` already done inside `frontend-build`; the ~10s overlap buys a discrete, earlier-failing gate.

## Migration Notes

- **Prerequisite (manual, one-time):** create the five GitHub Actions secrets
  (`DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `E2E_TEST_PASSWORD`,
  `E2E_DATABASE_URL`) pointing at the shared Supabase project, and confirm the
  `e2e-hmc@example.com` account exists and is email-confirmed there. Until the
  secrets exist, the e2e job fails at the preflight (by design); the other eight
  gates are unaffected.

## References

- Test plan: `context/foundation/test-plan.md` (§3 Phase 4, §4, §5, §6.2)
- E2E source of truth: `context/changes/critical-path-e2e/plan.md`, `plan-brief.md`
- Existing CI (F-04): `.github/workflows/ci-cd.yml`; archived `context/archive/2026-06-29-ci-cd-wiring/`
- Playwright config: `frontend/playwright.config.ts:50-68`
- Integration setup: `backend/tests/integration/README.md`, `conftest.py:38-59`
- Backend settings: `backend/app/core/config.py:28-30`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Secret-free CI jobs

#### Automated

- [x] 1.1 Workflow YAML parses without error — 0a372c9
- [x] 1.2 `frontend/package.json` has a `typecheck` script; `npm run typecheck` passes locally — 0a372c9
- [x] 1.3 `npm run test:run` passes locally — 0a372c9
- [x] 1.4 `uv run pytest tests/integration` passes locally with Docker running — 0a372c9

#### Manual

- [x] 1.5 The three secret-free jobs appear and pass in CI with no secret config — 32fb569
- [x] 1.6 backend-integration log shows testcontainers start/teardown of postgres:17-alpine — 32fb569
- [x] 1.7 The three jobs run in parallel with existing gates — 32fb569

### Phase 2: E2E job wiring

#### Automated

- [x] 2.1 Workflow YAML parses without error after edits
- [x] 2.2 Preflight shell script passes `bash -n`

#### Manual

- [ ] 2.3 With secrets set, frontend-e2e runs green; Playwright boots both servers; teardown sweeps rows
- [ ] 2.4 With a secret unset, the job fails fast at preflight naming the missing secret
- [ ] 2.5 On induced failure, the Playwright report artifact uploads
- [ ] 2.6 deploy waits on frontend-e2e before starting

### Phase 3: Docs & status reconciliation

#### Automated

- [ ] 3.1 No stale strings remain (rg check over test-plan.md, integration README, AGENTS.md)

#### Manual

- [ ] 3.2 test-plan.md §3/§4/§5 read consistently with the shipped workflow
- [ ] 3.3 AGENTS.md no longer claims CI is absent

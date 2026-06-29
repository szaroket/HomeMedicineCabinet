# CI/CD Wiring (F04) Implementation Plan

## Overview

Finalize the F04 CI/CD feature. Two draft artifacts already exist on this branch but are **untracked**: `.github/workflows/ci.yml` (gates) and `render.yaml` (Render Blueprint). This plan completes them into a committed, coherent CI/CD setup:

- **CI** gates every PR/push to `main` and `develop` with the existing checks **plus** a frontend build, a backend type-check (pyright), and a backend coverage threshold; it also carries a scaffolded-but-disabled E2E job ready to enable once Playwright lands.
- **CD** deploys to Render **only when a GitHub Release is published**, via per-service Render Deploy Hooks stored as GitHub secrets.
- **render.yaml** is corrected (health-check path bug) and documented so a first deploy succeeds.

## Current State Analysis

- Branch: `feature/f04-ci-cd-wiring`.
- `.github/workflows/ci.yml` (untracked) defines three jobs — `vulnerability-scan` (pip-audit + npm audit), `pre-commit`, `backend-tests` (`uv run pytest`) — triggered on push/PR to `main` and `develop`.
- `render.yaml` (untracked) is a Blueprint with a `python` web service (`home-medicine-cabinet-backend`) and a `static` site (`home-medicine-cabinet-frontend`). `healthCheckPath` is `/v1/health/`.
- **Verified bug**: the real route is `/api/v1/health/` — `app/api/v1/router.py:9` mounts `prefix="/api/v1"`, includes `health_router` whose own `prefix="/health"` (`app/api/v1/health/router.py:3`); `app/main.py:71` includes the v1 router. So `/v1/health/` would 404 and Render health checks would fail.
- **Gaps vs. documented PR gate**: AGENTS.md (line 125) says run `npm run build` and `pre-commit run --all-files` manually before a PR — CI never builds the frontend. `pyright` is a backend dependency (`backend/pyproject.toml:18,27`) and there is a recent `feat: fix pyright issues` commit (`3930d8f`), yet type-checking is gated **nowhere** (not in `.pre-commit-config.yaml`, not in CI).
- **No coverage config**: `coverage>=7.14.1` is a dependency but there is no `[tool.coverage]` block and no `pytest-cov` — coverage must be driven via the `coverage` CLI (`coverage run -m pytest` → `coverage report`).
- **No pyright config**: no `pyrightconfig.json` and no `[tool.pyright]` block — pyright currently runs with defaults over the whole tree.
- **E2E / frontend unit tests not testable yet**: `frontend/e2e/` has no specs and no `playwright.config.*`; Vitest is not configured. These cannot be live CI gates in this change.
- Tests exist for `auth/`, `cabinet/`, and shared `conftest.py` under `backend/tests/`.

## Desired End State

- `.github/workflows/ci.yml` is committed and, on every PR/push to `main`/`develop`, runs: vulnerability-scan, pre-commit, **frontend build**, **backend pyright**, and **backend tests with a coverage floor**; plus a `frontend-e2e` job that is present but skipped.
- `.github/workflows/ci-cd.yml` carries a release-gated `deploy` job (guarded by `if: github.event_name == 'release'`, `needs:` the CI jobs) that, on `release: published`, triggers Render deploys for both services using `secrets.RENDER_DEPLOY_HOOK_BACKEND` and `secrets.RENDER_DEPLOY_HOOK_FRONTEND`. (See Phase 3 addendum — CD is merged into `ci-cd.yml`, not a separate `cd.yml`.)
- `backend/pyproject.toml` has `[tool.coverage.run]`, `[tool.coverage.report]` (with `fail_under = 60`), and a `[tool.pyright]` block; `uv run coverage run -m pytest && uv run coverage report` and `uv run pyright` both pass locally.
- `render.yaml` `healthCheckPath` is `/api/v1/health/` and both services have `autoDeploy: false`, so the only deploy path is the release-triggered Deploy Hook.
- A deployment doc records the required GitHub secrets and the Render `sync:false` env vars.

**Verification**: open a PR into `develop` → all CI jobs pass except the intentionally-skipped E2E job. Publishing a GitHub Release fires the `deploy` job in `ci-cd.yml` and both Render services redeploy.

### Key Discoveries:

- Health route is `/api/v1/health/` — `backend/app/api/v1/router.py:9` + `backend/app/api/v1/health/router.py:3`.
- Coverage tool is the `coverage` CLI, not `pytest-cov` — `backend/pyproject.toml:16`.
- `pyright` already a dep (`backend/pyproject.toml:18,27`); a recent commit fixed type issues but nothing gates regressions.
- Existing CI uses `astral-sh/setup-uv@v4`, `actions/setup-python@v5`, `actions/setup-node@v4` (node 22), `uv sync --all-groups`, and `pre-commit/action@v3.0.1` — reuse these exact versions/patterns for consistency.
  - **Addendum (2026-06-29, Phase 2)**: superseded — actions were deliberately bumped to current majors (`checkout@v7`, `setup-python@v6`, `setup-node@v6`; `setup-uv` SHA-pinned) in commit `16757c5`. Verified green on Actions runs `28390866751`/`28391109360`.
- `render.yaml` env vars are all `sync:false` (must be set in Render dashboard): `FRONTEND_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL` (backend) and `VITE_API_URL` (frontend).

## What We're NOT Doing

- Not writing Playwright/Vitest specs or configuring them — the E2E CI job is scaffolded and disabled only.
- Not adding a `develop → staging` or PR-preview environment — `main`/release → production only.
- Not switching deploy to the Render API/polling — fire-and-forget Deploy Hooks only.
- Not automating GitHub branch-protection / required-status-checks via API — that's a repo-settings step the user does in the GitHub UI (noted in docs).
- Not introducing any secret-handling code in the app; secrets live only in GitHub Actions / Render config.
- Not raising coverage above the ~60% baseline or adding new tests to chase coverage.

## Implementation Approach

Build bottom-up so CI never goes red on its own new gates: first make the backend gate config deterministic and locally green (Phase 1), then expand `ci.yml` to enforce those gates (Phase 2), then add the release-triggered `cd.yml` (Phase 3), then correct and document `render.yaml` (Phase 4). Reuse the action versions and job scaffolding already present in the draft `ci.yml`.

## Critical Implementation Details

- **Coverage driver**: there is no `pytest-cov`; use the `coverage` CLI — `coverage run -m pytest` then `coverage report --fail-under=60` (or `fail_under` in config). Do not add a `--cov` pytest flag; it won't exist.
- **pyright scope**: default pyright may scan migrations/tests and report noise. Scope `[tool.pyright]` to `include = ["app"]` (and exclude `migrations`) so the gate reflects application code, matching the ruff per-file-ignore posture for `migrations/*`.
- **Deploy job must never run on PRs**: ~~it lives in a separate `cd.yml` keyed solely on `on: release: { types: [published] }`~~ — **superseded by Phase 3 addendum**: the `deploy` job lives in `ci-cd.yml` and is gated by `if: github.event_name == 'release'`, so it is skipped on every `push`/`pull_request`. The "never on PRs" invariant still holds.

## Phase 1: Backend gate config

### Overview

Add deterministic coverage and pyright configuration to `backend/pyproject.toml` and confirm both pass locally, so the CI gates added in Phase 2 start green.

### Changes Required:

#### 1. Coverage configuration

**File**: `backend/pyproject.toml`

**Intent**: Make `coverage` produce a stable, app-scoped report with an enforced floor so the CI coverage gate is reproducible.

**Contract**: Add `[tool.coverage.run]` with `source = ["app"]` and `branch = true`, and `[tool.coverage.report]` with `fail_under = 60` and `show_missing = true`. Omit test files from `source`. No change to `[tool.pytest.ini_options]`.

#### 2. Pyright configuration

**File**: `backend/pyproject.toml`

**Intent**: Scope type-checking to application code so the gate is meaningful and not drowned in migration/template noise.

**Contract**: Add a `[tool.pyright]` block with `include = ["app"]`, `exclude = ["migrations", "**/__pycache__"]`, and `pythonVersion = "3.13"`. Choose `typeCheckingMode` ("basic" recommended) so `uv run pyright` passes on the current tree; if "standard"/"strict" surfaces pre-existing errors, use "basic" — do not fix unrelated type errors in this change.

### Success Criteria:

#### Automated Verification:

- Coverage runs and meets the floor: `cd backend && uv run coverage run -m pytest && uv run coverage report`
- Type-check passes: `cd backend && uv run pyright`
- Lint/format still clean: `cd backend && uv run ruff check . && uv run ruff format --check .`
- TOML is valid (pre-commit `check-toml`): `pre-commit run check-toml --all-files`

#### Manual Verification:

- Coverage floor (~60%) is cleared by the current test suite without adding tests; if it isn't, the floor is lowered to the current value rather than blocking.
- `typeCheckingMode` chosen is the strictest mode that passes today.

**Implementation Note**: After automated verification passes, pause for human confirmation before Phase 2.

---

## Phase 2: Expand CI workflow

### Overview

Extend the existing `ci.yml` with a frontend build job, a backend pyright job, a coverage threshold in the backend tests job, and a scaffolded-but-disabled E2E job. Triggers stay on PR/push to `main` and `develop`.

### Changes Required:

#### 1. Frontend build job

**File**: `.github/workflows/ci.yml`

**Intent**: Close the documented gap where `npm run build` is only run manually — fail PRs that break the TypeScript compile or Vite build.

**Contract**: New job `frontend-build` (runs-on `ubuntu-latest`): checkout, `actions/setup-node@v4` (node 22, npm cache keyed on `frontend/package-lock.json`), `npm ci`, `npm run build`, all `working-directory: frontend`. Mirror the node setup already used by the `pre-commit` job.

#### 2. Backend type-check job

**File**: `.github/workflows/ci.yml`

**Intent**: Gate pyright so the type-correctness fixed in `3930d8f` cannot regress.

**Contract**: New job `backend-typecheck`: checkout, `actions/setup-python@v5` (3.13), `astral-sh/setup-uv@v4`, `uv sync --all-groups` then `uv run pyright`, `working-directory: backend`. Mirror the `backend-tests` job setup.

#### 3. Coverage threshold in backend tests

**File**: `.github/workflows/ci.yml`

**Intent**: Enforce the Phase 1 coverage floor in CI.

**Contract**: In the existing `backend-tests` job, replace `uv run pytest` with `uv run coverage run -m pytest` followed by `uv run coverage report` (the `fail_under` from config makes the step fail under the floor). Job name/structure otherwise unchanged.

#### 4. Scaffolded, disabled E2E job

**File**: `.github/workflows/ci.yml`

**Intent**: Reserve reviewable wiring for Playwright E2E that can be enabled by flipping one switch once specs and config exist.

**Contract**: New job `frontend-e2e` guarded so it never executes yet — `if: false` — with the intended steps drafted (checkout, node setup, `npm ci`, `npx playwright install --with-deps`, start backend + frontend, `npx playwright test`) and a `# TODO: enable once frontend/e2e specs + playwright.config exist` comment. The job must be syntactically valid YAML so the workflow parses.

### Success Criteria:

#### Automated Verification:

- Workflow YAML is valid: `pre-commit run check-yaml --all-files`
- Pushing the branch / opening a PR triggers CI and the new `frontend-build`, `backend-typecheck` jobs and the coverage step all pass (observed in GitHub Actions).
- The `frontend-e2e` job is skipped (not failed) in the Actions run.

#### Manual Verification:

- All non-E2E jobs are green on a PR into `develop`.
- The E2E job shows as skipped with its TODO visible.

**Implementation Note**: Verifying CI requires pushing to GitHub and observing the Actions run. After automated checks pass and the run is green, pause for human confirmation before Phase 3.

**Addendum (2026-06-29)**: Phase 2 also absorbed plumbing needed to make CI green, beyond the four contracts above: (a) security dependency bumps in `backend/pyproject.toml` (added `cryptography`, `python-multipart`, `starlette`; raised `pydantic-settings`) to satisfy the pre-existing `vulnerability-scan` job; (b) dummy `DATABASE_URL` (asyncpg scheme) and `SUPABASE_*` env vars plus `--ignore=tests/db` in the `backend-tests` job, so unit tests run without a live DB. The `--ignore` drops only live-DB integration tests; coverage remains 86% and the env vars match `app/core/config.py`.

---

## Phase 3: Add CD workflow

### Overview

Add a separate `cd.yml` that deploys both Render services when a GitHub Release is published, using per-service Deploy Hook secrets.

### Changes Required:

#### 1. Release-triggered deploy workflow

**File**: `.github/workflows/cd.yml`

**Intent**: Trigger production deploys for backend and frontend exactly when a release is published — never on PRs or pushes.

**Contract**: New workflow `name: CD`, `on: release: { types: [published] }`, single job `deploy` (runs-on `ubuntu-latest`) that curls two Deploy Hook URLs read from secrets. Each step fails the job on non-2xx (`curl --fail`). Secrets referenced: `RENDER_DEPLOY_HOOK_BACKEND`, `RENDER_DEPLOY_HOOK_FRONTEND`. No checkout needed.

```yaml
on:
  release:
    types: [published]
# steps: curl --fail "$RENDER_DEPLOY_HOOK_BACKEND"; curl --fail "$RENDER_DEPLOY_HOOK_FRONTEND"
# hook URLs injected via env from secrets.*
```

### Success Criteria:

#### Automated Verification:

- Workflow YAML is valid: `pre-commit run check-yaml --all-files`
- The deploy job is guarded by `if: github.event_name == 'release'` so it is skipped on push/PR: grep confirms. (See Phase 3 addendum — CD lives in `ci-cd.yml`, not a separate `cd.yml`.)

#### Manual Verification:

- `RENDER_DEPLOY_HOOK_BACKEND` and `RENDER_DEPLOY_HOOK_FRONTEND` are set in GitHub repo secrets (from the Render dashboard).
- Publishing a test release triggers the `deploy` job in `ci-cd.yml`; both curl steps return success and both Render services show a new deploy.
- Opening/merging a PR does **not** run the `deploy` job.

**Implementation Note**: Live verification needs the Render hooks configured and a release published. After YAML checks pass, pause for human confirmation (and secret setup) before Phase 4.

**Addendum (2026-06-29, Phase 3)**: CD was **not** split into a separate `cd.yml`. Instead, commit `a83be89` renamed `ci.yml` → `ci-cd.yml` and added the `deploy` job into that same workflow, gated by `if: github.event_name == 'release'` and `needs:` on all five CI jobs; `release: { types: [published] }` was added to the existing `on:` block alongside `push`/`pull_request`. This supersedes the "separate `cd.yml`" design in this phase's contract and the Critical Implementation Detail. Rationale: because `deploy` `needs:` the five CI jobs and the whole workflow re-runs on the release event, deploy is gated by a **fresh green CI run on the released commit** — a property the separate-file design lacked (it would have fired the Deploy Hook on release without re-running any gate). The PR-safety goal is preserved: the job-level `if` skips `deploy` on every push/PR. Downstream consequence: Phase 4 docs and the "Desired End State" should describe the single `ci-cd.yml` with a release-gated deploy job, not a separate `cd.yml`.

---

## Phase 4: Fix & document render.yaml

### Overview

Correct the health-check path and document the deploy prerequisites so a first Render deploy succeeds.

### Changes Required:

#### 1. Health-check path fix & disable autoDeploy

**File**: `render.yaml`

**Intent**: Point Render's health check at the real endpoint so deploys pass their health gate, and make the release-triggered Deploy Hook the *only* deploy path so a plain push/merge to a tracked branch never deploys.

**Contract**: Change `healthCheckPath` from `/v1/health/` to `/api/v1/health/`. Also add `autoDeploy: false` to **both** services (`home-medicine-cabinet-backend` and `home-medicine-cabinet-frontend`) — Render Blueprints default to `autoDeploy: true`, which would redeploy on every push to the tracked branch and contradict the "only on release" design. No other service fields change.

#### 2. Deployment documentation

**File**: `docs/reference/deployment.md` (new) — and a short pointer line added to `README.md`.

**Intent**: Record what must be configured outside the repo for CI/CD to function, so the wiring is reproducible.

**Contract**: Document (a) GitHub secrets `RENDER_DEPLOY_HOOK_BACKEND` / `RENDER_DEPLOY_HOOK_FRONTEND` and where to obtain them in Render; (b) the `sync:false` Render env vars per service — backend: `FRONTEND_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`; frontend: `VITE_API_URL`; (c) the **release procedure** (deploy trigger): merge the change to `main` → create a new tag at `main` HEAD → publish a GitHub Release (with release notes) from that tag. Include the operating assumption that makes this safe: the Render Deploy Hook is fire-and-forget and deploys the **tracked branch's HEAD** (Render tracks `main`), carrying no commit/tag reference — so releases **must** be cut from the tip of `main` immediately after merge, so the deployed artifact matches the released commit; (d) a note to enable required status checks in GitHub branch protection for `main`/`develop`. All prose in English (docs), app UI text rule does not apply to internal docs.

### Success Criteria:

#### Automated Verification:

- `render.yaml` parses and path is fixed: `pre-commit run check-yaml --all-files` and grep shows `healthCheckPath: /api/v1/health/`.
- Both services disable native autodeploy: grep shows `autoDeploy: false` appears twice in `render.yaml`.
- Docs file exists: `ls docs/reference/deployment.md`.
- README points at the deployment doc: `grep -F "docs/reference/deployment.md" README.md`.

#### Manual Verification:

- A Render deploy passes its health check against `/api/v1/health/`.
- A new contributor can follow `docs/reference/deployment.md` to set secrets + env vars and produce a working deploy.

**Implementation Note**: After automated checks pass, pause for human confirmation. Final step (outside this plan's edits): commit all artifacts with a `feat:`/`chore:` Conventional Commit and open the PR.

---

## Testing Strategy

### Unit Tests:

- No new application unit tests — this change is CI/CD config. Existing `backend/tests/**` must continue to pass under the coverage runner.

### Integration Tests:

- CI itself is the integration test: a PR into `develop` exercises every job. A published release exercises the `deploy` job in `ci-cd.yml`.

### Manual Testing Steps:

1. Run Phase 1 commands locally; confirm coverage ≥ floor and pyright green.
2. Push the branch; open a PR into `develop`; confirm all CI jobs pass and `frontend-e2e` is skipped.
3. Set the two Render Deploy Hook secrets; publish a test release; confirm the `deploy` job in `ci-cd.yml` runs and both services redeploy.
4. Hit the deployed backend `/api/v1/health/`; confirm `{"status":"healthy"}` and a passing Render health check.

## Performance Considerations

- Frontend build and pyright add ~1–3 min to CI; jobs run in parallel so wall-clock impact is bounded by the slowest job. npm and uv caching already in the draft reduce install time.

## Migration Notes

- The draft `ci.yml` and `render.yaml` are currently untracked; this change is their first commit. No existing pipeline to migrate from.
- Branch protection / required status checks are a one-time GitHub UI step documented in Phase 4, not automated here.

## References

- Repo rules: `AGENTS.md` (build/test commands, PR gate, hard rules)
- Health route: `backend/app/api/v1/router.py:9`, `backend/app/api/v1/health/router.py:3`
- Workflow + draft artifacts: `.github/workflows/ci-cd.yml` (renamed from `ci.yml`; carries CI jobs + release-gated `deploy`), `render.yaml`
- Pre-commit config: `.pre-commit-config.yaml`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Backend gate config

#### Automated

- [x] 1.1 Coverage runs and meets the floor (`uv run coverage run -m pytest && uv run coverage report`) — ca1ce29
- [x] 1.2 Type-check passes (`uv run pyright`) — ca1ce29
- [x] 1.3 Lint/format still clean (`uv run ruff check . && uv run ruff format --check .`) — ca1ce29
- [x] 1.4 TOML valid (`pre-commit run check-toml --all-files`) — ca1ce29

#### Manual

- [x] 1.5 Coverage floor cleared by current suite without new tests (or floor lowered to current value) — ca1ce29
- [x] 1.6 Strictest passing pyright `typeCheckingMode` chosen — ca1ce29

### Phase 2: Expand CI workflow

#### Automated

- [x] 2.1 Workflow YAML valid (`pre-commit run check-yaml --all-files`) — 554eaa8
- [x] 2.2 CI triggers and `frontend-build`, `backend-typecheck`, and coverage step pass in Actions
- [x] 2.3 `frontend-e2e` job is skipped (not failed) in the Actions run

#### Manual

- [x] 2.4 All non-E2E jobs green on a PR into `develop`
- [x] 2.5 E2E job shows as skipped with its TODO visible

### Phase 3: Add CD workflow

#### Automated

- [x] 3.1 Workflow YAML valid (`pre-commit run check-yaml --all-files`) — a83be89
- [x] 3.2 Deploy job guarded by `if: github.event_name == 'release'` (skipped on push/PR; grep confirms) — a83be89

#### Manual

- [x] 3.3 `RENDER_DEPLOY_HOOK_BACKEND` / `RENDER_DEPLOY_HOOK_FRONTEND` set in GitHub secrets
- [ ] 3.4 Publishing a test release triggers the `deploy` job in `ci-cd.yml`; both curl steps succeed and both services redeploy
- [x] 3.5 A PR does not run the `deploy` job — a83be89

### Phase 4: Fix & document render.yaml

#### Automated

- [x] 4.1 `render.yaml` parses and `healthCheckPath: /api/v1/health/` (check-yaml + grep)
- [x] 4.2 Both services have `autoDeploy: false` (grep shows two occurrences)
- [x] 4.3 Docs file exists (`ls docs/reference/deployment.md`)
- [x] 4.4 README points at the deployment doc (`grep -F "docs/reference/deployment.md" README.md`)

#### Manual

- [ ] 4.5 Render deploy passes health check against `/api/v1/health/`
- [ ] 4.6 A contributor can follow `docs/reference/deployment.md` to set secrets + env vars and deploy

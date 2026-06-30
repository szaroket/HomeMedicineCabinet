# CI/CD Wiring (F04) — Plan Brief

> Full plan: `context/changes/ci-cd-wiring/plan.md`

## What & Why

The repo has draft `.github/workflows/ci.yml` and `render.yaml` that are untracked and incomplete — frontend builds and type-checks aren't gated, there's no deploy step, and `render.yaml` has a broken health-check path. This change finalizes F04: a committed CI pipeline that gates every PR, a release-triggered deploy to Render, and a corrected, documented Blueprint.

## Starting Point

On branch `feature/f04-ci-cd-wiring`. CI draft runs vulnerability-scan, pre-commit, and backend pytest on PR/push to `main`/`develop`. `render.yaml` defines a FastAPI service + static frontend but points its health check at `/v1/health/` (real route is `/api/v1/health/`). Pyright is a dependency but gated nowhere; `coverage` is installed but unconfigured; Playwright/Vitest aren't set up yet.

## Desired End State

CI additionally builds the frontend, runs pyright, and enforces a ~60% coverage floor, while carrying a disabled E2E job ready to switch on later. A separate `cd.yml` deploys both Render services when a GitHub Release is published, via Deploy Hook secrets. `render.yaml`'s health path is fixed and a deployment doc captures the required secrets and env vars.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Deploy trigger | GitHub Actions job on `release: published` | Deploy only on an explicit release, GitHub as the gate | Plan |
| Environments | `main`/release → production only | One env is right for the MVP | Plan |
| Deploy auth | Per-service Render Deploy Hooks (secrets) | Simplest, no broad API token to manage | Plan |
| Extra CI gates | Frontend build + pyright + coverage floor | Closes documented gaps, prevents type regressions | Plan |
| Coverage policy | `fail_under ≈ 60` baseline | Gate passes today, ratchet up later | Plan |
| E2E in CI | Scaffolded job, `if: false` | Reviewable wiring now, enable when specs exist | Plan |
| Workflow layout | `ci.yml` (PR/push) + `cd.yml` (release) | Different triggers belong in separate files | Plan |
| render.yaml | Fix `healthCheckPath` + document env vars | Ship a deployable, correct Blueprint | Plan |

## Scope

**In scope:** Complete `ci.yml` gates; new `cd.yml`; backend coverage + pyright config; `render.yaml` health-path fix; deployment docs.

**Out of scope:** Writing Playwright/Vitest tests; staging/preview environments; Render API polling deploy; automating branch protection; app secret-handling code; chasing higher coverage.

## Architecture / Approach

Bottom-up so CI never reds out on its own new gates: (1) make backend coverage + pyright config locally green, (2) extend `ci.yml` to enforce them plus a frontend build and a disabled E2E job, (3) add a release-only `cd.yml` that curls two Render Deploy Hooks, (4) fix and document `render.yaml`. Reuse the action versions already in the draft (`setup-uv@v4`, `setup-python@v5`, `setup-node@v4` node 22, `pre-commit/action@v3.0.1`).

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Backend gate config | coverage + pyright config in `pyproject.toml`, locally green | Pyright surfaces pre-existing errors → use `basic` mode / lower floor |
| 2. Expand CI | frontend build, pyright job, coverage gate, disabled E2E | Coverage floor too high for current suite |
| 3. Add CD | `cd.yml` deploy on release via Deploy Hooks | Deploy job must never run on PRs |
| 4. Fix render.yaml | health-path fix + deployment doc | Wrong prod route assumption |

**Prerequisites:** GitHub repo admin (to set secrets + branch protection); Render account with both services + their Deploy Hook URLs.
**Estimated effort:** ~1–2 sessions across 4 phases (mostly config + GitHub Actions verification).

## Open Risks & Assumptions

- Pyright in stricter modes may flag pre-existing errors; the plan falls back to `basic` mode rather than fixing unrelated types here.
- The ~60% coverage floor is assumed achievable by the current suite; if not, it's lowered to the current value.
- Live CD verification depends on Render hooks being configured by the user (secrets are not in the repo).

## Success Criteria (Summary)

- A PR into `develop` runs all CI jobs green, with `frontend-e2e` skipped.
- Publishing a GitHub Release redeploys both Render services; a PR does not.
- The deployed backend answers `/api/v1/health/` and passes Render's health check.

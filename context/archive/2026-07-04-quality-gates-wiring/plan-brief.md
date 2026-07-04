# Quality-Gates Wiring — Plan Brief

> Full plan: `context/changes/quality-gates-wiring/plan.md`
> Upstream spec: `context/foundation/test-plan.md` (§3 Phase 4)

## What & Why

Close the last CI gaps in `.github/workflows/ci-cd.yml` (test-plan.md §3 Phase 4).
The five lint/typecheck/backend-test/build gates already ship via F-04; this
change wires in the jobs that are still missing or stubbed so that no regression
in the frontend unit tests, TypeScript types, backend integration path, or the
critical user journey can reach `main` — or a release — unnoticed.

## Starting Point

`ci-cd.yml` runs five real gate jobs plus a `frontend-e2e` **TODO stub**
(`if: false`) that is also wired incorrectly (it hand-starts servers Playwright
already boots, and skips `uv sync`). There is no frontend-unit job, no standalone
frontend typecheck (types are only checked implicitly inside `frontend-build`),
and the backend integration suite is `--ignore`'d in CI "until Phase 4." The
Vitest, Playwright, and integration suites themselves all already exist on disk.

## Desired End State

Eight parallel gate jobs run on every PR and push to `main`/`develop` — the five
existing plus `frontend-unit`, `frontend-typecheck`, `backend-integration`, and a
correct `frontend-e2e`. All eight are in `deploy.needs`, so a release deploys only
when every gate is green. The e2e job fails fast, naming the missing secret, if
its live-infra secrets are absent.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| E2E trigger | PR + push to main/develop | Catch journey breaks before merge, per test-plan §5 ("e2e on PR"). | Plan |
| E2E gating | Fully blocking — in `deploy.needs` | A broken critical journey must stop a release. | Plan |
| Secrets handling | Preflight step that fails fast if any required secret is missing | Turns an opaque mid-run failure into a clear, seconds-fast error. | Plan |
| frontend-unit | Separate job, in `deploy.needs` | Matches test-plan's named gate; parallel, discrete signal. | Plan |
| Added scope | Also add backend-integration + frontend-typecheck jobs | Phase 4 is exactly when integration un-ignores; typecheck fills a real gap (pre-commit doesn't run tsc). | Plan |
| E2E Supabase target | Existing shared project | Inherited from `critical-path-e2e`; zero new infra, swappable via secrets later. | Research (critical-path-e2e) |
| Integration Postgres | testcontainers (self-provisioned), no `services:` container | The suite spins up `postgres:17-alpine` itself; runner Docker suffices. | Research (integration README) |

## Scope

**In scope:**
- Add `frontend-unit`, `frontend-typecheck`, `backend-integration` jobs (secret-free).
- Fix + enable `frontend-e2e`: remove wrong manual server steps, add `uv sync`, secrets preflight, Chromium install, live env from secrets, report artifact on failure.
- Add all four to `deploy.needs`.
- Reconcile docs: test-plan.md, integration README, AGENTS.md, change.md.

**Out of scope:**
- Authoring any new tests (gate layer only).
- Creating a dedicated test Supabase project or provisioning the GitHub secrets/test account (manual prerequisite; the plan only checks + documents).
- A `services: postgres` container; changes to pre-commit, branch protection, or deploy hooks.

## Architecture / Approach

One file carries the functional change (`.github/workflows/ci-cd.yml`), plus a
one-line `typecheck` script in `frontend/package.json` and doc edits. Three new
jobs are secret-free and reuse the existing job scaffolds (node/uv setup). The
e2e job hands server orchestration to Playwright's own `webServer` array and
injects live env from `secrets.*` at the level the uvicorn child inherits; a
first `run` step verifies every secret is present before the expensive browser
install.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Secret-free jobs | frontend-unit + frontend-typecheck + backend-integration, all gating deploy | testcontainers needs Docker (present on ubuntu-latest) — verify it starts |
| 2. E2E job wiring | Correct, enabled, blocking frontend-e2e with secrets preflight + report artifact | Live secrets/test-account must exist; job-level env inheritance for the webServer child |
| 3. Docs reconciliation | test-plan.md, integration README, AGENTS.md, change.md updated | Low — string-level edits |

**Prerequisites:** For Phase 2 only — five GitHub secrets (`DATABASE_URL`,
`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `E2E_TEST_PASSWORD`, `E2E_DATABASE_URL`) and
the confirmed `e2e-hmc@example.com` account in the shared Supabase project.
Phase 1 needs nothing external.
**Estimated effort:** ~1 session; one workflow file + minor doc edits.

## Open Risks & Assumptions

- e2e runs against the shared Supabase project; its live-DB nature makes it the flakiest job (mitigated by `retries: 2` already in the config).
- Fork PRs cannot read secrets and would fail the e2e preflight — acceptable for this single-maintainer repo; revisit if outside contributors arrive.
- The `frontend-typecheck` job re-runs the `tsc -b` already inside `frontend-build` (~10s overlap) — accepted for a discrete gate.

## Success Criteria (Summary)

- On a PR, all eight jobs run; the three secret-free jobs pass with no configuration.
- With secrets set, `frontend-e2e` passes and Playwright boots both servers itself; with a secret unset, it fails fast naming the missing one.
- A `release` deploy waits on all eight gate jobs.

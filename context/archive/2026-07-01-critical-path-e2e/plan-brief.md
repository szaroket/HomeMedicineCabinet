# Playwright Critical-Path E2E Bootstrap — Plan Brief

> Full plan: `context/changes/critical-path-e2e/plan.md`
> Research: `context/changes/critical-path-e2e/research.md`

## What & Why

Bootstrap Playwright from scratch and lock the single most critical user
journey — login → add medication → see it in cabinet (Risk #2 in
`context/foundation/test-plan.md`) — with a config that runs identically on a
dev machine and in CI. This is test-plan.md §3 Phase 2.

## Starting Point

No Playwright dependency, config, or `frontend/e2e/` directory exists.
`AGENTS.md` already documents the expected shape (`e2e/` with
`*.spec.ts` + `auth.setup.ts`) and names this exact golden path, but nothing
has been built yet. The cabinet router has no `DELETE` endpoint, which shapes
the cleanup approach below.

## Desired End State

`npx playwright test` (from `frontend/`) boots both the backend and frontend
dev servers, logs in via a reused `storageState`, adds a medication, confirms
it's visible in the cabinet, confirms it survives a page reload, confirms the
expanded row shows correct details, and cleans up its own test data from the
database afterward — with zero manual setup steps and zero extra backend
endpoints.

## Key Decisions Made

| Decision | Choice | Why | Source |
|---|---|---|---|
| Journey scope | Journey A only (login→add→see, +refresh, +expand-detail) | No DELETE endpoint means any e2e-created data accumulates; narrowing scope limits volume | Research |
| Dev server startup | `playwright.config.ts` `webServer` array starts backend + frontend both | Same command works locally and in CI — no separate orchestration script to keep in sync | Plan |
| Supabase env | Use existing project via existing env vars now | Zero infra blocking; swappable to a dedicated test project later via env vars only | Plan |
| Browser scope | Chromium only | Risk #2 is a data-seam risk, not cross-browser rendering; keeps CI light for when Phase 4 wires it in | Plan |
| Cleanup | Direct-DB teardown script (no new API endpoint) | Avoids backend scope creep; works from both local and CI runs via `globalTeardown` | Plan |
| Test count | One spec file (`seed.spec.ts`) covering the full journey | Matches the `/10x-e2e` skill's seed-test convention — this file doubles as the project's first quality-lever exemplar | Plan |
| CI workflow wiring | Deferred to test-plan.md §3 Phase 4 | Keeps this phase scoped to "make it CI-compatible," not "make CI enforce it" | Plan |
| Auth strategy | `auth.setup.ts` registers via UI once, saves `storageState` for reuse | Already decided in research; backend is proxied to Supabase so storage-state reuse matches how the app itself persists sessions | Research |

## Scope

**In scope:**
- Playwright dependency, config (dual `webServer`, Chromium project), npm script
- tsconfig/eslint accommodation for the new `frontend/e2e/` directory
- `auth.setup.ts` (UI registration → `storageState`)
- `seed.spec.ts` covering Journey A end-to-end
- Direct-DB teardown script wired as Playwright `globalTeardown`

**Out of scope:**
- Journey B (display/filter cabinet data) — deferred
- CI workflow (`ci-cd.yml`) wiring — test-plan.md Phase 4
- Dedicated test Supabase project provisioning
- New backend API endpoints (seed or teardown)
- Cross-browser (Firefox/WebKit) coverage
- Frontend Vitest/unit bootstrap — test-plan.md Phase 3

## Architecture / Approach

`playwright.config.ts` owns dual-server orchestration via its `webServer`
array (backend via `uv run uvicorn`, frontend via `npm run dev`), so one
command works everywhere. A `setup` project (`auth.setup.ts`) runs first and
saves `storageState`; the `chromium` project depends on it and reuses the
saved session. `seed.spec.ts` is the one real test, exercising the journey
against the real API. `globalTeardown` runs a direct-DB script afterward that
deletes rows matching the test-user email convention — no new backend surface
area anywhere.

## Phases at a Glance

| Phase | What it delivers | Key risk |
|---|---|---|
| 1. Playwright Bootstrap & Dual-Server Config | Installed, configured, both servers boot on `--list` | tsconfig/eslint friction with the existing project-references split |
| 2. Auth Setup via `storageState` | `auth.setup.ts` produces a reusable session | Register-form field/redirect drift breaking setup silently |
| 3. Journey A Seed Test | `seed.spec.ts` — the one real test, full journey | Non-unique test data colliding with `uq_cabinet_entries_user_med_expiry` |
| 4. Direct-DB Teardown Script | `globalTeardown` deletes test-created rows | FK-order deletion without a confirmed cascade |

**Prerequisites:** Backend runnable locally via `uv run uvicorn`; `backend/.env` populated with valid Supabase credentials; Docker not required (no testcontainers here).
**Estimated effort:** ~1-2 sessions across 4 phases.

## Open Risks & Assumptions

- Assumes the live Supabase project (referenced by `backend/.env`) tolerates
  throwaway test users indefinitely until a dedicated test project is
  provisioned — flagged, not solved, in this phase.
- Assumes no DB-level cascade delete exists from auth user → cabinet entries;
  Phase 4's script deletes entries explicitly before the user row as a
  precaution.
- Assumes `AUTH_COOKIE_SECURE=False` is safe to pass only in the Playwright
  `webServer` env (not committed anywhere) — verify this doesn't leak into a
  real `.env` file during implementation.

## Success Criteria (Summary)

- `cd frontend && npx playwright test` passes locally with 1 test, 0 failures
- The same command would pass unchanged in CI once Phase 4 wires it in (no CI-specific config branches beyond `process.env.CI` checks already in the config)
- No manual database cleanup is needed between consecutive local runs

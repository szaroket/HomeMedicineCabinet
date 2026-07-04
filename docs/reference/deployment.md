# Deployment Reference

This document records everything that must be configured **outside the repository** for CI/CD to function. It is the single source of truth for a first deploy and for onboarding a new maintainer.

---

## Architecture overview

- **CI** — every PR/push to `main` or `develop` runs nine parallel gates: vulnerability scan, pre-commit, frontend build, backend typecheck (pyright), backend unit tests with a coverage floor, frontend unit tests (Vitest), frontend typecheck (`tsc -b`), backend integration tests (testcontainers-provisioned Postgres), and frontend E2E (Playwright, secrets-gated — fails fast if a required secret is missing).
- **CD** — a GitHub Release publication triggers `.github/workflows/ci-cd.yml`'s `deploy` job, which fires Render Deploy Hooks for both services. No code is ever deployed on a plain push/merge.
- **Hosting** — both services run on [Render](https://render.com/). The backend is a Python web service; the frontend is a static site. `render.yaml` (Render Blueprint) defines both services with `autoDeploy: false` so the only deploy path is the release-triggered hook.

---

## Required GitHub secrets

Set these in **GitHub → Settings → Secrets and variables → Actions → Repository secrets**.

| Secret name | Description |
|---|---|
| `RENDER_DEPLOY_HOOK_BACKEND` | Render Deploy Hook URL for `home-medicine-cabinet-backend` |
| `RENDER_DEPLOY_HOOK_FRONTEND` | Render Deploy Hook URL for `home-medicine-cabinet-frontend` |
| `DATABASE_URL` | Postgres connection string (asyncpg driver) for the shared Supabase project — used by the `frontend-e2e` job to boot the backend |
| `SUPABASE_URL` | Supabase project URL — used by the `frontend-e2e` job to boot the backend |
| `SUPABASE_ANON_KEY` | Supabase anon/public API key — used by the `frontend-e2e` job to boot the backend |
| `E2E_TEST_PASSWORD` | Password for the confirmed `e2e-hmc@example.com` test account that `auth.setup.ts` logs in as |
| `E2E_DATABASE_URL` | Direct Postgres connection string used by Playwright's `globalTeardown` to sweep the test account's rows after each E2E run |

### Obtaining the Deploy Hook URLs

1. Open the [Render dashboard](https://dashboard.render.com/).
2. Select the service (backend or frontend).
3. Go to **Settings → Deploy Hook**.
4. Copy the URL and paste it into the corresponding GitHub secret.

### E2E secrets prerequisite

The five E2E secrets above point at the same shared Supabase project used elsewhere (no dedicated test project — see `context/changes/quality-gates-wiring/plan.md`). The `e2e-hmc@example.com` account must exist and be email-confirmed in that project before `frontend-e2e` can pass; until all five secrets are set, the job fails fast at a preflight step naming the missing secret(s), and the other eight gates are unaffected.

---

## Render environment variables

These variables must be set in the Render dashboard for each service. They are declared as `sync: false` in `render.yaml`, meaning Render never overwrites them from the Blueprint — you set them once in the dashboard.

### Backend (`home-medicine-cabinet-backend`)

| Variable | Description |
|---|---|
| `FRONTEND_URL` | The public URL of the deployed frontend (e.g. `https://home-medicine-cabinet.onrender.com`) |
| `SUPABASE_URL` | Supabase project URL (Settings → API), e.g. `https://xxxx.supabase.co` |
| `SUPABASE_ANON_KEY` | Supabase anon/public API key (Settings → API → anon public) |
| `DATABASE_URL` | Postgres connection string using the **asyncpg** driver, e.g. `postgresql+asyncpg://postgres:<password>@<host>:5432/postgres` |

### Frontend (`home-medicine-cabinet-frontend`)

| Variable | Description |
|---|---|
| `VITE_API_URL` | The public URL of the deployed backend, e.g. `https://home-medicine-cabinet-backend.onrender.com` |

---

## Release procedure (how to deploy)

Because the Render Deploy Hook is fire-and-forget and deploys the **tracked branch's HEAD** (Render tracks `main`), releases **must be cut from the tip of `main` immediately after merge**. This ensures the deployed artifact matches the released commit.

1. Merge the change branch into `main` (via a squash or merge commit on GitHub).
2. Create a new version tag at `main` HEAD:
   ```bash
   git fetch origin main
   git tag <major>.<minor>.<patch> origin/main
   git push origin <major>.<minor>.<patch>
   ```
3. Go to **GitHub → Releases → Draft a new release**.
4. Select the tag you just pushed.
5. Write release notes and click **Publish release**.
6. The `deploy` job in `ci-cd.yml` is triggered automatically. It re-runs all CI gates against the release commit; if they pass, it fires the Deploy Hooks for both services.
7. Monitor the Render dashboard to confirm both services pick up the new deploy.

---

## Branch protection (one-time GitHub UI step)

To enforce CI gates on PRs, enable required status checks in **GitHub → Settings → Branches → Branch protection rules** for `main` and `develop`:

- Require status checks to pass before merging.
- Select these checks (listed by their display names): `Vulnerability Scan`, `Pre-commit Checks`, `Frontend Build`, `Backend Type Check`, `Backend Unit Tests`, `Frontend Unit Tests`, `Frontend Type Check`, `Backend Integration Tests`, `Frontend E2E Tests`.
- Enable "Require branches to be up to date before merging."

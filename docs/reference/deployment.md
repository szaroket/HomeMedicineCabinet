# Deployment Reference

This document records everything that must be configured **outside the repository** for CI/CD to function. It is the single source of truth for a first deploy and for onboarding a new maintainer.

---

## Architecture overview

- **CI** — every PR/push to `main` or `develop` runs vulnerability scan, pre-commit, frontend build, backend pyright, and backend tests with a coverage floor. The E2E job is scaffolded but disabled.
- **CD** — a GitHub Release publication triggers `.github/workflows/ci-cd.yml`'s `deploy` job, which fires Render Deploy Hooks for both services. No code is ever deployed on a plain push/merge.
- **Hosting** — both services run on [Render](https://render.com/). The backend is a Python web service; the frontend is a static site. `render.yaml` (Render Blueprint) defines both services with `autoDeploy: false` so the only deploy path is the release-triggered hook.

---

## Required GitHub secrets

Set these in **GitHub → Settings → Secrets and variables → Actions → Repository secrets**.

| Secret name | Description |
|---|---|
| `RENDER_DEPLOY_HOOK_BACKEND` | Render Deploy Hook URL for `home-medicine-cabinet-backend` |
| `RENDER_DEPLOY_HOOK_FRONTEND` | Render Deploy Hook URL for `home-medicine-cabinet-frontend` |

### Obtaining the Deploy Hook URLs

1. Open the [Render dashboard](https://dashboard.render.com/).
2. Select the service (backend or frontend).
3. Go to **Settings → Deploy Hook**.
4. Copy the URL and paste it into the corresponding GitHub secret.

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
   git tag v<major>.<minor>.<patch> origin/main
   git push origin v<major>.<minor>.<patch>
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
- Select these checks (listed by their display names): `Vulnerability Scan`, `Pre-commit Checks`, `Frontend Build`, `Backend Type Check`, `Backend Unit Tests`.
- Enable "Require branches to be up to date before merging."

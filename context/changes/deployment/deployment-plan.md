# Render Deployment Plan — Home Medicine Cabinet

## Context
The project has a completed infrastructure decision (Render, per `context/foundation/infrastructure.md`) and a working monorepo scaffold (FastAPI backend + Vite/React frontend). Before the first deploy can run, several code-level fixes are required: the backend CORS config is hardcoded to localhost, the frontend API URL is hardcoded, Python 3.14 is not yet supported by Render's buildpack, and `uv` needs an explicit install step in the build command. This plan covers all code changes, manual platform gates, smoke tests, and rollback procedures.

> **CI/CD deferred** — Phase 4 (GitHub Actions) and section 1.7 (`deploy.yml`) are intentionally skipped. Deploys are triggered manually from the Render dashboard.

---

## Phase 0: Pre-flight Checks
- [x] **Python version** — `backend/.python-version` → `3.13` ✅; `pyproject.toml` → `>=3.12` ✅
- [x] **uv package manager** — `render.yaml` build command: `pip install uv && uv sync --frozen` ✅
- [x] **`.env.local` already gitignored** — `frontend/.gitignore` has `*.local` ✅

---

## Phase 0.5: CLI Tools Installation

### Render CLI
- [x] Install — Windows: download `cli_*_windows_amd64.zip` from https://github.com/render-oss/cli/releases, extract, **rename the exe to `render.exe`**, place it in a folder on your PATH (e.g. `C:\Program Files\render\`); Mac: `brew install render`; Linux: download matching archive from the same releases page
- [x] Authenticate: `render login` (opens browser — requires Render account from Phase 4.1)
- [x] Verify: `render whoami`

### GitHub CLI
- [x] Install — Windows: `winget install --id GitHub.cli`; Mac: `brew install gh`; Ubuntu/Debian: `sudo apt install gh`
- [x] Authenticate: `gh auth login` (select: GitHub.com → HTTPS → Login with a web browser)
- [x] Verify: `gh auth status`

---

## Phase 1: Code Changes ✅ (all applied)

### 1.1 `backend/.python-version` ✅
`3.13`

### 1.2 `backend/pyproject.toml` ✅
`requires-python = ">=3.12"`

### 1.3 `backend/main.py` ✅
Env-driven CORS: `FRONTEND_URL` env var drives allowed origins; absent → localhost only.

### 1.4 `frontend/src/App.tsx` ✅
`fetch(\`${import.meta.env.VITE_API_URL ?? "http://localhost:8000"}/healthz\`)` — baked at build time.

### 1.5 `frontend/.env.local` ✅ (present locally, NOT committed)

### 1.6 `render.yaml` (new file at repo root)
```yaml
services:
  - type: web
    name: home-medicine-cabinet-backend
    runtime: python
    rootDir: backend
    buildCommand: pip install uv && uv sync --frozen
    startCommand: uv run --active uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers
    healthCheckPath: /healthz
    envVars:
      - key: FRONTEND_URL
        sync: false
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_SERVICE_ROLE_KEY
        sync: false
      - key: DATABASE_URL
        sync: false

  - type: static
    name: home-medicine-cabinet-frontend
    rootDir: frontend
    buildCommand: npm run build
    staticPublishPath: dist
    envVars:
      - key: VITE_API_URL
        sync: false
```

`sync: false` on all env vars — values are set in the Render dashboard only, never committed.

### 1.7 `.github/workflows/deploy.yml` — **SKIPPED (CI/CD deferred)**

---

## Phase 2: Local Verification (before committing)
- [x] `cd backend && uv sync` — no lock file conflicts after pyproject.toml change
- [x] `cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000` — `/v1/health/` returns `{"status":"healthy"}`
- [x] `cd frontend && npm run build` — build succeeds (with `.env.local` present)
- [x] `cd frontend && npm run dev` Frontend dev server + backend running — UI shows "healthy", no CORS errors in console
- [x] `git status` — `frontend/.env.local` does NOT appear

---

## Phase 3: Supabase Database Setup

### 3.1 [HUMAN GATE] Create Supabase account
Sign up at supabase.com with GitHub (free tier available, no credit card for dev).

### 3.2 [HUMAN GATE] Create a new project
Dashboard → New Project → choose an organisation → set a **strong database password** (save it — it cannot be retrieved later) → select a region close to your Render backend region → Create Project.

### 3.3 [HUMAN GATE] Collect credentials
Once the project finishes provisioning, collect the three values from **Project Settings**:

| Credential | Where to find it | Render env var |
|---|---|---|
| Project URL | **Data API** → "API URL" | `SUPABASE_URL` |
| `service_role` key | **API Keys** → "service_role" (secret, reveal to copy) | `SUPABASE_SERVICE_ROLE_KEY` |
| DB connection string | **Connect to your project** (button at top of dashboard) → Transaction pooler → URI | `DATABASE_URL` |

⚠️ The `service_role` key bypasses Row Level Security — treat it like a root password. Never expose it in frontend code or commit it to the repo.

---

## Phase 4: Render Services Setup

### 4.1 [HUMAN GATE] Create Render account
Sign up at render.com with GitHub (free, no credit card). Connect the monorepo.

### 4.2 [HUMAN GATE] Create backend Web Service
New → Web Service → select repo → Root Dir: `backend` → Runtime: Python 3 → Build: `pip install uv && uv sync --frozen` → Start: `uv run --active uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers` → Instance: Free.

Before saving, set env vars in the **Environment** section (use Supabase credentials from Phase 3.3):
| Key | Value |
|---|---|
| `FRONTEND_URL` | *(leave blank for now — fill in after frontend is created, see 4.3)* |
| `SUPABASE_URL` | from Phase 3.3 |
| `SUPABASE_SERVICE_ROLE_KEY` | from Phase 3.3 |
| `DATABASE_URL` | from Phase 3.3 |

Note: `$PORT` does **not** need to be added to the env vars — Render sets it automatically at runtime.

**Do not deploy yet.**

### 4.3 [HUMAN GATE] Create frontend Static Site
New → Static Site → same repo → Root Dir: `frontend` → Build: `npm run build` → Publish Dir: `dist`.

Before saving, set env vars in the **Environment** section:
| Key | Value |
|---|---|
| `VITE_API_URL` | `https://<backend-service-name>.onrender.com` |

⚠️ `VITE_API_URL` is baked at build time — must be set before the first build runs.

Once the Static Site is saved, Render shows its URL. Go back to the backend service → Environment tab and fill in:
| Key | Value |
|---|---|
| `FRONTEND_URL` | `https://<frontend-site-name>.onrender.com` |

### 4.5 [HUMAN GATE] Trigger first deploys
1. Backend: Manual Deploy → Deploy Latest Commit — watch build log for `uv sync` success
2. Verify: `https://<backend>.onrender.com/healthz` → `{"status":"healthy"}`
3. Frontend: Manual Deploy → Deploy Latest Commit
4. Verify: open the Static Site URL → app loads, "Backend status: healthy" shown

---

## Phase 5: GitHub Actions CI/CD — **SKIPPED (deferred)**

Deploys are triggered manually from the Render dashboard. Re-introduce this phase when CI/CD automation is needed.

---

## Phase 6: Post-Deploy Smoke Tests
- [x] `https://home-medicine-cabinet.onrender.com/` loads in browser
- [x] "Backend status: healthy" shown (not "unreachable")
- [x] DevTools → Network: `/v1/health/` fetch goes to Render backend URL (not localhost)
- [x] DevTools → Console: no CORS errors
- [x] `https://home-medicine-cabinet-backend.onrender.com/v1/health/` → `{"status":"healthy"}`
- [x] Swagger UI (`/docs`) works in browser — disable ad/content blockers (e.g. uBlock Origin) if fetch requests fail

---

## Phase 7: Future DB credential rotation
When Supabase credentials need to be rotated: update the three env vars in the Render dashboard → Manual Deploy on the backend service. **Never** commit Supabase credentials to any file.

---

## Edge Case Reference

| Edge case | Mitigation |
|---|---|
| Python 3.14 not on Render | `backend/.python-version` → `3.13`; `pyproject.toml` relaxed to `>=3.12` ✅ |
| uv not supported natively | Build command: `pip install uv && uv sync --frozen` ✅ |
| CORS misconfiguration | `FRONTEND_URL` drives origins; absent → localhost only, no wildcard ✅ |
| `VITE_API_URL` baked at build time | Must be set in Render dashboard before first frontend build |
| Secrets in render.yaml | All env vars use `sync: false` — values in dashboard only ✅ |
| Cold starts on free tier | Accept for solo dev phase; upgrade to $7/mo when sharing externally |
| No CLI rollback | Use Render dashboard → Events → Rollback, or Render REST API |
| SPA deep-link refresh → 404 | Static site has no rewrite rule; refreshing on a client-side route (e.g. `/cabinet`) 404s because Render looks for a literal file. Fix: add to `render.yaml` static service — `routes: [{ type: rewrite, source: /*, destination: /index.html }]`. Tracked for F-04 (`ci-cd-wiring`), not yet applied. |

---

## Rollback Procedure

**Service rollback** (no DB schema change involved):
- Dashboard: Services → Events → prior deploy → "Rollback to this deploy" (~2–3 min)
- REST API: `POST https://api.render.com/v1/services/{id}/rollback-deploy` with `{"deployId":"<id>"}` and `Authorization: Bearer <api-key>`
- Git: `git revert <sha>` → push → manual deploy from Render dashboard

**CORS broken after deploy** → update `FRONTEND_URL` in backend env tab → manual redeploy (no code change needed).

**Wrong `VITE_API_URL`** → update in Static Site env tab → manual redeploy (Render rebuilds frontend).

**Supabase credentials rotated** → update three env vars in Render dashboard → manual backend redeploy.

---

## Critical Files

| File | Status |
|---|---|
| `backend/.python-version` | ✅ Done |
| `backend/pyproject.toml` | ✅ Done |
| `backend/uv.lock` | ✅ Done |
| `backend/main.py` | ✅ Done |
| `frontend/src/App.tsx` | ✅ Done |
| `frontend/.env.local` | ✅ Present locally (not committed) |
| `render.yaml` | ✅ Done |
| `.github/workflows/deploy.yml` | ⏭ Skipped (CI/CD deferred) |
| Render CLI | Install & authenticate before Phase 4 |
| GitHub CLI | Install & authenticate before Phase 4 |

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

## Phase 1: Code Changes ✅ (all applied)

### 1.1 `backend/.python-version` ✅
`3.13`

### 1.2 `backend/pyproject.toml` ✅
`requires-python = ">=3.12"`

### 1.3 `backend/main.py` ✅
Env-driven CORS: `FRONTEND_URL` env var drives allowed origins; absent → localhost only.

### 1.4 `frontend/src/App.tsx` ✅
`fetch(\`${import.meta.env.VITE_API_URL ?? "http://localhost:8000"}/health\`)` — baked at build time.

### 1.5 `frontend/.env.local` ✅ (present locally, NOT committed)

### 1.6 `render.yaml` (new file at repo root)
```yaml
services:
  - type: web
    name: home-medicine-cabinet-backend
    runtime: python
    rootDir: backend
    buildCommand: pip install uv && uv sync --frozen
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /health
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
- [ ] `cd backend && uv sync` — no lock file conflicts after pyproject.toml change
- [ ] `cd backend && uv run uvicorn main:app --host 0.0.0.0 --port 8000` — `/health` returns `{"status":"healthy"}`
- [ ] `cd frontend && npm run build` — build succeeds (with `.env.local` present)
- [ ] Frontend dev server + backend running — UI shows "healthy", no CORS errors in console
- [ ] `git status` — `frontend/.env.local` does NOT appear

---

## Phase 3: Render Services Setup

### 3.1 [HUMAN GATE] Create Render account
Sign up at render.com with GitHub (free, no credit card). Connect the monorepo.

### 3.2 [HUMAN GATE] Create backend Web Service
New → Web Service → select repo → Root Dir: `backend` → Runtime: Python 3 → Build: `pip install uv && uv sync --frozen` → Start: `uvicorn main:app --host 0.0.0.0 --port $PORT` → Instance: Free.
**Do not deploy yet** — set env vars first.

### 3.3 [HUMAN GATE] Create frontend Static Site
New → Static Site → same repo → Root Dir: `frontend` → Build: `npm run build` → Publish Dir: `dist`.
**Do not deploy yet** — set env vars first.

### 3.4 [HUMAN GATE] Set backend env vars
In backend Web Service → Environment tab:
| Key | Value |
|---|---|
| `FRONTEND_URL` | *(leave blank until frontend URL known — see 3.6)* |
| `SUPABASE_URL` | `https://placeholder.supabase.co` *(update when DB created)* |
| `SUPABASE_SERVICE_ROLE_KEY` | `placeholder` *(update when DB created)* |
| `DATABASE_URL` | `postgresql://placeholder` *(update when DB created)* |

### 3.5 [HUMAN GATE] Set frontend env var
In Static Site → Environment tab. Backend URL format: `https://home-medicine-cabinet-backend.onrender.com`.
| Key | Value |
|---|---|
| `VITE_API_URL` | `https://<backend-service-name>.onrender.com` |

⚠️ This MUST be set before the first frontend build runs — Vite bakes it at compile time.

### 3.6 [HUMAN GATE] Set FRONTEND_URL in backend
After Static Site is created, Render shows its URL. Go back to backend env vars and fill in:
| Key | Value |
|---|---|
| `FRONTEND_URL` | `https://<frontend-site-name>.onrender.com` |
Then trigger a manual backend redeploy.

### 3.7 [HUMAN GATE] Trigger first deploys
1. Backend: Manual Deploy → Deploy Latest Commit — watch build log for `uv sync` success
2. Verify: `https://<backend>.onrender.com/health` → `{"status":"healthy"}`
3. Frontend: Manual Deploy → Deploy Latest Commit
4. Verify: open the Static Site URL → app loads, "Backend status: healthy" shown

---

## Phase 4: GitHub Actions CI/CD — **SKIPPED (deferred)**

Deploys are triggered manually from the Render dashboard. Re-introduce this phase when CI/CD automation is needed.

---

## Phase 5: Post-Deploy Smoke Tests
- [ ] `https://<frontend>.onrender.com` loads in browser
- [ ] "Backend status: healthy" shown (not "unreachable")
- [ ] DevTools → Network: `/health` fetch goes to Render backend URL (not localhost)
- [ ] DevTools → Console: no CORS errors
- [ ] `https://<backend>.onrender.com/health` → `{"status":"healthy"}`

---

## Phase 6: Future Supabase Wiring (deferred)
When the database layer is implemented:
1. Create a Supabase project
2. Rotate the three backend env vars in the Render dashboard (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`)
3. Trigger a manual backend redeploy
4. **Never** commit Supabase credentials to any file

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

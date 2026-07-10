# Home Medicine Cabinet

A web app for managing your home medicine cabinet. Track medications from the Polish approved drug registry — what you have, how many packages remain, when they expire, and whether your supply will last through an active course. In-app notifications alert you to upcoming expiry, low stock on important medications, and run-out risk. The interface is in Polish.

The project was created as part of the [10xDevs 3.0](https://www.10xdevs.pl/) training.

## Status

**MVP complete and deployed.** Every slice on the [roadmap](context/foundation/roadmap.md) is done — from registry-backed medication entry through cabinet management, dosage tracking, notifications, and the dashboard. The app is live on Render:

- **Frontend:** https://home-medicine-cabinet.onrender.com
- **Backend API:** https://home-medicine-cabinet-backend.onrender.com (`/docs` for the OpenAPI UI)

> Both services run on Render's free tier, so the first request after a period of inactivity may take 30–60 seconds while the backend cold-starts.

## What the app supports

- **Accounts** — register with email + password (with a confirm-password check), log in, log out, and permanently delete your account and all associated data. Cabinet data is strictly isolated per account.
- **Registry-backed add flow** — search the official Polish approved-medicines registry via autocomplete, pick a tablet count, enter package count and expiry date, and optionally record a partially-opened package. Adding the same drug + tablet count + expiry date merges into the existing entry and re-normalises the tablet pool. Non-tablet medications (syrups, drops) are tracked by name, package count, and expiry only.
- **Cabinet list** — filter by status (valid / expiring soon / expired / out-of-stock) and category (important / used), sort by name, paginate, and search by medication name or active ingredient. Each entry shows producer, route of administration, and links to the drug leaflet and specification from the registry. Fully responsive down to mobile widths.
- **Manage entries** — increment/decrement package count, update the partial tablet count, and delete entries with explicit confirmation. Important/used entries stay at zero packages so you can restock.
- **Important category** — mark entries as important, set a global minimum package count, and get an attention badge when stock falls below the minimum or the medication is expiring/expired.
- **Dosage tracking (used category)** — assign a schedule (times × tablets, per day or per week) with an optional end date; see the estimated finish date or days-of-supply-vs-days-remaining. Non-tablet medications get start/end date tracking only.
- **Notifications** — a notification bell with unread count and a notification center listing expiry alerts, below-minimum important stock, and used medications at risk of running out. Dismiss individual notifications; configure the expiry and close-to-finish thresholds in settings.
- **Dashboard** — the landing screen after login, showing summary counts (total / valid / expiring soon / expired / out-of-stock) that link straight to the pre-filtered cabinet list.
- **Public landing page** — an unauthenticated welcome page describing the app, with links to log in and register.

## Quality & CI/CD

Every push and PR to `main`/`develop` runs parallel CI gates: vulnerability scan, pre-commit lint/format, backend typecheck (pyright) and unit tests (pytest, with a coverage floor), backend integration tests against a testcontainers Postgres, frontend build, typecheck (`tsc -b`), and unit tests (Vitest), plus a Playwright E2E golden path. Deployment is release-gated — publishing a GitHub Release fires the Render deploy hooks; ordinary merges never deploy. See [`docs/reference/deployment.md`](docs/reference/deployment.md).

## Running locally

Monorepo: `backend/` (FastAPI + Python 3.13, [uv](https://docs.astral.sh/uv/), SQLModel + Alembic) and `frontend/` (Vite + React 19 + TypeScript + Tailwind, npm). Both talk to [Supabase](https://supabase.com/) (Auth + PostgreSQL). You need both running.

### Supabase

The backend uses [Supabase](https://supabase.com/) for two things: **authentication** (Supabase Auth issues JWTs, which the API verifies against the project's JWKS endpoint) and the **Postgres database** (the app connects directly via `DATABASE_URL`).

Create a Supabase project (cloud at [supabase.com](https://supabase.com/dashboard), or local via the [Supabase CLI](https://supabase.com/docs/guides/local-development)), then grab these values for `backend/.env`:

- `SUPABASE_URL` — Project URL (Settings → API), e.g. `https://xxxx.supabase.co`
- `SUPABASE_ANON_KEY` — the `anon` / public API key (Settings → API)
- `DATABASE_URL` — the Postgres connection string (Settings → Database), using the **asyncpg** driver, e.g. `postgresql+asyncpg://postgres:<password>@<host>:5432/postgres`

### Backend

```bash
cd backend
cp .env.structure .env          # then fill in the Supabase values above
uv sync                         # install dependencies
uv run alembic upgrade head     # apply database migrations
uv run uvicorn app.main:app --reload
```

API runs at `http://localhost:8000` (docs at `/docs`).

### Frontend

```bash
cd frontend
cp .env.structure .env.local    # VITE_API_URL defaults to http://localhost:8000
npm install
npm run dev
```

App runs at the URL Vite prints (default `http://localhost:5173`).

## Key documents
- [`context/foundation/prd.md`](context/foundation/prd.md) — product requirements
- [`context/foundation/tech-stack.md`](context/foundation/tech-stack.md) — tech stack
- [`context/foundation/infrastructure.md`](context/foundation/infrastructure.md) — deployment platform
- [`context/foundation/roadmap.md`](context\foundation\roadmap.md) — implementation roadmap
- [`docs/reference/deployment.md`](docs/reference/deployment.md) — CI/CD setup and release procedure

## Requirements

### Mandatory Requirements
- [x] Access control mechanism appropriate for the application type (e.g., login screen)
- [x] Data management — creating, reading, updating, and deleting items (CRUD) in a way that makes sense for the application domain
- [x] Business logic (with or without AI - OpenRouter is just one integration option)
- [x] Context documents (e.g., prd.md, infrastructure.md, roadmap.md)
- [x] Tests — at least one test verifying functionality from the user's perspective
- [x] CI/CD pipeline — building the application and verifying quality automatically

#### Optional (preferred):
- [x] Project available at a public URL — live at https://home-medicine-cabinet.onrender.com

# Home Medicine Cabinet

A web app for managing your home medicine cabinet. Track medications from the Polish approved drug registry — what you have, how many packages remain, when they expire, and whether your supply will last through an active course. In-app notifications alert you to upcoming expiry, low stock on important medications, and run-out risk.

The project was created as part of the [10xDevs 3.0](https://www.10xdevs.pl/) training.

## Running locally

Monorepo: `backend/` (FastAPI + Python 3.13, [uv](https://docs.astral.sh/uv/)) and `frontend/` (Vite + React 19 + TypeScript, npm). You need both running.

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
- [`context\foundation\roadmap.md`](context\foundation\roadmap.md) — implementation roadmap
- [`docs/reference/deployment.md`](docs/reference/deployment.md) — CI/CD setup and release procedure

## Requitements

### Mandatory Requirements
- [x] Access control mechanism appropriate for the application type (e.g., login screen)
- [ ] Data management — creating, reading, updating, and deleting items (CRUD) in a way that makes sense for the application domain
- [x] Business logic (with or without AI - OpenRouter is just one integration option)
- [x] Context documents (e.g., prd.md, infrastructure.md, roadmap.md)
- [ ] Tests — at least one test verifying functionality from the user's perspective
- [x] CI/CD pipeline — building the application and verifying quality automatically

#### Optional (preferred):
- [ ] Project available at a public URL, in the App Store, or as an installable package (if the application type does not allow this, omit this from the project description)

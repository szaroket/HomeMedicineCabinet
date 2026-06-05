# Repository Guidelines

Home Medicine Cabinet — a Polish-language web app for tracking medication inventory. Monorepo: `backend/` (FastAPI + Python 3.13, uv) and `frontend/` (Vite + React 19 + TypeScript, npm).

## Hard Rules

- Never run `git push --force` on `main`.
- Never commit secrets or `.env` files — no secret handling is wired yet; use environment variables only.
- `context/` is the bootstrap chain's source of truth — do not delete or restructure it.
- All user-facing text must be in Polish.
- Pre-commit hooks run automatically on staged files; do not bypass with `--no-verify` without fixing the underlying lint/format error.

## Project Structure

```
backend/
  app/
    main.py          sole entry point: create_app() factory, middleware, uvicorn __main__
    core/
      config.py      pydantic-settings — single source of truth for env config
    db/
      connector.py   async engine, session factory, get_session dependency, init_db
    api/
      v1/
        router.py    aggregates all domain routers under prefix /api/v1
        health/
          router.py  GET /api/v1/health/ — router layer only
        auth/
          router.py  route definitions only
          service.py business logic
          crud.py    database operations
        medicines/
          router.py
          service.py
          crud.py
  pyproject.toml     dependencies and uv config
frontend/
  e2e/               Playwright specs (*.spec.ts) + auth.setup.ts
  src/
    app/             composition root: App, providers, router.tsx, layouts/
    components/
      ui/            shared, domain-agnostic primitives (button, input, modal)
      layout/        shared composite layout pieces
    features/        one folder per domain feature; each owns its slice
      <feature>/     components/ hooks/ api/ schemas/ types.ts (+ store.ts if needed)
    lib/             configured third-party wrappers: api-client, query-client, utils (cn)
    hooks/           generic shared hooks only
    types/           genuinely cross-feature types only
    utils/           shared pure helpers
    test/setup.ts    Vitest setup (jest-dom, cleanup)
  vite.config.ts     Vite + @tailwindcss/vite + Vitest (test block) + @/ alias
context/             project documentation — PRD, shape-notes, tech-stack hand-off
docs/
  reference/
    backend-structure.md   backend layer rules and conventions for adding new domains
```

See `context/foundation/prd.md` for full functional requirements and business logic.
See `docs/reference/backend-structure.md` for backend directory rules, layer responsibilities, and instructions for adding new domains or API versions.
See `docs/reference/frontend-structure.md` for frontend directory rules, the feature-based layout, and instructions for adding new features.

### Backend layer rules

- `app/main.py` — app factory and middleware only. No domain routes.
- `app/core/config.py` — pydantic-settings `Settings` singleton; import `settings` from here everywhere.
- `app/db/connector.py` — async engine, session factory, `get_session` dependency, `init_db`.
- `app/api/v1/router.py` — imports and includes every domain router. No route logic here.
- Domain directories live under `app/api/v1/<domain>/`. URL paths mirror the directory path: `app/api/v1/<domain>/<endpoint>` → `/api/v1/<domain>/<endpoint>`.
- `router.py` — route decorators only; calls service functions.
- `service.py` — business logic and orchestration; calls crud functions.
- `crud.py` — raw database operations; no business logic.
- Domains with no DB access (e.g. `health/`) may omit `service.py` and `crud.py`.
- To add a new domain: create `app/api/v1/<domain>/` with `__init__.py`, `router.py`, `service.py`, `crud.py`; import and include the router in `app/api/v1/router.py`.

### Frontend structure rules

- **Feature-based layout**: most code lives in `src/features/<feature>/`. A feature owns its `components/`, `hooks/`, `api/` (typed fetchers + TanStack Query hooks + query-key factory), `schemas/` (zod), and `types.ts`. Create feature folders **just-in-time** per roadmap slice — do not scaffold all features up front, and do not create empty `api/`/`schemas/` until needed.
- **Shared layer is thin**: only genuinely cross-feature code goes in top-level `components/`, `hooks/`, `types/`, `utils/`, `lib/`. Promote feature code to shared only when a second feature needs it ("colocate first, extract later"). Domain-agnostic UI primitives live in `components/ui/`; anything that knows the domain stays in its feature.
- **Composition at `app/`**: routing, providers, and layouts live in `src/app/`. Compose features there; avoid cross-feature imports.
- **No barrel files**: import directly via the `@/*` path alias (configured in `tsconfig.app.json` + `vite.config.ts`). Avoid `index.ts` re-exports — they hurt Vite tree-shaking and hide circular dependencies.
- **Data access**: FastAPI is the sole backend client — the frontend never calls Supabase/DB directly. One `lib/api-client.ts` wraps `${VITE_API_URL}/api/v1/...` and attaches `Authorization: Bearer <jwt>`; per-feature `api/` functions are the typed REST contract, Query hooks are the cache layer.
- **Tailwind v4**: the CSS entry is `src/index.css` (`@import "tailwindcss"` + an `@theme` token block — config lives in CSS). The `cn()` helper (clsx + tailwind-merge) lives in `lib/utils.ts`.
- Full rules and recommended tree: `docs/reference/frontend-structure.md`. Rationale, paradigm comparison, and migration path: `context/changes/frontend-structure/research.md`.

## Build, Test, and Dev Commands

**Backend** (run from `backend/`):
- `uv run uvicorn app.main:app --reload` — start dev server
- `uv run pytest` — run all backend tests (pytest + pytest-asyncio + httpx)
- `uv run ruff check . && uv run ruff format --check .` — lint and format check

**Frontend** (run from `frontend/`):
- `npm run dev` — start Vite dev server
- `npm run build` — TypeScript compile + Vite production build (`tsc -b && vite build`)
- `npm run lint` — ESLint across all `*.ts`/`*.tsx` files
- `npx prettier --check src/` — format check

**Pre-commit** (repo root):
- `pre-commit run --all-files` — run all hooks against every file

## Coding Style & Naming Conventions

Backend: Python 3.13, enforced by ruff v0.11.12 (lint + format). See `.pre-commit-config.yaml` for active rule set. Place SQLModel table models in `backend/app/api/v1/<domain>/models.py` (one file per domain). Place FastAPI routers in `backend/app/api/v1/<domain>/router.py`; router files use `snake_case`.

Docstrings follow the **Google style** convention (`Args:`/`Returns:`/`Raises:` sections), enforced by ruff's pydocstyle rules (`convention = "google"` in `backend/pyproject.toml`). Docstrings are not required everywhere (`D1` rules are ignored), but any docstring you write must follow Google formatting. Alembic migrations under `backend/migrations/` are exempt.

Frontend: TypeScript strict mode (`frontend/tsconfig.app.json`). **Files and folders use `kebab-case`** (`medication-form.tsx`, `use-debounce.ts`, `api-client.ts`) — chosen for cross-OS safety (Windows dev, Linux deploy). Component *identifiers* are still `PascalCase` (`export function MedicationForm`); only the filename is kebab-case. Folders: lowercase, plural for type buckets (`components/`, `hooks/`), singular for feature names (`auth/`, `cabinet/`). ESLint enforces `react-hooks` and `react-refresh` rules; Prettier formats `src/**/*.{ts,tsx,css}`.

## Testing Guidelines

Backend: pytest with pytest-asyncio; test files in `backend/tests/` (directory not yet created — place tests there). Use `httpx.AsyncClient` as the FastAPI test client.

Frontend: Vitest + React Testing Library (not yet configured — add `vitest.config.ts` when writing first test). Playwright covers one golden-path E2E: login → add medication → verify cabinet entry.

## Commit & Pull Request Guidelines

Use Conventional Commits prefixes: `feat:` new features, `fix:` bug fixes, `docs:` documentation, `refactor:` code changes without behaviour change, `test:` adding/updating tests, `chore:` tooling and config. No CI workflow exists yet — no automated gate on PRs. Run `pre-commit run --all-files` and `npm run build` manually before opening a PR.

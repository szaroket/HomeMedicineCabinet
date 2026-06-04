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
    v1/
      router.py      aggregates all domain routers under prefix /v1
      health/
        router.py    GET /v1/health/ — router layer only
      auth/
        router.py    route definitions only
        service.py   business logic
        crud.py      database operations
      medicines/
        router.py
        service.py
        crud.py
  pyproject.toml     dependencies and uv config
frontend/
  src/
    components/      React components (PascalCase.tsx)
    pages/           page-level components
    hooks/           custom React hooks
  vite.config.ts
context/             project documentation — PRD, shape-notes, tech-stack hand-off
docs/
  reference/
    backend-structure.md   backend layer rules and conventions for adding new domains
```

See `context/foundation/prd.md` for full functional requirements and business logic.
See `docs/reference/backend-structure.md` for backend directory rules, layer responsibilities, and instructions for adding new domains or API versions.

### Backend layer rules

- `app/main.py` — app factory and middleware only. No domain routes.
- `app/v1/router.py` — imports and includes every domain router. No route logic here.
- Domain directories live under `app/v1/<domain>/`. URL paths mirror the directory path: `app/v1/<domain>/<endpoint>` → `/v1/<domain>/<endpoint>`.
- `router.py` — route decorators only; calls service functions.
- `service.py` — business logic and orchestration; calls crud functions.
- `crud.py` — raw database operations; no business logic.
- Domains with no DB access (e.g. `health/`) may omit `service.py` and `crud.py`.
- To add a new domain: create `app/v1/<domain>/` with `__init__.py`, `router.py`, `service.py`, `crud.py`; import and include the router in `app/v1/router.py`.

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

Backend: Python 3.13, enforced by ruff v0.11.12 (lint + format). See `.pre-commit-config.yaml` for active rule set. Place SQLModel table models in `backend/app/v1/<domain>/models.py` (one file per domain). Place FastAPI routers in `backend/app/v1/<domain>/router.py`; router files use `snake_case`.

Frontend: TypeScript strict mode (`frontend/tsconfig.app.json`). Components `PascalCase.tsx`, utilities `camelCase.ts`. ESLint enforces `react-hooks` and `react-refresh` rules; Prettier formats `src/**/*.{ts,tsx,css}`.

## Testing Guidelines

Backend: pytest with pytest-asyncio; test files in `backend/tests/` (directory not yet created — place tests there). Use `httpx.AsyncClient` as the FastAPI test client.

Frontend: Vitest + React Testing Library (not yet configured — add `vitest.config.ts` when writing first test). Playwright covers one golden-path E2E: login → add medication → verify cabinet entry.

## Commit & Pull Request Guidelines

Use Conventional Commits prefixes: `feat:` new features, `fix:` bug fixes, `docs:` documentation, `refactor:` code changes without behaviour change, `test:` adding/updating tests, `chore:` tooling and config. No CI workflow exists yet — no automated gate on PRs. Run `pre-commit run --all-files` and `npm run build` manually before opening a PR.

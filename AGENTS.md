# Repository Guidelines

Home Medicine Cabinet — a Polish-language web app for tracking medication inventory. Monorepo: `backend/` (FastAPI + Python 3.14, uv) and `frontend/` (Vite + React 19 + TypeScript, npm).

## Hard Rules

- Never run `git push --force` on `main`.
- Never commit secrets or `.env` files — no secret handling is wired yet; use environment variables only.
- `context/` is the bootstrap chain's source of truth — do not delete or restructure it.
- All user-facing text must be in Polish.
- Pre-commit hooks run automatically on staged files; do not bypass with `--no-verify` without fixing the underlying lint/format error.

## Project Structure

```
backend/
  main.py          entry point
  models/          SQLModel table models, one file per domain entity
  routers/         FastAPI routers, one file per feature area
  pyproject.toml   dependencies and uv config
frontend/
  src/
    components/    React components (PascalCase.tsx)
    pages/         page-level components
    hooks/         custom React hooks
  vite.config.ts
context/           project documentation — PRD, shape-notes, tech-stack hand-off
```

See `@context/foundation/prd.md` for full functional requirements and business logic.

## Build, Test, and Dev Commands

**Backend** (run from `backend/`):
- `uv run uvicorn main:app --reload` — start dev server
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

Backend: Python 3.14, enforced by ruff v0.11.12 (lint + format). See `@.pre-commit-config.yaml` for active rule set. Place SQLModel table models in `backend/models/`, one file per domain entity (`medication.py`, `user.py`, etc.). Place FastAPI routers in `backend/routers/`, one file per feature area; router files use `snake_case`.

Frontend: TypeScript strict mode (`@frontend/tsconfig.app.json`). Components `PascalCase.tsx`, utilities `camelCase.ts`. ESLint enforces `react-hooks` and `react-refresh` rules; Prettier formats `src/**/*.{ts,tsx,css}`.

## Testing Guidelines

Backend: pytest with pytest-asyncio; test files in `backend/tests/` (directory not yet created — place tests there). Use `httpx.AsyncClient` as the FastAPI test client.

Frontend: Vitest + React Testing Library (not yet configured — add `vitest.config.ts` when writing first test). Playwright covers one golden-path E2E: login → add medication → verify cabinet entry.

## Commit & Pull Request Guidelines

Use Conventional Commits prefixes: `feat:` new features, `fix:` bug fixes, `docs:` documentation, `refactor:` code changes without behaviour change, `test:` adding/updating tests, `chore:` tooling and config. No CI workflow exists yet — no automated gate on PRs. Run `pre-commit run --all-files` and `npm run build` manually before opening a PR.

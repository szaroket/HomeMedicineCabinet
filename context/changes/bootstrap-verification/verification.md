---
bootstrapped_at: 2026-05-29T00:00:00Z
starter_id: fastapi + vite-react (monorepo)
starter_name: "FastAPI (backend) + Vite React TypeScript (frontend)"
project_name: home-medicine-cabinet
language_family: multi
package_manager: uv (backend) / npm (frontend)
cwd_strategy: "native-cwd into backend/ (FastAPI) + subdir-then-move into frontend/ (Vite React)"
bootstrapper_confidence: first-class
phase_3_status: ok
audit_command: "npm audit --json (frontend); pip-audit --format json (backend — unavailable)"
---

## Hand-off

```yaml
starter_id: fastapi
package_manager: uv
project_name: home-medicine-cabinet
hints:
  language_family: multi
  team_size: solo
  deployment_target: fly
  ci_provider: github-actions
  ci_default_flow: auto-deploy-on-merge
  bootstrapper_confidence: first-class
  path_taken: custom
  quality_override: false
  self_check_answers:
    typed: true
    from_official_starter: true
    conventions: true
    docs_current: true
    can_judge_agent: false
  has_auth: true
  has_payments: false
  has_realtime: false
  has_ai: false
  has_background_jobs: false
  frontend_starter_id: vite-react
  frontend_deployment_target: cloudflare-pages
  frontend_css: tailwind
  database: postgresql
  database_orm: sqlmodel
  database_host: neon
  auth_method: jwt
  repo_structure: monorepo
  monorepo_layout: "backend/ (FastAPI/uv) + frontend/ (Vite React/npm) — single Git repo, no dedicated orchestrator"
  backend_linter: ruff
  backend_formatter: ruff
  frontend_linter: eslint
  frontend_formatter: prettier
  pre_commit_framework: pre-commit
  pre_commit_scope: "lint + format checks only (ruff check, ruff format --check, eslint, prettier --check)"
  backend_test_framework: pytest
  backend_test_libs: "pytest-asyncio (async endpoint tests), httpx (FastAPI test client), pytest-cov (coverage)"
  frontend_test_framework: vitest
  frontend_test_libs: "@testing-library/react, @testing-library/jest-dom, @testing-library/user-event"
  frontend_e2e_framework: playwright
  frontend_e2e_scope: "single golden-path test: login → add medication → see it in cabinet"
  test_runner_location: ci-only
```

**Why this stack**: Solo developer building a Polish-language medication cabinet web app in 2 weeks after-hours. Custom path taken because the developer has an explicit Python/FastAPI constraint from shaping. FastAPI clears all four agent-friendly gates within the Python family (typed via Pydantic, convention-based, popular in Python training data, well-documented). The database is PostgreSQL with SQLModel (SQLAlchemy + Pydantic combined — type-safe, fits FastAPI naturally), hosted on Neon's free tier (0.5 GB, always free). The architecture is a single-repository monorepo: backend/ (FastAPI/uv) and frontend/ (Vite React TypeScript SPA/npm + Tailwind CSS for styling). No monorepo orchestrator — a flat two-directory layout with path-filtered GitHub Actions jobs is the practical approach for this polyglot stack. Backend deploys to Fly.io; frontend deploys to Cloudflare Pages; CI auto-deploys on merge. Auth is in scope (FR-001, FR-002) via JWT tokens (python-jose + passlib for password hashing); the React SPA stores the token and sends it as a Bearer header on every request. Notifications are computed on page load so no background queue is needed. Code quality is gated by a `pre-commit` hook running fast lint and format checks on staged files (ruff handles both lint and format on the Python side; ESLint + Prettier on the React/TypeScript side). Backend tests run on pytest (pytest-asyncio, httpx, pytest-cov); frontend tests use Vitest + React Testing Library + Playwright for one golden-path E2E.

## Pre-scaffold verification

| Signal        | Value                                     | Severity | Notes                                          |
| ------------- | ----------------------------------------- | -------- | ---------------------------------------------- |
| npm package   | create-vite v9.0.7 published 2026-05-11   | fresh    | resolved from vite-react cmd_template          |
| GitHub repo   | tiangolo/fastapi — not checked            | n/a      | gh CLI not available in this shell             |
| GitHub repo   | vitejs/vite — not checked                 | n/a      | docs_url is not a GitHub URL; no check run     |

## Scaffold log

### Backend (FastAPI)

**Resolved invocation**: `mkdir backend && uv init . && uv add fastapi "uvicorn[standard]" --native-tls`
**Strategy**: native-cwd into backend/ subdirectory
**Exit code**: 0
**Files written by CLI**: pyproject.toml, main.py, README.md, .python-version, uv.lock, .venv/ (19 packages installed)
**Pre-existing files preserved**: none (backend/ was empty)
**Packages installed**: fastapi==0.136.3, uvicorn==0.48.0, pydantic==2.13.4, starlette==1.2.0 + 15 transitive

### Frontend (Vite React)

**Resolved invocation**: `npm create vite@latest .bootstrap-scaffold -- --template react-ts`
**Strategy**: scaffold into temp directory then move files up into frontend/
**Exit code**: 0
**Files moved**: 10 (eslint.config.js, index.html, package.json, public/, README.md, src/, tsconfig.app.json, tsconfig.json, tsconfig.node.json, vite.config.ts)
**Conflicts (.scaffold siblings)**: none
**.gitignore handling**: absent in scaffold (Vite omits .gitignore from the react-ts template output at this invocation)
**.bootstrap-scaffold cleanup**: deleted

**npm install**: 152 packages added, 0 vulnerabilities found.

## Post-scaffold audit

### Frontend (npm audit)

**Tool**: `npm audit --json`
**Summary**: 0 CRITICAL, 0 HIGH, 0 MODERATE, 0 LOW
**Direct vs transitive**: not applicable (0 findings)

Clean tree.

### Backend (pip-audit)

**Tool**: `pip-audit --format json`
**Status**: failed to run
**Reason**: pip-audit not installed in shell PATH. Install with `uv tool install pip-audit` or `pip install pip-audit` and re-run manually.

## Hints recorded but not acted on

| Hint                       | Value                                                                                 |
| -------------------------- | ------------------------------------------------------------------------------------- |
| bootstrapper_confidence    | first-class                                                                           |
| quality_override           | false                                                                                 |
| path_taken                 | custom                                                                                |
| self_check_answers         | typed: true, from_official_starter: true, conventions: true, docs_current: true, can_judge_agent: false |
| deployment_target          | fly (backend) + cloudflare-pages (frontend)                                           |
| ci_provider                | github-actions                                                                        |
| ci_default_flow            | auto-deploy-on-merge                                                                  |
| has_auth                   | true                                                                                  |
| has_payments               | false                                                                                 |
| has_realtime               | false                                                                                 |
| has_ai                     | false                                                                                 |
| has_background_jobs        | false                                                                                 |
| frontend_css               | tailwind                                                                              |
| database                   | postgresql                                                                            |
| database_orm               | sqlmodel                                                                              |
| database_host              | neon                                                                                  |
| auth_method                | jwt                                                                                   |
| backend_linter             | ruff                                                                                  |
| backend_formatter          | ruff                                                                                  |
| frontend_linter            | eslint (installed via vite-react starter)                                             |
| frontend_formatter         | prettier                                                                              |
| pre_commit_framework       | pre-commit                                                                            |
| pre_commit_scope           | lint + format checks only                                                             |
| backend_test_framework     | pytest                                                                                |
| backend_test_libs          | pytest-asyncio, httpx, pytest-cov                                                     |
| frontend_test_framework    | vitest                                                                                |
| frontend_test_libs         | @testing-library/react, @testing-library/jest-dom, @testing-library/user-event       |
| frontend_e2e_framework     | playwright                                                                            |
| frontend_e2e_scope         | single golden-path test: login → add medication → see it in cabinet                  |
| test_runner_location       | ci-only                                                                               |

## Next steps

Next: a future skill will set up agent context (CLAUDE.md, AGENTS.md). For now, your project is scaffolded and verified — happy hacking.

Useful manual steps in the meantime:
- `git init` (if you have not already) to start your own repo history.
- Review any `.scaffold` siblings the conflict policy created and decide which version to keep (none in this run).
- Install pip-audit to run the backend security audit: `uv tool install pip-audit --native-tls`, then run `pip-audit --format json` from `backend/`.
- Add Tailwind CSS to the frontend: `npm install -D tailwindcss @tailwindcss/vite` (hinted in tech-stack.md but not installed by the Vite starter).
- Add SQLModel + python-jose + passlib to the backend: `uv add sqlmodel python-jose passlib --native-tls` (auth + ORM stack from tech-stack.md hints).
- Configure pre-commit: add `.pre-commit-config.yaml` at repo root referencing ruff hooks (backend) and eslint/prettier hooks (frontend).

---
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
---

## Why this stack

Solo developer building a Polish-language medication cabinet web app in 2 weeks after-hours. Custom path taken because the developer has an explicit Python/FastAPI constraint from shaping. FastAPI clears all four agent-friendly gates within the Python family (typed via Pydantic, convention-based, popular in Python training data, well-documented). The database is PostgreSQL with SQLModel (SQLAlchemy + Pydantic combined — type-safe, fits FastAPI naturally), hosted on Neon's free tier (0.5 GB, always free). The architecture is a single-repository monorepo: backend/ (FastAPI/uv) and frontend/ (Vite React TypeScript SPA/npm + Tailwind CSS for styling). No monorepo orchestrator — a flat two-directory layout with path-filtered GitHub Actions jobs is the practical approach for this polyglot stack. Backend deploys to Fly.io; frontend deploys to Cloudflare Pages; CI auto-deploys on merge. Auth is in scope (FR-001, FR-002) via JWT tokens (python-jose + passlib for password hashing); the React SPA stores the token and sends it as a Bearer header on every request. Notifications are computed on page load so no background queue is needed. Code quality is gated by a `pre-commit` hook running fast lint and format checks on staged files (ruff handles both lint and format on the Python side — replacing black/flake8/isort with a single fast tool; ESLint + Prettier on the React/TypeScript side); the gate stays under a few seconds so commits do not slow down. Backend tests run on pytest (with pytest-asyncio for async endpoint coverage, httpx as the FastAPI test client, and pytest-cov for coverage reporting); tests are gated in CI on every push and PR, not in pre-commit, so commits stay fast. Frontend tests use Vitest (Vite-native — reuses the existing Vite config, transforms, and aliases) with React Testing Library for component tests, and Playwright covers one golden-path E2E flow (login → add medication → see it in cabinet) that verifies the primary user journey on every deploy. Self-check returned 4/5 — React is new territory for the developer, flagged for extra care when reviewing agent-generated frontend code.

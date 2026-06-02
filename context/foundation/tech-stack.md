---
starter_id: vite-react+fastapi
package_manager: npm+uv
project_name: home-medicine-cabinet
hints:
  language_family: multi
  team_size: solo
  deployment_target: render
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
  frontend_deployment_target: render-static-site
  frontend_css: tailwind
  database: postgresql
  database_provider: supabase
  database_orm: sqlmodel
  database_access_rule: "FastAPI is the sole Supabase/DB client — frontend never connects directly"
  auth_method: supabase-auth
  auth_access_rule: "Supabase Auth is consumed via FastAPI only — frontend sends credentials to FastAPI, which validates against Supabase"
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

Solo developer building a Polish-language medication cabinet web app in 2 weeks after-hours. Custom path taken because the developer has an explicit Python/FastAPI constraint from shaping. FastAPI clears all four agent-friendly gates within the Python family (typed via Pydantic, convention-based, popular in Python training data, well-documented). The database is PostgreSQL hosted on Supabase (free tier, 500 MB). Supabase was chosen over Neon for two reasons: it eliminates auth boilerplate (FR-001/FR-002 registration and login come out of the box via Supabase Auth), and its Row Level Security provides a defence-in-depth isolation guarantee aligned with the PRD guardrail that one user's cabinet data must never be visible to another. The ORM layer is SQLModel (SQLAlchemy + Pydantic combined — type-safe, fits FastAPI naturally) connecting to Supabase's PostgreSQL via a standard connection string. The architectural constraint is firm: FastAPI is the sole Supabase/DB client — the frontend never holds a Supabase service key and never calls Supabase directly. All auth and data access flows through FastAPI, which validates sessions and enforces business logic before any query runs. RLS acts as a safety net, not the primary enforcement layer.

The architecture is a single-repository monorepo: backend/ (FastAPI/uv) and frontend/ (Vite React TypeScript SPA/npm + Tailwind CSS). No monorepo orchestrator — a flat two-directory layout with path-filtered GitHub Actions jobs is the practical approach for this polyglot stack. Backend deploys to Render as a Web Service (free tier with cold starts after 15 min inactivity; upgradeable to always-on at $7/month); frontend deploys to Render as a Static Site (always free, CDN-served, no cold starts). Both services live in the same Render project. CI auto-deploys on merge to main via Render deploy hooks wired into GitHub Actions. Notifications are computed on page load so no background queue is needed.

Code quality is gated by a `pre-commit` hook running fast lint and format checks on staged files (ruff for Python lint + format; ESLint + Prettier for React/TypeScript). Backend tests run on pytest with pytest-asyncio, httpx, and pytest-cov; frontend tests use Vitest with React Testing Library; Playwright covers one golden-path E2E flow (login → add medication → see it in cabinet). Tests are gated in CI, not in pre-commit, so commits stay fast. Self-check returned 4/5 — React is new territory for the developer, flagged for extra care when reviewing agent-generated frontend code.

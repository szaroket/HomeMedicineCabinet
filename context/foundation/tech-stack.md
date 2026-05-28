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
---

## Why this stack

Solo developer building a Polish-language medication cabinet web app in 2 weeks after-hours. Custom path taken because the developer has an explicit Python/FastAPI constraint from shaping. FastAPI clears all four agent-friendly gates within the Python family (typed via Pydantic, convention-based, popular in Python training data, well-documented). The database is PostgreSQL with SQLModel (SQLAlchemy + Pydantic combined — type-safe, fits FastAPI naturally), hosted on Neon's free tier (0.5 GB, always free). The architecture is a single-repository monorepo: backend/ (FastAPI/uv) and frontend/ (Vite React TypeScript SPA/npm + Tailwind CSS for styling). No monorepo orchestrator — a flat two-directory layout with path-filtered GitHub Actions jobs is the practical approach for this polyglot stack. Backend deploys to Fly.io; frontend deploys to Cloudflare Pages; CI auto-deploys on merge. Auth is in scope (FR-001, FR-002) via JWT tokens (python-jose + passlib for password hashing); the React SPA stores the token and sends it as a Bearer header on every request. Notifications are computed on page load so no background queue is needed. Self-check returned 4/5 — React is new territory for the developer, flagged for extra care when reviewing agent-generated frontend code.

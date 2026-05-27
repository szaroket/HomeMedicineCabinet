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
  frontend_starter_id: react-router
  frontend_deployment_target: cloudflare-pages
  repo_structure: monorepo
  monorepo_layout: "backend/ (FastAPI/uv) + frontend/ (React Router/npm) — single Git repo, no dedicated orchestrator"
---

## Why this stack

Solo developer building a Polish-language medication cabinet web app in 2 weeks after-hours. Custom path taken because the developer has an explicit Python/FastAPI constraint from shaping: FastAPI clears all four agent-friendly gates within the Python family (typed via Pydantic, convention-based, popular in Python training data, well-documented). The architecture is a single-repository monorepo with two top-level directories: backend/ (FastAPI/uv) and frontend/ (React Router v7/npm). No dedicated orchestrator (Turborepo/Nx) is used — both are JS-only and don't manage Python packages; a flat two-directory layout with path-filtered GitHub Actions jobs is the practical monorepo for this polyglot stack. Frontend deploys to Cloudflare Pages; backend deploys to Fly.io; CI auto-deploys on merge to main with separate jobs per directory. Auth is in scope (FR-001, FR-002); notifications are computed on page load, so no background queue is needed. Self-check returned 4/5 — React is new territory for the developer, flagged for extra care when reviewing agent-generated frontend code.

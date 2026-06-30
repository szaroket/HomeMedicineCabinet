<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: CI/CD Wiring (F04)

- **Plan**: context/changes/ci-cd-wiring/plan.md
- **Scope**: Full plan — Phases 1–4 of 4
- **Date**: 2026-06-29
- **Verdict**: REJECTED
- **Findings**: 1 critical, 1 warning, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | WARNING |
| Safety & Quality | FAIL |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

## Findings

### F1 — render.yaml declares a Supabase env var the app never reads

- **Severity**: ❌ CRITICAL
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality (reliability — deploy will fail)
- **Location**: render.yaml:15 · docs/reference/deployment.md:43
- **Detail**: The backend config requires `SUPABASE_ANON_KEY` (`backend/app/core/config.py:30` — `supabase_anon_key: str`, required, no default; consumed at `backend/app/db/supabase_auth.py:39`). But `render.yaml` declares `SUPABASE_SERVICE_ROLE_KEY` (sync:false), and the deployment doc instructs the maintainer to set that same name. `Settings` uses `extra="ignore"`, so the service-role var is silently dropped and `SUPABASE_ANON_KEY` stays unset → `Settings()` raises a pydantic ValidationError at import time → backend crashes on boot → the `/api/v1/health/` check never passes → the Render deploy fails. Nothing in `app/` reads any service-role key (grep confirms). This traces to a flaw in the plan itself: `plan.md:40` and the Desired End State both list `SUPABASE_SERVICE_ROLE_KEY` as the backend var; the implementation followed the plan faithfully. Note the CI test job already uses the correct name — `ci-cd.yml:96` sets `SUPABASE_ANON_KEY`.
- **Fix**: Rename the var to `SUPABASE_ANON_KEY` in `render.yaml:15` and in the backend env-var table at `docs/reference/deployment.md:43` (and fix the plan's references so future reviews don't re-introduce it).
- **Decision**: FIXED — renamed in render.yaml, deployment.md, and plan.md (lines 40 & 227)

### F2 — Branch-protection doc lists job IDs, not the status-check names

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency (doc accuracy)
- **Location**: docs/reference/deployment.md:78
- **Detail**: The doc says to select status checks `vulnerability-scan`, `pre-commit`, `frontend-build`, `backend-typecheck`, `backend-tests`. Those are the job *ids*, but each job sets a `name:`, and GitHub branch protection lists checks by display name: "Vulnerability Scan", "Pre-commit Checks", "Frontend Build", "Backend Type Check", "Backend Unit Tests". A maintainer searching for the lowercase ids won't find the checks.
- **Fix**: Update the bullet list to the display names from each job's `name:` field in `ci-cd.yml`.
- **Decision**: FIXED — bullet now uses display names (deployment.md:78)

### F3 — requires-python bumped 3.12 → 3.13 (undocumented; no Render pin)

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: backend/pyproject.toml:6 · render.yaml:2-9
- **Detail**: `requires-python` was tightened from `>=3.12` to `>=3.13`. Phase 1's contract covered only the coverage and pyright blocks; the Phase 2 addendum documented dependency bumps but not this. It's almost certainly intentional (aligns with `[tool.pyright] pythonVersion = "3.13"` and CI Python 3.13), so it's benign — but `render.yaml`'s `runtime: python` pins no version. If Render's default Python is < 3.13, `uv sync --frozen` will fail the build.
- **Fix**: Confirm Render uses Python ≥ 3.13, or pin the runtime version; note the requires-python bump in the plan's epilogue.
- **Decision**: FIXED — pinned `PYTHON_VERSION: "3.13"` in render.yaml; documented the 3.12→3.13 bump in plan.md Migration Notes

## Notes on what's solid

- Release-gating is correct: `deploy` has `if: github.event_name == 'release'` and `needs:` all five CI jobs; those jobs have no event guard so they re-run on the release event — deploy is genuinely gated on a fresh green run of the released commit. PR/push never deploys.
- `frontend-e2e` (`if: false`) is correctly excluded from deploy's `needs`.
- SHA-pinned 3rd-party action + major tags for GitHub-owned actions is a sound supply-chain posture. healthCheckPath fix and `autoDeploy: false` ×2 verified. Unchecked manual items (3.4, 4.5, 4.6) require live infra and are appropriately left pending.

<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: CI/CD Wiring (F04)

- **Plan**: context/changes/ci-cd-wiring/plan.md
- **Scope**: Phase 2 of 4
- **Date**: 2026-06-29
- **Verdict**: APPROVED
- **Findings**: 0 critical, 1 warning, 2 observations

## Summary

All four planned Phase 2 contracts match the plan: `frontend-build`, `backend-typecheck`, the coverage threshold in `backend-tests`, and the `if: false` scaffolded `frontend-e2e` job (TODO comment present). Locally verified: `check-yaml` passes; `coverage run -m pytest --ignore=tests/db` → 349 passed, TOTAL 86% (floor is 60); the test job's `SUPABASE_ANON_KEY` matches `app/core/config.py`. CI-observed criteria (2.2/2.4) are marked complete in Progress; the live Actions run was not observable from the review environment.

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | WARNING |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

## Findings

### F1 — GitHub Action versions bumped against the plan's explicit directive

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: .github/workflows/ci.yml:14,17,29 (repeated per job)
- **Detail**: The plan's Key Discoveries (plan.md:38) and Phase 2 contracts call for reusing the draft's exact versions "for consistency": setup-uv@v4, setup-python@v5, setup-node@v4 (node 22). The implementation uses actions/checkout@v7, actions/setup-python@v6, actions/setup-node@v6, with a dedicated commit (16757c5) bumping to "latest". Deliberate and defensible, but it contradicts a directive the plan singled out and is recorded nowhere. These are unusually high major versions; if a tag fails to resolve, every job errors at setup. Progress marks 2.2/2.4 green, implying the run passed, but the Actions run was not observable from here.
- **Fix**: Confirm the latest Actions run is green on these majors, then add a one-line addendum to plan.md recording the deliberate bump (supersedes the "reuse v4/v5/v4" guidance).
- **Decision**: FIXED — runs 28390866751/28391109360 confirmed green; addendum added to plan.md Key Discoveries.

### F2 — Phase 2 absorbed unplanned dependency + test-env plumbing

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: backend/pyproject.toml:12-14,21 ; .github/workflows/ci.yml:91-95
- **Detail**: Fixup commits beyond the four planned contracts: security bumps (cryptography, python-multipart, starlette added; pydantic-settings raised) to satisfy the pre-existing vulnerability-scan job, plus DATABASE_URL/SUPABASE_* dummy env vars and `--ignore=tests/db` in the backend-tests job. None appear in the Phase 2 plan text (which said the test job is "otherwise unchanged"). All benign and necessary to make CI green — `--ignore=tests/db` only drops live-DB integration tests (coverage still 86%), and the env vars match app/core/config.py. "What We're NOT Doing" forbids none of it.
- **Fix**: Add a short addendum to plan.md noting the dep bumps and the backend-tests env/`--ignore=tests/db` plumbing.
- **Decision**: FIXED — addendum added to plan.md Phase 2.

### F3 — Mixed action pinning (SHA for one action, floating tags for the rest)

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: .github/workflows/ci.yml:22,55,83,134
- **Detail**: astral-sh/setup-uv is pinned to a full commit SHA (08807647e7069bb48b6ef5acd8ec9567f424441b) while every other action uses a floating major tag (@v7/@v6). Defensible — pinning the third-party action to a SHA while trusting first-party GitHub-owned actions on tags is a reasonable supply-chain posture — but reads as inconsistent and carries no explanatory comment.
- **Fix**: Add a trailing comment on the setup-uv line (e.g. "# pinned: 3rd-party action") documenting the deliberate SHA pin.
- **Decision**: FIXED — explanatory comment added to all 4 setup-uv lines; check-yaml passes.

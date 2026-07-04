<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Quality-Gates Wiring

- **Plan**: context/changes/quality-gates-wiring/plan.md
- **Scope**: All 3 phases (full plan)
- **Date**: 2026-07-04
- **Verdict**: APPROVED
- **Findings**: 0 critical, 2 warnings, 0 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | WARNING |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | WARNING |

## Summary

Clean execution. All nine CI jobs land and match their plan contracts; the e2e
rewrite correctly drops the broken manual `&` server-start steps and lets
Playwright's `webServer` boot both servers (with `uv sync` in place); the
secrets-preflight fails fast, prints only secret *names* (never values), and its
`set -e` / indirect-expansion logic is sound (proven by manual item 2.3 passing
green alongside 2.4). Secrets are hoisted to **job-level** env — an improvement
over the plan's step-level snippet and exactly what the Critical Implementation
Details required for the Playwright child boot. New jobs mirror sibling setup
blocks (SHA-pinned `setup-uv`, `setup-node@v6` cache, placeholder env reused
verbatim from `backend-tests`); `deploy.needs` lists all nine gates.

Automated verification re-run at review time: preflight `bash -n` OK; `typecheck`
npm script present (`tsc -b`); stale-strings `rg` returns nothing (incl.
deployment.md's old "scaffolded but disabled"); workflow YAML structurally sound.
Local suite runs (Progress 1.2–1.4) verified by implementer with commit SHAs; not
re-run here (Docker/testcontainers + TLS-DB abort under Bash tool per L-001).

## Findings

### F1 — Unplanned edit to docs/reference/deployment.md

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: docs/reference/deployment.md
- **Detail**: Phase 3's "Changes Required" enumerates four files (test-plan.md, integration README, AGENTS.md, change.md). The implementation also edited docs/reference/deployment.md — added the five E2E secrets to the secrets table, an "E2E secrets prerequisite" section, and the four new branch-protection check names. This is a good, necessary edit: the old text ("The E2E job is scaffolded but disabled") would now be stale, exactly parallel to the planned AGENTS.md stale-note fix, and it falls within Phase 3's stated mandate. It's just not in the enumerated file list.
- **Fix**: Add docs/reference/deployment.md to Phase 3's file list as a one-line addendum so the plan matches what shipped.
- **Decision**: FIXED — added as Phase 3 item #5 (addendum) in plan.md.

### F2 — change.md marked `complete` with 4 manual Progress items unchecked

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: context/changes/quality-gates-wiring/plan.md:445-457
- **Detail**: change.md is `status: complete` and the plan was closed out (epilogue commit 45cbb5a), yet Progress items 2.5, 2.6, 3.2, 3.3 are still `- [ ]`. The facts are satisfiable by inspection — the upload-artifact `if: failure()` step (2.5) is present (ci-cd.yml:271-279), `frontend-e2e` is in `deploy.needs` (2.6, ci-cd.yml:294), and the docs read consistently (3.2/3.3). Bookkeeping gap, not missing work, but a "complete + closed out" change with unticked boxes reads as a mild rubber-stamp risk.
- **Fix**: Tick 2.5/2.6 noting they're confirmed by workflow inspection (or a real induced-failure / release run) and 3.2/3.3 as verified, so Progress matches the `complete` status.
- **Decision**: SKIPPED

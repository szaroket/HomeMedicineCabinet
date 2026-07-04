<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: CI/CD Wiring (F04)

- **Plan**: context/changes/ci-cd-wiring/plan.md
- **Scope**: Phase 3 of 4
- **Date**: 2026-06-29
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 2 warnings, 1 observation

> Core safety goal holds: the deploy job is guarded by `if: github.event_name == 'release'`, so it is skipped on push/PR. The warnings concern *how* CD was wired vs. how the plan specified it, plus a success criterion that no longer matches reality.

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | WARNING |
| Safety & Quality | PASS |
| Architecture | WARNING |
| Pattern Consistency | PASS |
| Success Criteria | WARNING |

## Findings

### F1 — CD merged into renamed ci-cd.yml instead of a separate cd.yml

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Plan Adherence / Architecture / Scope Discipline
- **Location**: .github/workflows/ci-cd.yml:1-9, 181-201
- **Detail**: The plan's Critical Implementation Detail is explicit: "Deploy job must never run on PRs: it lives in a SEPARATE cd.yml keyed SOLELY on `on: release: { types: [published] }`. No push/pull_request triggers in that file." The Phase 3 contract repeats: "New workflow name: CD ... single job deploy." Instead, commit a83be89 renamed ci.yml → ci-cd.yml, added `release: published` alongside the existing push/pull_request triggers, and added a deploy job gated by `if: github.event_name == 'release'` with `needs:` on all five CI jobs. No cd.yml exists. This is a genuine deviation from an explicit "must" with no recorded addendum (Phase 2 documented its deviations as addenda at plan.md:39, :158). It is defensible — arguably superior: deploy `needs:` the five CI jobs and the whole workflow re-runs on the release event, so deploy is gated by a fresh green CI run on the released commit; the planned separate-file design would have fired the Deploy Hook on release WITHOUT re-running any gate.
- **Fix A ⭐ Recommended**: Keep the merged design; record it as a Phase 3 addendum in plan.md (mirroring the Phase 2 addendum style).
  - Strength: Preserves working, arguably-better wiring (deploy gated by a green CI re-run); updates the source of truth so Phase 4 and deployment.md describe reality; matches this repo's established addendum convention.
  - Tradeoff: Plan diverges from original "separate file" intent; must update Phase 3 contract + the cd.yml references in Phase 4 (plan.md:233, References) and deployment.md.
  - Confidence: HIGH — addendum pattern already used twice in this plan.
  - Blind spot: Branch-protection required-status-checks key on job names (unchanged), so the rename breaks nothing — but external badges/links to the ci.yml path are now stale.
- **Fix B**: Split back out to a standalone cd.yml as planned.
  - Strength: Honors the explicit plan; deploy file has a single obvious trigger; CI file stays CI-only.
  - Tradeoff: Loses the "deploy gated by fresh CI run" property unless needs/workflow_run plumbing is re-added; discards working, verified wiring.
  - Confidence: MED — straightforward to write, but re-introduces the ungated-deploy gap the merged form closed.
  - Blind spot: Whether CI should re-run on the release commit at all (cost vs. assurance).
- **Decision**: FIXED via Fix A (Phase 3 addendum added to plan.md)

### F2 — Success criterion 3.2 marked done but is unverifiable as written

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: context/changes/ci-cd-wiring/plan.md:314 (criterion 3.2)
- **Detail**: Criterion 3.2 reads "cd.yml `on:` contains only `release: published` (no push/pull_request): grep confirms" and is checked `[x]` — a83be89. But there is no cd.yml, and ci-cd.yml's `on:` block contains push, pull_request, AND release (verified: ci-cd.yml:4,6,8). The literal criterion is false. The safety intent (deploy never on PR) is met by the job-level `if`, but the checkbox attests to a condition that does not hold.
- **Fix**: Rewrite criterion 3.2 to match the chosen mechanism, e.g. "the deploy job is guarded by `if: github.event_name == 'release'` so it is skipped on push/PR: grep confirms" — then it is true and re-verifiable. (Pairs with F1's addendum.)
- **Decision**: FIXED (rewrote criterion 3.2 at plan.md:191 and Progress mirror at :314)

### F3 — Stale cd.yml references downstream of the rename

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: plan.md:26,172,176,233,275 (Phase 4 + References)
- **Detail**: Phase 4 and References still describe a cd.yml, and "Desired End State" still says ".github/workflows/cd.yml is committed" (plan.md:26). Phase 4's deployment doc (not yet written) should describe the single CI/CD workflow + release-gated deploy job, not a separate cd.yml. Heads-up for the Phase 4 implementation/review, not a defect in the Phase 3 code.
- **Fix**: When writing Phase 4, describe the merged ci-cd.yml design; fold into F1's addendum so the plan is internally consistent.
- **Decision**: FIXED (updated forward-facing/live cd.yml refs at plan.md:26, :31, :59, :196-197, :255, :261, Progress 3.4/3.5, References; historical Phase 3 contract left intact under the addendum)

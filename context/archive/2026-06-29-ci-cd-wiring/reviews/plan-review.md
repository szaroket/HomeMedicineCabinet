<!-- PLAN-REVIEW-REPORT -->
# Plan Review: CI/CD Wiring (F04) Implementation Plan

- **Plan**: context/changes/ci-cd-wiring/plan.md
- **Mode**: Deep
- **Date**: 2026-06-29
- **Verdict**: REVISE → SOUND (all 3 findings fixed during triage 2026-06-29)
- **Findings**: 0 critical   2 warnings   1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | WARNING → PASS (F1 fixed) |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | WARNING → PASS (F2 fixed) |
| Plan Completeness | PASS (F3 observation fixed) |

## Grounding

6/6 paths ✓, symbols ✓ (health route `/api/v1/health/` confirmed at router.py:9 + health/router.py:3; coverage is the CLI, no pytest-cov in deps; pyright is a dep; CI action versions match), brief↔plan ✓. Progress↔Phase mechanically consistent (1 `## Progress` block; all phases and success-criteria bullets mapped).

## Findings

### F1 — render.yaml never disables Render autoDeploy; pushes deploy regardless of the release gate

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: End-State Alignment
- **Location**: Overview (L8) / Desired End State (L26) / Phase 4
- **Detail**: The central promise is "CD deploys to Render only when a GitHub Release is published". But Render Blueprints default to `autoDeploy: true` — each service redeploys on every push to its tracked branch. `render.yaml` sets no `autoDeploy` field (verified render.yaml:1-27), and Phase 4 changes only `healthCheckPath`. So merging this PR into `main` would trigger an immediate Render deploy before any release exists, contradicting the "only on release" design. The `cd.yml` hook then becomes a second deploy path layered on Render's native one, not the sole gate.
- **Fix A ⭐ Recommended**: Add `autoDeploy: false` to both services in render.yaml
  - Strength: Makes the release-triggered Deploy Hook the only deploy path — matches the stated end state exactly. One-line-per-service edit in the file Phase 4 already touches.
  - Tradeoff: All deploys depend on the GH Action + hook firing correctly; loses Render's native push-to-deploy.
  - Confidence: HIGH — `autoDeploy` is a documented Render Blueprint key and default-true is its known behavior.
  - Blind spot: Haven't confirmed whether the user wants zero push-based deploys on `develop` vs only `main`.
- **Fix B**: Keep autoDeploy on; reframe the release hook as an extra trigger
  - Strength: Simplest; uses Render's native mechanism.
  - Tradeoff: Breaks the "only when a Release is published" promise — the criterion "a PR/merge does not deploy" becomes false.
  - Confidence: HIGH.
  - Blind spot: None significant.
- **Decision**: FIXED via Fix A (added `autoDeploy: false` to both services in Phase 4 + Desired End State + success criteria/Progress)

### F2 — Deploy Hook deploys the tracked branch's HEAD, not the released commit

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Phase 3 — cd.yml / Critical Implementation Details (L58)
- **Detail**: A Render Deploy Hook is fire-and-forget: it tells Render to deploy the current HEAD of the service's tracked branch, carrying no commit/tag reference. So `cd.yml` firing on `release: published` does not guarantee the *released* commit ships — if the release tag points at an older commit, or the branch advanced past the tag, Render deploys branch HEAD instead. The plan deliberately chose hooks over the Render API (What We're NOT Doing, L45), so the fix is to make the assumption explicit and safe, not to switch mechanisms.
- **Fix**: In `docs/reference/deployment.md` (Phase 4), document the operating assumption — releases must be published from the tip of the Render-tracked branch (tag branch HEAD, then publish) — as a release-procedure note so the deployed artifact matches the release.
  - Strength: Keeps the simple hook approach; closes the correctness gap with a documented procedure.
  - Tradeoff: Relies on human discipline rather than a hard guarantee.
  - Confidence: HIGH — consistent with the fire-and-forget decision.
  - Blind spot: None significant.
- **Decision**: FIXED via Fix in plan (Phase 4 doc contract now spells out the release procedure: merge to `main` → tag at `main` HEAD → publish Release; Render tracks `main`, so branch HEAD == released commit).

### F3 — README pointer line has no verification criterion

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 4 — Changes #2 (L218) vs Success Criteria (L226-234)
- **Detail**: Phase 4 promises "a short pointer line added to README.md", but no automated/manual success criterion confirms README was touched (criteria only check render.yaml path + deployment.md existence). Easy to forget at implementation time.
- **Fix**: Add an automated check (grep README.md for the deployment-doc link) to Phase 4's success criteria, or drop the README edit.
- **Decision**: FIXED via Fix in plan (added `grep -F` README criterion + Progress 4.4)

## Note (not a finding)

The 60% coverage floor was not live-verified — running `coverage` from the Bash tool risks the OpenSSL applink abort (lesson L-001) on DB-touching tests. The plan self-handles this via manual step 1.5 (lower floor to current value). Confirm on a native PowerShell run during Phase 1.

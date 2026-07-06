<!-- PLAN-REVIEW-REPORT -->
# Plan Review: SPA Refresh Fallback

- **Plan**: context/changes/spa-refresh-fallback/plan.md
- **Mode**: Deep
- **Date**: 2026-07-04
- **Verdict**: SOUND
- **Findings**: 0 critical, 1 warning, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | WARNING |
| Plan Completeness | WARNING |

## Grounding

6/6 paths ✓ (render.yaml, router.tsx, dashboard-page.tsx, app/components/, ci-cd.yml deploy job, infrastructure.md), 3/3 symbols ✓ (createBrowserRouter, `type: static` with no `routes:` block, `autoDeploy: false`), brief↔plan ✓, test harness ✓ (vite.config.ts test block: jsdom env, globals, jest-dom setup, `*.test.tsx` already in `include`).

## Findings

### F1 — Phase 1's automated + preview verification cannot catch a broken rewrite

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Phase 1 — Success Criteria (Automated + Manual 1.3)
- **Detail**: The plan's own Current State (lines 32-35) states `vite preview` does history-fallback automatically and does not read `render.yaml`. Yet manual step 1.3 uses `vite preview` + refresh `/cabinet` as verification of the Phase 1 fix — that step passes identically with or without the render.yaml change, so it proves the prod bundle can client-route but proves nothing about the rewrite under test. Compounding it, the two automated criteria are "build succeeds" and "render.yaml is valid YAML"; valid YAML ≠ valid Render Blueprint, so a mis-nested/mistyped `routes:` block parses fine and silently does nothing. The entire real validation of Phase 1 rests on post-deploy steps 1.4/1.5 — nothing before deploy can fail if the rewrite is wrong.
- **Fix**: Reframe 1.3 as "confirms the production bundle client-routes to a deep path" (not rewrite validation), and state explicitly that the rewrite is validated ONLY by 1.4 (live deep-route refresh) and 1.5 (dashboard rule present). Add a pre-deploy eyeball step: confirm the `routes:` block is nested under the static service and matches Render's key names before pushing.
- **Decision**: FIXED — added a "what proves what" note + pre-deploy eyeball step to Phase 1 Manual Verification; renumbered Progress manual steps 1.3–1.6.

### F2 — `/* → /index.html` masks 404s for deleted hashed chunks

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Desired End State → Key Discoveries (lines 63-65)
- **Detail**: The plan reassures that static hosts "serve existing files before applying rewrites, so /* does not clobber real asset requests" — true for files that still exist, but not for a deleted chunk. An old open tab requesting `/assets/index-<oldhash>.js` after a redeploy hits the rewrite and gets index.html (HTTP 200, text/html) instead of a clean 404, surfacing as a confusing MIME/parse error. Low impact for this app (infrequent deploys, small surface) but worth a one-line acknowledgment.
- **Fix**: Add a one-line note in Key Discoveries that deleted hashed assets return index.html under the catch-all rewrite (accepted tradeoff); no code change needed.
- **Decision**: FIXED — added accepted-tradeoff note to Key Discoveries.

### F3 — NotFoundPage chrome under-specified; doc target left as "X or Y"

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 2 change 1 (lines 188-191); Phase 1 change 2 (line 137)
- **Detail**: Phase 2 says NotFoundPage should "follow the styling/idiom of dashboard-page.tsx" but "do not require AppLayout." The no-AppLayout call is correct (AppLayout pulls in LogoutButton, an auth-coupled component — app-layout.tsx:6). But once AppLayout is removed, dashboard-page.tsx is just `<AppLayout><Link/></AppLayout>` — almost no idiom left to follow, so the implementer must invent the page shell (bg, centering, heading size) with no reference. Separately, the doc target is "infrastructure.md ... or the frontend deploy notes if preferred"; infrastructure.md exists, so the "or if preferred" is an unresolved coin-flip.
- **Fix**: Give NotFoundPage a concrete minimal shell (e.g. full-height centered container matching AppLayout's `bg-slate-900` dark theme, a Polish `<h1>` heading, and a `Link to="/"`), and pin the doc target to `context/foundation/infrastructure.md` (drop the "or").
- **Decision**: FIXED — specified a concrete dark-theme shell (verified against app-layout.tsx) in Phase 2 change 1; pinned doc target to infrastructure.md in Phase 1 change 2.

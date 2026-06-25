<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Important Category

- **Plan**: context/changes/important-category/plan.md
- **Scope**: Phase 6 of 7 (frontend settings feature)
- **Date**: 2026-06-16
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 3 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | WARNING |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | WARNING |

## Success Criteria results

- 6.1 `npm run build` — PASS ✅ (built in 175ms, 192 modules)
- 6.2 `npm run lint` (eslint) — PASS ✅ (no errors)
- 6.3 `npx prettier --check src/` — FAILS repo-wide on 34 pre-existing files; see F3. Phase 6's own files are prettier-clean.

## Findings

### F1 — Nav delivered as full responsive sidebar, not the planned header link

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Scope Discipline
- **Location**: frontend/src/app/components/app-sidebar.tsx (new), app-layout.tsx (new), cabinet-page.tsx, add-medication-page.tsx
- **Detail**: Plan scoped navigation as "a 'Ustawienia' link in the shared header." Implementation built a responsive sidebar with mobile hamburger drawer (app-sidebar.tsx), a shared chrome wrapper (app-layout.tsx), added two icon assets, and migrated cabinet-page.tsx and add-medication-page.tsx onto the new layout. No behavioral regressions (page migrations are layout-only) but materially larger than planned and touches files outside the settings feature.
- **Fix A ⭐ Recommended**: Document the layout/sidebar refactor as a plan addendum under Phase 6 (consistent with existing 2026-06-16 addenda).
  - Strength: Preserves working code; keeps plan.md truthful; matches existing addendum pattern (Phases 2/3/4).
  - Tradeoff: Plan grows beyond original phrasing.
  - Confidence: HIGH — addendum pattern already used in this plan.
  - Blind spot: Dashboard page was NOT migrated to AppLayout — confirm asymmetry is intentional (see F5).
- **Fix B**: Revert sidebar/layout work, ship only a header link.
  - Strength: Strict scope discipline; smaller diff.
  - Tradeoff: Throws away working, reasonable nav infra; header-only link is arguably worse UX.
  - Confidence: MED — would need to re-verify cabinet/add pages render after revert.
- **Decision**: FIXED via Fix A (Phase 6 addendum added to plan.md)

### F2 — Backend CORS change landed in a frontend-scoped phase

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: backend/app/main.py:43
- **Detail**: allow_methods broadened from [GET, POST, PUT, DELETE] to add PATCH. Correct, minimal (explicit allowlist, not "*"), and required — without it the browser preflight blocks PATCH /users/preferences (Phase 2) and PATCH /cabinet/entries/{id} (Phase 4). Flag is twofold: (a) undocumented backend change in a frontend-scoped phase; (b) reveals those PATCH endpoints were never browser-reachable when Phases 2/4 were marked complete — a latent integration gap surfaced only now.
- **Fix**: Note the CORS PATCH addition in the Phase 6 addendum (or retroactively under Phase 2). No code change — the fix is correct.
- **Decision**: FIXED (CORS PATCH addition documented in Phase 6 addendum)

### F3 — Criterion 6.3 references prettier, which the project does not use

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: context/changes/important-category/plan.md:413,601
- **Detail**: Criterion 6.3 "Format check passes: npx prettier --check src/" is marked [x], but prettier is not a devDependency, there is no prettier config, and there is no prettier npm script. `npx prettier --check src/` runs default-config prettier and reports 34 pre-existing files with style issues (auth, cabinet, dashboard, lib, App.tsx); none are Phase 6 files. The criterion is invalid for this project and could not have passed at af71b43. Real gates `npm run lint` (eslint) and `npm run build` both pass.
- **Fix**: Replace 6.3 with the project's real gate (eslint via npm run lint, already covered by 6.2) and drop the prettier criterion from this plan and from test-plan.md so future phases don't re-stamp an unachievable check.
- **Decision**: FIXED (prettier criterion dropped from Phase 6 & 7 in plan.md; verified absent from test-plan.md and package.json)

### F4 — Update-preferences payload type inlined/duplicated

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: frontend/src/features/settings/api/settings-queries.ts:21, settings-api.ts:13-15
- **Detail**: Cabinet pattern exports a named payload type (AddEntryPayload) from the api module and reuses it in queries. Settings inlines `{ min_package_count: number }` literally in both files. Functionally fine; minor convention divergence.
- **Fix**: Export an UpdatePreferencesPayload interface from settings-api.ts and import it in settings-queries.ts.
- **Decision**: FIXED (UpdatePreferencesPayload exported and reused in both files; lint passes)

### F5 — Dashboard not migrated to AppLayout; status messages lack aria-live

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency / Accessibility
- **Location**: frontend/src/features/dashboard/components/dashboard-page.tsx; settings-page.tsx:59-67,100-105
- **Detail**: (1) cabinet/add/settings now use AppLayout but the dashboard keeps its own wrapper and gets no sidebar — likely intentional but worth confirming. (2) settings save/error messages render as plain <p> without role="status"/aria-live, so screen readers won't announce them (consistent with rest of app).
- **Fix**: Confirm the dashboard exclusion is deliberate; optionally add aria-live="polite" / role="alert" to status messages.
- **Decision**: FIXED (1) — dashboard-page.tsx migrated onto AppLayout per user (now consistent with cabinet/add/settings; lint + build pass). Asymmetry was NOT intentional. (2) aria-live not requested; status-message a11y left as-is, consistent with the rest of the app.

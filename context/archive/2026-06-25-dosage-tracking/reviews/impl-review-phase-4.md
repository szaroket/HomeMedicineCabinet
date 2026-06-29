<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Dosage Tracking (S-05)

- **Plan**: context/changes/dosage-tracking/plan.md
- **Scope**: Phase 4 of 6
- **Date**: 2026-06-26
- **Verdict**: NEEDS ATTENTION → RESOLVED (all 6 findings fixed during triage, 2026-06-26)
- **Findings**: 0 critical · 3 warnings · 3 observations — all FIXED

## Triage Outcome (2026-06-26)

All six findings resolved. The user elected to **keep** the server-side `sufficiency`
filter (deliberate product requirement) and refactor rather than revert:

- **F1/F2/F3/F4** — Extracted `crud._sufficiency_clauses` as a single documented SQL builder
  cross-referencing the Python `compute_usage_view`; added the closed-window guard (F2) and a
  `NULLIF` zero-rate guard (F4); added 11 parity tests in `TestBuildBaseQuerySufficiency` (F3).
  Backend: ruff clean, 186 cabinet tests pass. (pyright not runnable in this shell — `OPENSSL_Applink`
  env issue, fails identically on unchanged files.)
- **F5** — Documented the unplanned cabinet-list/cabinet-page wiring + server-side filter as a
  Phase 4 addendum in plan.md.
- **F6** — Sufficiency badge now renders via shared `StatusBadge` (`sufficiencyInfo`); frontend
  build + lint + prettier pass.

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | FAIL |
| Safety & Quality | WARNING |
| Architecture | WARNING |
| Pattern Consistency | WARNING |
| Success Criteria | WARNING |

## Success Criteria (Phase 4 — automated)

- `npm run build` — PASS
- `npm run lint` — PASS (0 errors; 1 pre-existing warning in add-medication-form.tsx, Phase 2)
- `npx prettier --check src/` — FAIL on 6 files, but **none are Phase 4 files** (app-footer, login-page, register-page, entry-icons, status-badge, settings-page). Phase-4 files are clean; the gate fails on untouched pre-existing files.

## Findings

### F1 — Unplanned backend `sufficiency` filter duplicates the calc in SQL

- **Severity**: ⚠️ WARNING
- **Impact**: 🔬 HIGH — architectural stakes; think carefully before deciding
- **Dimension**: Scope Discipline / Architecture
- **Location**: backend/app/api/v1/cabinet/crud.py:249-296 (+ schemas.py, service.py, facade.py, router.py)
- **Detail**: Phase 4 is "GET frontend" per the plan. Its only filter task (§3) was adding the "used" category OPTION to the filter UI — the backend already supported `category=used` from Phase 3. Instead, a brand-new `sufficiency=insufficient|sufficient` query param was added across five backend files, re-implementing days_of_supply / sufficiency entirely in raw SQLAlchemy (total_tablets, daily rate, floor, date projection). This is not in the plan at any phase. The plan's architecture (Overview, lines 16-19) is explicit: "the backend owns the quantitative calc … so S-06 notifications can reuse ONE calc path." This introduces a SECOND calc path that already drifts from the Python one (see F2), in the exact Risk #6 high-impact area.
- **Fix A ⭐ Recommended**: Revert the backend `sufficiency` filter; drive the Wystarczy/Zabraknie filter client-side off the `is_sufficient` field already returned per entry.
  - Strength: Restores the single-calc-path invariant the plan depends on for S-06; removes the SQL duplication and the F2/F4 drift at the source. Display badges already use `entry.is_sufficient`.
  - Tradeoff: Client-side filtering only sees the current page; a true server-side "show only short" across all pages would need the field surfaced differently later.
  - Confidence: MED — depends on whether cross-page sufficiency filtering is a real requirement (not in PRD/plan).
  - Blind spot: Not confirmed whether this filter was a deliberate late requirement vs. agent scope creep.
- **Fix B**: Keep the filter but document it as a plan addendum AND make the SQL delegate to / be tested against the Python calc (close F2, F3, F4).
  - Strength: Preserves the work; server-side filter works across pages.
  - Tradeoff: Permanently maintains two calc implementations — the thing the plan explicitly set out to avoid.
  - Confidence: MED — keeping duplicated business logic is a standing liability.
  - Blind spot: Future calc changes must touch both paths or silently diverge.
- **Decision**: FIXED via Fix B (refactor) — filter kept (deliberate product requirement: works across all pages). Extracted `crud._sufficiency_clauses` as a single documented builder cross-referencing `compute_usage_view`, pinned by parity tests (`TestBuildBaseQuerySufficiency`); same documented-duplication pattern as `is_below_minimum`. Closes F2/F3/F4 together.

### F2 — Sufficiency filter disagrees with the display calc for closed windows

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality (correctness)
- **Location**: crud.py:285-296 vs service.py:266-271
- **Detail**: Python `compute_usage_view` sets `is_sufficient = None` when `days_until_end <= 0` (end date today or past) — "window closed, no verdict", so no badge shows. The SQL predicate `today + days_of_supply >= end_date` evaluates TRUE for those past/today-end rows, so `sufficiency=sufficient` returns entries that render no "Wystarczy" badge — the filter and the card contradict each other for closed windows. (Resolved automatically if F1 Fix A is taken.)
- **Fix**: Add `dosage_end_date > today` to the predicate's WHERE guards so closed windows are excluded, matching the `until_end > 0` gate in compute_usage_view. (Moot if F1 Fix A is chosen.)
- **Decision**: FIXED — added `dosage_end_date > today` guard in `_sufficiency_clauses`; covered by `TestBuildBaseQuerySufficiency.test_closed_window_excluded`.

### F3 — New backend sufficiency filter has zero test coverage (Risk #6)

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Success Criteria / Safety & Quality
- **Location**: backend/tests/cabinet/ (no test references `sufficiency`)
- **Detail**: Risk #6 ("dosage finish-date / sufficiency miscalc", High) mandates explicit tests for this calc. The unplanned SQL filter — the most error-prone piece of Phase 4 — has no test exercising it (a grep finds only an unrelated comment). The F2 drift would have been caught by a single parametrized crud test.
- **Fix**: If keeping the filter (F1-B), add parametrized crud tests: insufficient vs sufficient, partial-package total, floor boundary, past/today end-date exclusion. If reverting (F1-A), this is moot.
- **Decision**: FIXED — added `TestBuildBaseQuerySufficiency` (11 parametrized cases): closed-window exclusion, zero-rate guard, used-only, predicate direction per filter, no-clause when inactive. Hermetic (structural SQL assertions) since the DB-backed suite needs a live Postgres unavailable here. Full cabinet suite 186 passed.

### F4 — SQL daily-rate division has no zero guard

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: crud.py:268-274
- **Detail**: Python `days_of_supply_from_rate` guards `daily_rate <= 0 → None`. The SQL divides by `dosage_times * dosage_amount / period_days` with no guard — a zero rate would raise a DB division-by-zero. Not reachable today (validate_usage enforces ≥1), but another silent divergence from the Python guard.
- **Fix**: Moot under F1-A. Under F1-B, add `dosage_times > 0 AND dosage_amount > 0` to the WHERE guards.
- **Decision**: FIXED — used `NULLIF(daily_rate, 0)` (stronger than the suggested `> 0` guards: a zero rate yields a NULL verdict regardless of Postgres WHERE-clause evaluation order, mirroring the Python `daily_rate <= 0 → None` guard). Covered by `test_zero_rate_guarded`.

### F5 — Unplanned frontend files changed (cabinet-list.tsx, cabinet-page.tsx)

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: cabinet-list.tsx, cabinet-page.tsx
- **Detail**: Plan §1-3 named cabinet-card, filter-options, filter-sheet, cabinet-api, use-cabinet-entry. The table view (cabinet-list) and page wiring (cabinet-page) also changed to surface usage + the stock filter. Reasonable adjacent scope — the table needs the same display the card got — but not enumerated. Benign.
- **Fix**: None needed; note in the plan that the list/table view shares the card's usage display.
- **Decision**: FIXED (documented) — added a post-impl-review addendum to Phase 4 in plan.md noting cabinet-list/cabinet-page wiring, the server-side sufficiency filter, and the StatusBadge usage.

### F6 — Sufficiency badge uses inline spans instead of StatusBadge

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: cabinet-card.tsx:76-85, cabinet-list.tsx:80-93
- **Detail**: Plan §2 said "Reuse StatusBadge styling conventions." The Wystarczy/Zabraknie badges are hand-rolled inline spans; cabinet-list even imports StatusBadge for the status column but not for sufficiency. Cosmetic divergence.
- **Fix**: Render the sufficiency badge via the StatusBadge component (or a shared Badge) for consistent styling.
- **Decision**: FIXED — added `sufficiencyInfo` descriptor to `use-cabinet-entry.ts` (`SUFFICIENCY_LABEL`) and render it via `StatusBadge` in both cabinet-card and cabinet-list, removing the duplicated hand-rolled spans. Pixel-identical output; frontend build + lint + prettier pass.

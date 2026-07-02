<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Playwright Critical-Path E2E Bootstrap

- **Plan**: context/changes/critical-path-e2e/plan.md
- **Scope**: Phase 3 of 4 (Journey A Seed Test)
- **Date**: 2026-07-02
- **Verdict**: APPROVED
- **Findings**: 0 critical, 1 warning, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | WARNING |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

## Evidence

- `seed.spec.ts` locators verified against source:
  - `getByLabel("Nazwa leku" / "Rozmiar opakowania" / "Termin ważności")` ↔ add-medication-form / product-autocomplete / variant-select labels now carry `htmlFor`/`id`.
  - `getByRole("heading", { name: "Dodano lek" })` + button `"Nie"` ↔ `AddResultDialog`.
  - `getByRole("searchbox")` ↔ single *visible* `type="search"` at Desktop Chrome viewport (mobile one is `md:hidden` → display:none → excluded from a11y tree).
  - `aria-label="Pokaż szczegóły"` toggle + `"Substancja czynna:"` detail row ↔ `cabinet-list.tsx`.
  - Spec's `productLabel()` (lines 64-72) replicates `product-autocomplete.tsx`'s (lines 12-20) exactly.
- `cd frontend && npm run build` — PASS.
- `cd frontend && npm run lint` — PASS (0 errors; 2 pre-existing React-Compiler `watch()` warnings, unrelated to this phase).
- `cd frontend && npx playwright test` — NOT re-run by the reviewer (L-001: DB-touching command must not run from the agent's Git Bash tool). Recorded `[x]` at commit `9a57f05` and driven through the `/10x-e2e` workflow; treated as verified-by-prior-run.

## Findings

### F1 — App source edited in a "seed test" phase (a11y labels)

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: frontend/src/features/cabinet/components/add-medication-form.tsx:162,211; product-autocomplete.tsx:47; variant-select.tsx (label/id)
- **Detail**: Phase 3's "Changes Required" enumerates only `seed.spec.ts` (and a possible rules reference). The commit also added `htmlFor`/`id` to three cabinet form components. This is a benign, *necessary* deviation: the plan assumed "the existing form's real `<label>`s" were locatable, but they had no `htmlFor`/`id`, so `getByLabel(...)` could not have worked without it. The fix is exactly the sanctioned project pattern (memory: locator-a11y-over-testid — fix accessibility, don't add `data-testid`) and is behavior-preserving. Flagged only because it's an unplanned source change surfacing in a test phase — the right call, just not enumerated.
- **Fix**: None needed — accept as a documented, in-spirit scope addition. Optionally note it in the Phase 3 block so future reviews don't re-flag it.
- **Decision**: FIXED — documented as addendum §3 in the Phase 3 block of plan.md.

### F2 — Detail assertions are row-level substring matches

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: frontend/e2e/seed.spec.ts:179-187
- **Detail**: `detailRow.toContainText(variant.<field> ?? "—")` checks the whole detail `<tr>` (which holds Dawka/Postać/Substancja czynna/Droga podania + Ulotka/Charakterystyka), not the specific `<dd>` cell. The oracle itself is sound (values come from the variants API, and `?? "—"` mirrors the app's own null rendering), but two soft spots: (a) a null API field degrades to matching the ubiquitous `"—"` placeholder, so that field isn't truly verified; (b) a substring could in theory match text from a sibling field. In practice `PRODUCT_SEARCH="Apap"` populates these fields, so the run is meaningful.
- **Fix**: If cell-level rigor is wanted later, scope each assertion to its `<dd>` via `getByRole("term"/"definition")` or a label-anchored locator. Not required for a smoke journey.
- **Decision**: FIXED — replaced the whole-row `toContainText` checks with cell-scoped `getByRole("definition").filter({ hasText })` assertions; null fields skipped (not uniquely verifiable). seed.spec.ts:174-194.

### F3 — Per-run expiry uniqueness rides on a 3650-value modulus

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: frontend/e2e/seed.spec.ts:77-81
- **Detail**: `uniqueFutureExpiryIso()` uses `Date.now() % 3650` as a day offset — only 3650 distinct values, and it's the sole isolation axis (`user_id` is the shared fixed account). Two runs whose `Date.now()` differ by an exact multiple of 3650 ms would collide on `uq_cabinet_entries_user_med_expiry`. Negligible for human/CI-spaced runs, and Phase 4's teardown is the intended backstop — but note Phase 4 is still PENDING, so right now this modulus is the *only* thing preventing accumulation collisions.
- **Fix**: None needed now; Phase 4 teardown removes the residual risk. For belt-and-suspenders, fold more entropy into the offset (e.g. include `package_count` or a wider modulus).
- **Decision**: SKIPPED — accepted; Phase 4 teardown is the backstop and the collision window is negligible for human/CI-spaced runs.

## Note on the seed-test convention (raised during review)

A doubt was raised on whether `seed.spec.ts` should hold a *real* test or only rules/skeleton. Per `.claude/skills/10x-e2e/references/seed-test-pattern.md:3-7`, the seed **is** a real, runnable test that doubles as the exemplar every generated test is modeled on ("what you show is what you get"). The written rules live separately in `frontend/e2e/CLAUDE.md`. Both were produced this phase — the pair is correct, and this confirms (rather than contradicts) the APPROVED verdict. New tests go in their own `<feature>.spec.ts` files (SKILL.md:251,387) with a `// seed: e2e/seed.spec.ts` provenance header; `seed.spec.ts` is never appended to.

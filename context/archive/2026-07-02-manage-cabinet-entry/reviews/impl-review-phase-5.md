<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Manage Cabinet Entry (FR-005)

- **Plan**: context/changes/manage-cabinet-entry/plan.md
- **Scope**: Phase 5 of 5 (E2E — manage/delete spec + teardown)
- **Date**: 2026-07-03
- **Verdict**: APPROVED
- **Findings**: 0 critical  0 warnings  2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

## Verification evidence

- **5.3 lint + prettier** — ran now, both green: `npm run lint` clean; `prettier --check e2e/` reports all files styled.
- **5.1 / 5.2 Playwright runs** — DB-touching (real Supabase TLS), not runnable from the agent shell (L-001). Marked done at `eea956d`; commit body documents per-assertion break-verification (inverting the confirm and bypassing the zero branch each turned the matching test red, then reverted).
- **Locators cross-checked against source, all exist**: aria-labels `Zwiększ/Zmniejsz liczbę opakowań`, `Usuń lek` (cabinet-list.tsx / cabinet-card.tsx); confirm copy `Czy na pewno chcesz usunąć` / `Zmniejszenie liczby opakowań do zera usunie` (use-cabinet-entry.ts:263-264); `role="dialog"` + `confirmLabel="Usuń"` (confirm-dialog.tsx); localStorage key `auth_token` (auth/store.ts:13). Table cell `nth(1)` = "Opak." column holding the count span — assertion unambiguous.
- **Plan contract met**: plain-delete + decrement-to-zero-delete both covered; role/text locators only; `waitForResponse` (never `waitForTimeout`); per-run-unique expiry; per-test fixture cleanup + `afterAll` safety net + `globalTeardown` backstop; teardown errors swallowed so they can't mask assertions.

## Findings

### F1 — Test-helper duplication across the two e2e specs

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: frontend/e2e/manage-cabinet-entry.spec.ts:47-93
- **Detail**: `productLabel()`, `toDisplayDate()`, and the `ProductOut`/`VariantOut` interfaces are byte-for-byte copies of seed.spec.ts:50-97. `uniqueFutureExpiryIso()` is a near-copy that intentionally diverges (base year 2060 vs 2035, module-scoped sequence) to keep the two specs' expiry bands disjoint on the shared account — so that one is deliberately NOT shared. Not a defect: self-contained e2e specs are defensible and each header documents the decoupling from `@/…` src types. A third cabinet spec would make a shared `e2e/helpers.ts` worth extracting.
- **Fix**: None needed now; extract shared helpers to `e2e/helpers.ts` if a third cabinet spec appears.
- **Decision**: FIXED — extracted `productLabel`, `toDisplayDate`, `ProductOut`, and a superset `VariantOut` into new `frontend/e2e/helpers.ts`, imported by both specs. `uniqueFutureExpiryIso()` deliberately kept per-spec (disjoint expiry bands). Verified: prettier --check, eslint, and tsc -p tsconfig.e2e.json all green.

### F2 — Unplanned reformat of pre-existing e2e files + .prettierignore

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: frontend/.prettierignore, frontend/e2e/auth.setup.ts, frontend/e2e/seed.spec.ts
- **Detail**: Beyond the planned "new spec + teardown", the commit adds `.prettierignore` and reformats auth.setup.ts + seed.spec.ts. Load-bearing, not scope creep: criterion 5.3 runs `prettier --check e2e/` over the whole directory, so the pre-existing files had to be Prettier-styled for the gate to pass, and `.prettierignore` excludes Playwright's generated `e2e/.auth` + reports. The auth.setup.ts diff is pure whitespace (a `setup()` call wrapped across lines); no logic changed. Documented in the commit body.
- **Fix**: None needed; changes are correct and documented.
- **Decision**: SKIPPED — accepted as-is; the reformat + `.prettierignore` are load-bearing for the `prettier --check e2e/` gate and documented in the commit body.

<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Delete User Account

- **Plan**: context/changes/delete-user-account/plan.md
- **Scope**: Phase 3 of 3 (Frontend — Settings delete-account UX)
- **Date**: 2026-07-06
- **Verdict**: APPROVED
- **Findings**: 0 critical, 1 warning, 2 observations

All four automated success criteria verified green: build (`tsc -b && vite build`),
lint (`eslint`), `prettier --check src/`, and `vitest` (38/38 passing). The single
deviation from the plan (redirect target + mechanism) is deliberate, technically
justified by a real race with `ProtectedLayout`, and documented in change.md Notes
and code comments.

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

## Findings

### F1 — Plan §3 body not reconciled with the shipped redirect approach

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: context/changes/delete-user-account/plan.md:377-396
- **Detail**: Plan §3 still prescribes redirect to `/login` via router `navigate()` + `clearSession()`, with the notice passed "via router state." As built, success/502 redirect to a dedicated `/account-deleted` page via a HARD `window.location.href` and a new `clearStoredToken()` (storage-only, no React state), with the partial notice via `?partial=1`. The deviation is correct — `protected-layout.tsx:17-19` renders `<Navigate to="/login" replace />` the instant the token *state* flips null, which races a client-side navigate. It IS documented in change.md Notes (14-25) and code comments, and Progress checkboxes were flipped, but the plan §3 body itself was never updated and now contradicts the shipped code. Phase 2 already set the precedent of an inline "Addendum (impl)" block (plan.md:279-284); §3 lacks the equivalent.
- **Fix**: Add an "Addendum (impl)" block under Phase 3 §2/§3 (mirroring plan.md:279) noting the `/account-deleted` page + hard redirect + `clearStoredToken()` and the race that motivated it. Pure doc-hygiene; no code change.
- **Decision**: FIXED — added "Addendum (impl)" block under Phase 3 §3 in plan.md.

### F2 — 502 teardown + partial-redirect branch has no automated test

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: frontend/src/features/settings/api/settings-queries.ts:43-61
- **Detail**: Required criterion 3.4 (confirm-gate test) is met, and account-deleted-page.test covers the partial *message*. But the trickiest, race-motivated logic — the mutation's status branching (502 → `clearStoredToken` + `queryClient.clear` + redirect to `?partial=1`; 503/other → keep session, show error) — has no test. This is the part most likely to silently regress and carries the subtle correctness argument. Beyond the plan's required criteria, so not a gate failure — just the highest-risk code left uncovered.
- **Fix**: Add a settings-queries/section test asserting a mocked 502 tears down the token + clears the cache, and a 503 leaves both intact.
- **Decision**: FIXED — added `settings-queries.test.ts` (success + 502 tear-down, 503 intact); 41/41 vitest green.

### F3 — Confirm dialog missing aria-labelledby / focus trap / Esc-to-close

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: frontend/src/features/settings/components/delete-account-section.tsx:55-63
- **Detail**: The dialog sets `role="dialog"` + `aria-modal="true"` and click-outside to close, and the input is properly label-associated (`useId` + `htmlFor` — satisfies the project locator rule). But the dialog `<h2>` isn't linked via `aria-labelledby`, there's no focus trap / initial focus, and no Escape-to-close. The plan only required the input be label-locatable (met), so this isn't a plan miss — just an a11y gap on a destructive-action modal. This is the repo's first modal, so there's no existing pattern to diverge from.
- **Fix**: Add `aria-labelledby` pointing at the heading id, focus the email input on open, and close on Escape.
- **Decision**: FIXED — added `aria-labelledby` (heading `useId`), initial-focus effect on the email input, and Escape-to-close in delete-account-section.tsx.

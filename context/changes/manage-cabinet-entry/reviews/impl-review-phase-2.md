<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Manage Cabinet Entry (FR-005)

- **Plan**: context/changes/manage-cabinet-entry/plan.md
- **Scope**: Phase 2 of 5 (Frontend — delete action)
- **Date**: 2026-07-03
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 2 warnings, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

**Plan Adherence note**: all 7 planned files landed as described. The one divergence — `deleteEntry` uses `apiFetch`, not the plan's `apiJson` — is correct: `apiJson` unconditionally calls `res.json()` (api-client.ts:72), which throws on a 204 empty body. The impl matches `apiJson`'s own error shape (`throw res`). Code improved on the plan; no action.

**Success Criteria**: `npm run build`, `npm run lint`, `npx prettier --check src/` all pass (2026-07-03). Manual items 2.4–2.6 marked `[x]` with observable evidence in the diff (trash button + ConfirmDialog + confirmDelete + invalidate; adaptive `deleteNote`; both row and card).

## Findings

### F1 — ConfirmDialog renders a `<div>` as a direct child of `<tbody>`

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: frontend/src/features/cabinet/components/cabinet-list.tsx:246
- **Detail**: EntryRow returns a fragment holding `<tr>…</tr>`, the optional expanded `<tr>`, and `<ConfirmDialog>`. EntryRow is mapped directly into `<tbody>` (cabinet-list.tsx:335-338). When `confirmingDelete` is true, ConfirmDialog returns a `<div className="fixed inset-0…">`, so a `<div>` becomes a direct child of `<tbody>` — invalid DOM nesting (tbody may contain only `<tr>`). React logs a `validateDOMNesting` warning and browser handling of the fostered node is unpredictable. The dialog is `position:fixed` so it looks correct, which is why manual check 2.4 passed and this slipped through. The mobile card path (cabinet-card.tsx) is fine — its dialog sits inside a normal `<div>`.
- **Fix**: Render the overlay through a portal in the shared primitive — wrap the returned markup in `createPortal(…, document.body)` inside ConfirmDialog. Fixes every current and future caller at once (Phase 4 reuses this dialog for the zero-delete flow) and is the idiomatic modal pattern; the dialog is already `position:fixed` so nothing else changes.
  - Strength: One edit in the primitive clears the table-nesting problem for the list and any later caller.
  - Tradeoff: Minor — a portal import; SSR-N/A here (Vite SPA).
  - Confidence: HIGH — standard React modal remedy; escape/backdrop logic unaffected.
  - Blind spot: None significant.
- **Decision**: FIXED — portal via createPortal(…, document.body)

### F2 — Shared modal primitive lacks dialog a11y semantics

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: frontend/src/components/ui/confirm-dialog.tsx:39
- **Detail**: The overlay div has no `role="dialog"`, `aria-modal="true"`, or `aria-labelledby`, and focus is not moved into the dialog on open (Escape works via a global listener). This matches the two siblings it was cloned from (add-result-dialog, filter-sheet also omit these), so it is not a regression. But the plan positions this as "the project's first shared UI primitive" — the deliberately-reusable one is exactly where dialog a11y should be led, and it aligns with the standing a11y-first preference (locate elements by accessibility, not test-id). The confirm/cancel buttons already have accessible names, so Phase 5 e2e can still target them; this is about screen-reader/keyboard semantics, not e2e locatability.
- **Fix**: Add `role="dialog"`, `aria-modal="true"`, and `aria-labelledby` pointing at the `<h2>` title (give it an id) on the panel div. Focus-trap is a nice-to-have; the ARIA roles are the load-bearing part.
- **Decision**: FIXED — role/aria-modal/aria-labelledby added; titleId via useId

### F3 — Delete copy duplicated across row and card

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: cabinet-list.tsx:37-40, cabinet-card.tsx:37-40
- **Detail**: `deleteMessage` and `deleteNote` are computed identically inline in both components. The plan centralised handlers in use-cabinet-entry.ts so row and card share one implementation; these two derived strings escaped that and are duplicated. Minor today, but Phase 4 adds more shared copy (the zero-delete message + loose-tablet note), so the duplication will compound.
- **Fix**: Return `deleteMessage`/`deleteNote` from `useCabinetEntry` so both callers consume one source.
- **Decision**: FIXED — both strings now returned from useCabinetEntry; inline duplicates removed

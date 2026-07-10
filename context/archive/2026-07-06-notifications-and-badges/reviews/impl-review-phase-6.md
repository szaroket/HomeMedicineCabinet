<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Notifications and Badges (S-06)

- **Plan**: context/changes/notifications-and-badges/plan.md
- **Scope**: Phase 6 of 8
- **Date**: 2026-07-08
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical  3 warnings  1 observation  (F4 found post-review, fixed)

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | WARNING |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

Automated success criteria all pass: `npm run test` (4 tests in notifications), `npm run build`, `npm run lint`, `npx prettier --check src/` all green. Manual criterion 6.3 checked with wired evidence (bell in app-layout.tsx:45, panel + dismiss present).

## Findings

### F1 — Unplanned "Dismiss all" feature (scope creep)

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Scope Discipline
- **Location**: features/notifications/api/notifications-queries.ts:34-50, features/notifications/components/notification-panel.tsx:99-108
- **Detail**: The plan's Phase 6 §1 API contract enumerates exactly two calls (getNotifications, dismissNotification) and the bell/panel spec never mentions a bulk action. The implementation adds a `useDismissAllNotifications` hook plus an "Odrzuć wszystkie" button. The hook fans out one POST per item via `Promise.all` — no bulk endpoint, so N notifications = N requests, and a partial failure (Promise.all rejects on first error) leaves some dismissed and some not, with the query invalidated either way. It is tested (notification-bell.test.tsx:113) and works, but was not in the plan.
- **Fix A ⭐ Recommended**: Keep it, document as a Phase 6 addendum in plan.md
  - Strength: Preserves working, tested UX; updates source of truth. Benign at PRD scale (small cabinets → few requests).
  - Tradeoff: Plan becomes a moving target; O(N)-request partial-failure semantics ship un-addressed.
  - Confidence: HIGH — feature is self-contained and test-covered.
  - Blind spot: No bulk-dismiss endpoint; fan-out cost and partial-failure window widen if cabinets grow.
- **Fix B**: Remove the dismiss-all hook + button, defer to a follow-up
  - Strength: Restores strict scope; a future slice can add an atomic bulk-dismiss endpoint.
  - Tradeoff: Loses implemented+tested work; another PR later.
  - Confidence: MED — must also drop the test at :113.
  - Blind spot: Haven't checked whether product expects dismiss-all in S-06 UX.
- **Decision**: FIXED via Fix A (documented as Phase 6 addendum in plan.md, 2026-07-08)

### F2 — Frontend omits trailing slash → 307 redirect on every GET

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: features/notifications/api/notifications-api.ts:17
- **Detail**: The backend route is `@router.get("/")` under prefix `/notifications` (router.py:29), canonical path `/api/v1/notifications/` — exactly what the integration tests hit (test_list_notifications.py:65, test_dismiss_notification.py:42). The frontend calls `apiJson("/notifications")` with no trailing slash, so FastAPI's default `redirect_slashes` issues a 307 to the slashed path on every request. It works (same-origin redirect preserves the Authorization header) but adds a redirect round-trip to a high-frequency endpoint (bell mounts every page + per-mutation invalidation + 5-min refetchInterval).
- **Fix**: Call `apiJson("/notifications/")` (trailing slash) to hit the route directly, matching the integration tests.
- **Decision**: FIXED (notifications-api.ts:17 now `"/notifications/"`, 2026-07-08)

### F3 — Polish pluralization: "za 1 dni" is ungrammatical

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: features/notifications/components/notification-panel.tsx:22,26
- **Detail**: `rowLabel` interpolates `days_remaining` into a fixed "...za {n} dni" string. For an entry expiring/running out tomorrow (days_remaining === 1) this renders "Termin ważności kończy się za 1 dni" / "Zabraknie za 1 dni", where correct Polish is "za 1 dzień". The 2+ cases ("za 5 dni") are fine. Inherited from the plan's illustrative copy; the rest of the row copy diverges from the plan's placeholder strings but reads as an improvement (noted, not flagged).
- **Fix**: Special-case days_remaining === 1 → "dzień" (small pluralize helper), or reword to avoid count-noun agreement.
- **Decision**: FIXED (added `dayWord` helper in notification-panel.tsx; 1 → "dzień", else "dni", 2026-07-08)

### F4 — Notification panel list has no height cap / scroll (found post-review)

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality (UX reliability)
- **Location**: features/notifications/components/notification-panel.tsx:109
- **Detail**: User-reported after Phase 6 landed. The panel's `<ul>` had no `max-height`, so with many active alerts the list grew unbounded and ran off the bottom of the viewport with no way to scroll to the lower items — they were unreachable. Not caught by the Phase 6 component tests (jsdom does not compute layout) nor manual check 6.3 (tested with a short list).
- **Fix**: Cap the list at `max-h-[70vh] overflow-y-auto` so only the list scrolls while the "Odrzuć wszystkie" header stays pinned. Applied 2026-07-08.
- **Verification**: jsdom regression test added (notification-bell.test.tsx — 15 items, asserts `max-h-[70vh]` + `overflow-y-auto` on the list); real Chromium run at mobile (375×667) and desktop (1280×800) confirmed the list caps at exactly 70vh, content overflows and scrolls (scrollTop moves), and the whole panel stays within the viewport. Build + lint + prettier + `npm run test:run` (5/5 notifications tests) green.
- **Decision**: FIXED

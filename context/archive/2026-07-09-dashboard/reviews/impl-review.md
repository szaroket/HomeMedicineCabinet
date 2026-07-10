<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Dashboard (S-07 / FR-009)

- **Plan**: context/changes/dashboard/plan.md
- **Scope**: All 4 phases (full-plan review)
- **Date**: 2026-07-10
- **Verdict**: APPROVED (all findings triaged & fixed 2026-07-10)
- **Findings**: 1 critical, 0 warnings, 2 observations — all FIXED

The code is correct and every planned change matches intent. The single blocker
was stale test wiring introduced by the develop merge (891080d) — a one-file test
fix, not a product defect. Triage 2026-07-10: F1 fixed via Fix A (dashboard suite
8/8), F2 documented the parity invariant, F3 hardened NotificationBell against a
missing `items`.

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS (1 observation) |
| Architecture | PASS |
| Pattern Consistency | PASS (1 observation) |
| Success Criteria | PASS (F1 fixed; dashboard suite 8/8) |

## Automated verification (run at HEAD)

- ✅ frontend `tsc -b` — pass
- ✅ frontend `eslint` — pass
- ✅ frontend `prettier --check src/features/dashboard` — pass
- ❌ frontend `vitest run src/features/dashboard` — 3 failed / 65 passed (see F1)
- ✅ backend `ruff check` + `ruff format --check` (cabinet) — pass
- ⏸ backend `pyright` / `pytest tests/cabinet` / integration `test_summary.py` — could not run from the Bash tool (L-001 OpenSSL applink abort); passed at d8b08c0 and backend files are unchanged since. Re-run from native PowerShell to reconfirm.

## Findings

### F1 — dashboard-page.test.tsx: 3 component tests fail at HEAD

- **Severity**: ❌ CRITICAL — failing tests (Phase 3 criterion 3.4)
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Success Criteria
- **Location**: frontend/src/features/dashboard/components/dashboard-page.test.tsx:65
- **Detail**: `npx vitest run src/features/dashboard` fails 3 of 4 tests in dashboard-page.test.tsx (full suite: 3 failed / 65 passed). These passed when Phase 3 landed (7088759) but broke at the develop merge (891080d): `AppLayout` now renders `<NotificationBell/>` (app-layout.tsx:45), which calls `useNotifications()` and fires a *second* fetch. The test stubs a single bare `vi.fn()` and queues `mockResolvedValueOnce` per call, so (a) the retry test asserts `fetch` called 2× but gets 3× (dashboard-page.test.tsx:65), and (b) the notifications query consumes the summary's `once` response, leaving `data.items` undefined → NotificationBell crashes on `data?.items.length` (notification-bell.tsx:8). Phase 4 only ran the targeted sidebar test and the epilogue didn't re-run the frontend suite, so the merge regression was never caught. Sibling cabinet-page.test.tsx survives because its fetch mock is URL-aware (routes `/notifications`).
- **Fix A ⭐ Recommended**: Mock `useNotifications` in the dashboard test — add `vi.mock("@/features/notifications/api/notifications-queries", () => ({ useNotifications: () => ({ data: { items: [] } }) }))` at the top of dashboard-page.test.tsx.
  - Strength: Isolates the dashboard component test from an unrelated feature AppLayout pulls in; the bell fires no fetch, so all existing assertions (incl. `toHaveBeenCalledTimes(2)`) stay valid untouched. Bell integration is already covered by notification-bell.test.tsx.
  - Tradeoff: Test no longer exercises the real bell wiring (by design — that's another test's job).
  - Confidence: HIGH — smallest edit; assertions unchanged.
  - Blind spot: None significant.
- **Fix B**: URL-aware fetch mock mirroring cabinet-page.test.tsx — route `url.includes("/notifications")` → empty list, else the summary response, and rework the retry test to count only summary calls instead of total `fetch` calls.
  - Strength: More integration-faithful; consistent with the cabinet-page.test.tsx pattern in this repo.
  - Tradeoff: More code; forces reworking the `toHaveBeenCalledTimes(2)` assertion since the bell still calls fetch.
  - Confidence: MED — heavier change, more surface to get wrong.
  - Blind spot: Other queued `once` responses may still race between the two queries.
- **Decision**: FIXED via Fix A (vi.mock of useNotifications; dashboard suite 8/8 pass)

### F2 — `total` parity silently depends on expiry_date NOT NULL

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/api/v1/cabinet/crud.py:483-493
- **Detail**: `total` uses `func.count()` while valid/expiring/expired use `SUM(CASE …)`. The `total == valid+expiring+expired` invariant (and its parity test) holds only because `CabinetEntry.expiry_date` is NOT NULL (models.py:24) — a NULL-expiry row would be counted in `total` but fall into no status bucket. Correct today; the coupling is just undocumented.
- **Fix**: Add a one-line comment at count_summary noting the parity relies on expiry_date being non-nullable.
- **Decision**: FIXED (comment added above the summary select in crud.py)

### F3 — NotificationBell latent NPE (outside dashboard diff)

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Reliability
- **Location**: frontend/src/features/notifications/components/notification-bell.tsx:8
- **Detail**: `data?.items.length` guards `data` but not `items`; if the query ever resolves with a body lacking `items`, this throws (it is what surfaces the F1 crash). Not part of the dashboard diff — flagging only because this review empirically triggered it. Belongs to the notifications feature; fix there, not in this change.
- **Fix**: `data?.items?.length ?? 0` (in the notifications feature, not this change's scope).
- **Decision**: FIXED (notification-bell.tsx:8 now optional-chains items)

---
change_id: testing-backend-safety-net
title: Backend business-logic + CRUD safety net (test-plan Phase 1)
status: plan_reviewed
created: 2026-06-16
updated: 2026-06-30
archived_at: null
---

## Notes

Open a change folder for rollout Phase 1 of context/foundation/test-plan.md:
"Backend business-logic + CRUD safety net".
Risks covered: #1 (silent data-path regression), #3 (dedup/merge math
corrupts tablet totals, FR-010), #4 (cabinet filter/search/status wrong
set), #5 (cross-account leak / wrong-owner read or write).
Test types planned: backend unit (pure domain functions in service.py) +
integration (httpx AsyncClient over routers/CRUD).
Risk response intent:
- #1: prove a populated cabinet still returns its rows with correct shape
  after a change (an empty list is also a 200).
- #3: prove known inputs → known merged totals/normalization per FR-010
  (full + partial package); oracle from FR-010, not the implementation.
- #4: prove seeded cabinet + filter/search/sort/status → exactly the
  expected entry set (membership, not just count).
- #5: prove user B is rejected/empty on user A's resource; writes verify
  ownership, not just authentication.
After creating the folder, follow the downstream continuation rule.

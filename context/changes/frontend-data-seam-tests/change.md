---
change_id: frontend-data-seam-tests
title: Frontend data-seam unit tests (API-calling layer, bootstraps Vitest)
status: plan_reviewed
created: 2026-07-03
updated: 2026-07-03
archived_at: null
---

## Notes

Phase 3 from context/foundation/test-plan.md (§3 Phased Rollout, row 3):
Verify the API-calling layer (typed fetchers, request/response shape, error
handling) cheaply. Bootstraps Vitest. Narrow by design — scoped to
`features/<feature>/api/`, not presentational components. Covers risks #2
and #1. See test-plan.md §6.4 for the cookbook pattern (currently TBD, to be
filled in as this phase lands).

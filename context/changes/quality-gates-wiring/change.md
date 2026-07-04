---
change_id: quality-gates-wiring
title: Wire frontend-unit and e2e jobs into CI to close the remaining gates
status: impl_reviewed
created: 2026-07-04
updated: 2026-07-04
archived_at: null
---

## Notes

phase 4 from @context/foundation/test-plan.md

Test plan §3 Phase 4 ("Quality-gates wiring"): close the remaining CI gaps by
wiring the **frontend-unit** and **e2e** jobs into `.github/workflows/ci-cd.yml`
(the e2e job is currently a TODO stub). Lint/typecheck/backend-test/build
gates already ship via F-04 (`2026-06-29-ci-cd-wiring`). Covers Risks #1–#6
per the test plan's risk map (§2) since it's the gate layer, not new test
authoring. Frontend-unit tests landed in `frontend-data-seam-tests`; e2e
tests land in `critical-path-e2e` — this phase assumes both exist and wires
their runners into CI.

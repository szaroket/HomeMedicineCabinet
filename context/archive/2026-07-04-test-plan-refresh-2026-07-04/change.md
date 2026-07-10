---
change_id: test-plan-refresh-2026-07-04
title: Refresh test-plan.md — reconcile shipped rollout, add S-09/S-06 risks
status: archived
created: 2026-07-04
updated: 2026-07-10
archived_at: 2026-07-10T20:45:22Z
---

## Notes

Triggered by `/10x-test-plan --refresh` (2026-07-04). Primarily documentation
reconciliation + a forward-looking risk-map extension, not new test code.

Honest refresh triggers (guide vs disk):

- **§3 rollout is effectively complete but mislabeled.** All four phases are
  archived (`2026-06-16-testing-backend-safety-net`, `2026-07-01-critical-path-e2e`,
  `2026-07-03-frontend-data-seam-tests`, `2026-07-04-quality-gates-wiring`), yet
  §3 showed Phase 1 `change opened`, Phase 2 `not started`, Phase 3
  `implementing`; Phase 1/3 change-folder cells pointed at `context/changes/`
  folders that have moved to `context/archive/`.
- **§4 Stack stale.** Guide claimed frontend suite = "none yet"; frontend now
  has a meaningful Vitest suite (api-client, cabinet-api, auth-api, settings-api,
  auth-schemas) + Playwright e2e (playwright.config.ts, auth.setup.ts,
  manage-cabinet-entry.spec.ts, seed.spec.ts). Backend grew 17→24 test files
  incl. full `tests/integration/cabinet/`. Test-base bucket is now `meaningful`
  on both sides.
- **New risk surface from the roadmap** (`proposed` slices, user-confirmed): S-09
  delete-user-account (irreversible cascade delete / IDOR — user's #1 worry) and
  S-06 notifications (dismiss-don't-re-fire idempotency + threshold gating).

## Scope (user-approved)

1. Reconcile §3 (Phases 1–3 → `complete`, repoint folders to archive), §4
   (frontend → meaningful; backend 17→24), §8 (dates → 2026-07-04).
2. Add §2 Risk #7 (S-09, TOP) + #8 (S-06) with Risk Response Guidance rows
   (evidence + response intent only, no file anchors — §1 principle #3).
3. Add §3 rollout phases for S-09 (and S-06), marked **gated on the feature
   shipping** — both slices are unshipped, so their test code cannot be written
   until the slice lands (mirrors how S-05/Risk #6 was handled).

Out of scope: the parked login-refresh bug (user did not select it as a top
risk) — noted only as a watch item. §7 negative space stays as-is.

## Epilogue (closed 2026-07-10)

All three scope items landed **in-place** in `context/foundation/test-plan.md`
(this was a documentation-only reconciliation, no downstream research/plan): §3
Phases 1–3 → `complete` and repointed to archive, §4 frontend → `meaningful` +
backend 17→24, §2 Risks #7/#8 + Risk Response Guidance rows added, §3 gated
Phases 5–6 added, §8 dates bumped. The folder was left `in-progress` by mistake
(no research/plan artifacts were ever needed). Closed and archived during the
2026-07-10 docs-only refresh, which superseded it — by then S-09 and S-06 had
shipped, so §3 Phases 5–6 moved from `gated` to `complete` (covered by slice
tests). See the guide header + §8 for the 2026-07-10 entry.

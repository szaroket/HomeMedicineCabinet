---
change_id: notifications-and-badges
title: Notifications and badges
status: archived
created: 2026-07-06
updated: 2026-07-09
archived_at: 2026-07-09T13:32:34Z
---

## Notes

<!-- Free-form notes for this change: links, ad-hoc context, decisions that don't belong in research/frame/plan. -->

### Resolved planning flags (2026-07-07)

- **Phase 5 kept as explicit `delete_by_user`.** The `cabinet_entry_id` FK `ON DELETE CASCADE` already removes dismissals transitively on account delete (S-09 deletes all the user's entries first), so Phase 5 is technically redundant — but kept as belt-and-suspenders: documents intent, survives any future reorder of the S-09 entry-delete, and gives a dedicated no-orphans integration test for test-plan Risk #7.
- **Login-refresh bug left parked.** The roadmap-parked "login requires a manual page refresh" bug is out of scope for S-06; it needs its own `/10x-frame` root-cause pass. S-06 is built/tested against an already-logged-in user, so the bug does not block it. Manual end-to-end testing may hit the login friction until it's fixed separately.
- **Scope reconsidered and confirmed full.** Weighed dropping S-06 to v2 (dashboard-only) or shipping simplified read-only alerts on the dashboard. Decided to keep the full notification center + dismiss/GC as planned: in-app alerting is a PRD *primary* success criterion (#2) and multiple must-have FRs (007/008/019/020), and it's the product's core "proactive" value — a passive inventory list without it. Note: the dashboard (S-07) does **not** actually depend on S-06 — its five counts are computable from fields already shipped in S-02/S-04/S-05.

### Post-review fixes (2026-07-08)

- **Notification panel now scrolls when the list is long.** User-reported after Phase 6: with many active alerts the panel list ran off-screen with no scroll. Fixed by capping the `<ul>` at `max-h-[70vh] overflow-y-auto` (`notification-panel.tsx`) so only the list scrolls while the "Odrzuć wszystkie" header stays pinned. Guarded by a jsdom regression test (asserts both classes on the list) and confirmed in a real Chromium run at mobile (375×667) and desktop (1280×800): list caps at exactly 70vh, content overflows and scrolls, and the whole panel stays within the viewport on both. Logged as F4 in `reviews/impl-review-phase-6.md`.

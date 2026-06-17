---
change_id: mobile-responsive-cabinet
title: Mobile responsive cabinet
status: impl_reviewed
created: 2026-06-17
updated: 2026-06-17
archived_at: null
---

## Notes

<!-- Free-form notes for this change: links, ad-hoc context, decisions that don't belong in research/frame/plan. -->

- **Known issue found during Phase 2 manual testing**: changing sort order (`Sortowanie` on mobile, `Nazwa A→Z/Z→A` on desktop) resets the page back to 1, even when the user was on a different page. This is pre-existing behavior (`setParam("order", ..., true)` passes `resetPage=true`) carried unchanged into the new mobile sort button — not a regression introduced by this change, but worth fixing. Candidate fix: stop resetting the page on sort-order change, since sort is a display preference, not a filter (see `clearFilters` comment in `cabinet-page.tsx`, which already treats sort/page-size as preferences, not filters). Consider addressing this as part of Phase 3 (pagination work touches the same page-state logic).

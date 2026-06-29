---
change_id: frontend-structure
title: Frontend directory structure
status: archived
created: 2026-06-05
updated: 2026-06-29
archived_at: 2026-06-29T00:00:00Z
---

## Notes

<!-- Free-form notes for this change: links, ad-hoc context, decisions that don't belong in research/frame/plan. -->

- Best-practices research → [research.md](./research.md). Recommends a lightweight **hybrid `features/` + thin shared layer** (trimmed Bulletproof React), `@/` path aliases, no barrel files, colocated Vitest tests, Playwright in `frontend/e2e/`.

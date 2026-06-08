---
change_id: auth-scaffold
title: Auth scaffold
status: impl_reviewed
created: 2026-06-05
updated: 2026-06-08
archived_at: null
---

## Notes

<!-- Free-form notes for this change: links, ad-hoc context, decisions that don't belong in research/frame/plan. -->

- Library research → [research.md](./research.md). Decision: `supabase-py` (Auth client) + `PyJWT` with JWKS/`PyJWKClient` for local token verification. Avoid `python-jose` (abandoned, dropped by FastAPI).
- Plan review (2026-06-05) → [reviews/plan-review.md](./reviews/plan-review.md). All 3 findings fixed in plan; verdict REVISE → SOUND. F1: hermetic tests via `get_session` override (extends existing conftest). F2: Phase 1 guard gates reworded, real-route 401/200 check moved to Phase 2 (2.6). F3: localStorage/XSS accepted-risk note added.

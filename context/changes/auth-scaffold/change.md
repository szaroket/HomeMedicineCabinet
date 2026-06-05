---
change_id: auth-scaffold
title: Auth scaffold
status: planned
created: 2026-06-05
updated: 2026-06-05
archived_at: null
---

## Notes

<!-- Free-form notes for this change: links, ad-hoc context, decisions that don't belong in research/frame/plan. -->

- Library research → [research.md](./research.md). Decision: `supabase-py` (Auth client) + `PyJWT` with JWKS/`PyJWKClient` for local token verification. Avoid `python-jose` (abandoned, dropped by FastAPI).

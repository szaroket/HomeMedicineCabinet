# SPA Refresh Fallback — Plan Brief

> Full plan: `context/changes/spa-refresh-fallback/plan.md`

## What & Why

Refreshing or deep-linking a client-side route (`/cabinet`, `/cabinet/add`,
`/settings`) on the deployed frontend returns Render's static 404 — the app never
boots. The router uses the HTML5 history API but the Render Static Site has no
history-fallback rewrite. We add the canonical `/* → /index.html` rewrite so the
SPA always loads, plus a Polish 404 page for genuinely-unknown paths.

## Starting Point

`render.yaml`'s `type: static` frontend service has no `routes:` block, so Render
404s on any path without a matching file. The router (`createBrowserRouter`) has
no `*` catch-all. Auth-on-refresh already works (localStorage + silent refresh),
and dev/`vite preview` already do fallback — so the bug is Render-only.

## Desired End State

On the live Render frontend, refreshing/deep-linking any real route loads the
correct page (behind the existing auth gate), and an unknown path renders a Polish
"nie znaleziono strony" page with a link home — no English React Router error.

## Key Decisions Made

| Decision             | Choice                                              | Why (1 sentence)                                                        | Source |
| -------------------- | --------------------------------------------------- | ---------------------------------------------------------------------- | ------ |
| Rewrite location     | `render.yaml` routes + documented dashboard step    | Version-controlled and reproducible, safe whether or not Blueprint-synced | Plan   |
| Unknown-route 404    | Polish `NotFoundPage` catch-all `*` route           | Satisfies the Polish-only hard rule; real UX vs default English error   | Plan   |
| Verification         | `vite preview` + unit-test 404 + manual deploy check | Automates what's automatable; pins the untestable hosting bit to a manual step | Plan   |
| Scope                | Rewrite + Polish 404 only                           | Targets the actual bug; auth/dev already work                          | Plan   |
| Fix mechanism        | Server rewrite (not HashRouter)                     | Keeps clean URLs; standard SPA hosting pattern                         | Plan   |

## Scope

**In scope:**
- `render.yaml` history-fallback rewrite (`/* → /index.html`, rewrite action)
- Documented Render dashboard fallback (for manually-created, non-Blueprint sites)
- Polish `NotFoundPage` + top-level `*` route + unit test

**Out of scope:**
- Auth-on-refresh / session rehydration (already works)
- Dev server / `vite preview` (already do fallback)
- Any backend/API/database change; `HashRouter`; per-route `errorElement`

## Architecture / Approach

Two independent changes. **Hosting:** add a `routes` rewrite to the Render static
service so non-file paths serve `index.html` (URL preserved). **Client:** add a
top-level `*` route (outside `ProtectedLayout`, so it isn't pushed through the
auth gate) rendering an app-level `NotFoundPage` that follows the existing
`dashboard-page.tsx` pattern (Tailwind, Polish, `Link`).

## Phases at a Glance

| Phase                              | What it delivers                                   | Key risk                                                              |
| ---------------------------------- | -------------------------------------------------- | -------------------------------------------------------------------- |
| 1. Render history-fallback rewrite | Deep-link/refresh loads the SPA instead of 404     | render.yaml may not drive the live service — needs a dashboard apply |
| 2. Polish catch-all 404 route      | Unknown paths render a Polish 404 with a home link | Catch-all placed under the auth gate would redirect 404s to `/login` |

**Prerequisites:** Access to the Render dashboard to confirm/apply the rewrite
after deploy.
**Estimated effort:** ~1 short session across 2 phases.

## Open Risks & Assumptions

- **render.yaml may not be the live source of truth** (`autoDeploy: false`,
  hook-based deploy). If the static site was created manually, the rewrite must be
  applied once in the dashboard — Phase 1 documents this so the fix isn't silently
  ineffective.
- Assumes the existing auth rehydration continues to work on refresh (unchanged).

## Success Criteria (Summary)

- Refreshing `/cabinet` (and other deep routes) on the live Render URL loads the
  app, not a 404.
- Visiting an unknown path shows a Polish 404 page with a working home link.
- The 404 page is covered by a passing unit test; build/typecheck/lint stay green.

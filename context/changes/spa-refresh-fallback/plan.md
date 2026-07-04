# SPA Refresh Fallback Implementation Plan

## Overview

Deep-linking or refreshing (F5) a client-side route such as `/cabinet`,
`/cabinet/add`, or `/settings` on the deployed frontend returns Render's static
404 page — the app never boots. The frontend uses `createBrowserRouter` (real
HTML5 history paths) and is served as a **Render Static Site**, which has no
history-fallback rewrite configured. This plan adds the canonical Render rewrite
(`/* → /index.html`, rewrite action) so the SPA always loads and its router
takes over, and adds a Polish catch-all 404 page so genuinely-unknown paths get
a proper in-app screen instead of React Router's default English error.

## Current State Analysis

- **Router uses the history API.** `frontend/src/app/router.tsx:11` calls
  `createBrowserRouter` with real paths (`/`, `/cabinet`, `/cabinet/add`,
  `/settings`, `/login`, `/register`). These require the host to serve
  `index.html` for any path that isn't a real file.
- **Frontend is a Render Static Site with no rewrite.** `render.yaml:22-31`
  defines `type: static`, `staticPublishPath: dist`, and has **no `routes:`
  block**. Render therefore looks for a file at the requested path and 404s when
  none exists. This is the root cause and it is server-side, not client-side.
- **Auth-on-refresh already works and is out of scope.** The token persists in
  `localStorage` (`frontend/src/features/auth/store.ts:30,86`) and rehydrates on
  reload via `use-session-init.ts:14-24` (plus a silent `refreshOnce`). Refresh
  does not log users out; the only failure is the server 404.
- **No catch-all / error route exists.** `router.tsx` defines no `*` route and no
  `errorElement`. Once the fallback serves `index.html` for an unknown path,
  React Router renders its built-in **English** error screen — a violation of the
  Polish-only hard rule (AGENTS.md "All user-facing text must be in Polish").
- **Dev already behaves correctly.** Vite's dev server and `vite preview` both do
  history-fallback automatically, so the bug is invisible locally and only
  manifests on Render. This is why verification of the rewrite itself is
  necessarily manual/post-deploy.
- **Page pattern to follow:** `frontend/src/features/dashboard/components/dashboard-page.tsx`
  — pages compose `AppLayout`, use `react-router-dom` `Link`, Polish copy, and
  Tailwind utility classes.

## Desired End State

On the deployed Render frontend:

1. Refreshing or deep-linking any real route (`/cabinet`, `/cabinet/add`,
   `/settings`, `/`) loads the SPA and lands on the correct page (subject to the
   existing auth gate) instead of a Render 404.
2. Visiting an unknown path (e.g. `/nonexistent`) loads the SPA and renders a
   Polish "nie znaleziono strony" page with a link back into the app — no English
   error screen.

Verification: (a) `vite preview` serves deep routes locally without 404;
(b) the `NotFoundPage` renders Polish copy and a working home link (unit test);
(c) after deploy, manually refreshing a deep route on the live Render URL loads
the app.

### Key Discoveries:

- Render Blueprint static services accept a `routes:` list; a `type: rewrite`
  entry with `source: /*` and `destination: /index.html` is the documented
  history-fallback (rewrite serves the file *without* changing the URL, unlike a
  redirect). Add it to `render.yaml:22-31`.
- Static hosts serve existing files (hashed `dist/assets/*`) before applying
  rewrites, so `/*` does not clobber real asset requests. The static service
  serves only the frontend — API calls go to `VITE_API_URL` (the separate backend
  service) — so no `/api` exclusion is needed.
- Accepted tradeoff: a *deleted* hashed asset (e.g. an old tab requesting
  `/assets/index-<oldhash>.js` after a redeploy) no longer exists, so the catch-all
  serves `index.html` (HTTP 200, `text/html`) instead of a clean 404 — surfacing as
  a confusing MIME/parse error in that stale tab. Low impact here (infrequent
  deploys, small surface); no mitigation planned.
- The catch-all must be a **top-level** route (sibling of the layout routes), not
  a child of `ProtectedLayout`, so a 404 does not get pushed through the auth gate
  and redirected to `/login`.

## What We're NOT Doing

- Not touching auth-on-refresh / session rehydration — it already works
  (`use-session-init.ts`, `store.ts`).
- Not changing the dev server or `vite preview` — history-fallback already works
  there.
- Not making any backend, database, or API change.
- Not switching the router to `HashRouter` (would fix refresh but change all URLs
  to `/#/...` — rejected in favour of the standard rewrite).
- Not adding per-route `errorElement` boundaries (separate concern from the 404
  fallback).

## Implementation Approach

Two small, independent phases. Phase 1 is the actual reported fix (a hosting
rewrite in `render.yaml`, plus a documented dashboard fallback for the case where
the Render service was created manually rather than Blueprint-synced). Phase 2 is
the UX completion the fallback enables: a Polish catch-all 404 route with a unit
test. Phase 1 first because it fixes the user-visible bug; Phase 2 closes the
Polish-only gap that the fallback exposes.

## Critical Implementation Details

- **Rewrite vs redirect.** The Render route must use `type: rewrite` (serves
  `index.html` at the original URL) — a `redirect` would change the browser URL to
  `/index.html` and break client routing. This distinction is load-bearing.
- **render.yaml may not be the live source of truth.** `autoDeploy: false` and
  deploy-via-hook (`.github/workflows/ci-cd.yml:302-305`) mean the Render services
  may have been created manually in the dashboard rather than synced from this
  Blueprint. If so, editing `render.yaml` alone will not apply the rewrite — it
  must also be set once in the dashboard (Static Site → Redirects/Rewrites: source
  `/*`, destination `/index.html`, action Rewrite). Phase 1 documents this so the
  fix is not silently ineffective in production.

## Phase 1: Render History-Fallback Rewrite

### Overview

Add the SPA history-fallback rewrite to the Render static service so deep-link
and refresh serve `index.html` instead of 404, and document the dashboard step
in case the service is not Blueprint-synced.

### Changes Required:

#### 1. Render static service rewrite

**File**: `render.yaml`

**Intent**: Add a history-fallback rewrite to the `home-medicine-cabinet-frontend`
static service so any path without a matching file serves the SPA entry point.

**Contract**: Add a `routes:` list to the `type: static` service with one entry —
`type: rewrite`, `source: /*`, `destination: /index.html`. Keep it a rewrite (not
a redirect) so the URL is preserved.

```yaml
  - type: static
    name: home-medicine-cabinet-frontend
    # ...existing keys unchanged...
    routes:
      - type: rewrite
        source: /*
        destination: /index.html
```

#### 2. Document the dashboard fallback

**File**: `context/foundation/infrastructure.md` (Operational Story / Getting
Started section).

**Intent**: Record that the SPA rewrite must also be applied in the Render
dashboard if the static site was created manually rather than from the Blueprint,
so the fix isn't silently ineffective. Note the exact dashboard values.

**Contract**: One short subsection: Static Site → Redirects/Rewrites → source
`/*`, destination `/index.html`, action **Rewrite**. Prose only; no code.

### Success Criteria:

#### Automated Verification:

- Frontend build still succeeds: `cd frontend && npm run build`
- `render.yaml` is valid YAML (parses without error)

#### Manual Verification:

> Note on what proves what: `vite preview` does history-fallback automatically
> and never reads `render.yaml` (Current State, above), so the local preview step
> only confirms the **production bundle can client-route to a deep path** — it
> passes identically with or without the rewrite and does **not** validate the
> rewrite. The rewrite itself is validated ONLY by the live steps (1.5, 1.6).
> "Valid YAML" (1.2) is likewise not "valid Render Blueprint" — hence the
> pre-deploy eyeball step below.

- Pre-deploy eyeball: confirm the new `routes:` block is nested under the
  `home-medicine-cabinet-frontend` static service (correct indentation) and uses
  Render's exact key names (`type: rewrite`, `source`, `destination`) before
  pushing — a mis-nested/mistyped block parses as valid YAML but silently does
  nothing.
- `cd frontend && npm run build && npm run preview`, then hard-navigate to
  `http://localhost:4173/cabinet` and refresh — the app loads (no 404). This
  confirms the production bundle client-routes to a deep path; it does not
  validate the rewrite.
- After deploy, refreshing `/cabinet` (and other deep routes) on the live Render
  URL loads the app instead of Render's 404. **This is the primary validation of
  the rewrite.**
- The rewrite rule is confirmed present in the Render dashboard (Blueprint-synced
  or manually applied per the documented step).

**Implementation Note**: After completing this phase and all automated
verification passes, pause here for manual confirmation from the human that the
manual testing (local `vite preview` and, once deployed, the live refresh check)
was successful before proceeding to the next phase.

---

## Phase 2: Polish Catch-All 404 Route

### Overview

Add a top-level `*` catch-all route that renders a Polish "not found" page, so
unknown paths (now served the SPA by the Phase 1 rewrite) get a proper in-app
screen instead of React Router's default English error.

### Changes Required:

#### 1. NotFoundPage component

**File**: `frontend/src/app/components/not-found-page.tsx`

**Intent**: A standalone Polish 404 page — a short "nie znaleziono strony"
message and a `Link` back into the app (`/`). App-level (not feature-scoped)
because it is domain-agnostic.

**Contract**: `export function NotFoundPage()` returning a standalone centered
layout with Polish copy and a `react-router-dom` `Link` to `/`. Standalone shell
— do **not** require `AppLayout`/auth (`AppLayout` pulls in the auth-coupled
`LogoutButton`, `app-layout.tsx:6,43`), since a 404 may be hit while
unauthenticated. Since `AppLayout` is removed, the page must supply its own shell;
match the app's dark theme rather than `dashboard-page.tsx` (which is only
`<AppLayout><Link/></AppLayout>` once the layout is gone):

- Root: a full-height, flex-centered container on the app's dark background —
  `flex min-h-screen flex-col items-center justify-center bg-slate-900 px-6 text-center`
  (mirrors `AppLayout`'s `bg-slate-900`, `app-layout.tsx:17`).
- Heading: Polish `<h1>` (e.g. "Nie znaleziono strony") in a prominent size with
  light text — `text-2xl font-semibold text-white`.
- Optional supporting `<p>` line in `text-slate-400`.
- `Link to="/"` styled as a call-to-action with the app's blue accent
  (`text-blue-500`, `focus:ring-blue-500` idiom from `app-layout.tsx`), Polish
  label (e.g. "Wróć do strony głównej").

These classes are a concrete starting point, not a hard spec — adjust to keep
visual parity with the rest of the app.

#### 2. Register the catch-all route

**File**: `frontend/src/app/router.tsx`

**Intent**: Add a top-level `*` route so any unmatched path renders
`NotFoundPage`, outside the `ProtectedLayout` auth gate.

**Contract**: Add `{ path: "*", element: <NotFoundPage /> }` as a top-level entry
in the `createBrowserRouter` array (a sibling of the existing layout route
objects, not a child of `ProtectedLayout`). Import `NotFoundPage` alongside the
other page imports.

#### 3. Unit test

**File**: `frontend/src/app/components/not-found-page.test.tsx`

**Intent**: Verify the page renders Polish copy and a home link.

**Contract**: Vitest + React Testing Library. Render `NotFoundPage` inside a
router context (e.g. `MemoryRouter`) and assert the Polish heading text is present
and a link resolving to `/` exists. Use `getByRole`/`getByText` locators per the
repo's a11y-first convention.

### Success Criteria:

#### Automated Verification:

- Unit tests pass: `cd frontend && npm run test:run`
- Type check passes: `cd frontend && npm run typecheck`
- Lint passes: `cd frontend && npm run lint`
- Build succeeds: `cd frontend && npm run build`

#### Manual Verification:

- `npm run dev`, visit `/nonexistent` — the Polish 404 page renders (not the
  English React Router error), and the home link returns to the app.
- Visiting `/nonexistent` while unauthenticated shows the 404 page (not a redirect
  to `/login`).

**Implementation Note**: After completing this phase and all automated
verification passes, pause here for manual confirmation from the human that the
manual testing was successful.

---

## Testing Strategy

### Unit Tests:

- `NotFoundPage` renders the Polish not-found message and a working link to `/`.

### Integration Tests:

- None required — no backend/API surface changes.

### Manual Testing Steps:

1. `cd frontend && npm run build && npm run preview`; navigate to
   `/cabinet` and refresh — app loads, no 404.
2. `npm run dev`; visit `/nonexistent` — Polish 404 page renders; home link works.
3. Visit `/nonexistent` while logged out — 404 shows, no redirect to `/login`.
4. Post-deploy: refresh `/cabinet` and other deep routes on the live Render URL —
   app loads; confirm the rewrite rule exists in the Render dashboard.

## Performance Considerations

None. The rewrite adds no runtime cost (static hosts serve real files first); the
404 component is a trivial leaf.

## Migration Notes

None. If the Render static site was created manually (not from the Blueprint),
the rewrite must be applied once in the dashboard — see Phase 1, change 2.

## References

- Router: `frontend/src/app/router.tsx:11`
- Render static service: `render.yaml:22-31`
- Deploy pipeline (autoDeploy off, hook-based): `.github/workflows/ci-cd.yml:281-305`
- Auth-on-refresh (out of scope, already works): `frontend/src/features/auth/hooks/use-session-init.ts`, `frontend/src/features/auth/store.ts`
- Page pattern: `frontend/src/features/dashboard/components/dashboard-page.tsx`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Render History-Fallback Rewrite

#### Automated

- [x] 1.1 Frontend build still succeeds: `cd frontend && npm run build`
- [x] 1.2 `render.yaml` is valid YAML (parses without error)

#### Manual

- [x] 1.3 Pre-deploy eyeball: `routes:` block nested under the static service with Render's exact key names
- [x] 1.4 `vite preview` confirms the production bundle client-routes to a deep path (no 404; not rewrite validation)
- [ ] 1.5 Live Render URL: refreshing deep routes loads the app (primary rewrite validation)
- [ ] 1.6 Rewrite rule confirmed present in the Render dashboard

### Phase 2: Polish Catch-All 404 Route

#### Automated

- [ ] 2.1 Unit tests pass: `cd frontend && npm run test:run`
- [ ] 2.2 Type check passes: `cd frontend && npm run typecheck`
- [ ] 2.3 Lint passes: `cd frontend && npm run lint`
- [ ] 2.4 Build succeeds: `cd frontend && npm run build`

#### Manual

- [ ] 2.5 `/nonexistent` renders the Polish 404 page with a working home link
- [ ] 2.6 `/nonexistent` while unauthenticated shows the 404 (no redirect to `/login`)

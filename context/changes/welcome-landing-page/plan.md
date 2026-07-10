# Welcome Landing Page (S-10) Implementation Plan

## Overview

Build a public welcome/landing page for unauthenticated visitors that briefly describes the app and what they can do, with clear paths to register and log in. The landing page becomes the public front door at `/`; the dashboard (currently at `/`) moves to `/dashboard`. Already-authenticated visitors who hit any public page (`/`, `/login`, `/register`) are redirected past it to the dashboard.

This is roadmap slice **S-10** (`context/foundation/roadmap.md:273`). All user-facing text is Polish per the project NFR.

## Current State Analysis

- **Routing** (`frontend/src/app/router.tsx`) uses `react-router-dom` `createBrowserRouter` with two layout-wrapper groups and a catch-all:
  - **Public group** wrapped by `<PublicLayout />` (`router.tsx:14-21`): `/login`, `/register`, `/account-deleted`.
  - **Protected group** wrapped by `<ProtectedLayout />` (`router.tsx:22-30`): `/` (dashboard), `/cabinet`, `/cabinet/add`, `/settings`.
  - Catch-all `path: "*"` → `NotFoundPage` (`router.tsx:31`).
- **`PublicLayout` is a bare pass-through** (`frontend/src/app/layouts/public-layout.tsx:3-5`) — it renders `<Outlet />` with no auth check. A logged-in user can currently still see the login/register forms (an existing gap this plan closes).
- **`ProtectedLayout` is the guard** (`frontend/src/app/layouts/protected-layout.tsx`): reads `useAuth().token`, shows a "Ładowanie…" spinner while `useSessionInit()` validates, then `<Navigate to="/login" replace />` when there is no token.
- **Auth state** is a React Context (`frontend/src/features/auth/store.ts`), token persisted in `localStorage`; a component is "authenticated" when `useAuth().token` is truthy.
- **The dashboard is mounted at `/`** — there is no `/dashboard` route today. Post-login and post-register both `navigate("/")` (`login-form.tsx:22`, `register-form.tsx:27`).
- **Public-page convention** (model: `frontend/src/features/auth/components/login-page.tsx`): full-screen `flex min-h-screen flex-col bg-slate-900` shell, centered card, `logo.png` from `@/assets/logo.png`, Polish copy, `AppFooter` at the bottom, `Link` for internal nav. Tailwind-only dark theme (`slate-900/800/700`, `blue-600` accents). No shared button/input primitives — raw elements styled inline.

### Every `/`-reference that must change when the dashboard moves to `/dashboard` (8 references):

- `frontend/src/app/router.tsx:25` — `{ path: "/", element: <DashboardPage /> }` → `/dashboard`.
- `frontend/src/features/auth/components/login-form.tsx:22` — `navigate("/")` → `navigate("/dashboard")`.
- `frontend/src/features/auth/components/register-form.tsx:27` — `navigate("/")` → `navigate("/dashboard")`.
- `frontend/src/features/auth/components/account-deleted-page.tsx:13` — `<Navigate to="/" replace />` (its authed-visitor guard) → `/dashboard`.
- `frontend/src/app/components/app-sidebar.tsx:28` — `{ to: "/", label: "Panel główny", …, end: true }` → `/dashboard`.
- `frontend/src/app/components/app-sidebar.test.tsx:15` — asserts the "Panel główny" link `href="/"` → `/dashboard`.
- `frontend/src/app/components/not-found-page.tsx:13` — home `Link to="/"` **stays `/`** (now the public welcome page; an authed user clicking it is redirected onward by the new `PublicLayout` guard). Its test (`not-found-page.test.tsx:21`) asserting `href="/"` therefore needs **no** change.
- `frontend/e2e/auth.setup.ts:75` — `await page.waitForURL("/")` after the post-login redirect → `waitForURL("/dashboard")`. This is the shared `setup` project every chromium test depends on (`playwright.config.ts:39,47` via `dependencies: ['setup']`); once login lands on `/dashboard` (Phase 2 #3) a `waitForURL("/")` times out and fails the **entire** E2E suite. Line 76-78's `getByRole(link, "Apteczka")` assertion still holds on the dashboard, so only line 75 moves.

## Desired End State

- Visiting `/` while unauthenticated renders the Polish welcome page: logo + headline + one-paragraph description, 4 short capability highlights, and two CTAs (Register primary, Login secondary) linking to `/register` and `/login`, with `AppFooter` at the bottom.
- Visiting `/`, `/login`, or `/register` while authenticated redirects to `/dashboard`.
- Visiting `/dashboard` (and other protected routes) while unauthenticated redirects to `/` (the welcome page), a deliberate Phase 2 deviation from the original plan — see "Deviations from plan" below.
- Successful login or registration lands the user on `/dashboard`.
- The sidebar "Panel główny" link points to `/dashboard` and shows the active state there.
- `npm run build`, `npm run lint`, unit tests, and E2E all pass.

### Key Discoveries:

- The guard lives in the layout element, not a wrapper HOC — so the authed-redirect for public pages belongs in `PublicLayout` (`public-layout.tsx:3-5`), mirroring the `useAuth().token` + `<Navigate>` pattern from `protected-layout.tsx:17-19`.
- `/account-deleted` is a child of `PublicLayout`; after deletion the token is cleared, so the new authed-redirect guard will not fire during that flow (the user is unauthenticated there). Its own internal `to="/"` guard becomes redundant but is updated to `/dashboard` for consistency.
- Public pages own their full-screen shell + `AppFooter` themselves (`login-page.tsx:8,38`) — the welcome page follows the same self-contained pattern, not the sidebar `AppLayout`.

## What We're NOT Doing

- No rich multi-section marketing site (no scrolling feature sections, no how-it-works steps, no illustrations beyond the existing logo).
- No new backend endpoint, schema, or data fetching — the page is fully static.
- No new shared UI primitives (button/input) — styling stays inline per current convention.
- ~~No change to `ProtectedLayout`'s unauthenticated redirect target (stays `/login`).~~ Superseded during Phase 2 — see "Deviations from plan".
- No i18n framework — Polish copy is written inline as everywhere else.
- No changes to the login/register form internals beyond the post-submit navigation target.

## Implementation Approach

Build the self-contained welcome page component first (unit-testable in isolation, zero routing risk), then perform the routing rewire that mounts it at `/`, relocates the dashboard, adds the `PublicLayout` redirect guard, and updates every `/`-reference and its test in one coordinated phase. Splitting this way keeps the intermediate state shippable and isolates the higher-risk integration work.

## Critical Implementation Details

**State sequencing** — The `PublicLayout` guard should redirect on the presence of `token` alone (read synchronously from context/localStorage); it does not need `useSessionInit`'s silent-refresh validation. A stale token redirects to `/dashboard`, where `ProtectedLayout` then validates and, if invalid, clears the session and bounces back to `/login`. Do not add a second validation path in `PublicLayout`.

## Phase 1: Welcome page component

### Overview

Create the static, self-contained welcome page component with hero copy, four capability highlights, and the two CTAs. Unit-tested in isolation; not yet wired into the router.

### Changes Required:

#### 1. Welcome page component

**File**: `frontend/src/features/landing/components/welcome-page.tsx` (new)

**Intent**: A public marketing page describing the app and routing visitors to register/login. Follows the public-page shell convention from `login-page.tsx` (full-screen `bg-slate-900` column, centered content, `logo.png`, `AppFooter`) so it reads as part of the same product.

**Contract**: Exports `function WelcomePage()`. Structure:
- Full-screen shell: `flex min-h-screen flex-col bg-slate-900`, content area centered, `AppFooter` (`@/app/components/app-footer`) pinned at bottom.
- Hero: `logo.png` (`@/assets/logo.png`, alt `"Apteczka domowa"`), app name heading `Apteczka domowa`, one-paragraph Polish description of the app's purpose (registry-backed home medication tracking).
- Four capability highlights (short heading + one line each), Polish copy:
  1. **Czyste dane z rejestru** — leki dodajesz z oficjalnego polskiego rejestru, więc nazwy i dane są zawsze spójne.
  2. **Przypomnienia o terminach i zapasach** — dostajesz powiadomienia, gdy leki tracą ważność lub zapas ważnego leku spada poniżej minimum.
  3. **Śledzenie dawkowania** — ustaw harmonogram i zobacz szacowaną datę, kiedy skończy się lek, który aktualnie przyjmujesz.
  4. **Panel w jednym miejscu** — widzisz stan apteczki na skróty: ważne, kończące się i przeterminowane leki.
- Two CTAs: primary filled button/link `Zarejestruj się` → `/register`; secondary (outline or text link) `Zaloguj się` → `/login`. Use `Link` from `react-router-dom`. Register is visually primary.
- Reuse the Tailwind palette and card idiom from `login-page.tsx` (`slate-800` cards, `slate-700` borders, `blue-600` primary, `slate-400` muted text).

**Note**: Feature-card markup may be extracted to a small local sub-component in the same folder if it reduces repetition; not required. No `api/`/`schemas/` folders — this feature has no data layer.

#### 2. Welcome page unit test

**File**: `frontend/src/features/landing/components/welcome-page.test.tsx` (new)

**Intent**: Lock the page's public contract: it renders the headline, all four highlights, and both CTAs with correct destinations.

**Contract**: Vitest + React Testing Library, rendered inside a `MemoryRouter` (needed for `Link`). Assert via `getByRole`/`getByText`: heading `Apteczka domowa` present; the `Zarejestruj się` link has `href="/register"`; the `Zaloguj się` link has `href="/login"`; each of the four highlight headings is present. Use accessible-role/text locators (no test-ids, no CSS selectors).

### Success Criteria:

#### Automated Verification:

- [ ] Type check + build passes: `cd frontend && npm run build`
- [ ] Lint passes: `cd frontend && npm run lint`
- [ ] Format check passes: `cd frontend && npx prettier --check src/`
- [ ] Welcome page unit test passes: `cd frontend && npx vitest run src/features/landing`

#### Manual Verification:

- [ ] Rendering the component (via Storybook-less quick route or after Phase 2) shows logo, headline, four highlights, and both CTAs, all in Polish, with Register visually primary and no layout breakage at desktop and mobile widths.

**Implementation Note**: After completing this phase and all automated verification passes, pause for manual confirmation before proceeding to Phase 2.

---

## Phase 2: Routing rewire & redirects

### Overview

Mount the welcome page at `/` (public), move the dashboard to `/dashboard`, add the authed-visitor redirect guard to `PublicLayout`, and update every `/`-reference and its test. Add E2E coverage for the landing and redirect flows.

### Changes Required:

#### 1. Router: mount welcome, relocate dashboard

**File**: `frontend/src/app/router.tsx`

**Intent**: Make `/` the public welcome page and give the dashboard its own `/dashboard` path.

**Contract**: Import `WelcomePage` from `@/features/landing/components/welcome-page`. In the public group, add `{ path: "/", element: <WelcomePage /> }`. In the protected group, change the dashboard route from `path: "/"` to `path: "/dashboard"`. All other routes unchanged.

#### 2. PublicLayout: redirect authenticated visitors

**File**: `frontend/src/app/layouts/public-layout.tsx`

**Intent**: Send already-authenticated users away from public pages (`/`, `/login`, `/register`, `/account-deleted`) to the dashboard, closing the existing gap where logged-in users can see the auth forms.

**Contract**: Read `useAuth().token`; when truthy, `return <Navigate to="/dashboard" replace />`; otherwise render `<Outlet />`. Import `Navigate` and `useAuth` (mirror `protected-layout.tsx:1-2,17-19`). Do not add `useSessionInit` (see Critical Implementation Details).

#### 3. Post-auth navigation targets

**Files**: `frontend/src/features/auth/components/login-form.tsx` (line 22), `frontend/src/features/auth/components/register-form.tsx` (line 27)

**Intent**: Land users on the dashboard after login/registration now that it lives at `/dashboard`.

**Contract**: Change `navigate("/")` → `navigate("/dashboard")` in both `onSuccess` handlers.

#### 4. Account-deleted authed-guard target

**File**: `frontend/src/features/auth/components/account-deleted-page.tsx` (line 13)

**Intent**: Keep the redundant authed-visitor guard consistent with the new dashboard path.

**Contract**: Change `<Navigate to="/" replace />` → `<Navigate to="/dashboard" replace />`.

#### 5. Sidebar dashboard link

**File**: `frontend/src/app/components/app-sidebar.tsx` (line 28)

**Intent**: Point the "Panel główny" nav item at the dashboard's new path so navigation and active-state highlighting work.

**Contract**: Change the `TOP_NAV` entry `{ to: "/", label: "Panel główny", …, end: true }` → `to: "/dashboard"`. Keep `end: true`.

#### 6. Update affected tests

**Files**: `frontend/src/app/components/app-sidebar.test.tsx`, `frontend/src/features/auth/components/account-deleted-page.test.tsx`

**Intent**: Reflect the new dashboard path in every unit test that asserts against `/`, so `npx vitest run` (criterion 2.4) passes.

**Contract**:

- `app-sidebar.test.tsx` — the "marks it active only on the exact route" test renders at `/` and asserts both the href and the active state. Because the link moves to `/dashboard` with `end: true`, it is no longer active at `/`. Update **all three** touch-points:
  - `:15` assertion `toHaveAttribute("href", "/")` → `"/dashboard"`.
  - `:9` `initialEntries={["/"]}` → `["/dashboard"]` (so the route matches and `aria-current="page"` on `:16` still holds).
  - `:7` test-name string `"...link to / and marks it active..."` → `/dashboard` (keep it accurate).
- `account-deleted-page.test.tsx` — the "redirects an authenticated visitor to the dashboard" test (`:53-62`) stubs `<Route path="/" element={<div>Dashboard</div>} />` (`:15`) and asserts `getByText("Dashboard")` (`:58`). Since Phase 2 #4 changes the component's `<Navigate to="/">` → `/dashboard`, the redirect no longer matches the stub. Update the stub route `:15` `<Route path="/">` → `path="/dashboard"`; the `:58` assertion is then satisfied unchanged.
- The `not-found-page.test.tsx` `href="/"` assertion needs **no** change (home link still targets `/`).

Also update the E2E auth-setup redirect wait: `frontend/e2e/auth.setup.ts:75` — change `await page.waitForURL("/")` → `await page.waitForURL("/dashboard")`. **Required for criterion 2.5**: this is the shared `setup` project every chromium test depends on (`playwright.config.ts` `dependencies: ['setup']`); if left at `/` the post-login redirect (now `/dashboard`) never matches, setup times out, and the whole E2E suite fails before `welcome-landing.spec.ts` even runs. Line 76-78's `getByRole(link, "Apteczka")` assertion is unaffected.

#### 7. E2E: landing and redirect flows

**File**: `frontend/e2e/welcome-landing.spec.ts` (new)

**Intent**: Verify the public front door and the authed-redirect behaviour end-to-end. Follow the `/10x-e2e` skill workflow and the repo's E2E hard rules (role/label/text locators; wait for state, never `waitForTimeout`; independent tests with unique data + cleanup).

**Contract**: Cover:
- Unauthenticated visit to `/` renders the welcome page (assert a role/text unique to it, e.g. the `Zarejestruj się` CTA visible) and clicking `Zarejestruj się` navigates to `/register` (`waitForURL`).
- Unauthenticated visit to `/dashboard` redirects to `/login` (unchanged guard).
- Authenticated user (via `auth.setup.ts` storage state) visiting `/` is redirected to `/dashboard` (`waitForURL`).
- Post-login lands on `/dashboard`.

**Auth-state structure**: `playwright.config.ts` sets `storageState: 'e2e/.auth/user.json'` at the chromium **project** level, so every test is authenticated by default. Split the spec into two `describe` blocks by auth state:

- **Unauthenticated block** — must opt out of the project storageState with `test.use({ storageState: { cookies: [], origins: [] } })`. Without this override a `page.goto("/")` arrives logged-in, the new `PublicLayout` guard redirects to `/dashboard`, and the "unauth `/` shows welcome" and "`/dashboard` → `/login`" scenarios would silently exercise the wrong path. Covers: unauth `/` renders welcome + CTA nav to `/register`; unauth `/dashboard` → `/login`.
- **Authenticated block** — uses the default project storageState (from `auth.setup.ts`). Covers: authed `/` → `/dashboard`; post-login lands on `/dashboard`.

When writing the spec, confirm the empty-storageState context also clears any backend-set refresh-token cookie so the unauthenticated cases start genuinely logged-out.

### Success Criteria:

#### Automated Verification:

- [ ] Type check + build passes: `cd frontend && npm run build`
- [ ] Lint passes: `cd frontend && npm run lint`
- [ ] Format check passes: `cd frontend && npx prettier --check src/`
- [ ] Unit tests pass (incl. updated sidebar test): `cd frontend && npx vitest run`
- [ ] E2E passes: `cd frontend && npx playwright test welcome-landing`

#### Manual Verification:

- [ ] Logged out, visiting `/` shows the welcome page; `Zarejestruj się` → `/register`, `Zaloguj się` → `/login`.
- [ ] Logged out, visiting `/dashboard` redirects to `/login`.
- [ ] Logged in, visiting `/`, `/login`, or `/register` redirects to `/dashboard`.
- [ ] Login and registration both land on `/dashboard`; sidebar "Panel główny" is active at `/dashboard`.
- [ ] No console errors; page is responsive at mobile and desktop widths.

**Implementation Note**: After completing this phase and all automated verification passes, pause for manual confirmation.

---

## Testing Strategy

### Unit Tests:

- Welcome page renders headline, four highlights, and both CTAs with correct `href`s (`/register`, `/login`).
- Updated sidebar test asserts the dashboard link `href="/dashboard"` and active state.

### Integration Tests:

- E2E (`welcome-landing.spec.ts`): unauthenticated landing on `/`, CTA navigation, unauthenticated `/dashboard`→`/login`, authenticated `/`→`/dashboard`, post-login→`/dashboard`.

### Manual Testing Steps:

1. Log out (clear token). Visit `/` → welcome page renders in Polish; click each CTA and confirm destinations.
2. Visit `/dashboard` while logged out → redirected to `/login`.
3. Log in → land on `/dashboard`; confirm sidebar "Panel główny" active.
4. While logged in, manually visit `/`, `/login`, `/register` → each redirects to `/dashboard`.
5. Resize to mobile width → welcome layout holds, footer visible, CTAs reachable.

## Performance Considerations

None — the page is static, adds no data fetching, and reuses existing assets (`logo.png`).

## Migration Notes

The dashboard's URL changes from `/` to `/dashboard`. Any external bookmarks to `/` now hit the welcome page (which redirects authenticated users onward), so there is no broken experience. No data migration.

## References

- Roadmap slice: `context/foundation/roadmap.md:273` (S-10)
- Public-page pattern: `frontend/src/features/auth/components/login-page.tsx`
- Guard pattern to mirror: `frontend/src/app/layouts/protected-layout.tsx:17-19`
- Router: `frontend/src/app/router.tsx`
- Frontend structure rules: `docs/reference/frontend-structure.md`, `AGENTS.md:80-88`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Welcome page component

#### Automated

- [x] 1.1 Type check + build passes: `cd frontend && npm run build` — 1206092
- [x] 1.2 Lint passes: `cd frontend && npm run lint` — 1206092
- [x] 1.3 Format check passes: `cd frontend && npx prettier --check src/` — 1206092
- [x] 1.4 Welcome page unit test passes: `cd frontend && npx vitest run src/features/landing` — 1206092

#### Manual

- [x] 1.5 Component shows logo, headline, four highlights, and both CTAs in Polish; Register primary; no breakage at desktop/mobile

### Phase 2: Routing rewire & redirects

#### Automated

- [x] 2.1 Type check + build passes: `cd frontend && npm run build`
- [x] 2.2 Lint passes: `cd frontend && npm run lint`
- [x] 2.3 Format check passes: `cd frontend && npx prettier --check src/`
- [x] 2.4 Unit tests pass (incl. updated sidebar test): `cd frontend && npx vitest run`
- [x] 2.5 E2E passes: `cd frontend && npx playwright test welcome-landing`

#### Manual

- [x] 2.6 Logged out, `/` shows welcome; CTAs go to `/register` and `/login`
- [x] 2.7 Logged out, `/dashboard` redirects to `/` (changed from `/login` — see Deviations from plan)
- [x] 2.8 Logged in, `/`, `/login`, `/register` all redirect to `/dashboard`
- [x] 2.9 Login and registration land on `/dashboard`; sidebar "Panel główny" active
- [x] 2.10 No console errors; responsive at mobile and desktop widths

## Deviations from plan

- **`ProtectedLayout`'s unauthenticated redirect target changed from `/login` to `/`.** During Phase 2 manual verification the user judged that a logged-out visitor hitting a protected URL should land on the public welcome page rather than jump straight to the login form. Changed `frontend/src/app/layouts/protected-layout.tsx:18` accordingly, and updated the corresponding `welcome-landing.spec.ts` E2E case. This reverses the "No change to `ProtectedLayout`'s unauthenticated redirect target" item in "What We're NOT Doing" and the matching line in "Desired End State".
- **`AccountDeletedPage`'s "Powrót" link changed from `/login` to `/`.** For consistency with the redirect change above, the post-deletion "Powrót" link now sends the visitor to the public welcome page instead of straight to the login form. Changed `frontend/src/features/auth/components/account-deleted-page.tsx:26` and its unit test assertion in `account-deleted-page.test.tsx`.

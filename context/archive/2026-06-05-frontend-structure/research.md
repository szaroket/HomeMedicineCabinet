---
date: 2026-06-05T13:22:04+0200
researcher: szaroket
git_commit: 6e18f8e5fbff6d21034ded7cb277161719c87176
branch: feature/version-with-sql-db
repository: 10xDevs-Project
topic: "Best practices for frontend directory structure"
tags: [research, frontend, react, vite, architecture, directory-structure]
status: complete
last_updated: 2026-06-05
last_updated_by: szaroket
---

# Research: Best practices for frontend directory structure

**Date**: 2026-06-05T13:22:04+0200
**Researcher**: szaroket
**Git Commit**: 6e18f8e5fbff6d21034ded7cb277161719c87176
**Branch**: feature/version-with-sql-db
**Repository**: 10xDevs-Project

## Research Question

What is the best-practice directory structure for the `frontend/` of this project (Vite + React 19 + TypeScript + Tailwind v4 SPA), tailored as a concrete, prescriptive recommendation? Scope includes pure folder layout **plus** where routing, data/server-state, client-state, forms, types, tests, and shared/UI/Tailwind conventions live.

## Summary

The frontend is currently a **near-empty Vite scaffold** — only `src/main.tsx`, `src/App.tsx`, `src/index.css`, `src/App.css`, and `src/assets/` exist. `package.json` has just `react` + `react-dom`; no router, query, form, or path-alias setup is in place. `AGENTS.md` sketches a minimal `components/ pages/ hooks/` layout but nothing on disk implements it. This is a greenfield decision.

**Recommendation: a lightweight hybrid — feature-based `src/features/` + a thin global shared layer** (a trimmed Bulletproof React model). This is the strong, repeated 2024–2026 consensus for a solo-dev, small-to-medium app of ~7 feature areas. Concretely:

- **`src/features/<feature>/`** owns its components, hooks, `api/` (typed fetchers + TanStack Query hooks + key factory), `schemas/` (zod), `types.ts`, and (rarely) `store.ts`. Features map to this app's domains: `auth`, `cabinet`, `add-medication`, `dosage-tracking`, `notifications`, `dashboard`, `settings`.
- **`src/app/`** is the composition root: router, providers, layouts.
- **`src/components/ui/`** holds shared, domain-agnostic primitives (shadcn-style); `src/lib/` holds configured third-party wrappers (`apiClient`, `queryClient`, `cn()`); `src/hooks/`, `src/types/`, `src/utils/` hold only genuinely cross-feature code.
- **Set up `@/*` path aliases first.** Import directly — **avoid barrel files** (`index.ts` re-exports hurt Vite tree-shaking and hide circular deps).
- **Colocate Vitest `*.test.tsx`** next to source; **Playwright E2E** lives in `frontend/e2e/`.
- Use **declarative React Router v7** (not framework mode, not TanStack Router) and **TanStack Query** for server state; reserve a **Zustand** store only for the auth/session token.

Because **FastAPI is the sole backend client** (`tech-stack.md:31`), the frontend's data layer is purely a typed REST wrapper over `${VITE_API_URL}/api/v1/...` with a `Bearer <jwt>` header — no direct Supabase/DB access from the browser.

## Detailed Findings

### Current frontend state (baseline)

- Disk contents are only `frontend/src/{main.tsx, App.tsx, index.css, App.css, assets/}` plus standard config. The `components/ pages/ hooks/` layout in `AGENTS.md:37-42` is **planned, not created**.
- **No path alias** configured: no `baseUrl`/`paths` in `frontend/tsconfig.app.json`, no `resolve.alias` in `frontend/vite.config.ts`.
- **Tailwind v4 is wired** via `@tailwindcss/vite` (`frontend/vite.config.ts`), with `@import "tailwindcss";` as the entry directive in `frontend/src/index.css:1`. `App.css` holds the scaffold's demo styles.
- `package.json` dependencies are `react@^19.2.6` + `react-dom@^19.2.6` only — **no routing, form, or query library installed.**
- **API wiring today**: raw `fetch()` to `` `${import.meta.env.VITE_API_URL ?? "http://localhost:8000"}/api/v1/health/` `` (`frontend/src/App.tsx:12-18`); `VITE_API_URL` set in `frontend/.env.local`. No abstraction layer.
- Naming conventions already mandated (`AGENTS.md:87`): components `PascalCase.tsx`, utilities `camelCase.ts`, TS strict mode, Prettier formats `src/**/*.{ts,tsx,css}`.

### Backend domains to mirror as features

Backend exposes these domains under `backend/app/api/v1/` (each `router.py` + `service.py` + `crud.py` + `models.py`): **health, auth, medicines, cabinet, users**. The frontend feature folders should align with the user-facing slices in the roadmap rather than 1:1 with backend domains, but the API-call boundaries map onto these endpoints.

### Paradigm comparison (why hybrid feature-based)

| Paradigm | Scales to ~7 features? | Verdict for this app |
| --- | --- | --- |
| Type/layer-based (`components/ pages/ hooks/`) | Poorly — breaks past ~15-20 components; related code scatters | Too thin; the `AGENTS.md` sketch is a floor, not the target |
| Feature-based (`features/<feature>/`) | Very well — each feature self-contained, deletable as a unit | **Target paradigm** |
| Feature-Sliced Design (FSD) | Excellent for large/multi-team | **Overkill** — steep learning curve, entity/feature split, "slow in smaller apps" |
| **Hybrid (features + thin shared)** | Best balance for small-medium | **Recommended** (trimmed Bulletproof React) |

### Cross-cutting concern placement

- **Routing** → `src/app/router.tsx` (route tree) + `src/app/layouts/` (shared chrome via `<Outlet/>`); each route's page component colocated in its feature (`features/auth/pages/LoginPage.tsx`). Use **declarative React Router v7** (`createBrowserRouter`) — this is a pure client SPA with no SSR, so framework mode (file-based routing, loaders) and TanStack Router's generated route tree are both unnecessary weight. Keep data loading in TanStack Query, not route loaders (mixing them duplicates caching).
- **Server state / data fetching** → one shared `src/lib/apiClient.ts` (configured fetch wrapper: FastAPI base URL + `Authorization: Bearer <jwt>` + error normalization). Per feature: `features/<feature>/api/` holds (a) typed plain async fetchers, (b) a **query-key factory**, (c) `useQuery`/`useMutation` hooks. `QueryClient` instance in `src/lib/queryClient.ts`, provider in `src/app/`. Separate pure fetchers (unit-testable, no React) from hooks. Mutations `invalidateQueries` affected keys on success.
- **Client state** → reserve a **Zustand** store with `persist` for auth/session only, colocated at `src/features/auth/store.ts`. It can be read outside React, so `apiClient` pulls the token directly. Most other state is server state (Query) or local (`useState`). Avoid Context for dynamic auth state (re-render storms); use Context only for static config (locale/theme).
- **Forms & validation** → `react-hook-form` + `@hookform/resolvers/zod`; zod schemas colocated in `features/<feature>/schemas/`, with form types derived via `z.infer` (single source of truth for form + API payload). Polish validation messages live in the schemas. Promote a schema to `src/lib/schemas/` only when 2+ features share it.
- **Types** → colocate per feature (`features/<feature>/types.ts`), including API DTOs that mirror FastAPI responses. Global `src/types/` only for cross-feature types (shared `ApiError`, pagination envelope, `User`). Prefer deriving from zod where a runtime schema exists.
- **Tailwind v4** → keep the CSS entry at `src/index.css` (`@import "tailwindcss"` + an `@theme` token block — v4 config lives in CSS, no JS color config, no `content` array). UI primitives in `src/components/ui/` (shadcn-style); `cn()` helper (clsx + tailwind-merge) in `src/lib/utils.ts`. Keep the `@tailwindcss/vite` plugin. The scaffold's `App.css` demo styles should be removed/replaced when the real shell is built.
- **Test colocation** → Vitest `*.test.tsx` **colocated** next to source; Vitest config inside `vite.config.ts` (`test` block, `environment: 'jsdom'`); setup at `src/test/setup.ts` (imports `@testing-library/jest-dom/vitest`, `afterEach(cleanup)`). **Playwright** E2E (`*.spec.ts`) in `frontend/e2e/` with `frontend/playwright.config.ts`; exclude `e2e/` from Vitest `include` so the runners don't collide. The golden-path E2E (login → add medication → see in cabinet) is one spec; an `e2e/auth.setup.ts` storage-state fixture handles login.
- **Assets** → default to `src/assets/` for component-imported imagery (content-hashed, tree-shaken, build-time-checked). Use `frontend/public/` only for fixed-URL/verbatim files (favicon, robots.txt, manifest).

### Sub-question rulings

- **Barrel files**: avoid. Documented Vite tree-shaking/bundle-bloat and hidden circular-dependency costs. Use `@/` aliases for clean imports instead. (Narrow exception: a single named-export public-API barrel per feature — not worth it for a solo dev.)
- **Path aliases**: configure `@/*` in `tsconfig.app.json` (`baseUrl` + `paths`) **and** `vite.config.ts` (`resolve.alias`, absolute path). Easiest: the `vite-tsconfig-paths` plugin to define once.
- **Naming**: `PascalCase` component identifiers (already mandated). For file casing, **kebab-case files** (`medication-form.tsx`, `use-debounce.ts`) is the safer default for a Windows-developed / Linux-deployed app (avoids cross-OS casing bugs) — but this conflicts with the current `AGENTS.md:87` "Components `PascalCase.tsx`" rule. **Decision needed** (see Open Questions). Folders: lowercase, plural for type buckets, singular for feature names.
- **Nesting depth**: max ~2 levels inside a feature, ~3-4 total in `src/`; deeper is a smell.
- **Shared vs feature components**: domain-agnostic → `src/components/`; anything that knows the domain → `features/<feature>/components/`. Promote to shared only when a second feature needs it ("colocate first, extract later").
- **Import direction**: optionally enforce `shared → features → app` one-directional flow with the `import/no-restricted-paths` ESLint rule (cheap FSD-like safety).

## Recommended structure (concrete)

```
frontend/
├── e2e/                      # Playwright specs (*.spec.ts) + auth.setup.ts
├── playwright.config.ts
├── public/                   # favicon, robots.txt, manifest — verbatim/stable URL
├── vite.config.ts            # Vite + @tailwindcss/vite + Vitest (test block) + @/ alias
└── src/
    ├── main.tsx
    ├── index.css             # @import "tailwindcss"; + @theme tokens
    ├── app/                  # composition root
    │   ├── App.tsx
    │   ├── providers.tsx     # QueryClientProvider, RouterProvider, i18n (Polish)
    │   ├── router.tsx        # declarative route tree
    │   └── layouts/          # AppShell / TopBar / Sidebar (render <Outlet/>)
    ├── components/
    │   ├── ui/               # shared primitives: Button, Input, Modal, Spinner
    │   └── layout/           # shared composite layout pieces
    ├── features/
    │   ├── auth/             # pages/ components/ api/ schemas/ store.ts types.ts
    │   ├── cabinet/          # list: filter/sort/search/paginate
    │   ├── add-medication/   # registry autocomplete
    │   ├── dosage-tracking/
    │   ├── notifications/    # in-app notification center
    │   ├── dashboard/
    │   └── settings/
    ├── lib/                  # apiClient.ts, queryClient.ts, utils.ts (cn)
    ├── hooks/                # generic shared hooks (useDebounce, useMediaQuery)
    ├── types/                # genuinely global types (ApiError, pagination, User)
    ├── utils/                # shared pure helpers (formatDate, i18n helpers)
    └── test/setup.ts         # Vitest setup (jest-dom, cleanup)
```

Don't pre-create empty `api/ schemas/ store.ts` in every feature — add each only when the feature needs it. Compose features at the `app/` layer; avoid cross-feature imports.

## Migration path from the current scaffold

1. **Add `@/*` alias** to `tsconfig.app.json` + `vite.config.ts` (or add `vite-tsconfig-paths`).
2. **Create `src/app/`**: move `App.tsx` there, add `providers.tsx` + `router.tsx`; thin `main.tsx` to render `<App/>` inside providers.
3. **Strip scaffold demo code**: remove the counter/hero markup in `App.tsx` and the demo rules in `App.css`; keep `index.css` as the Tailwind entry and add an `@theme` token block.
4. **Add libs as slices need them**: `react-router`, `@tanstack/react-query`, `react-hook-form` + `zod` + `@hookform/resolvers`, `zustand`, `clsx` + `tailwind-merge`. Add Vitest + RTL + Playwright dev deps when the first test is written.
5. **Create `src/lib/`**: `apiClient.ts` (wrap the existing `${VITE_API_URL}/api/v1` fetch pattern + Bearer token), `queryClient.ts`, `utils.ts` (`cn`).
6. **Build the `auth` feature first** (roadmap F-01 / `auth-scaffold`): `features/auth/` with `pages/LoginPage.tsx`, `RegisterPage.tsx`, `api/`, `schemas/`, `store.ts`. Frontend POSTs credentials to FastAPI `/api/v1/auth/`, stores the returned JWT in the Zustand store, sends `Bearer <jwt>` thereafter (`context/changes/auth-scaffold/research.md:91-95`).
7. **Update `AGENTS.md`** to replace the `components/ pages/ hooks/` sketch with this feature-based layout and resolve the file-casing rule.

## Code References

- `frontend/src/App.tsx:12-18` — current raw-`fetch` API call pattern to migrate into `lib/apiClient.ts`
- `frontend/vite.config.ts` — `@tailwindcss/vite` wired; needs `resolve.alias` + Vitest `test` block
- `frontend/tsconfig.app.json` — needs `baseUrl` + `paths` for `@/*`
- `frontend/src/index.css:1` — `@import "tailwindcss";` Tailwind v4 entry (keep)
- `frontend/.env.local` — `VITE_API_URL=http://localhost:8000`
- `AGENTS.md:37-42` — current (to-be-revised) `components/ pages/ hooks/` sketch
- `AGENTS.md:87` — naming rule (`PascalCase.tsx`) that conflicts with kebab-case recommendation
- `AGENTS.md:93` — Vitest + RTL + Playwright testing intent
- `backend/app/api/v1/` — domains: health, auth, medicines, cabinet, users

## Architecture Insights

- **FastAPI is the sole backend client** (`tech-stack.md:31-33`): the frontend never holds a Supabase key or calls the DB directly. The whole data layer is a typed REST wrapper — this keeps the `api/` layer simple and makes server types a mirror of FastAPI response models.
- **Auth flow is JWT-over-REST** (`context/changes/auth-scaffold/research.md:91-95`): frontend POSTs credentials → FastAPI authenticates via `supabase-py` → returns access/refresh JWTs → frontend sends `Bearer <jwt>`. This is exactly the Zustand-persist + `apiClient`-reads-token pattern.
- **Solo dev, React is new territory** (`tech-stack.md:57`, self-check 4/5): argues for the *simplest* structure that still scales — hence trimmed Bulletproof React over FSD, declarative React Router over framework mode, and "colocate first, extract later" to avoid premature abstraction.
- **Polish UI mandate** (`AGENTS.md:10`): all user-facing strings (form labels, validation messages, notification copy) must be Polish — relevant to where zod messages and any i18n helpers live.
- **Roadmap order should drive folder creation**: F-01 `auth-scaffold` → S-01 `add-medication-from-registry` → S-02 `cabinet-view-and-search` → ... Build feature folders just-in-time per slice rather than scaffolding all seven up front.

## Historical Context (from prior changes)

- `context/changes/auth-scaffold/change.md` — F-01; status `new`. Backend-only library decisions so far (`supabase-py` + `PyJWT`); **no frontend component/route/folder decisions made yet** — this research fills that gap for the first feature.
- `context/changes/auth-scaffold/research.md:91-95` — defines the frontend↔FastAPI auth contract (credentials in, JWTs out, Bearer thereafter).
- `context/foundation/roadmap.md:59` — baseline confirms "no routing library or page components yet; `App.tsx` is a single monolithic component."
- `data-layer-scaffold`, `registry-import`, `deployment`, `bootstrap-verification` change folders — backend/infra only; no frontend structure decisions.

## Related Research

- None yet under `context/changes/**/research.md` for the frontend. This is the first frontend-structure research artifact.

## Decisions

- **File casing** → RESOLVED (2026-06-05): **kebab-case** files/folders (`medication-form.tsx`); component identifiers stay `PascalCase`. `AGENTS.md` updated accordingly.
- **Feature scaffolding** → RESOLVED (2026-06-05): **just-in-time** per roadmap slice, starting with `auth`. `AGENTS.md` updated accordingly.

## Open Questions

1. **Path-alias mechanism**: manual two-file config vs the `vite-tsconfig-paths` plugin (one source of truth). Minor; plugin is slightly cleaner.
2. **Import-boundary enforcement**: adopt `import/no-restricted-paths` ESLint rule now, or rely on convention for a solo dev? Cheap to add; optional.

## Sources (external)

Folder paradigms & conventions:
- Bulletproof React — `project-structure.md` (canonical hybrid features + shared, unidirectional imports)
- Robin Wieruch — React Folder Structure Best Practices (2026)
- DEV — Recommended Folder Structure for React 2025 (size thresholds)
- Feature-Sliced Design — official docs (and DEV "Mastering FSD" on when it's overkill)
- DEV / jsdev.space — barrel files: stop using them (tree-shaking/bundle evidence); vitejs/vite issue #20202 (circular deps)
- Kent C. Dodds — Colocation
- Medium (Vitor Vicente) — Path aliases in Vite + TS + React; Vite Shared Options docs
- legacy.reactjs.org — File Structure FAQ

Cross-cutting concerns:
- reactrouter.com — modes / SPA guide; LogRocket — RR7 modes; TanStack Router file-based routing; ekino — TanStack Router vs RR7
- TanStack Query — query-keys guide; tkdodo.eu / tanstackship — v5 best practices, key factories
- profy.dev — screaming architecture; colinhacks/zod #1663 (schema placement); shadcn RHF + zod docs
- shadcn — Tailwind v4 + Vite install (`components/ui/`, `lib/utils.ts`, `@theme`); webdong.dev — why `cn()`
- tkdodo.eu — Zustand vs Context (auth as Zustand case)
- nandann.com — Vitest in vite.config (2026); Playwright best practices / organizing tests (`e2e/`, storage state)
- vite.dev — assets guide (prefer importing; public/ for verbatim)

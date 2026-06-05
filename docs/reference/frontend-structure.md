# Frontend Structure

The frontend is a Vite + React 19 + TypeScript SPA styled with Tailwind v4. It uses a
**feature-based layout with a thin shared layer** (a trimmed Bulletproof React model).
Rationale, paradigm comparison, and migration path live in
`context/changes/frontend-structure/research.md`.

## Directory layout

```
frontend/
├── e2e/                      # Playwright specs (*.spec.ts) + auth.setup.ts (storage-state login)
├── playwright.config.ts
├── public/                   # verbatim/stable-URL files: favicon, robots.txt, manifest
├── vite.config.ts            # Vite + @tailwindcss/vite + Vitest (test block) + @/ alias
└── src/
    ├── main.tsx              # renders <App/> inside providers
    ├── index.css             # @import "tailwindcss"; + @theme token block (Tailwind v4 config lives in CSS)
    ├── app/                  # composition root
    │   ├── App.tsx
    │   ├── providers.tsx     # QueryClientProvider, RouterProvider, i18n (Polish)
    │   ├── router.tsx        # declarative React Router v7 route tree
    │   └── layouts/          # shared chrome (app-shell, top-bar) rendering <Outlet/>
    ├── components/
    │   ├── ui/               # shared, domain-agnostic primitives (button, input, modal, spinner)
    │   └── layout/           # shared composite layout pieces
    ├── features/             # one folder per domain feature (created just-in-time)
    │   └── <feature>/
    │       ├── components/   # feature-specific components
    │       ├── hooks/        # feature-specific hooks
    │       ├── api/          # typed fetchers + TanStack Query hooks + query-key factory
    │       ├── schemas/      # zod schemas (form + payload types via z.infer)
    │       ├── types.ts      # feature-local types
    │       └── store.ts      # (only if the feature needs client state, e.g. auth)
    ├── lib/                  # configured third-party wrappers: api-client.ts, query-client.ts, utils.ts (cn)
    ├── hooks/                # generic shared hooks only (use-debounce, use-media-query)
    ├── types/               # genuinely cross-feature types only (ApiError, pagination, User)
    ├── utils/               # shared pure helpers (format-date, i18n helpers)
    └── test/setup.ts        # Vitest setup: @testing-library/jest-dom/vitest + afterEach(cleanup)
```

## Rules

- **Feature-based layout** — most code lives in `src/features/<feature>/`. A feature owns its
  `components/`, `hooks/`, `api/`, `schemas/`, `types.ts`, and optional `store.ts`. Features map to
  user-facing roadmap slices: `auth`, `cabinet`, `add-medication`, `dosage-tracking`,
  `notifications`, `dashboard`, `settings`.
- **Just-in-time creation** — create feature folders (and the `api/`/`schemas/` subfolders inside
  them) only when a roadmap slice needs them. Do not scaffold all features up front; do not leave
  empty folders.
- **Thin shared layer** — only genuinely cross-feature code goes in top-level `components/`,
  `hooks/`, `types/`, `utils/`, `lib/`. Promote feature code to shared only when a second feature
  needs it ("colocate first, extract later"). Domain-agnostic UI primitives live in `components/ui/`;
  anything that knows the domain stays in its feature.
- **Composition at `app/`** — routing, providers, and layouts live in `src/app/`. Compose features
  there. Avoid cross-feature imports.
- **No barrel files** — import directly via the `@/*` path alias (configured in `tsconfig.app.json`
  `baseUrl`+`paths` and `vite.config.ts` `resolve.alias`). Avoid `index.ts` re-exports — they hurt
  Vite tree-shaking and hide circular dependencies.
- **Naming** — files and folders are `kebab-case` (`medication-form.tsx`, `use-debounce.ts`,
  `api-client.ts`); component *identifiers* stay `PascalCase` (`export function MedicationForm`).
  Folders: lowercase, plural for type buckets (`components/`, `hooks/`), singular for feature names
  (`auth/`, `cabinet/`). Nesting: max ~2 levels inside a feature, ~3–4 total in `src/`.
- **Data access** — FastAPI is the sole backend client; the frontend never calls Supabase/DB
  directly. One `lib/api-client.ts` wraps `${VITE_API_URL}/api/v1/...` and attaches
  `Authorization: Bearer <jwt>`. Per-feature `api/` functions are the typed REST contract;
  TanStack Query hooks are the cache layer; mutations `invalidateQueries` the affected keys.
- **Routing** — declarative React Router v7 (`createBrowserRouter`), not framework mode and not
  TanStack Router (pure client SPA, no SSR). Route page components are colocated in their feature
  (`features/auth/pages/login-page.tsx`); `router.tsx` is wiring only.
- **Client state** — most state is server state (TanStack Query) or local (`useState`). Reserve a
  Zustand `persist` store for the auth/session token only (`features/auth/store.ts`); it is read
  outside React by `api-client.ts`. Use Context only for static config (locale/theme).
- **Forms & validation** — `react-hook-form` + `@hookform/resolvers/zod`. zod schemas colocated in
  `features/<feature>/schemas/`; derive form/payload types via `z.infer`. Polish validation messages
  live in the schemas. Promote a schema to `lib/schemas/` only when 2+ features share it.
- **Tailwind v4** — CSS entry is `src/index.css` (`@import "tailwindcss"` + an `@theme` token block;
  no JS color config, no `content` array). Keep the `@tailwindcss/vite` plugin. The `cn()` helper
  (clsx + tailwind-merge) lives in `lib/utils.ts`.
- **Tests** — Vitest `*.test.tsx` colocated next to source; Vitest config inside `vite.config.ts`
  (`test` block, `environment: 'jsdom'`), setup at `src/test/setup.ts`. Playwright E2E (`*.spec.ts`)
  lives in `frontend/e2e/` with `frontend/playwright.config.ts`; exclude `e2e/` from Vitest `include`
  so the runners do not collide.
- **Assets** — default to `src/assets/` for component-imported imagery (content-hashed,
  tree-shaken, build-time-checked). Use `public/` only for fixed-URL/verbatim files.
- **Adding a new feature** — create `src/features/<feature>/` with the subfolders it needs, add its
  route to `src/app/router.tsx`, and (if it calls the backend) its typed fetchers + Query hooks in
  `features/<feature>/api/`.
- **All user-facing text must be in Polish.**

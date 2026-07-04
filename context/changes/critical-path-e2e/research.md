---
date: 2026-07-01T14:47:41+02:00
researcher: Claude
git_commit: 538d40e844305f4c28622c18651a4f6fa14ff020
branch: feature/t02-critical-path-e2e
repository: 10xDevs-Project
topic: "Playwright e2e bootstrap for the two most critical journeys (test-plan Phase 2)"
tags: [research, codebase, e2e, playwright, cabinet, auth]
status: complete
last_updated: 2026-07-01
last_updated_by: Claude
last_updated_note: "Added follow-up research for persistence/expand-row detail (journey A) and test isolation/cleanup constraints (journey B)"
---

# Research: Playwright e2e bootstrap for the two most critical journeys (test-plan Phase 2)

**Date**: 2026-07-01T14:47:41+02:00
**Researcher**: Claude
**Git Commit**: 538d40e844305f4c28622c18651a4f6fa14ff020
**Branch**: feature/t02-critical-path-e2e
**Repository**: 10xDevs-Project

## Research Question

Ground `context/foundation/test-plan.md` Phase 2 (Frontend critical-path E2E, Risks #2 + #1) in the current codebase so a `seed.spec.ts` can be written for the two most critical journeys: **(A) login → add medication → see it in cabinet** and **(B) display/filter cabinet data**.

## Summary

Neither Playwright nor any e2e scaffolding exists yet (`frontend/package.json` has no `playwright` dependency, no `playwright.config.ts`, no `frontend/e2e/`). The frontend is React 19 + React Router 7 + TanStack Query, backed by a FastAPI backend that proxies auth to Supabase and exposes clean REST endpoints for cabinet/medicines. All the pieces needed for both journeys use plain HTML form semantics (labeled inputs, real buttons, a real `<table>`/card list) — no test ids anywhere, which is compatible with the project's `getByRole`/`getByLabel`/`getByText`-first locator rule.

The one real gap: **there is no test-only login shortcut**. No test credentials env var, no seed-via-API endpoint, and Supabase is currently pointed at a live project in `.env`, not an isolated test instance. The pragmatic path for a self-contained e2e test (per the "test independence + cleanup" hard rule) is to **register a brand-new user through the UI** with a timestamp-suffixed email, rather than trying to reuse pytest fixtures (`seed_user` etc., which are async Python fixtures, not reachable from Playwright/TS).

## Detailed Findings

### Journey A: Login → Add Medication → See in Cabinet

**Auth**
- Login form: `frontend/src/features/auth/components/login-form.tsx` — email input `id="email"` (line 35), password input `id="password"` (line 54), submit button text "Zaloguj się" (line 72). Register page exists at `/register` (same feature folder) with an equivalent form.
- Session: token stored in `localStorage["auth_token"]` (`frontend/src/features/auth/store.ts:13`); sent as `Authorization: Bearer` (`frontend/src/lib/api-client.ts:35`).
- Backend: `POST /api/v1/auth/register` (`backend/app/api/v1/auth/router.py:55-85`) and `POST /api/v1/auth/login` (lines 88-110) both proxy to Supabase (`service.py`) and return `AuthResponse { access_token, token_type, user: {id, email} }`.
- Routing: React Router v7, `frontend/src/app/router.tsx`. Public: `/login`, `/register`. Protected (redirects to `/login` if unauthenticated, `protected-layout.tsx:18`): `/` (dashboard), `/cabinet`, `/cabinet/add`, `/settings`.

**Add medication**
- Entry point: "Dodaj lek" button/link on the cabinet page (`cabinet-page.tsx:208`) → `/cabinet/add` → `add-medication-page.tsx`.
- Form (`add-medication-form.tsx`):
  - `ProductAutocomplete` — labeled "Nazwa leku", debounced search, dropdown `<li>` options (`product-autocomplete.tsx:62-70`).
  - `VariantSelect` — strength/form/capacity dropdown (lines 150-154).
  - `package_count` — number input, label "Liczba opakowań" (lines 165-177).
  - `partial_tablet_count` — conditional, label "Liczba tabletek w otwartym opakowaniu" (lines 184-203).
  - `expiry_date` — date input, label "Termin ważności" (lines 210-218).
  - `is_important` — checkbox, label "Oznacz jako ważny" (lines 221-233).
  - Submit — "Dodaj do apteczki" (lines 246-252).
- API calls: `GET /medicines/products?search=` (autocomplete), `GET /medicines/variants?name=&strength=&form=` (returns `id` used as `medication_registry_id`), then `POST /cabinet/entries` with `{medication_registry_id, package_count, expiry_date, partial_tablet_count?, is_important?, usage?}` → `AddEntryResult { merged, entry, merge_summary }` (`backend/app/api/v1/cabinet/{router,schemas}.py:86-140`).

**See it in cabinet**
- List rendering: desktop `<table>` rows in `cabinet-list.tsx:273-302`, each row shows `entry.name` (line 69); mobile `cabinet-card.tsx` shows name in a `<span>` (line 59). No test ids — use `getByText(medicationName)` / `getByRole('row', {name: ...})`.

### Journey B: Display / Filter Cabinet Data

- Search input, placeholder "Szukaj po nazwie lub składniku…" (mobile, `cabinet-page.tsx:214-222`) / labeled "Szukaj" (desktop, lines 247-255).
- Status select — label "Kategoria ważności (status)" (lines 262-274), options: valid ("Aktualny"), expiring ("Bliski termin"), expired ("Przeterminowany") — defined in `filter-options.ts`.
- Category select — label "Kategoria" (lines 279-291): important/used.
- Stock select — label "Zapasy" (lines 296-308): low/insufficient/sufficient.
- "Wyczyść filtry" clear button (lines 321-328).
- Backend: `GET /cabinet/entries?status=&category=&search=&order=&page=&page_size=&below_minimum=&sufficiency=` → `CabinetPageOut { items: CabinetEntryOut[], total, page, page_size }` (`backend/app/api/v1/cabinet/router.py:43-83`, `schemas.py:54-190`).

### Test Infrastructure Gaps

- `frontend/package.json`: no Playwright dependency; dev server via `npm run dev` (Vite, default port 5173); frontend calls backend at `http://localhost:8000` (`.env.local`).
- No `playwright.config.ts`, no `frontend/e2e/`, no `auth.setup.ts` — Phase 2 bootstraps all of this from scratch.
- No test-only seed/reset API endpoint. Backend `tests/integration/conftest.py` has pytest-only async factories (`seed_user`, `seed_registry`, `seed_entry`, lines 176-325) that are **not reachable from a TypeScript Playwright test** — useful only as a reference for what "a populated cabinet" looks like.
- `.env`/`.env.local` point at what appears to be a live Supabase project, not an isolated test project — registering real users via the UI during e2e runs is the only currently-available path to a logged-in session (no test credentials env var exists).

## Code References

- `frontend/src/features/auth/components/login-form.tsx:35,54,72` - email/password ids, submit button text
- `frontend/src/features/auth/store.ts:13` - token storage key
- `frontend/src/app/router.tsx` - route table (public vs protected)
- `frontend/src/app/protected-layout.tsx:18` - auth redirect guard
- `frontend/src/features/cabinet/components/cabinet-page.tsx:208,214-329` - add button, search/filter controls
- `frontend/src/features/cabinet/components/add-medication-form.tsx:143-252` - add-medication form fields
- `frontend/src/features/cabinet/components/product-autocomplete.tsx:62-70` - medicine search autocomplete
- `frontend/src/features/cabinet/components/cabinet-list.tsx:273-302` - desktop entry rows
- `frontend/src/features/cabinet/components/cabinet-card.tsx:31-225` - mobile entry cards
- `frontend/src/features/cabinet/components/filter-options.ts` - status/category/stock option values
- `frontend/src/features/cabinet/api/cabinet-api.ts:106-113` - POST payload shape
- `backend/app/api/v1/auth/router.py:55-110` - register/login endpoints
- `backend/app/api/v1/cabinet/router.py:43-140` - list + create endpoints
- `backend/app/api/v1/cabinet/schemas.py:54-190` - list params + entry response shape
- `backend/app/api/v1/medicines/router.py:24-84` - product/variant lookup endpoints
- `backend/tests/integration/conftest.py:176-325` - pytest seed factories (reference only, not reusable from Playwright)

## Architecture Insights

- Frontend forms use real `<label>`-bound inputs and plain buttons throughout — no test-id crutch has been introduced anywhere in `features/cabinet` or `features/auth`, which lines up cleanly with the project's `getByRole`/`getByLabel`/`getByText`-first locator rule; `getByTestId` shouldn't be needed for either journey.
- Auth is backend-proxied to Supabase rather than direct frontend↔Supabase, so an `auth.setup.ts` storage-state approach (log in once via UI, reuse `localStorage` state) is viable and matches how the app itself persists sessions.
- Journey A and B share the same underlying cabinet-list component and API (`GET /cabinet/entries`), so journey A's "see it in cabinet" step and journey B's "display" step can share locator patterns — but journey B additionally needs a **pre-existing, larger seeded dataset** to meaningfully exercise filter semantics (filter intersection, status boundaries), which a single fresh-registration test won't produce on its own within one run.

## Historical Context (from prior changes)

- `context/foundation/test-plan.md` §3 Phase 1 (`context/changes/testing-backend-safety-net/`, merged PR #38) already hardened Risk #1 (silent data-path regression) and Risk #5 (cross-account leak) at the integration layer — Phase 2's e2e journeys should treat those as covered underneath and focus purely on the frontend↔API seam (Risk #2), not re-prove backend correctness.
- §6.6 Phase 5 notes (test-plan.md:184-187) flag a unique-constraint trap (`uq_cabinet_entries_user_med_expiry`) when seeding multiple entries for the same user/registry — relevant if journey B's test needs to seed several entries via repeated UI adds or direct API calls; vary `expiry_date` or registry per entry to avoid collisions.

## Related Research

- None yet under `context/changes/**/research.md` for this change; this is the first research artifact for `critical-path-e2e`.

## Follow-up Research 2026-07-01T14:47:41+02:00

User asked to also cover, for Journey A: (1) the added medication survives a page refresh, and (2) expanding the row reveals the expected details. For Journey B: confirmed scope is fine, but both tests must be fully isolated — own unique id, no inter-test dependency, and cleanup after each test.

### Persistence across refresh (Journey A)

No special client-side caching layer needs mocking — the cabinet list is fetched fresh via TanStack Query against `GET /cabinet/entries` on mount (see `frontend/src/features/cabinet/api/cabinet-api.ts` + `cabinet-page.tsx`), and auth persists via `localStorage["auth_token"]` (`frontend/src/features/auth/store.ts:13`), so `page.reload()` naturally re-triggers both the auth check and the entries fetch against the real backend. A `page.reload()` after adding the entry, followed by re-locating the row by name, is a direct, real assertion of persistence (no special setup needed beyond what's already used for the initial "see it in cabinet" step).

### Expand-row detail (Journey A)

`frontend/src/features/cabinet/components/cabinet-list.tsx:17-181` (`EntryRow`):
- Chevron toggle button: `aria-label="Pokaż szczegóły"`, `aria-expanded={expanded}` (lines 44-55) — use `getByRole('button', {name: 'Pokaż szczegóły'})` to expand, and assert `aria-expanded="true"`.
- When expanded, a detail row renders as a `<dl>` (lines 91-181) with labeled `dt`/`dd` pairs always shown for a non-dosed entry: "Dawka" (strength), "Postać" (pharmaceutical_form), "Substancja czynna" (active_ingredient), "Droga podania" (route_of_administration ) — all sourced directly from the entry the test just created, so exact-value assertions are possible (e.g. assert the strength/form the test submitted in the add form reappears here).
- Dosage-specific fields ("Dawkowanie", "Od", "Do", "Szacowany koniec", "Zapas / dni do końca") only render `if (entry.is_used)` (lines 96-139) — out of scope unless the add-medication test also sets a dosage/usage, which isn't required for this critical path.

### Test isolation & cleanup (Journey B, and generally)

Key constraint discovered: **the cabinet router has no DELETE endpoint** — only `GET` (line 43), `POST` (line 86), and two `PATCH` routes (lines 143, 181) exist in `backend/app/api/v1/cabinet/router.py`. There is no way to delete a cabinet entry (or a user) through the public API today.

Implication for isolation/cleanup, to be settled in `/10x-plan`:
- Per-entry cleanup via API is not currently possible — a `DELETE /cabinet/entries/{id}` (or a test-only teardown endpoint) would need to be added if strict "delete what you created" cleanup is required, or
- Isolation can instead be achieved by scoping data rather than deleting it: each test registers its own brand-new user (unique timestamp-suffixed email, per the existing hard rule) via the UI, so its cabinet is empty at the start and only ever contains that test's own entries — no cross-test interference even without teardown, since no other test will ever log in as that user again. This avoids needing new backend surface area but leaves orphaned test users/entries accumulating in the (currently live-pointed) Supabase project — worth flagging back to the open question about provisioning a dedicated test Supabase project.
- Journey B likely needs to seed more than one entry (to exercise filters) — each seeded within the same fresh per-test user, with distinct `expiry_date`/registry per entry to avoid the `uq_cabinet_entries_user_med_expiry` collision already documented in test-plan.md §6.6.

## Follow-up Research 2026-07-01T15:05:00+02:00 — Scope decision

Decided with the user:
- **Journey A only** for this rollout: login → add medication → see in cabinet (+ persists across refresh, + expand-row detail check). Journey B (display/filter) is deferred, not because it's B-specific but because the missing `DELETE /cabinet/entries/{id}` endpoint means any e2e-created data currently accumulates regardless of A or B; scoping to A minimizes that volume until cleanup exists or is otherwise accepted.
- **Auth via `storageState`**: one `auth.setup.ts` performs UI registration/login once per run and saves Playwright storage state; the actual test(s) reuse that state (no re-login per test). Each test still creates its own uniquely-named entry (e.g. timestamp-suffixed medicine choice or reliance on the registry's fixed catalog + a unique expiry_date) so runs stay independent even sharing one logged-in user.

## Open Questions

- Should journey A rely on UI registration (slow, but fully independent) or should the plan add a lightweight test-only seeding path (e.g., a `POST /test/seed-user` endpoint gated to non-prod) to speed up and stabilize the suite? Current findings show no such endpoint exists — this is a decision for `/10x-plan`, not settled by research.
- For journey B, what counts as a "representative" filtered dataset (how many entries, spanning which statuses) — needs a decision in planning, not just research, since the plan documents *what* not *the exact fixture*.
- Confirm whether the Supabase project referenced in `.env`/`.env.local` is dev/test-safe for creating throwaway users during CI runs, or whether Phase 2 planning needs to provision a dedicated test Supabase project first.

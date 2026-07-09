---
project: "Home Medicine Cabinet"
version: 1
status: draft
created: 2026-06-03
updated: 2026-07-09
prd_version: 1
main_goal: low-complexity
top_blocker: skills
---

# Roadmap: Home Medicine Cabinet

> Derived from `context/foundation/prd.md` (v1) + auto-researched codebase baseline.
> Edit-in-place; archive when superseded.
> Slices below are listed in dependency order. The "At a glance" table is the index.

## Vision recap

A single adult can't reliably track their home medication inventory — what they have, how many packages remain, and whether they'll run out before a doctor visit. Existing apps fail because free-text entry produces inconsistent records that erode trust. This app solves the data quality problem at the root by backing every cabinet entry with the official Polish-approved medicines registry, so medication names and metadata are always clean and standardised.

## North star

**S-01: user can search the Polish registry and add a medication to their cabinet** — this is the smallest end-to-end slice — the smallest vertical flow that, if shipped first, proves the core product hypothesis — whose delivery would confirm that registry-backed autocomplete produces clean cabinet data. It maps directly to Primary Success Criterion 1 and makes every downstream feature meaningful.

## At a glance

| ID   | Change ID                    | Outcome (user can …)                                                                                                                                 | Prerequisites    | PRD refs                          | Status   |
|------|------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------|------------------|-----------------------------------|----------|
| F-01 | auth-scaffold                | (foundation) auth entry screen in place; register/login/logout UI wired to Supabase Auth, plus FastAPI route protection                              | Supabase project created | FR-001, FR-002, Access Control | done    |
| F-02 | data-layer-scaffold          | (foundation) SQLModel models, Supabase PostgreSQL connection, and Alembic migration tooling ready                                                    | Supabase project created | FR-003, FR-010, NFR data-isolation | done |
| F-03 | registry-import              | (foundation) Polish medicines XML dataset loaded into PostgreSQL and queryable for autocomplete                                                       | F-02             | FR-003, FR-011, FR-012            | done |
| F-04 | ci-cd-wiring                 | (foundation) GitHub Actions auto-deploys backend and frontend to Render on merge to main                                                             | —                | NFR persist-across-sessions       | done    |
| S-01 | add-medication-from-registry | add a medication by searching the Polish registry autocomplete, choosing tablet count, entering package count and expiry date; entry appears in cabinet with correct status; duplicate entries merge per dedup rule | F-01, F-02, F-03 | US-01, FR-003, FR-010, FR-022 | done |
| S-08 | mobile-responsive-cabinet    | view and use the cabinet add flow and list on a mobile-width screen without layout breakage; desktop experience is preserved unchanged                                                                              | S-01             | NFR (responsive design)       | done |
| S-02 | cabinet-view-and-search      | view cabinet as a filterable, sortable, paginated list; search by name or active ingredient; see route of administration and leaflet/specification links on each entry | S-01 | US-03, FR-004, FR-006, FR-011, FR-012 | done |
| S-04 | important-category           | mark a medication as "important", set the global minimum package count, and see an attention badge when stock falls below minimum or medication is expiring/expired | S-02 | FR-013, FR-014, FR-020 (partial) | done |
| S-05 | dosage-tracking              | assign a tablet-based medication to the "used" category with a dosage schedule and optional end date; see the estimated finish date or sufficiency indicator; non-tablet medications marked used for date tracking only | S-02 | US-04, FR-015, FR-016, FR-017, FR-018 | done |
| S-03 | manage-cabinet-entry         | increment or decrement package count, update partial tablet count, and delete an entry with confirmation; important/used entries stay at zero so the user can restock | S-02, S-04 | FR-005 | done |
| S-06 | notifications-and-badges     | see a notification bell with unread count; notification center lists expiry alerts, below-minimum important stock, and used medications at risk of running out; configure expiry and close-to-finish thresholds in settings; dismiss individual notifications | S-03, S-05 | US-02, US-05, FR-007, FR-008, FR-019, FR-020 | done |
| S-07 | dashboard                    | land on a dashboard showing summary counts (total / valid / expiring soon / expired / out-of-stock) with clickable links to the cabinet list pre-filtered to each status | S-06 | FR-009 | proposed |
| F-01b | auth-polish                 | (foundation) confirm-password field on the registration form so users cannot submit a typo in their password | F-01 | FR-001 | done    |
| F-05 | backend-logging              | (foundation) structured logging across the FastAPI backend — central config, request/response middleware, consistent levels, meaningful logs at service/crud boundaries, no secrets/PII logged | F-01, F-02 | NFR (observability — baseline gap) | done |
| F-06 | spa-refresh-fallback        | (foundation) refreshing or deep-linking any client-side route on the deployed Render static site serves the app instead of a 404 | F-04 | NFR (data persists across sessions and devices — stable deployed environment) | done |
| S-09 | delete-user-account          | delete their own account and all associated data (cabinet entries, preferences) permanently, after explicit confirmation | F-01, F-02 | Access Control, NFR data-isolation | done |

## Streams

Navigation aid — groups items that share a Prerequisites chain. Canonical ordering still lives in the dependency graph below; this table is the proposed reading order across parallel tracks.

| Stream | Theme                | Chain                                          | Note                                                                          |
|--------|----------------------|------------------------------------------------|-------------------------------------------------------------------------------|
| A      | Core trunk           | `F-01` → `F-02` → `F-03` → `S-01` → `S-02`   | Main dependency spine; north star (S-01) sits as early as Prerequisites allow |
| A′     | Mobile polish        | `S-01` → `S-08`                                | Branches from S-01 in parallel with S-02; scoped to responsive layout only    |
| B      | CI/CD                | `F-04`                                         | Standalone; run in parallel with Stream A from day one                        |
| B″     | Deploy correctness   | `F-04` → `F-06`                                | SPA refresh/deep-link fallback on the Render static host; runnable any time after deploy exists |
| B′     | Observability        | `F-05`                                         | Standalone backend hardening; depends only on the backend skeleton (F-01, F-02), runnable any time |
| C      | Cabinet management   | `S-04` → `S-03`                                | Branches from S-02; S-03 needs category-aware zero behaviour from S-04        |
| D      | Dosage tracking      | `S-05`                                         | Branches from S-02 in parallel with Stream C                                  |
| E      | Alerts & dashboard   | `S-06` → `S-07`                                | Joins Streams C and D at S-06; completes the full notification loop           |
| F′     | Account lifecycle    | `F-01` → `S-09`                                | Standalone account-management addition; depends only on auth + data layer, runnable any time after F-02 |

## Baseline

What's already in place in the codebase as of 2026-06-03 (auto-researched + user-confirmed).
Foundations below assume these are present and do NOT re-scaffold them.

- **Frontend:** partial — React 19 + Vite + Tailwind present (`frontend/vite.config.ts`); no routing library or page components yet (`frontend/src/App.tsx` is a single monolithic component)
- **Backend / API:** partial — FastAPI skeleton with `GET /` and `GET /healthz` (`backend/main.py:23-30`); no domain routes, no middleware
- **Data:** absent — SQLModel not installed; no models, migrations, or DB connection (`backend/pyproject.toml` lists only FastAPI)
- **Auth:** absent — no Supabase Auth integration, no token middleware
- **Deploy / infra:** partial — `render.yaml` present (2 services defined); no GitHub Actions workflows
- **Observability:** partial — `/healthz` endpoint present (`backend/main.py:28-30`); no logging library or error tracking

## Foundations

### F-01: Auth scaffold

- **Outcome:** (foundation) Supabase Auth integrated end-to-end. The unauthenticated entry screen presents register and login forms plus a logout control, all wired to Supabase Auth; users can register, log in, and log out; a FastAPI dependency guard rejects unauthenticated requests on all protected routes. Scope is the minimal auth UI needed to exercise the flow — not account settings or profile management.
- **Change ID:** auth-scaffold
- **PRD refs:** FR-001, FR-002, Access Control section
- **Unlocks:** S-01 (all user-facing slices require a verified user identity before any cabinet data can be read or written)
- **Prerequisites:** Supabase project created with Auth enabled
- **Parallel with:** F-02, F-04
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Sequenced first because every downstream slice requires a verified user; auth bugs discovered late are expensive to retrofit across all routes. The thin auth UI (the app's entry screen) is included here so the flow is verifiable end-to-end — keeping it minimal avoids this foundation drifting into a full account-management slice.
- **Status:** done

### F-02: Data layer scaffold

- **Outcome:** (foundation) SQLModel installed; cabinet, medication-registry, and user-preference models defined; Alembic migration tooling wired; FastAPI connects to Supabase PostgreSQL via `DATABASE_URL`.
- **Change ID:** data-layer-scaffold
- **PRD refs:** FR-003, FR-010, NFR (per-account data isolation), NFR (data persists across sessions and devices)
- **Unlocks:** F-03 (registry import needs tables to load into); S-01 (cabinet entries require schema to exist before the add flow works)
- **Prerequisites:** Supabase project created with PostgreSQL enabled
- **Parallel with:** F-01, F-04
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Schema design decisions here ripple through all slices — modelling the deduplication key (drug + tablet count + expiry date, FR-010) correctly up front avoids a disruptive migration mid-build. A full-text index on medication name and active ingredient should be included here to satisfy the < 500ms p95 autocomplete NFR before S-01 is built.
- **Status:** done

### F-03: Registry import

- **Outcome:** (foundation) A one-off Python script parses the official Polish medicines XML dataset and loads it into the `medications_registry` table; data is queryable for autocomplete by name and active ingredient, and includes tablet count, producer, route of administration, leaflet URL, and specification URL.
- **Change ID:** registry-import
- **PRD refs:** FR-003, FR-011, FR-012
- **Unlocks:** S-01 (autocomplete dropdown requires registry data in DB); S-02 (producer, route of admin, and leaflet links are displayed from registry data)
- **Prerequisites:** F-02 (the registry table must exist before the script can load data)
- **Parallel with:** F-01, F-04
- **Blockers:** —
- **Unknowns:**
  - Does the XML dataset include all fields the PRD requires (tablet count per package, producer, route of administration, leaflet URL, specification URL)? — Owner: user. Block: no (developer has seen the dataset; field mapping is an implementation task, not an open question).
  - Dataset URL (public, no licence or registration required): `https://rejestry.ezdrowie.gov.pl/api/rpl/medicinal-products/public-pl-report/6.0.0/overall.xml` — large file, download only during the import script run.
- **Risk:** XML field normalisation may be non-trivial (e.g. tablet count stored as a string, multiple route-of-administration values per entry). Resolving this during F-03 keeps S-01 clean and avoids patching the import after the add flow is built.
- **Status:** done

### F-04: CI/CD wiring

- **Outcome:** (foundation) GitHub Actions workflow auto-deploys backend and frontend to Render on merge to main; deploy hook URLs and `RENDER_API_KEY` stored as GitHub Secrets.
- **Change ID:** ci-cd-wiring
- **PRD refs:** NFR (data persists across sessions and devices — implies a stable deployed environment)
- **Unlocks:** all slices (continuous deployment eliminates manual deploy steps during the build window; every merged slice is immediately verifiable at the Render URL)
- **Prerequisites:** —
- **Parallel with:** F-01, F-02
- **Blockers:** —
- **Unknowns:** —
- **Risk:** `render.yaml` already defines both services; wiring GitHub Actions is low-risk. Cold-start behaviour on the free Render tier is a known accepted trade-off (see `context/foundation/infrastructure.md`).
- **Status:** done

### F-05: Backend logging

- **Outcome:** (foundation) Structured logging is configured end-to-end across the FastAPI backend. A central logging setup lives in `app/core/` (initialised by the `create_app()` factory), request/response logging middleware records method, path, status code, and duration with a per-request correlation id, and service/crud boundaries emit meaningful logs at consistent levels (DEBUG/INFO/WARNING/ERROR). Ad-hoc `print`/unstructured output is removed. No secrets, tokens, or PII are written to logs. Scope is the logging foundation only — error tracking (e.g. Sentry) and log shipping are out of scope and parked.
- **Change ID:** backend-logging
- **PRD refs:** NFR (observability — addresses the baseline gap: "no logging library or error tracking")
- **Unlocks:** faster debugging across all slices; a consistent log surface that future error-tracking and notification-debugging work can build on
- **Prerequisites:** F-01 (app factory and middleware seam exist), F-02 (DB/session layer exists so crud-level logging has something to instrument)
- **Parallel with:** any slice — purely additive backend hardening with no schema or UI impact
- **Blockers:** —
- **Unknowns:**
  - Log format target: structured JSON (machine-parseable, Render-friendly) vs. human-readable console. Default to JSON in deployed environments and console in local dev, switchable via config. — Owner: developer. Block: no (implementation choice).
  - Whether to adopt a library (`structlog`) or wrap stdlib `logging`. Block: no — resolve during `/10x-plan`.
- **Risk:** Low. The main pitfall is leaking secrets/PII (auth tokens, emails) into logs — the plan must define a redaction/allow-list rule and verify it in tests. Introducing logging via the existing `create_app()` middleware seam keeps the change centralised and avoids scattering logging concerns across domains.
- **Status:** done

### F-06: SPA refresh fallback

- **Outcome:** (foundation) On the deployed Render static site, refreshing the browser or opening a deep link to any client-side route (e.g. `/cabinet`, `/dashboard`) serves the SPA and lands the user on the correct in-app view, instead of returning Render's 404 page. The React Router app (`frontend/src/app/router.tsx`) currently owns all routing client-side; the Render static service (`render.yaml`) has no rewrite rule, so any non-`/` request that misses a built file 404s. Fix is a catch-all rewrite to `/index.html` on the static service (the standard SPA fallback), verified against the live Render URL for both a refresh on a deep route and a cold deep-link.
- **Change ID:** spa-refresh-fallback
- **PRD refs:** NFR (data persists across sessions and devices — implies the deployed app is usable via refresh/bookmark, not just first-load navigation)
- **Unlocks:** reliable use of every user-facing slice on the deployed MVP — without the fallback, any refresh or shared/bookmarked link on a deep route breaks the app for real users
- **Prerequisites:** F-04 (a Render deploy must exist to configure and verify the rewrite against)
- **Parallel with:** any slice — infra/config-only change with no schema or app-code impact
- **Blockers:** —
- **Unknowns:**
  - Exact Render config surface for a static-service rewrite (`routes:` block in `render.yaml` vs. dashboard "Redirects/Rewrites" rule). Both are viable; prefer the `render.yaml` `routes` rewrite so the fix is version-controlled. Block: no — resolve during `/10x-plan`.
  - Confirm the rewrite does not shadow real static assets (hashed JS/CSS, favicon) — a `/*` → `/index.html` rewrite must only apply as a fallback for unmatched paths. Block: no.
- **Risk:** Low and well-understood (standard SPA hosting requirement). The only pitfall is a misconfigured rewrite that intercepts asset requests and returns HTML for JS/CSS; verifying against the live URL (refresh on a deep route + a fresh deep-link + assets still load) closes it.
- **Status:** done

## Slices

### S-01: Add medication from registry

- **Outcome:** user can type a medication name, select from the autocomplete dropdown sourced from the Polish registry, choose tablet count, enter package count (≥ 1), and set an expiry date; the entry appears in their cabinet with the correct status classification (valid / expiring soon / expired); adding the same drug + tablet count + expiry date a second time merges the entries per the deduplication and normalisation rule.
- **Change ID:** add-medication-from-registry
- **PRD refs:** US-01, FR-003, FR-010, FR-022
- **Prerequisites:** F-01, F-02, F-03
- **Parallel with:** —
- **Blockers:** —
- **Unknowns:** —
- **Risk:** The deduplication and tablet-pool normalisation logic (FR-010) is the most complex business rule in this slice; validate it with unit tests before wiring the UI to avoid subtle merge bugs appearing only in edge cases.
- **Status:** done

### S-08: Mobile-responsive cabinet

- **Outcome:** user can view and use the cabinet add flow and medicine list on a mobile-width screen without layout breakage; the desktop experience is preserved unchanged; the medication table adapts to narrow screens (card layout or horizontal scroll).
- **Change ID:** mobile-responsive-cabinet
- **PRD refs:** NFR (responsive design)
- **Prerequisites:** S-01
- **Parallel with:** S-02
- **Blockers:** —
- **Unknowns:** —
- **Risk:** The cabinet table is the primary breakage point — wide column sets collapse poorly at mobile widths. Scoping this slice to the add flow and list only (not the full rich list from S-02) keeps it small and shippable after S-01.
- **Status:** done

### S-02: Cabinet view and search

- **Outcome:** user can view their cabinet as a filterable (by status and category), sortable (by name), and paginated list; search by medication name or active ingredient; each entry shows route of administration and links to the drug leaflet and specification sourced from the registry.
- **Change ID:** cabinet-view-and-search
- **PRD refs:** US-03, FR-004, FR-006, FR-011, FR-012
- **Prerequisites:** S-01
- **Parallel with:** F-04
- **Blockers:** —
- **Unknowns:** —
- **Risk:** FR-011 and FR-012 (registry-sourced display fields) are folded here rather than in S-01 to keep the add flow lean. If the registry import (F-03) missed any display fields, it surfaces here rather than requiring a hotfix to the add flow.
- **Status:** done

### S-04: Important category

- **Outcome:** user can mark a cabinet entry as "important", set a global minimum package count, and see an attention badge on entries that fall below the minimum or are expiring/expired; the badge clears automatically when the condition resolves.
- **Change ID:** important-category
- **PRD refs:** FR-013, FR-014, FR-020 (partial — important-medication badge conditions)
- **Prerequisites:** S-02
- **Parallel with:** S-05
- **Blockers:** —
- **Unknowns:** —
- **Risk:** S-03 (manage entry) depends on this slice for the "stay at zero packages" behaviour on important entries; sequencing S-04 before S-03 prevents that branch logic being retrofitted after the fact.
- **Status:** done

### S-05: Dosage tracking

- **Outcome:** user can assign a tablet-based medication to the "used" category with a dosage schedule (times × tablets per period, per day or per week) and an optional end date; the cabinet entry displays the estimated finish date (no end date) or exact days-of-supply vs days-until-end (end date set); non-tablet medications can be marked used for start/end date tracking only, without dosage fields or finish-date calculation.
- **Change ID:** dosage-tracking
- **PRD refs:** US-04, FR-015, FR-016, FR-017, FR-018
- **Prerequisites:** S-02
- **Parallel with:** S-04
- **Blockers:** —
- **Unknowns:** —
- **Risk:** The finish-date calculation (FR-016) must display its assumptions explicitly (PRD guardrail: "calculations must clearly display their assumptions so the user can trust or override them"). Getting the UI copy right here means the notification logic in S-06 can reference the same computed values without introducing a second calculation path.
- **Status:** done

### S-03: Manage cabinet entry

- **Outcome:** user can increment or decrement package count, update the partial tablet count of an opened package, and delete an entry with explicit confirmation; decrementing to zero deletes non-categorised entries (with confirmation pop-up) and keeps important/used entries at zero so the user can restock.
- **Change ID:** manage-cabinet-entry
- **PRD refs:** FR-005
- **Prerequisites:** S-02, S-04
- **Parallel with:** —
- **Blockers:** —
- **Unknowns:** —
- **Risk:** The category-aware zero behaviour is the only state-dependent branch; sequencing after S-04 means the category state is already queryable when this slice is implemented, avoiding a conditional stub.
- **Status:** done

### S-06: Notifications and badges

- **Outcome:** user sees a notification bell with an unread count; the notification center lists alerts for expiring medications, important stock below minimum, and used medications at risk of running out before their end date; the user can dismiss individual notifications (dismissed notifications do not re-fire until the condition clears and re-triggers); expiry threshold and close-to-finish threshold are configurable in settings.
- **Change ID:** notifications-and-badges
- **PRD refs:** US-02, US-05, FR-007, FR-008, FR-019, FR-020
- **Prerequisites:** S-03, S-05
- **Parallel with:** —
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Notifications are computed on page load without a background queue (tech-stack.md constraint). The dismiss-and-don't-re-fire logic (FR-008) requires a `dismissed_notifications` record in the database — not client-side storage — to satisfy the per-account data isolation NFR and to persist correctly across devices.
- **Status:** done

### S-07: Dashboard

- **Outcome:** user lands on a dashboard showing summary counts (total medications / valid / expiring soon / expired / out-of-stock badges active); each count is a clickable link navigating to the cabinet list pre-filtered to that status.
- **Change ID:** dashboard
- **PRD refs:** FR-009
- **Prerequisites:** S-06
- **Parallel with:** —
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Dashboard depends on S-06 because the out-of-stock count (FR-009) requires the badge computation logic from S-06. Sequencing last keeps the dashboard query simple — all classification and badge logic is already in place and the counts are a straightforward aggregation.
- **Status:** proposed

### S-09: Delete user account

- **Outcome:** user can delete their own account from a settings/account screen, behind an explicit confirmation step (e.g. type-to-confirm or a confirmation dialog); on confirmation, the Supabase Auth user and all associated data (cabinet entries, user preferences, dismissed notifications) are permanently deleted; the user is logged out and returned to the entry screen.
- **Change ID:** delete-user-account
- **PRD refs:** Access Control section, NFR (per-account data isolation)
- **Prerequisites:** F-01, F-02
- **Parallel with:** any slice — standalone account-management addition
- **Blockers:** —
- **Unknowns:**
  - Whether deletion cascades via DB foreign keys or requires explicit per-table cleanup before removing the Supabase Auth user. Block: no — resolve during `/10x-plan`.
- **Risk:** Irreversible operation — confirmation UX must make the consequence unambiguous. Cascade deletion must be verified against every table keyed by user id to avoid orphaned rows.
- **Status:** done

## Backlog Handoff

| Roadmap ID | Change ID                    | Suggested issue title                                                         | Ready for `/10x-plan` | Notes                             |
|------------|------------------------------|-------------------------------------------------------------------------------|-----------------------|-----------------------------------|
| F-01       | auth-scaffold                | Auth scaffold: Supabase Auth via FastAPI (register / login / logout / guard)  | yes                   | Run `/10x-plan auth-scaffold`     |
| F-02       | data-layer-scaffold          | Data layer: SQLModel models + Alembic migrations + Supabase PostgreSQL        | yes                   | Run `/10x-plan data-layer-scaffold` |
| F-03       | registry-import              | Registry import: Polish medicines XML → PostgreSQL                            | no                    | Depends on F-02                   |
| F-04       | ci-cd-wiring                 | CI/CD: GitHub Actions → Render deploy hooks                                   | yes                   | Run `/10x-plan ci-cd-wiring`      |
| F-05       | backend-logging              | Backend logging: structured logging + request middleware + redaction         | yes                   | Depends on F-01, F-02; run `/10x-plan backend-logging` |
| F-06       | spa-refresh-fallback         | Deploy fix: SPA refresh/deep-link fallback on Render static site (`/*` → `/index.html`) | yes         | Depends on F-04; run `/10x-plan spa-refresh-fallback` |
| S-01       | add-medication-from-registry | Feature: add medication from Polish registry (autocomplete + add flow + dedup)| no                    | Depends on F-01, F-02, F-03       |
| S-08       | mobile-responsive-cabinet    | Feature: mobile-responsive cabinet add flow and list                          | yes                   | Depends on S-01; parallel with S-02; run `/10x-plan mobile-responsive-cabinet` |
| S-02       | cabinet-view-and-search      | Feature: cabinet list with filter, sort, search, and entry details            | no                    | Depends on S-01                   |
| S-04       | important-category           | Feature: important category + global minimum + attention badge                | no                    | Depends on S-02; parallel with S-05 |
| S-05       | dosage-tracking              | Feature: used category + dosage schedule + finish-date calculation            | no                    | Depends on S-02; parallel with S-04 |
| S-03       | manage-cabinet-entry         | Feature: manage cabinet entry (package count, partial tablet, delete)         | no                    | Depends on S-02, S-04             |
| S-06       | notifications-and-badges     | Feature: in-app notifications + threshold settings + out-of-stock badges      | no                    | Depends on S-03, S-05             |
| S-07       | dashboard                    | Feature: dashboard with summary counts and filter links                       | no                    | Depends on S-06                   |
| S-09       | delete-user-account          | Feature: delete user account with confirmation and cascading data cleanup     | yes                   | Depends on F-01, F-02; run `/10x-plan delete-user-account` |

## Open Roadmap Questions

_(none — all questions resolved before roadmap finalisation)_

## Parked

- **Bug: login requires a manual page refresh to reach the user page** — Reported 2026-07-03: entering correct email/password does not navigate to the user page after login; the login form just re-renders (looks like it "refreshes" back to itself), and this repeats on a second attempt — a full browser page reload is needed before login succeeds. Suspect area: post-login redirect/auth-state handling in the frontend (F-01 auth scaffold) — likely a stale auth-state race (token/session not yet propagated to the router/guard before the redirect fires) rather than a backend issue. Why parked: not yet scoped as a change; needs a `/10x-frame` or bug-triage pass to confirm root cause before planning a fix. Revisit before or alongside S-06/S-07 — do not let it block S-03.
- **Daily dataset update via GitHub Actions workflow** — Why parked: explicitly deferred to v2 by the user; the one-off import script (F-03) covers MVP needs. Revisit when dataset staleness becomes a real user pain point.
- **Inline PDF preview for drug leaflet and specification** — Why parked: PRD §Non-Goals (v2 item); links only for MVP (FR-012).
- **Native mobile app (iOS/Android)** — Why parked: PRD §Non-Goals; web-only for MVP.
- **Multi-profile / household member support** — Why parked: PRD §Non-Goals.
- **Photo, barcode, or document scanning for adding medications** — Why parked: PRD §Non-Goals; manual entry via approved list only for MVP.
- **Email or push notifications** — Why parked: PRD §Non-Goals; in-app notification center only for MVP.
- **Per-entry minimum package thresholds for important medications** — Why parked: PRD §Non-Goals; one global minimum applies to all in MVP.
- **Variable dosing schedules (as-needed / PRN dosing)** — Why parked: PRD §Non-Goals; fixed frequency only in MVP.
- **Grouped cabinet view by medication name** — Why parked: PRD §Non-Goals; flat list of entries in MVP.
- **Manual medication entry (not in the Polish registry)** — Why parked: PRD §FR-003 Socrates note; constraining to the approved list is the core differentiator; manual fallback deferred to v2.

## Done

- **F-03: (foundation) Polish medicines XML dataset loaded into PostgreSQL and queryable for autocomplete** — Archived 2026-06-15 → `context/archive/2026-06-04-registry-import/`. Lesson: —.

- **F-01: (foundation) Supabase Auth integrated end-to-end. The unauthenticated entry screen presents register and login forms plus a logout control, all wired to Supabase Auth; users can register, log in, and log out; a FastAPI dependency guard rejects unauthenticated requests on all protected routes. Scope is the minimal auth UI needed to exercise the flow — not account settings or profile management.** — Archived 2026-06-15 → `context/archive/2026-06-05-auth-scaffold/`. Lesson: —.
- **F-02: (foundation) SQLModel installed; cabinet, medication-registry, and user-preference models defined; Alembic migration tooling wired; FastAPI connects to Supabase PostgreSQL via `DATABASE_URL`.** — Archived 2026-06-15 → `context/archive/2026-06-04-data-layer-scaffold/`. Lesson: —.
- **S-01: user can type a medication name, select from the autocomplete dropdown sourced from the Polish registry, choose tablet count, enter package count (≥ 1), and set an expiry date; the entry appears in their cabinet with the correct status classification (valid / expiring soon / expired); adding the same drug + tablet count + expiry date a second time merges the entries per the deduplication and normalisation rule.** — Archived 2026-06-15 → `context/archive/2026-06-09-add-medication-from-registry/`. Lesson: —.
- **S-02: user can view their cabinet as a filterable (by status and category), sortable (by name), and paginated list; search by medication name or active ingredient; each entry shows route of administration and links to the drug leaflet and specification sourced from the registry.** — Archived 2026-06-16 → `context/archive/2026-06-15-cabinet-view-and-search/`. Lesson: —.
- **S-04: user can mark a cabinet entry as "important", set a global minimum package count, and see an attention badge on entries that fall below the minimum or are expiring/expired; the badge clears automatically when the condition resolves.** — Archived 2026-06-25 → `context/archive/2026-06-16-important-category/`. Lesson: —.
- **S-05: user can assign a tablet-based medication to the "used" category with a dosage schedule and optional end date; see the estimated finish date or sufficiency indicator; non-tablet medications marked used for date tracking only** — Archived 2026-06-29 → `context/archive/2026-06-25-dosage-tracking/`. Lesson: —.
- **S-08: user can view and use the cabinet add flow and medicine list on a mobile-width screen without layout breakage; the desktop experience is preserved unchanged** — Archived 2026-06-29 → `context/archive/2026-06-17-mobile-responsive-cabinet/`. Lesson: —.
- **F-05: (foundation) structured logging across the FastAPI backend — central config, request/response middleware, consistent levels, meaningful logs at service/crud boundaries, no secrets/PII logged** — Archived 2026-06-30 → `context/archive/2026-06-29-backend-logging/`. Lesson: —.
- **F-04: (foundation) GitHub Actions workflow auto-deploys backend and frontend to Render on merge to main; deploy hook URLs and `RENDER_API_KEY` stored as GitHub Secrets.** — Archived 2026-06-30 → `context/archive/2026-06-29-ci-cd-wiring/`. Lesson: —.
- **S-03: user can increment or decrement package count, update the partial tablet count of an opened package, and delete an entry with explicit confirmation; decrementing to zero deletes non-categorised entries (with confirmation pop-up) and keeps important/used entries at zero so the user can restock.** — Archived 2026-07-04 → `context/archive/2026-07-02-manage-cabinet-entry/`. Lesson: —.
- **F-01b: (foundation) confirm-password field on the registration form so users cannot submit a typo in their password** — Archived 2026-07-04 → `context/archive/2026-07-04-auth-polish/`. Lesson: —.
- **F-06: (foundation) refreshing or deep-linking any client-side route on the deployed Render static site serves the app instead of a 404** — Archived 2026-07-04 → `context/archive/2026-07-04-spa-refresh-fallback/`. Lesson: —.
- **S-09: user can delete their own account from a settings/account screen, behind an explicit confirmation step (e.g. type-to-confirm or a confirmation dialog); on confirmation, the Supabase Auth user and all associated data (cabinet entries, user preferences, dismissed notifications) are permanently deleted; the user is logged out and returned to the entry screen.** — Archived 2026-07-06 → `context/archive/2026-07-04-delete-user-account/`. Lesson: —.
- **S-06: user sees a notification bell with an unread count; the notification center lists alerts for expiring medications, important stock below minimum, and used medications at risk of running out before their end date; the user can dismiss individual notifications (dismissed notifications do not re-fire until the condition clears and re-triggers); expiry threshold and close-to-finish threshold are configurable in settings.** — Archived 2026-07-09 → `context/archive/2026-07-06-notifications-and-badges/`. Lesson: —.

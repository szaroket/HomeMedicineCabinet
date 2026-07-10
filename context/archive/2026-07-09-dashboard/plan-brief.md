# Dashboard — Plan Brief

> Full plan: `context/changes/dashboard/plan.md`

## What & Why

Build the authenticated landing screen at `/` (S-07, FR-009) as a five-count
navigation hub: total / valid / expiring soon / expired / out-of-stock. Each
count is a clickable card linking to the cabinet list pre-filtered to that
status. The at-a-glance counts are the primary value moment when the user opens
the app; the clickable counts turn the dashboard into an active navigation hub.

## Starting Point

Today `/` renders a stub (a single "Moja apteczka" link). Login/register already
redirect to `/`. Cabinet filtering is fully URL-driven, and the backend already
has the filtered query (`_build_base_query`) and preference resolution
(`_resolve_prefs`) needed to compute counts — the S-06 classification/badge logic
is done and archived.

## Desired End State

Login lands on `/` showing five tinted stat cards (row on desktop, stacked on
mobile) with correct counts; clicking any card opens the matching pre-filtered
cabinet list. Empty cabinet shows an "add first medication" CTA; loading shows
skeleton cards; errors show a Polish message with retry. The sidebar menu gains a
"Panel główny" link to `/`.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Count computation | New backend `GET /cabinet/summary` | One source of truth so counts match the list filters exactly; one round-trip; scales | Plan |
| "Out-of-stock" definition | Below-minimum important stock (`below_minimum=true`) | Maps 1:1 to an existing filter + the S-06 badge; clean drill-down | Plan |
| Card set | FR-009 set — "Aktualne" (valid), not the mockup's "Ważne" | Matches PRD; valid/expiring/expired cleanly partition the cabinet | Plan |
| Scope | Counts-only hub (FR-009 exactly) | No feed/charts/notification preview — matches FR-009 and avoids scope creep | Plan |
| Empty cabinet | Dedicated add-CTA empty state | Onboards new users; five zeros read as broken | Plan |
| Loading/error UX | Skeleton cards + inline retry | Perceived-performance + recovery on cold-start backend | Plan |
| Layout | Responsive card grid per `dashboard-v1.jpg`, five counts only, stacked on mobile | Matches the reference visual language on the existing dark theme | Plan |
| Endpoint placement | Existing `cabinet` domain | It is a cabinet aggregation; no new domain needed | Plan |
| Login landing | Verify-only (already `navigate("/")`) | Redirect is already correct; just add the menu link + real page | Plan |

## Scope

**In scope:** `GET /cabinet/summary` endpoint; dashboard feature data layer + UI
(five cards, loading/empty/error states); card→pre-filtered-cabinet links;
sidebar "Panel główny" menu item; login-landing verification; backend + frontend
tests.

**Out of scope:** notification/alert preview, charts, recent-activity list, quick
actions, the mockup's bottom "Leki bliskie terminu" list; an "important" card;
any change to cabinet filters or the login redirect; Playwright E2E (separate
`/10x-e2e`).

## Architecture / Approach

Backend: `crud.count_entries` (reuses `_build_base_query`) → `service.summarize_cabinet`
→ `facade.get_summary` (resolves prefs) → `GET /cabinet/summary` returning
`CabinetSummaryOut`. Frontend: `dashboard/api` fetcher + `useCabinetSummary` hook
(keyed under `["cabinet","summary"]`, invalidated by cabinet mutations) →
`dashboard-page` renders a config-driven card grid with loading/empty/error
branches. Sidebar gains a `/` link with `end`-prop active handling.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Backend summary endpoint | `GET /cabinet/summary` returning five counts | Count/list definition drift — mitigated by reusing `_build_base_query` |
| 2. Frontend data layer | Fetcher + query hook + mutation invalidation | Stale counts after cabinet edits — mitigated by invalidation wiring |
| 3. Dashboard UI | Five-card hub + loading/empty/error states + card links | Card link ≠ its count's filter — mitigated by single config + test |
| 4. Nav & landing wiring | Sidebar link + login-landing verification | `NavLink to="/"` always-active — mitigated by `end` prop |

**Prerequisites:** S-06 (done). No new deps, no migrations.
**Estimated effort:** ~2 sessions across 4 phases.

## Open Risks & Assumptions

- Assumes `total == valid + expiring + expired` (expiry categories partition the
  cabinet) — holds given the current status predicates; covered by a parity test.
- Sidebar icon: no home-icon asset exists, so the plan adds an inline SVG and a
  small `SidebarLink` extension rather than committing a new binary.

## Success Criteria (Summary)

- Login lands on `/` showing five cards with correct counts.
- Clicking each card opens the cabinet pre-filtered to that status, count matches.
- Empty cabinet shows the add-CTA; sidebar shows "Panel główny" active only on `/`.

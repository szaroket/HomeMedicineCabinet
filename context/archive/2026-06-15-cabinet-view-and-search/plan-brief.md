# Cabinet View and Search — Plan Brief

> Full plan: `context/changes/cabinet-view-and-search/plan.md`

## What & Why

S-01 shipped a cabinet that lists **every** entry with no filtering, search, or
pagination. S-02 turns it into the cabinet the PRD describes (US-03, FR-004,
FR-006): a list the user can filter by expiry status, search by name or active
ingredient, sort by name, and page through — where each entry also shows its
registry-sourced producer, route of administration, and leaflet/specification
links (FR-011, FR-012). This is the "find what I have, fast, at the pharmacy"
moment the product is built around.

## Starting Point

`GET /cabinet/entries` already returns all of a user's entries joined to the
registry with a Python-computed expiry status (valid/expiring/expired). The
registry row already carries every display field needed; they just aren't
surfaced. The frontend is a static table with no controls. React Router is wired
(so `useSearchParams` is available), and a proven full-text `search_vector` index
already powers the add-flow autocomplete.

## Desired End State

The user opens a paginated cabinet (default 20/page, selectable 20/50/100), types
to search by name or active ingredient, filters by expiry status, toggles name
sort A↔Z, and pages through — all combinable in one request. Each row expands to
show producer, route of administration, and links to the leaflet and
specification. All list state lives in the URL (shareable, reload-safe, and ready
for the S-07 dashboard to deep-link a pre-filtered view). Empty cabinet and
no-match show different messages.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Status filters in scope | valid / expiring / expired only | Out-of-stock badge depends on S-04 (important category + minimum); ship what's computable now | Plan |
| Category (important/used) filter | Defer to S-04/S-05 | Columns aren't assignable yet — a filter would act on always-false data | Plan |
| Status filtering + pagination | Push status into SQL, paginate in DB | Correct totals and stable pages; one query for filter+search+sort | Plan |
| Search matching | Reuse full-text `search_vector` index | Indexed, <500ms-friendly, consistent with the autocomplete users know | Plan |
| Filter/sort/search/page state | URL query params (`useSearchParams`) | Makes S-07 deep-links work for free; shareable + reload-safe | Plan |
| Sort controls | Name asc/desc toggle | Exactly satisfies FR-004 with a familiar table affordance | Plan |
| Pagination | Offset pages + user page-size selector (20/50/100, default 20) | User controls density; deep-linkable; fits small data scale | Plan |
| Empty states | Distinct empty-cabinet vs no-match (+ clear filters) | Prevents "did my data vanish?" confusion under a strict filter | Plan |
| Producer field (FR-011) | MA holder → manufacturer fallback | Matches the name printed on a Polish medication box; fallback avoids blanks | Plan |

## Scope

**In scope:** expiry-status filter, name/active-ingredient search, name sort
toggle, DB pagination with page-size selector, per-entry display fields
(producer, route, leaflet/specification links), URL-driven list state, distinct
empty states.

**Out of scope:** category filter & out-of-stock badge (S-04/S-05), entry
management/edit (S-03), any DB migration, inline PDF preview (v2), sort columns
beyond name.

## Architecture / Approach

Backend keeps the existing `cabinet_entries ⨝ medication_registry` query and adds
WHERE predicates: status as date comparisons against the user's expiry threshold
(mirroring `classify_status`), search via the registry `search_vector @@
to_tsquery` predicate (tsquery built by the promoted, injection-safe
`build_tsquery`, reused cross-domain through the cabinet facade), name
`ORDER BY`, and `LIMIT/OFFSET` + a `COUNT`. The response becomes a
`{ items, total, page, page_size }` envelope. Frontend reads/writes all list
state through `useSearchParams` and renders controls + an expandable per-row
detail.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. BE display fields | Producer/route/leaflet/spec on each entry (bare list preserved) | Producer fallback mapping correctness |
| 2. FE display fields | Expandable per-row detail with links | Mobile layout density |
| 3. BE filter/search/sort/pagination | Query params + paginated envelope | SQL status predicates must match `classify_status` exactly |
| 4. FE controls + URL state | Search/status/sort/page-size/pagination, empty states | URL ↔ input sync, page-reset semantics |

**Prerequisites:** S-01 shipped (it is). No new dependencies, no migration.
**Estimated effort:** ~2 sessions across 4 small phases.

## Open Risks & Assumptions

- **Status SQL ↔ classifier drift.** The SQL filter and `classify_status` are two
  expressions of one rule; a parity test at boundary dates is mandatory.
- **Envelope is a coordinated contract change.** Phase 3 breaks the Phase-1/2
  frontend until Phase 4; between them the list is verified via Swagger.
- **Vitest isn't configured** (AGENTS.md); frontend phases rely on
  build/lint/manual verification rather than component tests this slice.

## Success Criteria (Summary)

- User can filter by status, search by name/active ingredient, sort by name, and
  page through — combinable, with state preserved in the URL across reloads.
- Each entry shows producer, route of administration, and working
  leaflet/specification links.
- Empty cabinet and no-match results are clearly distinguished.

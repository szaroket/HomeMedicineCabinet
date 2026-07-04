# Manage Cabinet Entry (FR-005) — Plan Brief

> Full plan: `context/changes/manage-cabinet-entry/plan.md`

## What & Why

Give the user the last missing CRUD operations on a cabinet entry (roadmap **S-03** / **FR-005**): increase or decrease the package count, update or clear the partial-tablet count of an opened package, and delete an entry with confirmation. Today a user can add, view, star, and set dosage — but cannot adjust how much they hold or remove an entry, so the inventory drifts out of sync with reality.

## Starting Point

The `cabinet` domain has Create (with dedup/merge), Read (list), and two narrow PATCHes (importance, usage). There is **no DELETE endpoint** and no way to directly edit `package_count` / `partial_tablet_count` — they only change via the merge branch of `POST`. The frontend has no delete/edit affordance and no shared UI primitives (modals are hand-rolled). Prerequisites S-02 (list/search) and S-04 (important category) are done, so category state and the list UI this slice branches on already exist.

## Desired End State

From the cabinet list (desktop table or mobile card) the user can press −/+ to change package count, edit/clear the partial-tablet count, and delete an entry after a Polish confirmation. Decrementing an *uncategorised* entry to zero confirms then deletes it; an *important/used* entry stays at zero for restock. Status and out-of-stock badges stay correct because the list refetches after each change.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Count-edit API shape | PATCH `/entries/{id}/quantity`, absolute values | Mirrors the existing per-concern PATCH pattern; idempotent, avoids delta races | Plan |
| Zero-delete rule location | Client-orchestrated (confirm → DELETE) | Confirmation is inherently UI; keeps backend surface minimal (PATCH allows 0, DELETE removes) | Plan |
| Count/delete UX | Inline −/+ steppers + row actions | Matches existing inline affordances (star, usage-edit); zero navigation for the common ±1 | Plan |
| Confirmation UI | Reusable `ConfirmDialog` primitive (first `components/ui/`) | Consistent, on-brand, Polish; pays off for later slices | Plan |
| List freshness | Invalidate + refetch (no optimistic) | Server-computed status/badge/sufficiency never flash stale (a PRD trust guardrail) | Plan |
| Testing depth | Backend unit + integration + one Playwright e2e | Covers the stateful zero-branch end to end; new DELETE also gives the suite teardown | Plan |
| Phase split | One endpoint per phase, delete-first | Quantity phase reuses the delete flow for the decrement-to-zero branch, no stubbing | Plan |

## Scope

**In scope:** DELETE endpoint; quantity PATCH (package_count ≥ 0 + partial-tablet); inline steppers, partial-tablet edit, delete action; category-aware zero rule; `ConfirmDialog` primitive; unit + integration + e2e tests.

**Out of scope:** editing `expiry_date`; changing the medication/variant; undo/soft-delete; bulk delete; server-enforced zero invariant; optimistic UI.

## Architecture / Approach

Two endpoints, each split into a backend and a frontend phase, ordered **delete-first**. Backend: `DELETE /cabinet/entries/{id}` (router → service → new `delete_entry` crud, 204) and `PATCH /cabinet/entries/{id}/quantity` (router → facade → `set_entry_quantity` service, reusing `update_entry_counts` + existing partial validation → `CabinetEntryOut`). Frontend: `deleteEntry` / `updateQuantity` fetchers + invalidating mutation hooks; a shared `ConfirmDialog`; inline steppers + trash action on row and card; the decrement-to-zero decision (DELETE vs PATCH) made client-side from the entry's category flags. **No migration** — the `package_count >= 0` CHECK already exists.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Backend — DELETE | `DELETE /entries/{id}` + `delete_entry` crud + tests | Ownership scoping / cross-account 404 |
| 2. Frontend — delete action | `ConfirmDialog` primitive + trash action + delete hook | First `components/ui/` primitive; adaptive badge copy |
| 3. Backend — quantity PATCH | `PATCH /entries/{id}/quantity` (≥ 0) + service/facade + tests | Distinct `>= 0` schema (not the add path's `>= 1`) |
| 4. Frontend — steppers + zero rule | Inline ±/partial edit + client zero-delete branch | Getting the decrement-before-request sequencing right |
| 5. E2E — spec + teardown | Playwright delete + decrement-to-zero; teardown via DELETE | Zero-delete branch is fiddly to script |

**Prerequisites:** S-02 and S-04 done (both are). No new infra.
**Estimated effort:** ~2–3 sessions across 5 phases (small backend deltas; the two frontend phases carry most of the work).

## Open Risks & Assumptions

- Integration and Playwright specs open a real TLS DB connection → must run from **native PowerShell**, not the agent Bash tool (L-001).
- Rapid −/+ clicks each fire a refetch; acceptable at PRD `low` scale (softened by `keepPreviousData`). Revisit only if it feels laggy in manual testing.
- The client-side zero invariant means a raw API caller could park an uncategorised entry at 0; accepted for MVP (the UI is the only client).

## Success Criteria (Summary)

- User can adjust package/partial counts and delete entries from the list, with correct category-aware zero behaviour, in Polish, on desktop and mobile.
- Backend unit + integration tests and a Playwright manage/delete journey pass; build/lint/format clean.
- The e2e suite finally has a real teardown path via the new DELETE.

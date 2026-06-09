# Add Medication from Registry (S-01) — Plan Brief

> Full plan: `context/changes/add-medication-from-registry/plan.md`

## What & Why

The north-star slice: let a logged-in user search the Polish medicines registry and add a medication to their cabinet (pack count, optional partial-package tablet count, expiry date), with re-adds of the same `(drug + tablet count + expiry)` merging per FR-010. It proves the core product hypothesis — registry-backed entry produces clean cabinet data — and unlocks every downstream slice.

## Starting Point

F-01/F-02/F-03 are done: Supabase auth + JWT guard, all tables migrated (incl. a full `CabinetEntry` schema and a `search_vector` GIN index on the registry), and registry data imported. But the `medicines/` and `cabinet/` backend domains are empty stubs (router scaffold only), and the frontend has no cabinet feature, no UI primitives, and no Vitest.

## Desired End State

From an add screen, the user types ≥ 2 characters, picks a product then a pack size (two-step), enters packages + expiry (+ optional partial for tablet meds), and submits. A popup confirms the add — or shows an explicit merge notice with before/after totals on a duplicate — and asks whether to add another. The entry appears in a minimal read-only cabinet list with a computed status badge (valid / expiring / expired).

## Key Decisions Made

| Decision | Choice | Why | Source |
| --- | --- | --- | --- |
| Cabinet view scope | Minimal read-only list | S-02 owns the rich list; this just proves the add | Plan |
| Autocomplete matching | Full-text prefix on existing `search_vector` | Reuses F-02's GIN index; meets < 500ms p95 | Plan |
| Variant selection | Two-step: product (name+strength+form) → pack size | Each step is unambiguous; matches "select tablet count" | Plan |
| Merge feedback | Explicit merge notice w/ before/after totals | Transparency on why no new row appeared | Plan |
| Post-add | Success popup asks "add another?" (yes → stay; no → list) | Fits the stock-several-at-once task | Plan |
| Expiry input | Allow any date, incl. past | Lets users log already-expired stock; status handles it | Plan |
| Partial tablet count | Optional integer `1…capacity−1`, tablet meds only | Keeps tablet-pool math well-defined | Plan |
| Test depth | Unit tests on FR-010 merge math only | Covers the top risk; no integration/Vitest/E2E this slice | Plan |
| FE structure | Single `features/cabinet/` | Colocate-first per AGENTS | Plan |
| Autocomplete tuning | Min 2 chars, 250ms debounce, capped results | Protects p95 + query volume | Plan |
| Endpoint naming | Noun-based: `/medicines/products`, `/medicines/variants`, `/cabinet/entries` | REST: no verbs in paths | Plan |

## Scope

**In scope:** registry product search + variant lookup endpoints; cabinet add (with FR-010 merge) + minimal list endpoints; pure merge/normalization + status logic with unit tests; a `cabinet` frontend feature (two-step form, merge popup, minimal list, routes).

**Out of scope:** rich/filterable cabinet list + registry detail fields (S-02), categories/dosage/finish-date (S-04/S-05), edit/delete (S-03), notifications/badges/dashboard (S-06/S-07), cabinet search (S-02), integration tests / Vitest / E2E, any new migration.

## Architecture / Approach

Backend-first, one endpoint per phase for small reviewable PRs, following the existing router→service→crud split and auth-domain conventions. The DB unique constraint `(user_id, medication_registry_id, expiry_date)` already encodes the FR-010 dedup key, so no schema change is needed; "tablet count" = the registry row's `capacity`. The riskiest logic (tablet-pool merge/normalization + status classification) lands first as pure, DB-free, fully unit-tested functions, then is consumed by the add endpoint. Frontend wires two-step autocomplete (TanStack Query + debounce) and react-hook-form/zod, mirroring the auth feature.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Merge/status logic + unit tests | Pure FR-010 + status functions, fully tested | Subtle normalization edge cases |
| 2. `GET /medicines/products` | Step-1 product search | Safe tsquery construction |
| 3. `GET /medicines/variants` | Step-2 pack-size variants | NULL strength/form matching |
| 4. `POST /cabinet/entries` | Add with merge + before/after notice | Tablet vs non-tablet branching; capacity→int |
| 5. `GET /cabinet/entries` | Minimal list with computed status | Per-user isolation |
| 6. Frontend `cabinet` feature | Two-step form, merge popup, minimal list, routes | First feature w/o UI primitives; Polish copy |

**Prerequisites:** F-01, F-02, F-03 (all complete). DB-touching manual checks run from native PowerShell (L-001).
**Estimated effort:** ~3–4 after-hours sessions across 6 phases.

## Open Risks & Assumptions

- `capacity` is `Decimal`; tablet-based rows are assumed to have an integer capacity — the service guards a missing/non-integer value.
- Full-text `simple` prefix is word-start, not substring; mid-word fragments won't match (accepted for MVP; meets the ≥ 95% match guardrail for typed prefixes).
- Endpoint behavior is validated manually (PowerShell) rather than by integration tests this slice.

## Success Criteria (Summary)

- A user can search, pick a product + pack size, and add an entry that appears in the cabinet with the right status.
- Re-adding the same drug + tablet count + expiry merges and shows an explicit before/after notice; a different expiry creates a new entry.
- FR-010 merge/normalization is green under unit tests before any UI depends on it.

# Dosage Tracking (S-05) — Plan Brief

> Full plan: `context/changes/dosage-tracking/plan.md`

## What & Why

Let a user assign a cabinet entry to the **"used"** category with a dosage schedule
(`times × tablets`, per day or per week) and an optional end date, then see — at a glance,
in their local timezone — when a medication will run out. This answers the persona's core
pharmacy question ("will I run out before my next doctor visit?") and delivers FR-015–FR-018.

## Starting Point

The DB schema is already done: `cabinet_entries` carries `is_used` + five `dosage_*` columns
(with a `CHECK` on `dosage_period IN ('day','week')`) from the F-02 scaffold — currently
unread/unwritten by any code. The cabinet domain has a clean analog to copy: S-04's importance
flow (router → facade → service → crud → `_map_row_to_entry_out`). `total_tablets()` already
computes available stock.

## Desired End State

From the add form or an entry's expanded card, a user marks a tablet med "used", enters
`3 × 2 per day` and an optional end date, and immediately sees either an estimated finish date
(no end date) or days-of-supply vs days-until-end with a **Wystarczy / Zabraknie** badge (end
date set). Non-tablet meds can be marked used with dates only. "Used" entries are filterable.

## Key Decisions Made

| Decision | Choice | Why | Source |
| --- | --- | --- | --- |
| Set usage when adding | Yes — `POST` body carries usage too | User sets dosage at creation, not only later | Plan |
| Update path | New `PATCH /entries/{id}/usage` sub-resource | Keeps importance PATCH untouched; one focused schema | Plan |
| Merge with usage (dedup) | Incoming usage overwrites | Predictable last-write-wins; matches importance-on-merge | Plan |
| Finish-date base | From **today** (current stock) | Answers "run out from now?"; stock already reflects use | Plan |
| Rounding | **Floor** days-of-supply | Never overstate supply — serves guardrail + Risk #6 | Plan |
| Unassign | `is_used=false` **clears** all dosage/date columns | Clean state; calc never sees orphan data | Plan |
| Usage form UI | **Inline** in expanded card (+ in add form) | Reuses existing expand pattern; no modal/route infra | Plan |
| End-date display | Both day counts **+ sufficient/short badge** | Satisfies FR-017 + assumptions-visible guardrail | Plan |
| "Used" category filter | Added now | Small completion of FR-004; backend filter already generic | Plan |
| UTC vs local | Backend returns `days_of_supply`/sufficiency (UTC); **frontend renders local finish date** | Honors UTC storage; keeps one calc path for S-06 | Plan |

## Scope

**In scope:** usage on `POST`; `GET` calc (floored days-of-supply, days-until-end,
sufficiency) + response fields; `PATCH /entries/{id}/usage` (set/edit/unassign); `used`
category filter; inline + add-form usage UI; local-timezone finish-date rendering; unit tests
for the calc (Risk #6).

**Out of scope:** notifications + `close_to_finish_threshold` wiring (S-06); package/partial
count editing (S-03); any migration; variable/PRN dosing; finish calc for non-tablet meds.

## Architecture / Approach

Phases split **per endpoint, backend then frontend**, ordered `POST → GET → PATCH`. Backend
owns the quantitative calc in UTC (pure functions in `service.py` beside `total_tablets`);
the frontend converts `days_of_supply` to a local finish date. Shared dosage **validation**
is built in Phase 1 and reused by Phase 5; the shared **DosageFields** component is built in
Phase 2 and reused by Phase 6 ("colocate first, extract later").

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. POST backend | Add persists usage; merge overwrites; validator + error | Merge-overwrite path; DB CHECK / enum parity |
| 2. POST frontend | Usage fields in add form; reusable DosageFields | Tablet vs non-tablet field gating |
| 3. GET backend | Floored calc + response fields + `used` filter | **Risk #6** finish/sufficiency miscalc |
| 4. GET frontend | Local finish date + sufficiency badge + filter UI | UTC→local off-by-one at midnight |
| 5. PATCH backend | `/usage` set / edit / unassign-clears | Ownership scoping; clear-to-NULL |
| 6. PATCH frontend | Inline card usage edit + mutation | Click propagation vs card expand |

**Prerequisites:** S-02 (cabinet list/search) and S-04 (importance flow) — both done. No
migration, no new dependencies.
**Estimated effort:** ~2–3 sessions across 6 small phases.

## Open Risks & Assumptions

- Backend UTC-today vs frontend local-today can differ by one day at midnight — accepted
  (single user, PL timezone).
- `dosage_period` enum must match the DB CHECK exactly (`day`/`week`) or inserts fail.
- Sufficiency/day-count values are computed for display now and intended for reuse by S-06
  notifications without a second calc path.

## Success Criteria (Summary)

- A "used" tablet med shows a correct, locally-rendered finish date or sufficiency verdict.
- Non-tablet "used" meds track dates only; "used" entries are filterable.
- Calc functions are covered by parametrized unit tests (Risk #6) — floor, per-week, partial
  package, zero-rate guard, end-date sufficiency.

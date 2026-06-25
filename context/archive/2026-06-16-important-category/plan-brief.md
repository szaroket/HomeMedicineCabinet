# Important Category — Plan Brief

> Full plan: `context/changes/important-category/plan.md`

## What & Why

Roadmap slice **S-04** (FR-013, FR-014, FR-020 partial). A user can mark medications as **important**, set a **global minimum package count**, and get an at-a-glance **out-of-stock** signal when an important medication runs low — the first step toward the cabinet proactively telling the user what needs restocking before a pharmacy trip.

## Starting Point

The data model already exists from the F-02 scaffold: `CabinetEntry.is_important` and `UserPreferences.min_package_count` are defined and already in the initial-schema migration. The users domain is a read-only stub (no write path, no `schemas.py`); the cabinet list endpoint computes expiry status but exposes neither importance nor a below-minimum signal, and has no category filter. The frontend has no settings screen.

## Desired End State

A logged-in user opens **/settings** and sets a minimum (1–10). In the cabinet they mark entries important via an inline star (or a checkbox while adding), filter the list to **Ważne**, and see important entries below the minimum rendered as a **colored row with a "Brak w apteczce" label**. Expiry continues to show, unchanged, in the Status column. The signal clears automatically once stock reaches the minimum.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Preferences API | `GET` + `PATCH /users/preferences` (partial, upsert) | One natural home for all prefs; partial update won't clobber S-06 fields | Plan |
| Settings UI | New `settings` feature + `/settings` route | Natural home; S-06 thresholds slot in later; matches feature-based layout | Plan |
| Out-of-stock signal | Colored row + "Brak w apteczce" label, **below-minimum only** | Keeps stock signal separate from expiry, which stays in the Status column | Plan |
| Accessibility | Color paired with a text label | Color alone fails colorblind users and the PRD "name the condition" guardrail | Plan |
| Mark-important UX | Inline star per row **+** add-form checkbox | One-click flagging plus marking at creation time | Plan |
| Category filter | Add `important` now, extensible to `used` | S-02 promised category filtering; small, makes the flag immediately useful | Plan |
| Min value bounds | Integer 1–10, default 1 | Tight, clearly-realistic range for a personal cabinet | Plan |
| Merge importance | OR — important if either side is | Never silently un-flags an important entry on dedup-merge | Plan |
| Testing | Parametrized pure-logic + endpoint tests | Covers the badge math and the new write paths; matches S-01/S-02 style | Plan |

## Scope

**In scope:** preferences GET/PATCH; cabinet list importance field + below-minimum signal + important filter; toggle endpoint; add-time importance (OR-merge); settings screen; cabinet star/badge/filter/add-checkbox UI.

**Out of scope:** DB migration (columns exist); "used" category, dosage, finish dates (S-05); notifications/alerts (S-06); expiry-driven row color (stays in Status column); per-entry minimum (v2); decrement/delete (S-03); editing expiry/close-to-finish thresholds in settings (S-06).

## Architecture / Approach

Bottom-up, **one backend endpoint per phase** for small reviewable diffs, then two frontend surfaces. Cross-domain reads (cabinet needs `min_package_count` from users) go through `cabinet/facade.py`, which already fetches `UserPreferences` for the expiry threshold. The below-minimum rule is a pure function in `cabinet/service.py` (`is_important and package_count < min_package_count`) surfaced as one boolean on `CabinetEntryOut`; the frontend owns the color + copy.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. GET /users/preferences | Read effective prefs (defaults if no row) | Defaults-vs-stored fallback correctness |
| 2. PATCH /users/preferences | Update min (1–10) with upsert provisioning | Upsert/`L-004` error wrapping |
| 3. GET /cabinet/entries (enhance) | `is_important` + below-minimum + `category` filter | Keeping stock signal distinct from expiry |
| 4. PATCH /cabinet/entries/{id} | Toggle importance on an owned entry | Ownership check / 404 mapping |
| 5. POST /cabinet/entries (enhance) | Mark important at add time, OR-merge | Merge must never clear importance |
| 6. Frontend settings feature | `/settings` screen + minimum form | New route + nav wiring |
| 7. Frontend cabinet UI | Star, colored row + label, filter, add checkbox | Row color must not collide with Status colors; star vs expand click |

**Prerequisites:** S-02 (done). No new env, access, or migration.
**Estimated effort:** ~2–3 sessions across 7 small phases (backend phases are tiny single-endpoint diffs).

## Open Risks & Assumptions

- "Brak w apteczce" is not literally true when 1 of min 2 packages remain; accepted as an at-a-glance restock cue, copy kept in one constant for easy retuning.
- PATCH toggle returns a full `CabinetEntryOut` (recomputed status + below-minimum) for list consistency — slightly heavier than a minimal ack, but avoids a second client refetch.
- Endpoint tests use mocked sessions (`authed_client`), so they run from the Bash tool; only real-DB commands need PowerShell (L-001).

## Success Criteria (Summary)

- User can set a global minimum (1–10) that persists across sessions/devices.
- User can mark/unmark important (inline + at add time); importance survives dedup-merge.
- Important entries below the minimum show a colored row + "Brak w apteczce"; the signal clears automatically when restocked; expiry stays independent in the Status column.

# Notifications and Badges (S-06) — Plan Brief

> Full plan: `context/changes/notifications-and-badges/plan.md`

## What & Why

Build the in-app notification center (bell + unread count + dropdown panel) that alerts a user when a medication is entering the expiry window, an "important" medication is below its minimum, or a "used" medication with an end date is at risk of running out before the course ends — plus the two threshold settings that govern those alerts. This is the S-06 slice completing the PRD's core promise (Success Criterion 1): proactive, in-app warnings before a medication becomes unusable or runs out.

## Starting Point

Most of the substrate is already shipped. The `user_preferences` table stores all three thresholds (only `min_package_count` is editable so far); the cabinet domain already has the pure functions this feature reuses (`classify_status`, `is_below_minimum`, `compute_usage_view`); and the cabinet badges (status + "Brak w apteczce") already cover FR-020. What's missing: the notification derivation, a place to persist dismissals, the bell/panel UI, and editable expiry/close-to-finish thresholds.

## Desired End State

A logged-in user sees a header bell with an unread count (hidden at 0, capped `9+`). Clicking it opens a dropdown listing active alerts most-urgent-first, each with the medication name and a type-specific Polish line. Dismissing one removes it until its condition clears and re-triggers. Settings lets the user edit the expiry (7–90 days) and close-to-finish (≥1 day) thresholds. Account/entry deletion leaves no orphaned dismissal rows.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Notification storage | Derived on page load; not stored | Tech-stack has no background queue; storing rows creates a stale-reconciliation problem | Plan |
| Evaluation home | New `notifications` domain + facade | Follows the strict cross-domain layering rule; keeps a clean API surface | Plan |
| Unread-count model | Active, non-dismissed count | Simplest coherent model under compute-on-load; one interaction (dismiss) | Plan |
| Dismiss persistence | Dedicated `dismissed_notifications` table | Clean domain boundary; client-side ruled out by cross-device NFR | Plan |
| Re-fire detection | Garbage-collect stale dismissals on load | Minimal schema, no snapshot; clearance falls out naturally | Plan |
| FR-020 badge work | Leave badges as-is | Status badge + below-minimum pill already satisfy FR-020 | Plan |
| Cleanup | FK cascade (entry) + explicit delete-by-user (account) | No orphans; closes test-plan Risk #7 | Plan |
| Notification center UX | Bell-anchored dropdown panel | Standard tray UX; no popover primitive exists, build from ConfirmDialog pattern | Plan |
| Settings controls | Number inputs matching existing field | Consistent with the shipped settings form | Plan |
| Ordering / count | Urgency-first; hide at 0, cap `9+` | Surfaces the most pressing alert; clean glanceable bell | Plan |

## Scope

**In scope:** notifications domain (derive 3 triggers, GC, dismiss); `dismissed_notifications` table + migration; `GET /notifications` + `POST /notifications/dismiss`; editable expiry/close-to-finish thresholds; account-delete cascade for dismissals; frontend bell + dropdown panel; settings threshold controls.

**Out of scope:** stored notifications / background jobs; email/push; any new or changed cabinet badge (FR-020 already satisfied); a read/seen state separate from dismiss; the dashboard (S-07).

## Architecture / Approach

New `notifications` backend domain. Its facade reads the user's computed cabinet entries + effective preferences cross-domain, applies three pure predicates (reusing cabinet's `classify_status` / `is_below_minimum` / `compute_usage_view`), garbage-collects stale dismissals, filters against surviving dismissals, orders by urgency, and returns the list. `POST /dismiss` records a `(user, entry, trigger_type)` row. Frontend adds `features/notifications/` (API + bell + dropdown panel) and extends the settings form. `GET /notifications` carries a GC write side-effect, run inside one transaction.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Migration + model | `dismissed_notifications` table + SQLModel | FK cascade / migration on Supabase (run from PowerShell, L-001) |
| 2. Evaluation + GET | Three triggers, ordering, `GET /notifications` | Reusing cabinet reads unpaginated without duplicating SQL |
| 3. Dismiss + GC | `POST /dismiss`, load-time garbage collection | Correct suppress-then-re-fire semantics |
| 4. Editable thresholds | PATCH accepts expiry + close-to-finish | Validation bounds (7–90 / ≥1) |
| 5. Account-delete cascade | No orphaned dismissals on delete | Belt-and-suspenders vs transitive FK cascade |
| 6. Bell & panel | Header bell + dropdown + dismiss | No popover primitive — hand-built overlay |
| 7. Settings controls | Two threshold inputs | Seed/submit all three fields together |

**Prerequisites:** S-03 and S-05 shipped (both done); Supabase migration run from native PowerShell (L-001).
**Estimated effort:** ~3–4 sessions across 7 phases (backend-first, then frontend).

## Open Risks & Assumptions

- GC observes clearance only at page loads — a clear+retrigger entirely between two loads keeps the stale dismissal suppressing the alert (accepted MVP limitation, web-only app checked regularly).
- Account-delete is transitively covered by the entry FK cascade; Phase 5's explicit delete is defensive insurance and survives future reordering of the S-09 entry-delete.
- Assumes the existing cabinet computation can be reused unpaginated; if not, a thin `list_all_for_user` read is added in the cabinet layer.

## Success Criteria (Summary)

- The bell surfaces the correct active alerts, ordered most-urgent-first, with correct Polish copy.
- Dismissing an alert suppresses it until its condition clears and re-triggers.
- Editing thresholds changes which alerts fire; deleting accounts/entries leaves no orphaned dismissal rows.

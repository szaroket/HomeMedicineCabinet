<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Notifications and Badges (S-06)

- **Plan**: context/changes/notifications-and-badges/plan.md
- **Mode**: Deep
- **Date**: 2026-07-07
- **Verdict**: REVISE → SOUND (all findings triaged & fixed 2026-07-07)
- **Findings**: 0 critical, 2 warnings, 1 observation — all FIXED

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | WARNING → PASS (F2, F3 fixed) |
| Plan Completeness | WARNING → PASS (F1 fixed) |

## Grounding

- Paths 6/6 ✓ — cabinet/service.py, users/{service,crud,schemas,router,facade}.py, cabinet/crud.py, app-layout.tsx, settings-page.tsx, cabinet-queries.ts, connector.py all exist as described.
- Symbols ✓ — classify_status:162, is_below_minimum:144, compute_usage_view:221, get_effective_preferences:94, _build_base_query:263 (no ORDER BY/LIMIT/OFFSET, reusable unpaginated), persist(session) no-instance form already used at users/facade.py:42, update_preferences new-row path already constructs all three thresholds.
- Brief↔plan ✓ — phases, decisions, and scope match.
- Progress↔Phase contract ✓ — exactly one `## Progress`, all 7 phases mapped, every Success Criteria bullet has a matching `- [ ] N.M` entry. (Minor: body phase headers use backticks around `dismissed_notifications`/`GET /notifications` that the Progress headers drop; phase numbers match, so parsing is unaffected.)

## Findings

### F1 — Notification assembly & ordering underspecified

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real UX-affecting choice; pause to reason through it
- **Dimension**: Plan Completeness
- **Location**: Phase 2, §3 (predicates + ordering) and §2 (NotificationOut)
- **Detail**: Two gaps the implementer would fill by guessing.
  (a) **Ordering.** The comparator is "expired first, then by ascending days_remaining across expiry/run_out, with below_minimum interleaved by a defined rule (documented in the function)." That rule is a TBD. `below_minimum` carries `days_remaining = None`, so its position relative to numeric items is genuinely undefined; the plan defers the actual decision to implementation time. It drives which alert the user sees first.
  (b) **days_remaining derivation.** The predicate contract says the service operates on "already-computed fields (status, below_minimum, days_of_supply, days_until_end, is_sufficient) plus today and thresholds." But `NotificationOut.days_remaining` for the `expiry` type is days-to-expiry, which is none of those. It must come from `CabinetEntryOut.expiry_date` (present at cabinet/service.py:436) via `(expiry_date - today).days`. Field is available; the contract just doesn't hand it to the assembler, so the wiring is implicit.
- **Fix**: Pin the ordering rule in the plan (state where a `None`-valued below_minimum sorts relative to expired items and to positive/negative days_remaining), and state that the facade computes expiry days_remaining from expiry_date. Both are one-line clarifications.
  - Strength: Removes the only genuine "implementer invents it" spot; the promised ordering test then has a spec to assert against.
  - Tradeoff: None — pure specification tightening.
  - Confidence: HIGH — verified the field set against cabinet/service.py:426-457.
  - Blind spot: The intended UX priority of below-minimum vs. expiring isn't stated anywhere found; that's a product call.
- **Decision**: FIXED — pinned deterministic `order_notifications` sort key in Phase 2 §3 and stated the facade derives expiry `days_remaining` from `CabinetEntryOut.expiry_date` in §5.

### F2 — Bell can go stale on time-based threshold crossings

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff between the "proactive" promise and effort
- **Dimension**: Blind Spots
- **Location**: Phase 6, §1–2 (query hooks + cross-feature invalidation)
- **Detail**: Notifications are computed on load, and the bell refreshes only via (i) the initial `useNotifications()` fetch and (ii) invalidation after cabinet mutations (Phase 6 §2). An alert that becomes active purely from the passage of time — an entry crossing into the expiry window, or a course end date drawing within the close-to-finish threshold — will NOT surface while the SPA stays open, because nothing invalidates the query. The user sees it only on the next reload or cabinet edit. The PRD's primary success criterion is "proactive, in-app warnings"; for a long-lived tab this is quietly reactive. The design is compute-on-load by accepted constraint, so this is about the client refresh policy, not the backend.
- **Fix**: Give `useNotifications()` a refresh policy independent of mutations — `refetchOnWindowFocus: true` and/or a modest `staleTime`, or a low-frequency `refetchInterval`. Note the residual limitation (an alert arising mid-session without a focus/reload event) as explicitly accepted, mirroring the GC-race caveat already in the plan.
  - Strength: `refetchOnWindowFocus` alone covers the common case (tab away → return) with near-zero code; matches TanStack norms.
  - Tradeoff: A refetch on every focus is another GET (which now also runs the GC write — see F3); negligible at target scale.
  - Confidence: HIGH — confirmed cabinet-queries.ts invalidates only on mutations; no interval/focus policy set today.
  - Blind spot: Whether the app's default QueryClient already sets `refetchOnWindowFocus` globally — check before adding it.
  - Verified: `lib/query-client.ts` overrides only `retry`, so TanStack's default `refetchOnWindowFocus: true` is already active; the tab-away→return case is covered without new code. Fix narrowed to the mid-session gap.
- **Decision**: FIXED — added `refetchInterval: 5 * 60 * 1000` to `useNotifications()` in Phase 6 §1 with a refresh-policy rationale (focus-default + mutation-invalidation + interval) and the GC write-cost noted as accepted.

### F3 — GET /notifications writes (GC) on every call, and it's called often

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick to confirm; fix is obvious if it ever matters
- **Dimension**: Blind Spots
- **Location**: Critical Implementation Details (GC side-effect); Phase 6 §2
- **Detail**: The plan (correctly) makes GET carry a GC delete. Combined with Phase 6's "invalidate notifications after every cabinet mutation" plus the bell mounting on each page load — and F2's focus refetch if added — this endpoint performs a write-transaction on a high-frequency read path. The plan reasons about correctness (single transaction, idempotent) but not frequency. At the PRD's small target scale this is fine; the note is only to keep it conscious. Two concurrent GETs for the same user both running GC is safe (idempotent deletes), so no locking concern.
- **Fix**: No change needed now. If read volume ever grows, gate the GC to run only when the active set diverges from stored dismissals (skip the DELETE when nothing is stale), turning most GETs read-only.
- **Decision**: FIXED — applied the gate now (not deferred). Phase 3 §1/§2 changed to compute `stale_keys` in memory and call `delete_stale_dismissals` only when non-empty; Critical Implementation Details GC note updated to describe the conditional (read-only common case) write.

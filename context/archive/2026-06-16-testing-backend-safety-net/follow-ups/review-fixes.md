# Review follow-ups

Queued from `/10x-impl-review` triage. Each item links back to the originating finding.

## Phase 5 — exercise the within-test `act_as` identity switch (from F3, impl-review-phase-3)

Progress item 3.7 ("act_as switches identity within a test") is checked, but no
Phase 3 smoke test performs an intra-test A→B identity switch — each test calls
`act_as` once. The capability is just a `nonlocal` setter
(`backend/tests/integration/conftest.py:151`), so it's plausible by inspection but
not observably proven.

**Action:** When Phase 5 writes the ownership/authorization tests, include at least
one test that calls `act_as(user_a)` then `act_as(user_b)` within the same test
(e.g. user A creates an entry, switch to user B, assert B cannot see/access it).
Do not treat 3.7 as already-covered by the Phase 3 smoke suite.

# Review Follow-ups — Cabinet View and Search

Queued fixes from implementation reviews. Each item names its originating finding.

## F1 (Phase 3) — SQL status parity must be exercised by e2e

**Source**: impl-review-phase-3.md · `backend/tests/cabinet/test_service.py:210-240`

`TestStatusSQLParity` only checks a Python mirror (`_sql_status`) against
`classify_status`; it never executes the real predicates in
`crud._build_base_query` (crud.py:159-169). Deferred to the future e2e suite
instead of adding a DB-backed test now.

**Requirement for the e2e work** (do not drop — this is what actually closes the gap):
- Seed cabinet entries sitting *on* the status thresholds: `expiry_date == today`
  and `expiry_date == today + 30d`.
- Hit the cabinet list endpoint with `?status=expired`, `?status=expiring_soon`,
  and `?status=valid` against a real DB.
- Assert each filter returns exactly the rows `classify_status` would label —
  so a `<` vs `<=` edit in the SQL predicate is caught.

Without on-boundary seeding, a generic "filter returns some rows" e2e test does
NOT satisfy this and the parity gap remains open.

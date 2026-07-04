<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Backend Logging

- **Plan**: context/changes/backend-logging/plan.md
- **Scope**: Phase 3 of 4
- **Date**: 2026-06-29
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 2 warnings, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | WARNING |
| Success Criteria | PASS (1 caveat) |

Automated re-run: ruff check + format PASS; grep (no email in supabase_auth log)
PASS; pytest excluding tests/db = 349 passed. `tests/db/test_connection.py`
cannot run from the Bash tool (OpenSSL applink abort — L-001 env quirk, not a
defect); run from PowerShell to fully close criterion 3.2.

## Findings

### F1 — Email still logged at three auth-service call sites

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/api/v1/auth/service.py:40, 45, 80
- **Detail**: Phase 3's goal is "no email/token/password appears in any emitted line," and the overview says to "confirm the redaction filter covers the auth handlers." supabase_auth.py was fixed at the call site, but auth/service.py still passes `data.email` directly to three log calls (sign_up no-user line 40, sign_up no-session line 45, sign_in no-user/session line 80). The Phase 1 redaction filter scrubs these at runtime (defense-in-depth backstop), so this is not an unmitigated live leak — but it is inconsistent with the supabase_auth.py call-site fix, and if a future email variant slips past the regex these three leak.
- **Fix**: Drop `data.email` from the three calls — log user-less failure context (sign_up/sign_in failures need no address), matching the supabase_auth.py approach; the filter then stays a backstop, not the sole guard.
- **Decision**: FIXED — dropped `data.email` from log calls at service.py:40, 45, 80.

### F2 — Edited supabase_auth line still propagates single-letter `e`

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/app/db/supabase_auth.py:101
- **Detail**: The reworked line uses `e.code` / `e` (L-005: no single-letter names). The plan explicitly scoped the file-wide `e`→`exc` rename out, so this is a known, accepted carve-out — noted only for awareness; the whole file uses `e` consistently.
- **Fix**: None required for this phase (plan carve-out). Optional: rename `e`→`exc` across supabase_auth.py in a separate tidy-up.
- **Decision**: SKIPPED — accepted as plan-scoped carve-out.

### F3 — medicines/service.py left without any logging

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: backend/app/api/v1/medicines/service.py
- **Detail**: The plan named medicines as a candidate domain for service-layer logging; it got none. It only contains read-only `search_products` / `list_variants` with no notable business event, and the plan said "fill obvious gaps only," so skipping it is defensible.
- **Fix**: None — read-only search has no obvious INFO/WARNING gap.
- **Decision**: FIXED — added `app.medicines.service` logger; INFO on product-search result count and variant-list count, DEBUG on too-short query.

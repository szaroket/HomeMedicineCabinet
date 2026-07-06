<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Delete User Account

- **Plan**: context/changes/delete-user-account/plan.md
- **Scope**: Phases 1–3 (full plan)
- **Date**: 2026-07-06
- **Verdict**: APPROVED
- **Findings**: 0 critical, 0 warnings, 3 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

## What Was Verified

- **Plan adherence** — all 11 planned items MATCH. Three carry the plan's own documented addenda (facade→service pass-throughs; `clearStoredToken` vs `clearSession`; hard-redirect to `/account-deleted`). No MISSING items, no scope-creep EXTRAs, no guardrail violations (`medication_registry` untouched, no cascade migration, no notifications cleanup, no password re-verification, no soft-delete).
- **Safety invariants** — service-role key server-only and never logged; `DELETE /users/me` double-guarded and only ever deletes `current_user.id`; delete ordering children→parent with no FK-cascade reliance; local deletes atomic in a single `persist()`/commit with Supabase delete only after commit; 503 (nothing deleted, keep session) vs 502 (data gone, tear down) mapped correctly at router and frontend hook; Supabase 404 treated as idempotent no-op.
- **Automated success criteria**:
  - Backend ruff check + format — PASS
  - Backend unit tests (`tests/db/test_supabase_auth.py tests/users tests/cabinet`) — PASS (271 passed)
  - Frontend lint / prettier / vitest — PASS (42 passed)
  - Frontend build — PASS
  - Backend integration tests — INCONCLUSIVE from Bash (L-001 OpenSSL applink crash on TLS testcontainer; must run from PowerShell; verified passing in phase-2 review + CI)
  - Backend pyright typecheck — INCONCLUSIVE from Bash (same L-001 crash via `uv run`; verified passing in phase-2 review + CI)

## Findings

### F1 — 502 partial-deletion recovery path lacks a test

- **Severity**: 🔵 OBSERVATION
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Success Criteria
- **Location**: backend/tests/integration/users/test_delete_account.py
- **Detail**: On a 502 (Supabase delete fails after local commit) the auth identity + refresh-token cookie survive; recovery relies on re-login idempotently re-provisioning empty rows and the user re-triggering delete. That documented recovery loop is not directly exercised — the integration suite covers 204 / 401 / 503 / 502 mapping but not "re-login after 502, then re-delete succeeds."
- **Fix**: Add an integration test asserting a user can re-login after a 502 and a second delete completes to 204 (idempotent recovery).
- **Decision**: FIXED — added `test_delete_account_idempotent_recovery_after_502` in backend/tests/integration/users/test_delete_account.py (side_effect [AccountDeletionError, None]; asserts 502 → local rows gone → re-provision same identity → re-delete 204). Ruff clean; execution blocked locally by L-001 OpenSSL applink crash (whole integration suite), to be verified in CI.

### F2 — Broadest log sink on the admin delete path

- **Severity**: 🔵 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/db/supabase_auth.py:87-89
- **Detail**: Generic `except Exception` logs with `exc_info=True` on the admin (service-role) path. Verified safe today — supabase-py/httpx exceptions do not embed the Authorization header/key in message or traceback locals. Flagged only because it is the widest log sink on the sensitive path; worth an eye if the Supabase client changes its exception surface.
- **Fix**: None required. Keep the note; no key currently leaks.
- **Decision**: SKIPPED — accepted as-is; no key leaks today, no change warranted.

### F3 — useDeleteAccount error type narrower than reality

- **Severity**: 🔵 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: frontend/src/features/settings/api/settings-queries.ts:48
- **Detail**: Typed `useMutation<void, Response>`, but `apiFetch` can also reject with `AuthError` (refresh failure), not a `Response`. Behavior is correct — the `instanceof Response` guard skips teardown and the global `AuthError` subscriber handles it — the declared error type is just narrower than the real union. Cosmetic.
- **Fix**: Widen the mutation error type to `Response | AuthError` (or `unknown`) to match runtime.
- **Decision**: FIXED — `useMutation<void, Response | AuthError>` + `import { AuthError } from "@/lib/errors"` in settings-queries.ts. ESLint + tsc --noEmit clean.

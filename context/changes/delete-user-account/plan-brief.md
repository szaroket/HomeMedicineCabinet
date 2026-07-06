# Delete User Account — Plan Brief

> Full plan: `context/changes/delete-user-account/plan.md`

## What & Why

Let a signed-in user **permanently delete their own account and all associated
data** from the Settings screen, behind explicit confirmation, then log them out
and return to the entry screen. Implements roadmap slice **S-09** — the standalone
account-lifecycle feature.

## Starting Point

Supabase Auth is the identity provider; login/register idempotently provision a
local `users` row and a `user_preferences` row. The only user-owned data is
`cabinet_entries` and `user_preferences` (`medication_registry` is a shared
global catalog; notifications don't exist yet). There is **no FK cascade** and
**no service-role key** in config — both are prerequisites this plan adds. A
`settings` feature and `/settings` route already exist as the UI home.

## Desired End State

In **Ustawienia**, a "Usuń konto" section opens a dialog requiring the user to
type their own email to enable a destructive delete. Confirming wipes their
cabinet entries, preferences, and `users` row, deletes their Supabase Auth user,
clears the session, and lands them on `/login` with "Konto zostało usunięte." The
old credentials no longer work and no data for that user remains.

## Key Decisions Made

| Decision                    | Choice                                              | Why (1 sentence)                                                                 | Source |
| --------------------------- | --------------------------------------------------- | -------------------------------------------------------------------------------- | ------ |
| Cascade strategy            | Explicit deletes in the facade                      | No Alembic run (avoids L-001), deletion is visible/testable in Python.           | Plan   |
| Delete ordering             | Local DB first, then Supabase                       | Local delete is transactional; `provision_user` idempotency tolerates a re-login. | Plan   |
| Endpoint                    | `DELETE /api/v1/users/me`                           | Clear `me`-resource semantics on the already-guarded users router.               | Plan   |
| Re-auth                     | No re-auth; email-type-to-confirm in the UI         | Meets "explicit confirmation" with minimal surface; short-lived access tokens.   | Plan   |
| Confirm text                | The user's own email address                        | Unambiguous, personal, verifiable client-side against the auth store.            | Plan   |
| Post-delete                 | Clear session + query cache → `/login` with notice  | Reuses the existing logout teardown; `/login` is the neutral entry screen.       | Plan   |
| Testing                     | Backend unit + integration; frontend unit           | Covers the risky ordering + the confirm gate without destructive E2E cost.       | Plan   |

## Scope

**In scope:** service-role admin client + `delete_user`; new config field; explicit
cascade deletes (cabinet + users rows); users-domain facade; guarded
`DELETE /users/me`; Settings delete-account section with email-type-to-confirm;
session teardown + redirect; unit + integration + frontend-unit tests.

**Out of scope:** `ON DELETE CASCADE` migration; deleting `medication_registry`;
notifications cleanup (not built); password re-verification; soft-delete/recovery;
admin/other-user deletion; extra refresh-token revocation.

## Architecture / Approach

Frontend confirm dialog → `DELETE /api/v1/users/me` (guarded) → users-domain
`facade.delete_account`. The facade is the only cross-domain caller: it runs local
deletes as one atomic unit (`cabinet.crud.delete_by_user` → `users.crud.delete_user_rows`
→ commit), then calls `supabase_auth.delete_user` via a new service-role admin
client. On success the client clears the token + query cache and redirects to
`/login`.

## Phases at a Glance

| Phase                                   | What it delivers                                              | Key risk                                                        |
| --------------------------------------- | ------------------------------------------------------------ | -------------------------------------------------------------- |
| 1. Supabase admin delete + config       | Service-role client, `delete_user`, `AccountDeletionError`   | Handling the sensitive service-role key safely (server-only).  |
| 2. Cascade deletion, facade, endpoint   | Bulk deletes, facade orchestration, guarded `DELETE /users/me` | Partial-failure between local commit and Supabase delete.      |
| 3. Settings delete-account UX           | Confirm dialog, mutation, session teardown + redirect        | Getting the email-match gate + session teardown exactly right. |

**Prerequisites:** `SUPABASE_SERVICE_ROLE_KEY` provisioned in local `.env` and the
Render backend service (L-007), server-side only.
**Estimated effort:** ~3 sessions, one per phase.

## Open Risks & Assumptions

- The service-role key must never reach the frontend or the logs — it grants full
  admin access to Supabase.
- Local-DB-first ordering means a Supabase-side failure leaves an auth user with
  empty local data until they retry; accepted because re-login re-provisions
  idempotently.
- Assumes `auth.admin.delete_user` is the correct SDK call and that a missing
  auth user can be treated as already-deleted (confirm SDK behavior in Phase 1).

## Success Criteria (Summary)

- A user can delete their account from Ustawienia behind an email-type-to-confirm
  gate and is returned to `/login`.
- All of the user's cabinet entries, preferences, `users` row, and Supabase Auth
  user are gone; the shared `medication_registry` is untouched.
- The deleted credentials can no longer log in.

# Delete User Account Implementation Plan

## Overview

Give a signed-in user a way to **permanently delete their own account and all
associated data**. A new guarded `DELETE /api/v1/users/me` endpoint deletes the
user's cabinet entries, preferences, and `users` row (explicit deletes, local
DB first), then deletes the Supabase Auth user via a service-role admin client.
The capability is surfaced in the existing Settings page behind an
email-type-to-confirm dialog; on success the client tears down the session and
redirects to `/login` with a Polish notice.

Implements roadmap slice **S-09** (`context/foundation/roadmap.md:259-262`).

## Current State Analysis

- **Auth model**: Supabase Auth is the identity provider. On register/login the
  app idempotently provisions two local rows via `auth/crud.py::provision_user`
  — a `users` row and a `user_preferences` row (`insert(...).on_conflict_do_nothing`).
- **User-owned data today**: only `cabinet_entries` (per-user) and
  `user_preferences` (one-per-user). `medication_registry` is a **global shared
  catalog**, not user-owned — it must NOT be touched on account deletion.
  Notifications from the roadmap outcome line **do not exist yet** (no
  notifications domain), so there is nothing to delete there.
- **No FK cascade**: `user_preferences.user_id → users.id` and
  `cabinet_entries.user_id → users.id` are declared **without `ondelete`**
  (`users/models.py:29`, `cabinet/models.py:20`, initial migration
  `0e56afa1e4b6`). Deleting the `users` row today raises a FK violation unless
  children are deleted first.
- **Config gap**: `app/core/config.py` holds `supabase_anon_key` only. Supabase
  Auth **user deletion requires the admin API** (`auth.admin.delete_user(id)`),
  which needs a **service-role key** — a new, server-only, highly sensitive
  credential not present in the codebase.
- **Supabase access layer**: `app/db/supabase_auth.py` holds a lazily-created
  anon client (`get_supabase()`) plus thin auth operations (`sign_up`,
  `sign_in_with_password`, `refresh_session`) that map `AuthApiError` to domain
  errors. This is the natural home for a new admin client + `delete_user`.
- **Cross-domain rule**: deletion spans cabinet + users + Supabase, so per
  AGENTS.md it requires a **`facade.py`** in the owning domain — services/cruds
  may not call other domains directly.
- **Users domain** already exists with a `Security(get_current_user)`-guarded
  router (`users/router.py`), `service.py`, `crud.py` using the `persist(...)`
  transaction context manager, and the `CurrentUser` type carrying `id`/`email`.
- **Frontend home exists**: a `settings` feature with `SettingsPage`, a
  `/settings` protected route, `settings-api.ts` + `settings-queries.ts`, and
  clean session-teardown patterns (`useAuth().clearSession`, `queryClient`,
  `LogoutButton` navigating to `/login`).

### Key Discoveries:

- Explicit cascade in the facade is chosen over a DB `ON DELETE CASCADE`
  migration — no Alembic run needed (avoids the L-001 PowerShell-only DB
  constraint) and deletion is visible/testable in Python.
- `provision_user` idempotency (`auth/crud.py:21`) means the chosen
  **local-DB-first** ordering is safe: if the Supabase admin delete fails after
  local rows are gone, a re-login simply re-provisions empty local rows.
- L-004 applies to every new `crud` delete: wrap each `await session.execute`
  in `try/except SQLAlchemyError`, log with `exc_info=True`, raise the domain
  `*DatabaseError` chained `from exc`; router maps that to HTTP 503.
- The `persist(session, ...)` context manager (`db/connector.py:40`) is the
  established flush/commit/rollback wrapper used by users/cabinet crud.
- Cabinet crud already has a single-entry `delete_entry` (`cabinet/crud.py:546`)
  to mirror for the new bulk `delete_by_user`.

## Desired End State

A signed-in user opens **Ustawienia**, finds a "Usuń konto" section, and must
type their own email into a confirmation dialog to enable a destructive delete
button. Confirming calls `DELETE /api/v1/users/me`; the backend removes all of
the user's cabinet entries, their preferences row, their `users` row, and their
Supabase Auth user. The client then clears the token + query cache and lands on
`/login` showing "Konto zostało usunięte." The deleted user can no longer log in
with the old credentials, and no cabinet/preferences rows for that user remain.

Verify: register a throwaway user, add a cabinet entry, delete the account via
the UI, confirm redirect to `/login`, confirm login now fails, and confirm the
DB has no `cabinet_entries`/`user_preferences`/`users` rows for that id.

## What We're NOT Doing

- **No `ON DELETE CASCADE` migration** — cascade is done explicitly in the facade.
- **No deletion of `medication_registry`** — it is a shared global catalog.
- **No notifications cleanup** — the notifications feature does not exist yet.
- **No password re-verification / re-auth** — confirmation is email-type-to-confirm
  in the UI; the backend trusts the valid JWT.
- **No Supabase refresh-token revocation** beyond the account delete itself (the
  existing logout is already cookie-clear-only; account delete removes the auth
  user, which is sufficient).
- **No soft-delete / recovery / grace period** — deletion is immediate and permanent.
- **No admin/other-user deletion** — strictly self-service on the `me` resource.

## Implementation Approach

Three vertical phases. Phase 1 isolates the sensitive service-role credential and
the Supabase admin delete so it can be unit-tested before anything depends on it.
Phase 2 builds the local cascade deletes, the users-domain facade that orchestrates
local-DB-first-then-Supabase, and the guarded endpoint with status mapping.
Phase 3 wires the Settings UI, the typed API call + mutation, and the
success-path session teardown + redirect.

## Critical Implementation Details

- **Deletion ordering & partial-failure**: delete local rows **first** in a
  single committed unit (cabinet_entries → user_preferences → users), **then**
  call the Supabase admin delete. If the local delete fails → 503, nothing
  changed for Supabase. If Supabase delete fails after the local commit → return
  a 5xx account-deletion error; the auth user survives but its local data is
  gone and will be re-provisioned empty on next login (idempotent). Do not
  attempt to "roll back" the local delete.
- **Service-role key is server-only**: it must live solely in backend env/config,
  never be sent to or referenced by the frontend, and never be logged. It is a
  separate credential from `supabase_anon_key` and grants full admin access.
- **Delete order matters for FK**: children (`cabinet_entries`,
  `user_preferences`) must be deleted before the parent `users` row, since no DB
  cascade exists.

## Phase 1: Backend — Supabase admin delete + config

### Overview

Add the service-role admin client and a domain-mapped `delete_user` Supabase
operation, plus the config field that backs it. No app code depends on this yet;
it is unit-tested in isolation.

### Changes Required:

#### 1. Service configuration

**File**: `backend/app/core/config.py`

**Intent**: Add the server-only Supabase service-role key so the backend can call
the Auth admin API.

**Contract**: New required `supabase_service_role_key: str` field on `Settings`,
documented in the class docstring `Attributes:` block (Google style, per repo
convention). Loaded from env like the other Supabase settings. Also add the key
to `.env.example` / deployment env docs if such a file exists; note in the plan
that Render env vars must be set by hand (L-007).

#### 2. Supabase admin client + delete operation

**File**: `backend/app/db/supabase_auth.py`

**Intent**: Provide a lazily-created **admin** Supabase client (separate module
global from the anon `_client`) and a `delete_user(user_id)` operation that maps
Supabase failures to domain errors, mirroring the existing `sign_up` pattern.

**Contract**:
- `get_supabase_admin() -> Client` — lazily `create_client(settings.supabase_url,
  settings.supabase_service_role_key)`, cached in a module global.
- `delete_user(user_id: str) -> None` — calls
  `get_supabase_admin().auth.admin.delete_user(user_id)`; on `AuthApiError` /
  unexpected exception logs (without the key) and raises the new
  `AccountDeletionError`. Does not raise on "user not found" if that surfaces as
  a benign case — treat a missing auth user as already-deleted (idempotent);
  confirm the SDK's behavior during implementation and branch on `e.status`/
  `e.code` accordingly.

#### 3. Account-deletion domain error

**File**: `backend/app/utilities/errors.py`

**Intent**: Add an error type for the Supabase-side (non-DB) deletion failure so
the router can map it distinctly from `UserDatabaseError`.

**Contract**: New `AccountDeletionError(UserError)` with a default English
message (e.g. "Failed to delete account."), placed alongside `UserDatabaseError`.

### Success Criteria:

#### Automated Verification:

- Linting passes: `cd backend && uv run ruff check . && uv run ruff format --check .`
- Unit tests pass: `cd backend && uv run pytest tests/db/test_supabase_auth.py`
  (or existing supabase test module) covering: `delete_user` success calls
  `auth.admin.delete_user` with the id; `AuthApiError` maps to
  `AccountDeletionError`; admin client is created with the service-role key.
- Config loads with the new field present: `cd backend && uv run python -c "from app.core.config import settings"`
  (run from PowerShell if it touches TLS; here it only parses env).

#### Manual Verification:

- The service-role key is set in local `.env` and in the Render backend service
  env (L-007) — not committed, not exposed to the frontend.
- Log output during a delete does not contain the service-role key.

**Implementation Note**: After completing this phase and all automated verification
passes, pause for manual confirmation before proceeding.

---

## Phase 2: Backend — cascade deletion, facade, and endpoint

### Overview

Add the local cascade deletes, a users-domain facade that orchestrates
local-DB-first-then-Supabase, and the guarded `DELETE /users/me` endpoint with
HTTP status mapping.

### Changes Required:

#### 1. Cabinet bulk delete

**File**: `backend/app/api/v1/cabinet/crud.py`

**Intent**: Delete all cabinet entries owned by a user in one statement.

**Contract**: `delete_by_user(session: AsyncSession, user_id: uuid.UUID) -> None`
issuing a `delete(CabinetEntry).where(col(CabinetEntry.user_id) == user_id)`.
Wrap the `execute` in `try/except SQLAlchemyError` per L-004, log with
`exc_info=True`, raise `CabinetDatabaseError from exc`. Commit boundary is owned
by the facade (see facade contract) — this function executes the delete on the
shared session and does not independently commit; follow whichever pattern the
facade uses for a single atomic local transaction.

#### 2. Users local-rows delete

**File**: `backend/app/api/v1/users/crud.py`

**Intent**: Delete the user's `user_preferences` row and `users` row (children
before parent), on the shared session.

**Contract**: `delete_user_rows(session: AsyncSession, user_id: uuid.UUID) -> None`
executing `delete(UserPreferences).where(user_id == ...)` then
`delete(User).where(id == ...)`. L-004 wrapping → `UserDatabaseError`. Same
commit-ownership note as cabinet: the facade controls the single commit so all
local deletes land atomically.

#### 3. Users delete-account facade

**File**: `backend/app/api/v1/users/facade.py` (new)

**Intent**: Orchestrate the full account deletion across domains — the only place
allowed to call cabinet crud + users crud + the Supabase admin operation.

**Contract**: `delete_account(session: AsyncSession, user_id: uuid.UUID) -> None`.
Order: (1) local deletes as one atomic unit — `cabinet.crud.delete_by_user`,
`users.crud.delete_user_rows`, then a single `commit` (use `persist`/session
transaction so a failure rolls back and nothing is half-deleted); (2) on local
success, `supabase_auth.delete_user(str(user_id))`. Propagates
`CabinetDatabaseError` / `UserDatabaseError` (→ 503) and `AccountDeletionError`
(→ 5xx) to the router. Log start and completion with the user id.

#### 4. Delete-account endpoint

**File**: `backend/app/api/v1/users/router.py`

**Intent**: Expose the guarded self-service delete on the `me` resource.

**Contract**: `@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)`
(router already carries `dependencies=[Security(get_current_user)]`). Handler
takes `current_user: CurrentUser = Security(get_current_user)` + session, calls
`facade.delete_account(session, current_user.id)`. Map `UserDatabaseError` /
`CabinetDatabaseError` → 503; `AccountDeletionError` → 502 (upstream Supabase
failure) or 500 — pick one and keep consistent with existing mapping style; any
other exception → 500 via the existing `logger.exception` fallback pattern.

### Success Criteria:

#### Automated Verification:

- Linting passes: `cd backend && uv run ruff check . && uv run ruff format --check .`
- Unit tests pass: `cd backend && uv run pytest tests/users tests/cabinet` —
  covering `delete_by_user`, `delete_user_rows` (mocked `AsyncSession`, `spec=`),
  and the facade ordering (local deletes happen before Supabase; Supabase not
  called if local delete raises).
- Integration tests pass: `cd backend && uv run pytest tests/integration` —
  `DELETE /api/v1/users/me` returns 204 on success (Supabase admin mocked),
  requires auth (401 without token), and maps `UserDatabaseError` → 503 and
  `AccountDeletionError` → its chosen 5xx.
- Backend typecheck passes (project's configured typecheck command).

#### Manual Verification:

- Against a real dev DB + Supabase: deleting a throwaway account removes its
  `cabinet_entries`, `user_preferences`, and `users` rows and its Supabase Auth
  user; `medication_registry` is untouched.
- Re-login with the deleted credentials fails.

**Implementation Note**: After completing this phase and all automated verification
passes, pause for manual confirmation before proceeding.

---

## Phase 3: Frontend — Settings delete-account UX

### Overview

Add a "Usuń konto" section to the Settings page with an email-type-to-confirm
dialog, the typed API call + mutation hook, and success-path session teardown +
redirect to `/login`.

### Changes Required:

#### 1. Delete-account API call

**File**: `frontend/src/features/settings/api/settings-api.ts`

**Intent**: Add the typed fetcher for the delete endpoint.

**Contract**: `deleteAccount(): Promise<void>` calling
`apiFetch("/users/me", { method: "DELETE" })` (204, no body). Follows the
existing `logout()` shape in `auth-api.ts`.

#### 2. Delete-account mutation hook

**File**: `frontend/src/features/settings/api/settings-queries.ts`

**Intent**: Provide a `useDeleteAccount` mutation that tears down the session on
success.

**Contract**: `useDeleteAccount()` — `useMutation({ mutationFn: deleteAccount })`;
on success call `useAuth().clearSession()` and `queryClient.clear()` so no stale
protected data survives. Navigation is done by the component (mirrors
`LogoutButton`, which navigates in `onSettled`).

#### 3. Delete-account section + confirm dialog

**File**: `frontend/src/features/settings/components/settings-page.tsx` (and a
new `delete-account-section.tsx` component if the page grows too large — colocate
in `settings/components/`).

**Intent**: Render a destructive "Usuń konto" section that opens a confirmation
dialog requiring the user to type their own email before the delete button
enables; on confirm, run the mutation and redirect.

**Contract**:
- Reads the current email from `useAuth().user?.email`.
- A confirm input; the delete button is disabled until the typed value **exactly
  equals** the account email. Make the input properly labelled (`htmlFor`/`id`)
  so it is locatable by role/label, not test-id (per project locator rule).
- All visible copy in **Polish** (section title "Usuń konto", warning that the
  action is permanent, button "Usuń konto trwale", cancel "Anuluj").
- On mutation success: navigate to `/login` (component-level `useNavigate`) and
  surface the "Konto zostało usunięte." notice on the login screen — pass via
  router state or a lightweight mechanism consistent with existing patterns.
- On error: show a Polish error message (e.g. "Nie udało się usunąć konta.")
  and keep the user on the page.

### Success Criteria:

#### Automated Verification:

- Build passes: `cd frontend && npm run build`
- Lint passes: `cd frontend && npm run lint`
- Format check passes: `cd frontend && npx prettier --check src/`
- Unit test passes: `cd frontend && npx vitest run` — a test for the confirm gate:
  the delete button is disabled until the typed value equals the account email,
  and enabling + confirming calls the delete mutation.

#### Manual Verification:

- The delete button stays disabled until the exact email is typed.
- Confirming deletes the account, redirects to `/login`, shows the Polish notice,
  and a subsequent login attempt with the old credentials fails.
- Cancelling the dialog leaves the account intact.

**Implementation Note**: After completing this phase and all automated verification
passes, pause for manual confirmation.

---

## Testing Strategy

### Unit Tests:

- Backend: `supabase_auth.delete_user` success + `AuthApiError → AccountDeletionError`;
  admin client built with the service-role key. `cabinet.crud.delete_by_user` and
  `users.crud.delete_user_rows` with mocked `AsyncSession` (`spec=`), asserting
  the delete statements and L-004 error mapping. Facade ordering: local deletes
  run before Supabase; Supabase admin is **not** called when a local delete raises.
- Frontend: confirm-gate test — button disabled until typed value equals the
  account email; confirming triggers the delete mutation.

### Integration Tests:

- `DELETE /api/v1/users/me`: 204 on success (Supabase admin mocked), 401 without
  auth, 503 on `UserDatabaseError`, chosen 5xx on `AccountDeletionError`.

### Manual Testing Steps:

1. Register a throwaway user; add a cabinet entry.
2. Open Ustawienia → Usuń konto; verify the button is disabled until the exact
   email is typed.
3. Confirm; verify redirect to `/login` and the "Konto zostało usunięte." notice.
4. Attempt to log in with the deleted credentials — verify it fails.
5. Inspect the DB: no `cabinet_entries` / `user_preferences` / `users` rows for
   that id; `medication_registry` unaffected.

## Performance Considerations

Deletion is a one-off, low-volume operation on small per-user row counts; no
performance concerns. Bulk `delete ... where user_id = ...` is a single statement
per table.

## Migration Notes

No schema migration. Cascade is performed in application code, so existing data
and the DB schema are unchanged. The only new operational requirement is setting
`SUPABASE_SERVICE_ROLE_KEY` in every backend environment (local `.env` and the
Render backend service dashboard — L-007), kept server-side only.

## References

- Roadmap slice: `context/foundation/roadmap.md:259-262`
- Cross-domain facade rule: `AGENTS.md` (Backend layer rules)
- Supabase auth ops pattern: `backend/app/db/supabase_auth.py`
- Idempotent provisioning: `backend/app/api/v1/auth/crud.py:21`
- Single-entry delete to mirror: `backend/app/api/v1/cabinet/crud.py:546`
- Session teardown pattern: `frontend/src/features/auth/components/logout-button.tsx`,
  `frontend/src/features/auth/store.ts`
- Lessons: L-001 (TLS DB from PowerShell), L-004 (SQLAlchemyError wrapping),
  L-006 (top-of-file imports), L-007 (Render manual config)

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Backend — Supabase admin delete + config

#### Automated

- [ ] 1.1 Linting passes (ruff check + format)
- [ ] 1.2 Unit tests pass for `delete_user` (success, `AuthApiError → AccountDeletionError`, admin client uses service-role key)
- [ ] 1.3 Config loads with the new `supabase_service_role_key` field

#### Manual

- [ ] 1.4 Service-role key set in local `.env` and Render backend env; not committed, not exposed to frontend
- [ ] 1.5 Logs during a delete do not contain the service-role key

### Phase 2: Backend — cascade deletion, facade, and endpoint

#### Automated

- [ ] 2.1 Linting passes (ruff check + format)
- [ ] 2.2 Unit tests pass for `delete_by_user`, `delete_user_rows`, and facade ordering
- [ ] 2.3 Integration tests pass for `DELETE /api/v1/users/me` (204, 401, 503, 5xx mapping)
- [ ] 2.4 Backend typecheck passes

#### Manual

- [ ] 2.5 Real DB + Supabase: account rows removed, Supabase Auth user removed, `medication_registry` untouched
- [ ] 2.6 Re-login with deleted credentials fails

### Phase 3: Frontend — Settings delete-account UX

#### Automated

- [ ] 3.1 Build passes (`npm run build`)
- [ ] 3.2 Lint passes (`npm run lint`)
- [ ] 3.3 Format check passes (prettier)
- [ ] 3.4 Unit test passes for the email-type-to-confirm gate

#### Manual

- [ ] 3.5 Delete button disabled until exact email typed
- [ ] 3.6 Confirm deletes account, redirects to `/login`, shows Polish notice, subsequent login fails
- [ ] 3.7 Cancelling the dialog leaves the account intact

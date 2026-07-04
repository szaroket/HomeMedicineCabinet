# Auth Polish — Plan Brief

> Full plan: `context/changes/auth-polish/plan.md`

## What & Why

Add a "Powtórz hasło" (confirm password) field to the registration form so users
can't submit a password with a typo (roadmap slice F-01b, PRD FR-001). The second
value is a client-side typo guard only — it never reaches the backend.

## Starting Point

The register form has email + password fields (`react-hook-form` + zod). The
registration schema is `{ email, password: min(8) }`, and `auth-api.ts` serializes
the whole form object into the POST body. The backend `RegisterRequest` already
validates email + password min-8 and is unaffected.

## Desired End State

The registration screen shows three fields (e-mail, hasło, powtórz hasło). Two
different passwords produce a Polish mismatch error on the confirm field and block
submission; a corrected match clears the error live and submits `{email, password}`
only — no `confirmPassword` on the wire.

## Key Decisions Made

| Decision              | Choice                                   | Why (1 sentence)                                                       | Source |
| --------------------- | ---------------------------------------- | --------------------------------------------------------------------- | ------ |
| Validation timing     | On submit, then live re-validate         | Matches the current register form's default RHF behavior — no divergence. | Plan   |
| Scope                 | Confirm field only                       | Stays inside slice F-01b / FR-001; no toggle or password-rule changes. | Plan   |
| Payload safety        | Split schema; narrow API type to credentials | TypeScript guarantees `confirmPassword` can't be serialized to the backend. | Plan   |
| Backend change        | None                                     | Only one password is transmitted; there is nothing server-side to confirm. | Plan   |
| Test coverage         | Schema unit test only                    | Cheap, covers the actual match rule, fits the existing Vitest precedent. | Plan   |

## Scope

**In scope:** confirm-password field + Polish match error; schema split; API/mutation
payload-type narrowing; one schema unit test.

**Out of scope:** backend changes; show/hide toggle; password-strength rules; login
form; the parked "login needs a refresh" bug; RTL/E2E tests.

## Architecture / Approach

Two schemas: a credentials schema (email + password) that stays the API payload
contract, and a form schema extending it with `confirmPassword` + a `.refine()` match
rule. Narrow `register()` and `useRegister` to the credentials type so the confirm
value is structurally excluded from the request; the form strips it before `mutate`.

## Phases at a Glance

| Phase                                   | What it delivers                                         | Key risk                                            |
| --------------------------------------- | ------------------------------------------------------- | --------------------------------------------------- |
| 1. Confirm-password field on registration | Schema refine, narrowed payload types, form field, unit test | Accidentally sending `confirmPassword` to the backend (mitigated by the credentials type) |

**Prerequisites:** none — F-01 auth scaffold is already done.
**Estimated effort:** ~1 short session, single phase.

## Open Risks & Assumptions

- Assumes the RHF default validation mode is acceptable for the "on submit, then
  live-correct" UX (verified against the existing form — no config needed).
- Assumes Vitest run command (`npm test` / `npx vitest run`) is available as used by
  the existing `auth-api.test.ts`.

## Success Criteria (Summary)

- Mismatched passwords are caught in the UI with a Polish error and cannot be submitted.
- A corrected, matching registration succeeds and navigates to `/`.
- The `/auth/register` request body contains only `email` + `password`.

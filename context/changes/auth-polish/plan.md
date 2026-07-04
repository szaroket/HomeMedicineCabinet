# Auth Polish — Confirm-Password Field Implementation Plan

## Overview

Add a "Powtórz hasło" (confirm password) field to the registration form so a user
cannot submit a mistyped password. A cross-field zod refinement rejects mismatched
entries in the UI; the second value never reaches the network. This is roadmap
slice **F-01b (auth-polish)**, PRD ref **FR-001**. Frontend-only — the backend
registration contract is unchanged.

## Current State Analysis

- **`frontend/src/features/auth/components/register-form.tsx`** — email + password
  fields, `react-hook-form` + `zodResolver(registerSchema)`, default validation
  mode (validate on submit, re-validate on change). Password input uses
  `autoComplete="new-password"` and label/input are associated via `htmlFor`/`id`.
  On success it navigates to `/`; a 409 maps to a Polish "account exists" message.
- **`frontend/src/features/auth/schemas/auth-schemas.ts`** — `registerSchema` is
  `{ email: email(), password: min(8) }`; `RegisterValues` is inferred from it and
  is the payload type consumed downstream.
- **`frontend/src/features/auth/api/auth-api.ts`** — `register(data: RegisterValues)`
  does `JSON.stringify(data)`, so **every field on `RegisterValues` is POSTed** to
  `/auth/register`. `auth-queries.ts` `useRegister` types its mutation input as
  `RegisterValues` too.
- **`backend/app/api/v1/auth/schemas.py`** — `RegisterRequest` accepts `{email, password}`
  and already validates `EmailStr` + password min-length 8. Needs no change: a
  confirm field is a client typo guard, and only one password value is transmitted.
- **Tests** — Vitest is wired (`frontend/src/features/auth/api/auth-api.test.ts`
  exists). No RTL component test for the register form; E2E is golden-path only.

## Desired End State

On the registration screen the user sees three fields — e-mail, hasło, powtórz
hasło. Submitting with two different passwords shows a Polish mismatch error on the
confirm field and blocks submission; once corrected the error clears live and the
form submits `{email, password}` only. Verified by: a passing schema unit test, a
green `npm run build` / `npm run lint`, and a manual registration where a
deliberate mismatch is caught and a corrected match registers successfully.

### Key Discoveries:

- Payload leak risk: `auth-api.ts:19` serializes the whole form object — the API
  payload type must stay `{email, password}` so `confirmPassword` can't reach the
  backend (`frontend/src/features/auth/api/auth-api.ts:18-24`).
- Locator a11y: keep the confirm input associated to its label via `htmlFor`/`id`
  (matches the existing email/password fields and the project's locator-a11y rule).
- Validation timing is already correct by default in RHF for the chosen UX
  (error on submit, live re-validation after) — no mode config needed.

## What We're NOT Doing

- No backend change — `RegisterRequest` and its validators are untouched.
- No password-visibility (show/hide) toggle.
- No change to password strength rules (min-8 stays as-is on both ends).
- No changes to the login form or the parked "login needs a page refresh" bug.
- No RTL component test or new E2E — schema unit test only.

## Implementation Approach

Split the registration schema into two: a credentials schema (email + password) that
remains the API payload contract, and a form schema that extends it with
`confirmPassword` plus a cross-field `.refine()` for the match. Narrow the API and
mutation input types to the credentials type so TypeScript guarantees
`confirmPassword` never reaches the network. Add the field to the form and strip the
confirm value before calling `mutate`. Cover the match logic with a schema unit test.

## Phase 1: Confirm-password field on registration

### Overview

Extend the schema, narrow the payload types, render the field, and unit-test the
match rule — all frontend.

### Changes Required:

#### 1. Registration schemas

**File**: `frontend/src/features/auth/schemas/auth-schemas.ts`

**Intent**: Introduce a confirm-password field with a cross-field match rule while
preserving a credentials-only type for the API payload, so the confirm value is
structurally excluded from what gets sent to the backend.

**Contract**:
- Keep a credentials schema (email + password min-8) — this is the API payload
  shape. Export its inferred type (e.g. `RegisterCredentials`).
- Add a form schema that extends the credentials schema with
  `confirmPassword: z.string()` and a `.refine()` asserting
  `password === confirmPassword`, attaching the error to `path: ["confirmPassword"]`
  with a Polish message (e.g. "Hasła muszą być takie same"). Export its inferred
  type (e.g. `RegisterFormValues`).
- The existing `registerSchema` / `RegisterValues` names may be reused for the
  credentials pair to minimize churn, provided the form uses the new extended
  schema and downstream payload types resolve to email+password only.

#### 2. API + mutation payload types

**File**: `frontend/src/features/auth/api/auth-api.ts` and
`frontend/src/features/auth/api/auth-queries.ts`

**Intent**: Narrow the register request/mutation input to the credentials type so
`confirmPassword` cannot be serialized into the POST body.

**Contract**: `register(data: RegisterCredentials)` in `auth-api.ts`; `useRegister`
mutation input typed as `RegisterCredentials` in `auth-queries.ts`. No behavior
change beyond the type narrowing.

#### 3. Register form field

**File**: `frontend/src/features/auth/components/register-form.tsx`

**Intent**: Add the confirm-password input below the password field, render its
validation error, and pass only credentials to the mutation.

**Contract**:
- Resolver switches to the form schema; form values typed as `RegisterFormValues`.
- New input: `id="confirmPassword"`, matching `htmlFor` label "Powtórz hasło",
  `type="password"`, `autoComplete="new-password"`, styled like the existing inputs;
  render `errors.confirmPassword?.message` in the same red-text pattern.
- In `onSubmit`, pass `{ email, password }` to `mutate` (drop `confirmPassword`).
- Leave default RHF validation mode as-is (submit-then-live-revalidate).

#### 4. Schema unit test

**File**: `frontend/src/features/auth/schemas/auth-schemas.test.ts` (new)

**Intent**: Lock the match rule so a regression can't silently drop it.

**Contract**: Vitest tests parsing the register form schema — a mismatched
`confirmPassword` fails with the error on the `confirmPassword` path; an identical
`confirmPassword` (with valid email + min-8 password) passes.

### Success Criteria:

#### Automated Verification:

- Type check + build passes: `npm run build`
- Lint passes: `npm run lint`
- Format check passes: `npx prettier --check src/`
- Schema unit test passes: `npm test` (or `npx vitest run`)

#### Manual Verification:

- Registering with two different passwords shows the Polish mismatch error on the
  confirm field and blocks submission.
- Correcting the confirm field clears the error live (without another submit).
- A matching, valid registration submits and navigates to `/`.
- Network tab shows the `/auth/register` request body contains only `email` and
  `password` — no `confirmPassword`.

**Implementation Note**: After automated verification passes, pause for manual
confirmation from the human that the manual testing above succeeded before
considering the slice done.

---

## Testing Strategy

### Unit Tests:

- Register form schema: mismatch → error on `confirmPassword`; match + valid
  email/password → parses successfully.

### Manual Testing Steps:

1. Open the registration page.
2. Enter a valid email and a password (≥ 8 chars); type a different confirm value;
   submit → expect the Polish mismatch error, no navigation.
3. Fix the confirm value to match → error clears live.
4. Submit → expect navigation to `/` and, in DevTools Network, a request body with
   only `email` + `password`.

## Migration Notes

None — no schema/data/backend changes.

## References

- Roadmap slice: `context/foundation/roadmap.md` (F-01b auth-polish, FR-001)
- Payload serialization: `frontend/src/features/auth/api/auth-api.ts:18-24`
- Existing form pattern: `frontend/src/features/auth/components/register-form.tsx`
- Backend contract (unchanged): `backend/app/api/v1/auth/schemas.py:8-35`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles.

### Phase 1: Confirm-password field on registration

#### Automated

- [ ] 1.1 Type check + build passes: `npm run build`
- [ ] 1.2 Lint passes: `npm run lint`
- [ ] 1.3 Format check passes: `npx prettier --check src/`
- [ ] 1.4 Schema unit test passes: `npm test`

#### Manual

- [ ] 1.5 Mismatched passwords show the Polish error and block submission
- [ ] 1.6 Correcting the confirm field clears the error live
- [ ] 1.7 Matching valid registration submits and navigates to `/`
- [ ] 1.8 `/auth/register` request body contains only `email` + `password`

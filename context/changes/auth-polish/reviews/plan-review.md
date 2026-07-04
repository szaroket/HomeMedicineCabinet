<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Auth Polish — Confirm-Password Field

- **Plan**: context/changes/auth-polish/plan.md
- **Mode**: Deep
- **Date**: 2026-07-04
- **Verdict**: REVISE
- **Findings**: 0 critical, 1 warning, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | WARNING |
| Plan Completeness | WARNING |

## Grounding

5/5 paths ✓ (`auth-schemas.ts`, `auth-api.ts`, `auth-queries.ts`, `register-form.tsx`, backend `schemas.py`), symbols ✓ (`registerSchema` / `RegisterValues` confirmed; blast-radius sweep on `RegisterValues` finds exactly 3 consumers, all named in the plan), brief↔plan ✓. `docs/reference/contract-surfaces.md` absent → contract-surface check skipped. Progress↔Phase mechanical contract holds (one `## Progress`, phase heading matches, 4 automated + 4 manual criteria map 1:1 to `1.1–1.8`).

## Findings

### F1 — "Structural guarantee" against payload leak is overstated and has no automated guard

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Implementation Approach + Phase 1 Contracts #2/#3; brief "Payload safety"
- **Detail**: The plan's headline safety claim is that narrowing `register(data: RegisterCredentials)` means TypeScript "guarantees `confirmPassword` never reaches the network" / is "structurally excluded." That is not how TS structural typing works. In `onSubmit` the form value is `RegisterFormValues` (`{email, password, confirmPassword}`). Passing that variable to a param typed `RegisterCredentials` compiles with NO error — excess-property checks fire only on fresh object literals, not on variables. At runtime `JSON.stringify(values)` (`auth-api.ts:22`) serializes `confirmPassword` anyway. So the type narrowing does NOT prevent the leak. The only thing that actually prevents it is the explicit `mutate({ email, password })` reconstruction in Contract #3 — and that single line has no automated coverage (RTL excluded; the schema unit test #4 doesn't exercise the form submit path). Leak prevention rests entirely on manual network-tab inspection (step 1.8). If an implementer trusts the (false) type guarantee and writes `mutate(values)`, `confirmPassword` leaks and nothing — types, lint, or tests — catches it.
- **Fix A ⭐ Recommended**: Make the strip structural via zod, and guard it. In `onSubmit` call `mutate(registerSchema.parse(values))` (the credentials schema) — zod drops unknown keys, so `confirmPassword` is provably stripped — and add a small automated assertion that the submitted body has no `confirmPassword` key.
  - Strength: Turns the claimed guarantee into a real runtime one; the regression is caught by a test, not eyeballs.
  - Tradeoff: Slightly more than the planned "destructure + manual check"; needs a test seam for the form or a body assertion.
  - Confidence: HIGH — zod strips unknown keys by default; existing `auth-api.test` already asserts on the request body.
  - Blind spot: Whether you want the guard at the form or api layer.
- **Fix B**: Keep manual destructure, but correct the rationale. Reword the plan/brief to say the leak is prevented by the explicit `{email, password}` reconstruction (not by the type), and keep 1.8 as the (manual-only) guard.
  - Strength: Zero code change beyond what's planned.
  - Tradeoff: The one line that matters stays untested; a future edit to `mutate(values)` silently reintroduces the leak.
  - Confidence: HIGH — accurate, but leaves a manual-only safety net.
  - Blind spot: None significant.
- **Decision**: PENDING

### F2 — Credentials-type naming is left ambiguous between contracts

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 1 Contracts #1 and #2
- **Detail**: Contract #1 says the existing `registerSchema` / `RegisterValues` names "may be reused for the credentials pair." Contract #2 then hardcodes the API type as `RegisterCredentials`. If the implementer takes the reuse option, `RegisterCredentials` never exists and Contract #2's instruction dangles; if they mint `RegisterCredentials`, Contract #1's reuse note is dead. Harmless but forces a guess.
- **Fix**: Pin one naming. Simplest: keep `registerSchema`/`RegisterValues` as the credentials pair and name the extended one `registerFormSchema`/`RegisterFormValues`; update Contract #2 to reference `RegisterValues`, not `RegisterCredentials`.
- **Decision**: PENDING

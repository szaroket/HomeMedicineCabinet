<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Playwright Critical-Path E2E Bootstrap

- **Plan**: context/changes/critical-path-e2e/plan.md
- **Mode**: Deep
- **Date**: 2026-07-01
- **Verdict**: REVISE → SOUND (all 6 findings fixed during triage 2026-07-01)
- **Findings**: 1 critical, 2 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | FAIL |
| Plan Completeness | WARNING |

## Grounding
8/8 paths ✓ (package.json, eslint.config.js, tsconfig.json, no playwright.config/e2e as expected-new, health router, users/models, cabinet/models), 4/4 symbols ✓ (auth_token key, register→"/" auto-login via setSession, user_preferences FK→users.id, registerSchema min-8), brief↔plan ✓.

## Findings

### F1 — Auto-booted `uv run uvicorn` backend hits the L-001 TLS abort

- **Severity**: ❌ CRITICAL
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Phase 1 — webServer array; all `npx playwright test` verifications
- **Detail**: The plan applies lessons.md L-001 ("run TLS-DB commands from native PowerShell, not the Bash tool") only to the Phase 4 *manual* teardown query. But the Phase 1 `webServer` array auto-boots the backend via `uv run uvicorn` — the exact uv-CPython process L-001 says aborts with `OPENSSL_Uplink: no OPENSSL_Applink` the moment it opens a TLS connection to Supabase (fires on the first register/login/medicines request, Phase 2 setup onward). L-001's root cause is environment-driven (MSYS cert-path resolution inherited by child processes), so a uvicorn spawned by a `npx playwright test` launched from the agent's Bash tool inherits the broken env. Every DB-touching automated verification (2.1, 3.1, 4.1) then errors out looking like a Playwright/webServer bug rather than the known L-001 trap.
- **Fix ⭐**: Add an explicit execution constraint to the plan — the whole suite must run from native PowerShell (never the Bash tool), OR pre-start the backend in PowerShell and let `reuseExistingServer: !process.env.CI` reuse it so Playwright never spawns uv itself. State this next to the Phase 1 webServer block and in every `cd frontend && npx playwright test` success criterion, echoing L-001.
  - Strength: Turns a silent, confusing abort into a documented one-line workflow rule; `reuseExistingServer` is already in the config so the pre-start path needs no new code.
  - Tradeoff: Local dev must remember to launch from PowerShell; CI (Linux) is unaffected — Windows-dev-only friction.
  - Confidence: MED — L-001 is a confirmed standing rule; exact reproduction through the Node→uv spawn chain is inferred, not yet run.
  - Blind spot: Whether Playwright's webServer child actually inherits the MSYS SSL_CERT_FILE env — worth a 1-min spike before Phase 2.
- **Decision**: FIXED (reframed) — During triage the mechanism was empirically verified: reproducing the app's startup `init_db()` (`SELECT 1` over TLS) from the **agent's** Bash tool aborts with `OPENSSL_Uplink: no OPENSSL_Applink`, but the **user's** own Git Bash runs `uv run uvicorn` (which opens the same TLS connection at boot) cleanly. So the finding's framing was corrected: it is NOT human "Windows-dev-only friction" — it is an agent-execution constraint. Plan updated with an "Execution constraint (L-001, agent-only)" callout by the Phase 1 webServer block, stating the agent must hand every `npx playwright test` run (DB-touching from Phase 2 onward) to the user / native PowerShell, applying to all four phases.

### F2 — Teardown FK chain omits `user_preferences` → delete will fail

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 4 §1 — teardown script Intent
- **Detail**: The teardown deletes "cabinet entries before the user row (FK-safe order)" but registration provisions TWO child rows per user, not one: `auth/crud.py:37-43` inserts into `users` AND `user_preferences` (`user_preferences.user_id` FK→`users.id`, unique, one per user — `users/models.py:26-30`). Deleting the `users` row while a `user_preferences` row still references it raises a FK violation, so Phase 4's own success criterion 4.1 ("teardown runs without error") fails on the first real run.
- **Fix**: Delete in order cabinet_entries → user_preferences → users (all filtered by the resolved test user_id). Note the Supabase-managed `auth.users` account is separate and intentionally left (already flagged as the "accumulation" follow-up).
- **Decision**: FIXED — Verified `auth/crud.py:36,41` inserts both `users` and `user_preferences`. Phase 4 §1 teardown Intent updated to delete in FK-safe order cabinet_entries → user_preferences → users, with the FK rationale spelled out.

### F3 — Add-medication depends on a populated registry; "unique medicine per run" rationale is off

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Plan Completeness
- **Location**: Phase 3 §1 — seed spec Intent/Contract
- **Detail**: The autocomplete (`GET /medicines/products?search=`) only returns rows present in `medication_registry`. The test cannot invent a "unique medicine per run" — it must type a product name known to exist in the catalog (imported by the earlier `registry-import` change against the live Supabase). The plan names no concrete product and states no registry-data prerequisite, so the implementer has nothing to type. The stated rationale ("unique medicine/expiry to avoid the uq_cabinet_entries_user_med_expiry collision") is also moot: each run registers a fresh user, so user_id differs every run and that unique constraint can never collide — the only per-run uniqueness needed is the email (already covered).
- **Fix**: Pick a known-present catalog product name and hard-reference it in the spec; document "registry must be seeded (via registry-import)" as a prerequisite. Drop the uq-collision rationale — derive uniqueness from a fresh user + timestamp email, not the medicine.
- **Decision**: FIXED — Verified: `search_products` queries the registry `search_vector`; uq constraint is `(user_id, medication_registry_id, expiry_date)`. Phase 3 §1 updated with a "Registry-data prerequisite" block (hard-reference a `CATALOG_PRODUCT_NAME` constant confirmed present via PowerShell query; document registry-seeded prerequisite) and a "Per-run uniqueness" block (uniqueness from fresh user; uq rationale dropped). Contract line reworded to match.

### F4 — Playwright/Node won't auto-load `.env.local`; pg needs SSL config

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 4 §3 — env var wiring; §1 — pg connection
- **Detail**: "read via dotenv or Playwright's own env loading" — Playwright has no built-in .env loading (that's Vite's job for `.env.local`). The config must `import 'dotenv/config'` explicitly, so `dotenv` is an additional devDependency the Contract doesn't list. Separately, Supabase requires SSL for the Postgres connection; the Node `pg` client needs explicit `ssl` config, which the plan doesn't mention.
- **Fix**: Add `dotenv` to the devDependency list, `import 'dotenv/config'` at the top of `playwright.config.ts`, and specify the `pg` SSL option for the Supabase connection.
- **Decision**: FIXED — Phase 4 §1 Contract now lists `dotenv` as a devDependency and requires an explicit `pg` `ssl` option for Supabase's mandatory TLS; §3 Contract specifies `import 'dotenv/config'` in `playwright.config.ts` since Playwright does not auto-load `.env.local`.

### F5 — `playwright test --list` does not start webServers

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 1 — Overview & Manual Verification 1.5
- **Detail**: Phase 1 expects `npx playwright test --list` to "visibly start both the backend and frontend." In current Playwright, `--list` only collects tests and does NOT boot the `webServer` array — servers start when tests actually run. So 1.5 as written can't pass and isn't a real boot check.
- **Fix**: Verify dual-server boot with an actual run (e.g. the Phase 2 `--project=setup` run, or a trivial smoke test), not `--list`. Keep `--list` only as the "config parses / 0 tests" check (1.2).
- **Decision**: FIXED — Phase 1 Manual Verification 1.5 (body + Progress) reworded to confirm dual-server boot via an actual run, noting `--list` does not start webServers; `--list` retained only as the config-parse check (1.2).

### F6 — Phase 4 Progress count mismatch (minor)

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 4 Success Criteria vs. Progress
- **Detail**: Phase 4 lists four `#### Automated Verification:` bullets, but one ("direct query confirms no rows — verified manually, not scriptable") is represented under Manual (4.4) in Progress, so the Automated subsection has 3 items (4.1–4.3). Not malformed enough to break /10x-implement parsing, but it violates the strict 1:1 bullet↔checkbox contract.
- **Fix**: Move that bullet under `#### Manual Verification:` in the Phase 4 body so it lines up with Progress 4.4.
- **Decision**: FIXED — The misfiled Automated bullet ("direct query confirms no rows — verified manually") duplicated the existing Manual "post-run query confirms zero rows" bullet (= Progress 4.4), so it was removed rather than moved. Phase 4 body now has exactly 3 Automated (4.1-4.3) and 2 Manual (4.4-4.5) bullets, restoring the strict 1:1 bullet↔checkbox contract.

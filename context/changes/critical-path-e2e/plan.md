# Playwright Critical-Path E2E Bootstrap Implementation Plan

## Overview

Bootstrap Playwright for `frontend/` and lock the single most critical user
journey — **login → add medication → see it in cabinet** (Risk #2 in
`context/foundation/test-plan.md`, plus Risk #1 non-empty-response coverage as
a side effect) — with a CI-reusable configuration. This is test-plan.md §3
Phase 2.

## Current State Analysis

- No Playwright dependency, config, or `frontend/e2e/` directory exists yet
  (confirmed in `context/changes/critical-path-e2e/research.md`).
- `AGENTS.md:38` already documents the expected shape
  (`e2e/ — Playwright specs (*.spec.ts) + auth.setup.ts`) and `AGENTS.md:121`
  names the golden path: login → add medication → verify cabinet entry.
- Frontend dev server: `npm run dev` (Vite, port 5173, reads
  `VITE_API_URL` — defaults to `http://localhost:8000` per
  `frontend/src/lib/api-client.ts:4`).
- Backend dev server: `uv run uvicorn app.main:app --reload` per
  `AGENTS.md:93`; for a non-interactive test run drop `--reload` and pin
  host/port explicitly. Health endpoint: `GET /api/v1/health/` →
  `{"status": "healthy"}` (`backend/app/api/v1/health/router.py:3-8`) — usable
  as Playwright's `webServer` readiness probe.
- Backend `Settings` (`backend/app/core/config.py:8-53`) requires
  `database_url`, `supabase_url`, `supabase_anon_key` (no defaults) and loads
  them from `backend/.env` automatically (`env_file=".env"`) — so a
  `webServer` entry with `cwd: './backend'` inherits them without extra wiring.
  `auth_cookie_secure` defaults `True`; must be overridden to `False` for
  localhost HTTP e2e runs (cookie won't be set otherwise).
- `frontend/tsconfig.json` is project-references-only (`files: []`,
  references `tsconfig.app.json` + `tsconfig.node.json`) and `npm run build`
  runs `tsc -b` — a new `frontend/e2e/` dir needs its own tsconfig reference so
  Playwright globals (`test`, `expect`) don't break the build, and
  `eslint.config.js` lints all `**/*.{ts,tsx}` globally, so e2e specs need a
  Playwright-aware ESLint override to avoid false `no-undef`-style noise.
- No DELETE endpoint exists anywhere in `backend/app/api/v1/cabinet/router.py`
  (only GET, POST, two PATCH) — test-created users/entries cannot be removed
  through the public API.

### Key Discoveries:

- `backend/app/api/v1/health/router.py:3-8` — health endpoint usable as
  Playwright `webServer` readiness URL.
- `frontend/src/features/auth/store.ts:13` — session token key
  (`localStorage["auth_token"]`), what `storageState` needs to capture.
- `frontend/src/features/cabinet/components/cabinet-list.tsx:17-181` —
  `EntryRow`, chevron toggle `aria-label="Pokaż szczegóły"` /
  `aria-expanded`, and the `<dl>` detail fields (Dawka, Postać, Substancja
  czynna, Droga podania) for the expand-detail assertion.
- Cabinet router has no DELETE — cleanup must happen out-of-band (direct DB),
  not through the API.

## Desired End State

`npx playwright test` (from `frontend/`) starts both the backend and frontend
dev servers automatically, runs one spec —
`frontend/e2e/seed.spec.ts` — that logs in (via a pre-saved `storageState`
from `auth.setup.ts`), adds a medication, confirms it appears in the cabinet,
confirms it survives a page reload, and confirms the expanded row shows the
correct detail fields. A teardown step deletes the shared test account's
cabinet entries directly from the database afterward (the account itself
persists — see Phase 4). The same command works unchanged in CI once
test-plan.md Phase 4 wires it into `ci-cd.yml` (out of scope here).

**Verification**: `cd frontend && npx playwright test` exits 0 with 1 passed
test, and a post-run query against the test database shows no leftover
`cabinet_entries` rows for the shared test account (`e2e-hmc@example.com`),
while that account row itself remains.

## What We're NOT Doing

- Journey B (display/filter cabinet data) — deferred per research's
  follow-up decision; no `DELETE` endpoint means scoping to one journey
  minimizes data accumulation until cleanup infrastructure matures further.
- Wiring the e2e job into `.github/workflows/ci-cd.yml` — that's test-plan.md
  §3 Phase 4 ("Quality-gates wiring"); this phase only makes the suite
  CI-*compatible* (webServer config, env handling, teardown script), it does
  not touch the CI workflow file.
- Provisioning a dedicated test Supabase project — tests run against the
  existing project referenced by `backend/.env` / `frontend/.env.local`, with
  isolation coming from per-run unique cabinet-entry data (timestamped
  `expiry_date`) plus post-run teardown, not project separation. Flagged as a
  follow-up, not solved here.
- Adding a test-only teardown/seed API endpoint on the backend — cleanup goes
  through a direct-DB script instead, keeping this phase frontend-only in
  terms of backend surface area.
- Cross-browser coverage (Firefox, WebKit) — Chromium only; Risk #2 is about
  the frontend↔API data seam, not browser-engine rendering differences.
- Frontend unit/Vitest bootstrap — that's test-plan.md §3 Phase 3, separate
  change.

## Implementation Approach

Four phases, each independently verifiable: (1) get Playwright installed,
configured, and able to boot both servers and pass a `--list` dry run; (2)
add the auth `storageState` setup project; (3) write the one real spec
(`seed.spec.ts`) covering the full Journey A flow, which per the `/10x-e2e`
skill's seed-test convention doubles as this project's first quality-lever
exemplar; (4) add the direct-DB teardown script and wire it as Playwright's
global teardown so repeated local/CI runs don't accumulate data unboundedly.

## Phase 1: Playwright Bootstrap & Dual-Server Config

### Overview

Install Playwright, scaffold `frontend/e2e/`, and get `playwright.config.ts`
booting both the backend and frontend dev servers before any test runs —
locally and (once Phase 4 of test-plan.md wires it) in CI, with no separate
orchestration script to maintain.

### Changes Required:

#### 1. Playwright dependency + npm scripts

**File**: `frontend/package.json`

**Intent**: Add `@playwright/test` as a devDependency and an `e2e` script so
`npm run e2e` runs the suite the same way locally and in CI.

**Contract**: New devDependency `@playwright/test`; new script
`"e2e": "playwright test"`.

#### 2. Playwright config with dual `webServer`

**File**: `frontend/playwright.config.ts` (new)

**Intent**: Define `testDir: './e2e'`, a single `chromium` project, and a
`webServer` **array** of two entries so one `npx playwright test` invocation
boots backend then frontend and waits on each before proceeding — matching
the CI-reuse requirement decided in planning.

**Contract**:
```ts
webServer: [
  {
    command: 'uv run uvicorn app.main:app --host 0.0.0.0 --port 8000',
    cwd: '../backend',
    url: 'http://localhost:8000/api/v1/health/',
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    env: { AUTH_COOKIE_SECURE: 'False' },
  },
  {
    command: 'npm run dev',
    cwd: '.',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
],
use: { baseURL: 'http://localhost:5173' },
```
Entries start in array order and each `url` must respond before the next
starts / tests run. `AUTH_COOKIE_SECURE: 'False'` overrides the backend's
secure-cookie default so the refresh-token cookie is set over local HTTP.

> **Execution constraint (L-001, agent-only):** the backend booted here opens a
> TLS connection to Supabase at startup (`lifespan → init_db()` runs `SELECT 1`),
> so `npx playwright test` is a DB-touching command from Phase 2 onward. Run by a
> **human developer** it works normally (a normal Windows terminal / Git Bash
> resolves OpenSSL's cert path fine). Run by the **AI agent from its Git Bash
> tool** it hard-aborts with `OPENSSL_Uplink: no OPENSSL_Applink` the moment the
> webServer-spawned uvicorn opens that connection (confirmed — this is the exact
> L-001 trap, and it is an environment quirk of the agent's MSYS shell, not a code
> defect). So the agent must **hand every `npx playwright test` run to the user /
> native PowerShell** rather than run it from its Bash tool — do **not** "fix" it
> by weakening SSL. This applies to all `npx playwright test` success criteria in
> Phases 1-4 below, not just the Phase 4 teardown.

#### 3. tsconfig + eslint accommodation

**File**: `frontend/tsconfig.json`, new `frontend/e2e/tsconfig.json` (or a
new reference), `frontend/eslint.config.js`

**Intent**: Let `tsc -b` include `frontend/e2e/**` without breaking the
existing app/node project-reference split, and let ESLint recognize
Playwright's `test`/`expect` globals without `no-undef` noise.

**Contract**: Add a third project reference (e.g. `tsconfig.e2e.json`,
scoped to `e2e/**/*.ts`) to `frontend/tsconfig.json`'s `references` array;
add an `eslint-plugin-playwright` flat-config block scoped to
`e2e/**/*.spec.ts` (or equivalent globals override) in `eslint.config.js`.

#### 4. `.gitignore` for Playwright artifacts

**File**: `frontend/.gitignore`

**Intent**: Exclude Playwright's local run artifacts from version control.

**Contract**: Add `playwright-report/`, `test-results/`, and
`.playwright/` (storage-state output dir, see Phase 2) entries.

### Success Criteria:

#### Automated Verification:

- Playwright installs cleanly: `cd frontend && npm install`
- Config loads and lists zero tests without error: `cd frontend && npx playwright test --list`
- Type checking still passes with the new e2e project reference: `cd frontend && npm run build`
- Linting passes on the (empty) e2e dir setup: `cd frontend && npm run lint`

#### Manual Verification:

- Dual-server boot is confirmed by an **actual run** — not `--list`, which
  only collects tests and does NOT start the `webServer` array. Use the Phase 2
  `--project=setup` run (or a trivial smoke test) and confirm it visibly starts
  both the backend (uvicorn log lines) and frontend (Vite log lines) and does
  not hang past the configured timeout. (`--list` stays as the config-parses /
  0-tests check in 1.2.)
- Hitting `http://localhost:8000/api/v1/health/` and
  `http://localhost:5173` manually in a browser while the command is running
  confirms both are reachable.

---

## Phase 2: Auth Setup via `storageState`

### Overview

Add `auth.setup.ts`, a Playwright setup project that registers a brand-new
throwaway user through the real UI once per run and saves the resulting
session as reusable `storageState`, so the actual test doesn't re-login.

### Changes Required:

#### 1. Auth setup project

**File**: `frontend/e2e/auth.setup.ts` (new)

**Intent**: Navigate to `/register`, fill the form with a
timestamp-suffixed email (e.g. `e2e-<timestamp>@example.com`) matching the
naming convention Phase 4's teardown script will filter on, submit, wait for
the post-register redirect to a protected route, then save
`page.context().storageState()` to a fixed path.

**Contract**: Writes storage state to
`frontend/e2e/.auth/user.json` (gitignored per Phase 1); registered as a
Playwright `setup` project in `playwright.config.ts`'s `projects` array,
with the `chromium` project declaring `dependencies: ['setup']` and
`use: { storageState: 'e2e/.auth/user.json' }`.

#### 2. Config wiring for the setup project

**File**: `frontend/playwright.config.ts`

**Intent**: Register the two-project split (`setup` → `chromium`) so
`npx playwright test` runs `auth.setup.ts` first automatically.

**Contract**: `projects: [{ name: 'setup', testMatch: /auth\.setup\.ts/ }, { name: 'chromium', use: { ...devices['Desktop Chrome'], storageState: 'e2e/.auth/user.json' }, dependencies: ['setup'] }]`.

### Success Criteria:

#### Automated Verification:

- Setup project runs standalone and produces the storage-state file: `cd frontend && npx playwright test --project=setup`
- Type checking passes: `cd frontend && npm run build`
- Linting passes: `cd frontend && npm run lint`

#### Manual Verification:

- After running the setup project, `frontend/e2e/.auth/user.json` exists and
  contains an `auth_token`-shaped localStorage entry.
- Manually registering the same way in a browser confirms the redirect
  target and form field names match what `auth.setup.ts` expects.

---

## Phase 3: Journey A Seed Test

### Overview

Write `frontend/e2e/seed.spec.ts` — the one spec this phase delivers,
covering login (via the Phase 2 storage state) → add medication → see it in
cabinet → survives page reload → expand-row detail. Per the `/10x-e2e`
skill's seed-test convention, this file is both the actual Risk #2 coverage
and this project's first quality-lever exemplar for future e2e phases
(Journey B, Phase 3 of test-plan.md, etc.) to model against.

### Changes Required:

#### 1. Seed/journey spec

**File**: `frontend/e2e/seed.spec.ts` (new)

**Intent**: One independently-runnable test, using the `chromium` project's
pre-authenticated `storageState`, that: navigates to `/cabinet/add`; fills
the add-medication form (product autocomplete, variant select,
`package_count`, `expiry_date`); submits; asserts the new entry's name is
visible in the cabinet list; reloads the page and re-asserts visibility
(persistence); expands the row via the `aria-label="Pokaż szczegóły"` toggle
and asserts the `<dl>` detail fields (strength, form, active ingredient, route
of administration) match what was submitted.

**Registry-data prerequisite**: the product autocomplete
(`GET /medicines/products?search=`) queries the `medication_registry`
`search_vector` and only returns rows already imported into the catalog (by
the earlier `registry-import` change, against the live Supabase project). The
test therefore **cannot invent a product name** — it must type a concrete name
known to exist in the seeded catalog. Hard-reference one such product in the
spec (a constant, e.g. `CATALOG_PRODUCT_NAME`), and confirm it is present
before writing the assertions by querying the registry from native PowerShell
(per L-001, not the Bash tool). Document "registry must be seeded via
registry-import" as an explicit run prerequisite.

**Per-run uniqueness**: the setup project logs in a single fixed shared
account (`e2e-hmc@example.com`) rather than registering a fresh user (Phase 2
pivot, see `reviews/impl-review-phase-2.md` F1), so `user_id` is **constant**
across runs. Uniqueness therefore must come from the `expiry_date` (or
`package_count`), not the user. The `uq_cabinet_entries_user_med_expiry`
constraint is `(user_id, medication_registry_id, expiry_date)`; with a fixed
`user_id`, two runs that submit the same medicine + expiry **would collide**.
Derive a per-run `expiry_date` (e.g. a base date offset by a timestamp-derived
number of days) so the tuple is unique every run while the medicine name stays
a fixed known-catalog constant. Phase 4 teardown still removes the run's
`cabinet_entries` as a second line of defense.

**Contract**: `test.describe` title binds to Risk #2
(`context/foundation/test-plan.md`); all locators are
`getByRole`/`getByLabel`/`getByText` (no CSS/XPath/test-id, per the hard
rule and the existing form's real `<label>`s); waits use
`toBeVisible()`/`waitForResponse()`, never `waitForTimeout()`; per-run
isolation comes from a timestamp-derived `expiry_date` (the shared login means
`user_id` is constant), so the medicine name stays a fixed known-catalog
constant while the expiry varies per run to satisfy
`uq_cabinet_entries_user_med_expiry`.

#### 2. E2E rules reference (skill setup, if missing)

**File**: `.claude/skills/10x-e2e/references/e2e-quality-rules.md` equivalent
project-local copy, if the skill's SETUP step requires one not yet present

**Intent**: Confirm (during implementation, not planning) whether the
`/10x-e2e` skill already ships its rules reference globally or expects a
per-project copy; if per-project, this is where it lands. No action needed
in this plan if the skill resolves its own reference file globally — verify
at implementation time via the skill's SETUP step output.

### Success Criteria:

#### Automated Verification:

- Full suite passes end-to-end: `cd frontend && npx playwright test`
- Type checking passes: `cd frontend && npm run build`
- Linting passes: `cd frontend && npm run lint`
- Spec reviewed against the 5 anti-patterns in
  `.claude/skills/10x-e2e/references/e2e-anti-patterns.md` (no CSS
  selectors, no `waitForTimeout`, no inter-test dependency, no missing
  cleanup rationale, name ties to Risk #2)

#### Manual Verification:

- Watching a headed run (`npx playwright test --headed`) confirms the
  browser visibly logs in, adds the medication, sees it listed, reloads,
  and expands the row with correct details.
- Re-running the suite twice in a row (simulating CI re-runs) both pass
  without manual DB cleanup in between, confirming per-run uniqueness holds.

---

## Phase 4: Direct-DB Teardown Script

### Overview

Add a script that deletes the shared test account's **cabinet entries**
directly from Postgres after a run — **not** the user account itself — without
adding any new backend API endpoint. Because Phase 2 pivoted to a single fixed
confirmed login (`e2e-hmc@example.com`) that email confirmation makes
un-recreatable, the account must survive across runs; only the per-run
`cabinet_entries` it accumulates get cleaned up.

### Changes Required:

#### 1. Teardown script

**File**: `frontend/e2e/teardown/cleanup-test-users.ts` (new)

**Intent**: Connect directly to the database using the same connection
string the backend already uses (`DATABASE_URL`, converted to a plain
`postgres://` URL if the backend's asyncpg-prefixed form doesn't parse for
the Node `pg` client), resolve the shared test account's `user_id` by its
**exact** fixed email (`e2e-hmc@example.com`, the account Phase 2's
`auth.setup.ts` logs in), and delete **only** that user's `cabinet_entries`
rows. **Do NOT delete the `users`, `user_preferences`, or Supabase
`auth.users` rows** — the shared account is confirmed once and cannot be
re-registered (email confirmation), so deleting it breaks every subsequent
run. Match by exact email, never the `e2e-*` prefix, so the account row itself
is never a deletion target. This is deliberately narrower than a per-run-user
teardown: with a shared account there is no throwaway user to remove, only its
accumulated cabinet entries.

**Contract**: Exported as a Playwright `globalTeardown` function; registered
via `globalTeardown: './e2e/teardown/cleanup-test-users.ts'` in
`playwright.config.ts`. New devDependencies: `pg` (+ `@types/pg`) and `dotenv`
(Playwright has no built-in `.env` loading — that's Vite's job for
`.env.local`; the config must `import 'dotenv/config'` explicitly, see §3). The
Node `pg` client must be given an explicit `ssl` option (e.g.
`ssl: { rejectUnauthorized: false }` or the Supabase CA) because Supabase
requires TLS for Postgres and `pg` does not enable SSL by default.

#### 2. Config wiring

**File**: `frontend/playwright.config.ts`

**Intent**: Wire the new teardown as the config's `globalTeardown`.

**Contract**: `globalTeardown: require.resolve('./e2e/teardown/cleanup-test-users.ts')`.

#### 3. Env var for teardown DB access

**File**: `frontend/.env.local`, `frontend/.env.structure` (if present)

**Intent**: Surface the database connection string to the frontend test
runner (Playwright runs Node, not Vite, so this is read via `process.env`
directly, not `import.meta.env` — no `VITE_` prefix needed/wanted, since
this must never ship to the browser bundle).

**Contract**: New env var, e.g. `E2E_DATABASE_URL`, read only by
`cleanup-test-users.ts` — never referenced from application source under
`frontend/src/`. Load it by adding `import 'dotenv/config'` at the top of
`playwright.config.ts` (Playwright does **not** auto-load `.env`/`.env.local`;
only Vite does, and only for the app bundle) so `process.env.E2E_DATABASE_URL`
is populated before the teardown runs.

### Success Criteria:

#### Automated Verification:

- Teardown runs without error after a full suite pass: `cd frontend && npx playwright test`
- Type checking passes: `cd frontend && npm run build`
- Linting passes: `cd frontend && npm run lint`

#### Manual Verification:

- After a full local run, manually querying the test database (via
  `psql`/Supabase dashboard, from native PowerShell per `lessons.md` L-001,
  not the Bash tool) for the shared account's `user_id` confirms zero rows in
  the cabinet-entries table **and** that the `users` / `user_preferences` rows
  for `e2e-hmc@example.com` are still present (teardown must not delete the
  account).
- Running the suite twice consecutively confirms no
  `uq_cabinet_entries_user_med_expiry` collisions from leftover data between
  runs (uniqueness now rides on the per-run `expiry_date`, not a fresh user).

---

## Testing Strategy

### Unit Tests:

- None — this phase adds only e2e infrastructure and one e2e spec; no new
  unit-testable logic is introduced.

### Integration Tests:

- Not applicable — the "integration" layer for Risk #2 is the e2e journey
  itself (per test-plan.md's Risk Response Guidance table: "e2e (journeys) +
  thin unit on the API-calling layer" — the latter is test-plan.md Phase 3).

### Manual Testing Steps:

1. Run `cd frontend && npx playwright test --headed` and watch the full
   journey execute against a fresh browser context.
2. Manually break one link in the chain (e.g. temporarily rename the "Dodaj
   do apteczki" submit button text) and confirm the test fails with a clear
   locator-not-found error, not a false pass.
3. Query the test database after a run to confirm the teardown script left
   no orphaned rows.

## Performance Considerations

`webServer` startup (uvicorn + Vite) adds ~5-15s to every local/CI run before
the first test executes; `reuseExistingServer: !process.env.CI` avoids this
cost on repeated local runs by reusing an already-running dev server.

## Migration Notes

Not applicable — no data migration; the teardown script only deletes rows it
identifies as e2e-created via the `e2e-*` email pattern, never touching real
user data.

## References

- Related research: `context/changes/critical-path-e2e/research.md`
- Test-plan phase definition: `context/foundation/test-plan.md` §3 Phase 2,
  §6.3 (cookbook — currently "TBD, see §3 Phase 2")
- Project convention: `AGENTS.md:38,93-98,121`
- Skill workflow this plan will be driven by: `.claude/skills/10x-e2e/SKILL.md`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Playwright Bootstrap & Dual-Server Config

#### Automated

- [x] 1.1 Playwright installs cleanly: `cd frontend && npm install` — fffc3d6
- [x] 1.2 Config loads and lists zero tests without error: `cd frontend && npx playwright test --list` — fffc3d6
- [x] 1.3 Type checking still passes with the new e2e project reference: `cd frontend && npm run build` — fffc3d6
- [x] 1.4 Linting passes on the (empty) e2e dir setup: `cd frontend && npm run lint` — fffc3d6

#### Manual

- [x] 1.5 An actual run (Phase 2 `--project=setup` or a smoke test) visibly starts both backend and frontend and does not hang (`--list` does not boot webServers)
- [x] 1.6 Both health/dev URLs manually reachable while the command runs

### Phase 2: Auth Setup via `storageState`

#### Automated

- [x] 2.1 Setup project runs standalone and produces the storage-state file: `cd frontend && npx playwright test --project=setup` — 4c82fbd
- [x] 2.2 Type checking passes: `cd frontend && npm run build` — 4c82fbd
- [x] 2.3 Linting passes: `cd frontend && npm run lint` — 4c82fbd

#### Manual

- [x] 2.4 `frontend/e2e/.auth/user.json` exists with an `auth_token`-shaped entry
- [x] 2.5 Manual UI registration confirms redirect target and form field names match `auth.setup.ts` (switched to login — the passing setup confirms the login form fields "Adres e-mail"/"Hasło", button "Zaloguj się", and the `/` redirect all match)

### Phase 3: Journey A Seed Test

#### Automated

- [x] 3.1 Full suite passes end-to-end: `cd frontend && npx playwright test`
- [x] 3.2 Type checking passes: `cd frontend && npm run build`
- [x] 3.3 Linting passes: `cd frontend && npm run lint`
- [x] 3.4 Spec reviewed against the 5 anti-patterns in `e2e-anti-patterns.md`

#### Manual

- [x] 3.5 Headed run visibly completes the full journey correctly
- [x] 3.6 Two consecutive runs both pass without manual DB cleanup in between

### Phase 4: Direct-DB Teardown Script

#### Automated

- [ ] 4.1 Teardown runs without error after a full suite pass: `cd frontend && npx playwright test`
- [ ] 4.2 Type checking passes: `cd frontend && npm run build`
- [ ] 4.3 Linting passes: `cd frontend && npm run lint`

#### Manual

- [ ] 4.4 Post-run DB query confirms zero rows remain for the test user (cabinet entries + auth user)
- [ ] 4.5 Two consecutive runs show no unique-constraint collisions from leftover data

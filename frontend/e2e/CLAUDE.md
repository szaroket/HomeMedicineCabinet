# E2E Testing Rules

The quality lever for every Playwright spec in this directory. A generated test
inherits whatever the seed (`seed.spec.ts`) and these rules encode — *what you
show is what you get*. Read this before writing or modifying an e2e spec.

- Use `getByRole`, `getByLabel`, `getByText` as primary locators (also
  `getByPlaceholder` for user-facing placeholder text). Fall back to
  `getByTestId` **only when accessibility attributes are genuinely ambiguous** —
  not when they are merely missing. If a field can't be located, the right fix is
  to make it accessible (associate its visible `<label>` via `htmlFor`/`id`), not
  to add a test-only hook.
- Never use CSS selectors, XPath, or DOM structure to locate elements.
- Each test must be independently runnable — no shared state between tests.
  Playwright runs specs in parallel, in random order.
- Never use `page.waitForTimeout()`. Wait for a concrete condition:
  `toBeVisible()`, `waitForURL()`, `waitForResponse()`.
- Assert the business outcome (the data the user sees), not implementation
  details. Control question for every assertion: *would this fail if the
  `context/foundation/test-plan.md` risk came true?* If not, it's decorative.
- Use unique per-run identifiers for test data to avoid collisions in re-runs and
  parallel runs. Prefer timestamp-derived values.
- Authenticate via `storageState` (the `setup` project writes
  `e2e/.auth/user.json`) — never log in through the UI inside an individual test.
- Name the test after the risk it protects
  (`test('added medication appears in the cabinet ... (Risk #2)', ...)`), never
  `test('test 1', ...)`.

## Real vs mocked

Internal boundaries (auth, routing, API, DB) stay **real** — that seam is exactly
where Risk #2 hides. Mock only expensive or non-deterministic *external* APIs at
the network layer. This suite currently mocks nothing.

## Cleanup

The cabinet API exposes no `DELETE` endpoint, so a spec cannot tear down its own
rows through the app. Cleanup is therefore handled out-of-band by the direct-DB
`globalTeardown` (see the plan's Phase 4), and per-run uniqueness (a
timestamp-derived `expiry_date`) keeps re-runs from colliding on
`uq_cabinet_entries_user_med_expiry`. State this rationale in any spec that
creates cabinet data.

## Running (L-001)

`npx playwright test` boots the backend, which opens a TLS connection to
Supabase — a DB-touching command. Per `context/foundation/lessons.md` L-001, run
it from **native PowerShell**, not the agent's Git Bash tool (which aborts with
`OPENSSL_Uplink: no OPENSSL_Applink`). Set `E2E_TEST_PASSWORD` (and optionally
`E2E_TEST_EMAIL`) first.

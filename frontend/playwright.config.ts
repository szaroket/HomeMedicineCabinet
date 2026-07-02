import { config as loadEnv } from 'dotenv'
import { defineConfig, devices } from '@playwright/test'

// Playwright (unlike Vite) does not auto-load env files, so E2E_TEST_PASSWORD
// (setup project) and E2E_DATABASE_URL (teardown) would be undefined unless
// exported in the shell. Load .env.local first, then .env, before the config is
// built. Already-exported shell vars still win — dotenv never overrides an
// existing process.env value.
loadEnv({ path: ['.env.local', '.env'] })

/**
 * Playwright configuration for the critical-path E2E suite.
 *
 * A single `npx playwright test` invocation boots the backend (FastAPI/uvicorn)
 * then the frontend (Vite) via the `webServer` array below, waiting on each
 * health/dev URL before tests run — so the same command works locally and in CI
 * (test-plan.md §3 Phase 2). `reuseExistingServer` skips the boot when a dev
 * server is already up locally, but always starts fresh in CI.
 *
 * See `context/changes/critical-path-e2e/plan.md`.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: 'html',
  // After the whole run, sweep the shared test account's accumulated cabinet
  // entries directly from Postgres (the cabinet API has no DELETE) — the account
  // row itself is preserved. See e2e/teardown/cleanup-test-users.ts and Phase 4.
  globalTeardown: './e2e/teardown/cleanup-test-users.ts',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  projects: [
    // Runs auth.setup.ts first: logs in the shared test account and saves the
    // session to e2e/.auth/user.json (see Phase 2 of the plan).
    { name: 'setup', testMatch: /auth\.setup\.ts/ },
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        // Reuse the session captured by the setup project — no UI login per test.
        storageState: 'e2e/.auth/user.json',
      },
      dependencies: ['setup'],
    },
  ],
  webServer: [
    {
      command: 'uv run uvicorn app.main:app --host 0.0.0.0 --port 8000',
      cwd: '../backend',
      url: 'http://localhost:8000/api/v1/health/',
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      // Override the backend's secure-cookie default so the refresh-token
      // cookie is set over local HTTP (backend Settings.auth_cookie_secure).
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
})

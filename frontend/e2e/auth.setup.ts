import { test as setup, expect } from "@playwright/test";

import { TEST_EMAIL } from "./test-account";

/**
 * Auth setup project — Phase 2 of context/changes/critical-path-e2e/plan.md.
 *
 * Logs in a pre-existing, already-confirmed test account through the real login
 * UI once per run and saves the resulting session (cookies + localStorage
 * `auth_token`) as reusable `storageState`, so the Risk #2 journey spec
 * (Phase 3) skips UI login and authenticates via this file instead.
 *
 * Why login (not register): the Supabase project has email confirmation on, so
 * `sign_up` returns no session and the backend rejects a fresh registration
 * (service.py:43). A confirmed test account authenticates deterministically.
 *
 * Credentials: the email defaults to the shared test account below; the
 * password is a secret and is read from the env (never committed — AGENTS.md).
 * Set it before running:
 *   PowerShell:  $env:E2E_TEST_PASSWORD = '...'
 * Optionally override the email with E2E_TEST_EMAIL.
 *
 * This is a quality-lever exemplar: role-based locators, wait-for-state (never
 * time), and an API-response assertion that fails fast with a real status.
 */

// Kept in sync with the `storageState` path in `playwright.config.ts`. The
// `.auth/` dir is gitignored (root `.gitignore`); Playwright creates it on write.
const STORAGE_STATE = "e2e/.auth/user.json";

// Read a required env var, failing fast and clearly if it is missing — kept out
// of the test body so it doesn't trip playwright/no-conditional-in-test and so
// the return type narrows to string.
function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `${name} is not set. Provide the test account's password via the ` +
        "environment (e.g. PowerShell: $env:E2E_TEST_PASSWORD = '...') before " +
        "running the e2e suite.",
    );
  }
  return value;
}

setup(
  "authenticate: log in with the test account and persist the session",
  async ({ page }) => {
    const password = requireEnv("E2E_TEST_PASSWORD");

    // Log in through the real UI (no API shortcut) so this drives the same
    // login → API → DB → localStorage-token seam the app uses in production.
    await page.goto("/login");
    await page.getByLabel("Adres e-mail").fill(TEST_EMAIL);
    await page.getByLabel("Hasło").fill(password);

    // Capture the login API response so a rejection fails here with a precise
    // status (401 = wrong test-account credentials / unconfirmed account) instead
    // of a blind 30s navigation timeout downstream.
    const loginResponse = page.waitForResponse(
      (res) =>
        res.url().includes("/auth/login") && res.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Zaloguj się" }).click();
    const response = await loginResponse;
    expect(
      response.status(),
      "POST /auth/login must return 200; a 401 usually means the E2E_TEST_EMAIL/" +
        "E2E_TEST_PASSWORD pair is wrong or the account is unconfirmed",
    ).toBe(200);

    // Successful login redirects to the protected dashboard ("/"). Assert a
    // protected-route element actually renders — proof the session took and we
    // were not bounced back to /login by ProtectedLayout.
    await page.waitForURL("/");
    await expect(
      page.getByRole("link", { name: "Moja apteczka" }),
    ).toBeVisible();

    // Persist cookies + localStorage (incl. the `auth_token`) for the chromium
    // project to reuse via `storageState`.
    await page.context().storageState({ path: STORAGE_STATE });
  },
);

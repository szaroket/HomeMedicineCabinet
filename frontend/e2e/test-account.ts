/**
 * The shared, pre-confirmed e2e test account — the single source of truth for its
 * email. `auth.setup.ts` logs in as this account and persists its session; the
 * direct-DB `globalTeardown` (teardown/cleanup-test-users.ts) sweeps only this
 * account's `cabinet_entries` afterward. Both import from here so the fallback
 * default lives in exactly one place: if the two drifted, setup would log into one
 * account while teardown swept another, silently leaving rows behind.
 *
 * Override the email with the `E2E_TEST_EMAIL` env var; the password is a separate
 * secret read from `E2E_TEST_PASSWORD` (never defaulted, never committed).
 */
export const TEST_EMAIL = process.env.E2E_TEST_EMAIL ?? "e2e-hmc@example.com";

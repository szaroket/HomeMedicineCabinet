import { test, expect } from "@playwright/test";

/**
 * welcome-landing.spec.ts — S-10 (context/changes/welcome-landing-page/plan.md).
 *
 * Protects the public front door and its authed/unauthed redirect boundary:
 * "/" is a public welcome page for unauthenticated visitors, and every public
 * page (`/`, `/login`, `/register`) redirects an already-authenticated visitor
 * to `/dashboard`.
 *
 * The chromium project sets `storageState` (an authenticated session) at the
 * project level, so tests here are split into two describe blocks by the auth
 * state they need: the unauthenticated block opts out with
 * `test.use({ storageState: { cookies: [], origins: [] } })` so it starts
 * genuinely logged out (no leftover cookies or localStorage token).
 */

test.describe("unauthenticated visitor", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("visiting / shows the welcome page and Zarejestruj się navigates to /register (S-10)", async ({
    page,
  }) => {
    await page.goto("/");

    await expect(
      page.getByRole("heading", { name: "Apteczka domowa" }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Zarejestruj się" }),
    ).toBeVisible();

    await page.getByRole("link", { name: "Zarejestruj się" }).click();
    await page.waitForURL("/register");
    await expect(page).toHaveURL("/register");
  });

  test("visiting /dashboard while unauthenticated redirects to / (S-10)", async ({
    page,
  }) => {
    await page.goto("/dashboard");

    await page.waitForURL("/");
    await expect(page).toHaveURL("/");
  });
});

test.describe("authenticated visitor", () => {
  test("visiting / redirects to /dashboard (S-10)", async ({ page }) => {
    await page.goto("/");

    await page.waitForURL("/dashboard");
    await expect(page).toHaveURL("/dashboard");
  });
});

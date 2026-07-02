import { test, expect } from "@playwright/test";

/**
 * seed.spec.ts — Journey A, Phase 3 of context/changes/critical-path-e2e/plan.md.
 *
 * Protects Risk #2 (context/foundation/test-plan.md): "Critical journey breaks
 * at the frontend↔API seam — login → add medication → see it in cabinet". Drives
 * the full journey against the real backend + DB: add a medication through the
 * form, confirm it renders in the cabinet, confirm it survives a page reload
 * (which also exercises Risk #1: a data-path regression that returns an empty
 * list), and confirm the expanded row shows the detail fields that came back
 * from the medicines API. Authentication is reused from the `setup` project's
 * storageState — no UI login here.
 *
 * This file is also this project's first e2e quality-lever exemplar (see
 * ./CLAUDE.md): role/label locators, wait-for-state (never time), unique per-run
 * data, and assertions whose oracle is the API contract, not the implementation.
 *
 * ORACLE, not hard-coded values: the product name, its variant, and the detail
 * fields are read from the live `/medicines/*` responses (what the user actually
 * selected) and then asserted against what the cabinet renders — so the test
 * checks the data survived the seam, without copying expected values out of the
 * implementation under test.
 *
 * PREREQUISITES:
 * - The `medication_registry` catalog must be seeded (by the `registry-import`
 *   change, against the live Supabase project) — the product autocomplete only
 *   returns catalogued rows. If the search term below matches nothing, the test
 *   fails fast with a clear message rather than a blind timeout.
 * - E2E_TEST_PASSWORD (and optionally E2E_TEST_EMAIL) set for the setup project.
 * - Run from native PowerShell, not the agent's Git Bash tool (lessons.md L-001).
 *
 * CLEANUP: the cabinet API has no DELETE endpoint, so this spec cannot tear down
 * its own row through the app. Isolation instead comes from a per-run-unique
 * `expiry_date` (the shared login means `user_id` is constant, so uniqueness must
 * ride on the expiry to avoid an `uq_cabinet_entries_user_med_expiry` collision
 * across re-runs). Accumulated rows are swept out-of-band by the direct-DB
 * globalTeardown added in the plan's Phase 4.
 */

// The catalog product to drive the journey with. Kept as a constant (overridable
// per environment) so the medication_registry_id is stable across runs, which is
// what makes the per-run `expiry_date` the sole uniqueness axis. Adjust to any
// product known to exist in the seeded catalog if this one is absent.
const PRODUCT_SEARCH = process.env.E2E_PRODUCT_SEARCH ?? "Apap";

// Minimal structural views of the API responses — decoupled from the app's own
// types on purpose (the e2e tsconfig need not resolve `@/…` src paths).
interface ProductOut {
  name: string;
  strength: string | null;
  pharmaceutical_form: string | null;
}
interface VariantOut {
  id: string;
  strength: string | null;
  pharmaceutical_form: string | null;
  active_ingredient: string | null;
  route_of_administration: string | null;
}

// Rebuild the dropdown option label exactly as ProductAutocomplete renders it,
// so we click the right catalog row by its user-visible text.
function productLabel(product: ProductOut): string {
  return [
    product.name,
    product.strength,
    product.pharmaceutical_form ? `· ${product.pharmaceutical_form}` : null,
  ]
    .filter(Boolean)
    .join(" ");
}

// A future, per-run-unique expiry. Spread across ~10 years off a fixed base so
// two runs get different dates (uniqueness) while every date stays in the future
// (status stays "valid", never "expired").
function uniqueFutureExpiryIso(): string {
  const base = new Date(Date.UTC(2035, 0, 1));
  base.setUTCDate(base.getUTCDate() + (Date.now() % 3650));
  return base.toISOString().slice(0, 10); // YYYY-MM-DD
}

// The cabinet list renders dates with pl-PL `dd.MM.yyyy` (use-cabinet-entry
// formatDate). Build the same string deterministically from the ISO parts so we
// can locate our specific row by its unique expiry without depending on the
// runner's ICU locale data.
function toDisplayDate(expiryIso: string): string {
  const [year, month, day] = expiryIso.split("-");
  return `${day}.${month}.${year}`;
}

test.describe("Risk #2 — critical journey: add medication → see it in cabinet", () => {
  test("added medication renders in the cabinet, survives a reload, and shows correct details", async ({
    page,
  }) => {
    const expiryIso = uniqueFutureExpiryIso();
    const expiryDisplay = toDisplayDate(expiryIso);

    // --- Search the catalog and select a product (oracle: the products API) ---
    await page.goto("/cabinet/add");

    const productsResponse = page.waitForResponse(
      (res) =>
        res.url().includes("/medicines/products") &&
        res.request().method() === "GET",
    );
    await page.getByLabel("Nazwa leku").fill(PRODUCT_SEARCH);
    const products = (await (await productsResponse).json()) as ProductOut[];
    expect(
      products.length,
      `No catalog product matched "${PRODUCT_SEARCH}". Is the medication_registry ` +
        "seeded (registry-import)? Set E2E_PRODUCT_SEARCH to a known product.",
    ).toBeGreaterThan(0);
    const product = products[0];

    // --- Pick the product from the dropdown (oracle: the variants API) ---
    const variantsResponse = page.waitForResponse(
      (res) =>
        res.url().includes("/medicines/variants") &&
        res.request().method() === "GET",
    );
    await page.getByText(productLabel(product), { exact: true }).first().click();
    const variants = (await (await variantsResponse).json()) as VariantOut[];
    expect(
      variants.length,
      `Catalog product "${product.name}" returned no variants.`,
    ).toBeGreaterThan(0);
    const variant = variants[0];

    // --- Fill the rest of the form and submit (package_count defaults to 1) ---
    await page.getByLabel("Rozmiar opakowania").selectOption(variant.id);
    await page.getByLabel("Termin ważności").fill(expiryIso);

    const addResponse = page.waitForResponse(
      (res) =>
        res.url().includes("/cabinet/entries") &&
        res.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Dodaj do apteczki" }).click();
    expect(
      (await addResponse).ok(),
      "POST /cabinet/entries must succeed; a 409 usually means a leftover row " +
        "collided on uq_cabinet_entries_user_med_expiry (teardown did not run).",
    ).toBeTruthy();

    // Unique expiry ⇒ a fresh entry, not a merge into an existing one.
    await expect(
      page.getByRole("heading", { name: "Dodano lek" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Nie" }).click();
    await page.waitForURL("/cabinet");

    // --- See it in the cabinet: narrow the shared account's list, then find the
    //     row by product name + this run's unique expiry ---
    await page.getByRole("searchbox").fill(product.name);
    const myRow = page
      .getByRole("row")
      .filter({ hasText: product.name })
      .filter({ hasText: expiryDisplay });
    await expect(myRow).toBeVisible();
    // The narrowed search must be reflected in the URL so the reload below keeps
    // the same filter (otherwise the row could fall onto a later page).
    await expect(page).toHaveURL(/[?&]search=/);

    // --- Persistence: after a real SSR reload the entry is still there (Risk #2
    //     survives navigation; Risk #1 non-empty response) ---
    await page.reload();
    const myRowAfterReload = page
      .getByRole("row")
      .filter({ hasText: product.name })
      .filter({ hasText: expiryDisplay });
    await expect(myRowAfterReload).toBeVisible();

    // --- Detail fields render the data the medicines API returned for the
    //     selected variant (correct data at the seam, not just "a row exists") ---
    await myRowAfterReload
      .getByRole("button", { name: "Pokaż szczegóły" })
      .click();
    const detailRow = page
      .getByRole("row")
      .filter({ hasText: "Substancja czynna:" });
    await expect(detailRow).toContainText(variant.active_ingredient ?? "—");
    await expect(detailRow).toContainText(variant.strength ?? "—");
    await expect(detailRow).toContainText(variant.pharmaceutical_form ?? "—");
    await expect(detailRow).toContainText(
      variant.route_of_administration ?? "—",
    );
  });
});

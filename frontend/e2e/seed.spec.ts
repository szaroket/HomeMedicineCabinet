import { test, expect } from "@playwright/test";
import {
  productLabel,
  toDisplayDate,
  type ProductOut,
  type VariantOut,
} from "./helpers";

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
 * across re-runs *and* parallel workers — see `uniqueFutureExpiryIso`, which
 * gives each worker a disjoint day-band). Accumulated rows are swept out-of-band
 * by the direct-DB globalTeardown added in the plan's Phase 4.
 */

// The catalog product to drive the journey with. Kept as a constant (overridable
// per environment) so the medication_registry_id is stable across runs, which is
// what makes the per-run `expiry_date` the sole uniqueness axis. Adjust to any
// product known to exist in the seeded catalog if this one is absent.
const PRODUCT_SEARCH = process.env.E2E_PRODUCT_SEARCH ?? "Apap";

// The shared ProductOut/VariantOut structural views and the productLabel builder
// come from ./helpers.

// A future, per-run-unique expiry — the sole isolation axis for
// uq_cabinet_entries_user_med_expiry (the shared login fixes user_id). Each
// parallel worker owns a DISJOINT day-band, so two workers firing in the same
// millisecond can never land on the same date; within a band, wall-clock spreads
// re-runs apart. Everything stays a future date off a fixed base (status stays
// "valid", never "expired").
function uniqueFutureExpiryIso(): string {
  const workerIndex = Number(process.env.TEST_WORKER_INDEX ?? "0");
  const bandDays = 365; // each worker's disjoint slice of the day-space
  const dayOffset = workerIndex * bandDays + (Date.now() % bandDays);
  const base = new Date(Date.UTC(2035, 0, 1));
  base.setUTCDate(base.getUTCDate() + dayOffset);
  return base.toISOString().slice(0, 10); // YYYY-MM-DD
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
    await page
      .getByText(productLabel(product), { exact: true })
      .first()
      .click();
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
    //     selected variant (correct data at the seam, not just "a row exists").
    //     Assert each value inside its own detail cell (`<dd>`, role
    //     "definition") rather than as a substring of the whole detail row: this
    //     stops a value from being satisfied by a sibling field's text and stops
    //     a null field from being silently "verified" by the ubiquitous "—"
    //     placeholder. Null fields aren't uniquely checkable (they all render as
    //     "—"), so they're skipped — the populated ones carry the assertion. ---
    await myRowAfterReload
      .getByRole("button", { name: "Pokaż szczegóły" })
      .click();
    // The detail row must be expanded before its cells can be read.
    await expect(
      page.getByRole("row").filter({ hasText: "Substancja czynna:" }),
    ).toBeVisible();

    // Null fields all render as the shared "—" placeholder, so they aren't
    // uniquely verifiable — filter them out and let the populated fields carry
    // the assertion (filtering here keeps the test body free of conditionals).
    const populatedDetailValues = [
      variant.active_ingredient,
      variant.strength,
      variant.pharmaceutical_form,
      variant.route_of_administration,
    ].filter((value): value is string => value != null);
    for (const value of populatedDetailValues) {
      await expect(
        page.getByRole("definition").filter({ hasText: value }).first(),
      ).toBeVisible();
    }
  });
});

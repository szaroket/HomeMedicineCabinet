import { test as base, expect, type Page } from "@playwright/test";

/**
 * manage-cabinet-entry.spec.ts — Phase 5 of
 * context/changes/manage-cabinet-entry/plan.md (FR-005).
 *
 * Protects Risk #2 (context/foundation/test-plan.md): "Critical journey breaks
 * at the frontend↔API seam". The specific FR-005 seam here is the *manage/delete*
 * journey, which the seed spec never exercised:
 *   - increment / decrement drive a real `PATCH /cabinet/entries/{id}/quantity`,
 *   - the trash affordance drives a real `DELETE /cabinet/entries/{id}`,
 *   - and the client-orchestrated zero rule must translate a decrement of an
 *     uncategorised entry at count 1 into a real DELETE (via a confirm dialog),
 *     NOT a silent PATCH-to-0 that would leave a lingering out-of-stock row.
 *
 * ORACLE, not hard-coded values: the product/variant come from the live
 * `/medicines/*` responses (as in seed.spec.ts). The business outcomes asserted
 * are what the user sees — the visible package count after a PATCH and the row
 * disappearing after a DELETE — never internal state.
 *
 * Quality-lever conformance (see ./CLAUDE.md): role/label/text locators only,
 * wait-for-state (never time), unique per-run data, auth reused from the `setup`
 * project's storageState. Each test is independently runnable and cleans up after
 * itself.
 *
 * PREREQUISITES:
 * - `medication_registry` seeded (registry-import) so the autocomplete returns
 *   rows for PRODUCT_SEARCH; the add helper fails fast otherwise.
 * - E2E_TEST_PASSWORD (and optionally E2E_TEST_EMAIL) set for the setup project.
 * - Run from native PowerShell, not the agent's Git Bash tool (lessons.md L-001):
 *   `cd frontend; npx playwright test manage-cabinet-entry`
 *
 * CLEANUP (Phase 5 also closes the seed.spec.ts:33 gap): the happy path deletes
 * its own entries through the app, and the `afterEach` below deletes — via the
 * now-existing cabinet DELETE endpoint — any entry an aborted test left behind,
 * so a failing assertion never leaks a row. Teardown failures are swallowed so
 * they can't mask the test's own assertions. The direct-DB globalTeardown remains
 * the final backstop. Per-run-unique `expiry_date` keeps re-runs and parallel
 * workers from colliding on `uq_cabinet_entries_user_med_expiry`.
 */

const PRODUCT_SEARCH = process.env.E2E_PRODUCT_SEARCH ?? "Apap";
const API_BASE = `${process.env.VITE_API_URL ?? "http://localhost:8000"}/api/v1`;

// Minimal structural views of the API responses — decoupled from the app's own
// `@/…` types on purpose (the e2e tsconfig need not resolve src paths).
interface ProductOut {
  name: string;
  strength: string | null;
  pharmaceutical_form: string | null;
}
interface VariantOut {
  id: string;
}
interface AddEntryResult {
  entry: { id: string };
}

// Rebuild the ProductAutocomplete option label so we click the right catalog row
// by its user-visible text (mirrors seed.spec.ts::productLabel).
function productLabel(product: ProductOut): string {
  return [
    product.name,
    product.strength,
    product.pharmaceutical_form ? `· ${product.pharmaceutical_form}` : null,
  ]
    .filter(Boolean)
    .join(" ");
}

// A future, per-run-unique expiry — the sole isolation axis for
// uq_cabinet_entries_user_med_expiry (the shared login fixes user_id). Each
// parallel worker owns a disjoint 365-day band; a module-scoped sequence spreads
// the multiple entries a single worker creates. The base year (2060) sits far
// past seed.spec.ts's 2035 band so the two specs — same account, same default
// product — can never collide on expiry when the whole suite runs together.
let expirySeq = 0;
function uniqueFutureExpiryIso(): string {
  const workerIndex = Number(process.env.TEST_WORKER_INDEX ?? "0");
  const bandDays = 365;
  const within = (Date.now() + expirySeq++ * 6151) % bandDays;
  const dayOffset = workerIndex * bandDays + within;
  const base = new Date(Date.UTC(2060, 0, 1));
  base.setUTCDate(base.getUTCDate() + dayOffset);
  return base.toISOString().slice(0, 10); // YYYY-MM-DD
}

// The cabinet renders dates with pl-PL `dd.MM.yyyy`; rebuild the same string from
// the ISO parts (locale-independent) to locate our specific row by its expiry.
function toDisplayDate(expiryIso: string): string {
  const [year, month, day] = expiryIso.split("-");
  return `${day}.${month}.${year}`;
}

// Write-only ledger of EVERY entry id this file's tests create. It is never read
// by a test, so it adds no behavioral coupling between tests — it exists purely as
// the record the `test.afterAll` safety net sweeps at the very end, catching
// anything the per-test cleanup missed (e.g. a worker crash between add and the
// fixture teardown). Module-scoped ⇒ per-worker; each worker sweeps its own.
const allCreatedEntryIds = new Set<string>();

// Delete an entry straight through the cabinet API, reusing the logged-in
// session's bearer token from localStorage (the same auth the app's fetch layer
// uses). Best-effort: a 404 (already deleted by the test) or any error is
// swallowed so teardown never masks a real assertion failure.
async function deleteEntryViaApi(page: Page, id: string): Promise<void> {
  try {
    const token = await page.evaluate(() => localStorage.getItem("auth_token"));
    if (!token) return;
    await page.request.delete(`${API_BASE}/cabinet/entries/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    // Intentionally ignored — teardown must not fail the test.
  }
}

// Add a fresh entry through the real add flow (package_count defaults to 1) and
// return the locators/values the test needs. Records the created id into the
// caller's (test-scoped) set for cleanup.
async function addFreshEntry(
  page: Page,
  createdEntryIds: Set<string>,
): Promise<{
  productName: string;
  expiryDisplay: string;
}> {
  const expiryIso = uniqueFutureExpiryIso();

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

  await page.getByLabel("Rozmiar opakowania").selectOption(variants[0].id);
  await page.getByLabel("Termin ważności").fill(expiryIso);

  const addResponse = page.waitForResponse(
    (res) =>
      res.url().includes("/cabinet/entries") &&
      res.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Dodaj do apteczki" }).click();
  const added = await addResponse;
  expect(
    added.ok(),
    "POST /cabinet/entries must succeed; a 409 usually means a leftover row " +
      "collided on uq_cabinet_entries_user_med_expiry (teardown did not run).",
  ).toBeTruthy();
  const result = (await added.json()) as AddEntryResult;
  createdEntryIds.add(result.entry.id); // per-test cleanup
  allCreatedEntryIds.add(result.entry.id); // afterAll safety-net ledger

  // Unique expiry ⇒ a fresh entry, not a merge — dismiss the "add another?" prompt.
  await expect(page.getByRole("heading", { name: "Dodano lek" })).toBeVisible();
  await page.getByRole("button", { name: "Nie" }).click();
  await page.waitForURL("/cabinet");

  return { productName: product.name, expiryDisplay: toDisplayDate(expiryIso) };
}

// Narrow the shared account's list to our unique row and return a locator for it.
// Crucially, WAIT for the debounced search GET to land before returning: on
// /cabinet the row is already visible in the unfiltered list, so a bare
// toBeVisible() would resolve before the `?search=` query registers. If a test
// then mutated immediately, the mutation's invalidate could fire before that
// query exists — and the late search GET (which read the row pre-mutation) would
// repopulate it with stale data that nothing invalidates again. Waiting for the
// filtered response makes the search query the settled, active one first.
async function findEntryRow(
  page: Page,
  productName: string,
  expiryDisplay: string,
) {
  const searchResponse = page.waitForResponse(
    (res) =>
      res.url().includes("/cabinet/entries") &&
      res.url().includes("search=") &&
      res.request().method() === "GET",
  );
  await page.getByRole("searchbox").fill(productName);
  await searchResponse;

  const myRow = page
    .getByRole("row")
    .filter({ hasText: productName })
    .filter({ hasText: expiryDisplay });
  await expect(myRow).toBeVisible();
  return myRow;
}

// Per-test fixture: a FRESH set of created entry ids for each test, auto-swept
// after that test through the cabinet DELETE endpoint. Being a fixture (bound to
// the test's own lifecycle) — not module-level state — is what makes the tests
// structurally independent: there is no mutable state shared between them, so
// order, parallelism, and a mid-test failure can never leak one test's data into
// another's cleanup. Best-effort deletes (see deleteEntryViaApi) also mean the
// happy path (which deletes its own row) and an aborted run both end clean.
const test = base.extend<{ createdEntryIds: Set<string> }>({
  // The provide callback is named `provide` (not Playwright's usual `use`) so the
  // react-hooks lint rule doesn't mistake it for a React Hook.
  createdEntryIds: async ({ page }, provide) => {
    const ids = new Set<string>();
    await provide(ids);
    for (const id of ids) {
      await deleteEntryViaApi(page, id);
    }
  },
});

test.describe("Risk #2 — FR-005 manage/delete journey", () => {
  // Safety net (belt-and-suspenders with the per-test fixture cleanup above):
  // sweep any created entry the per-test teardown didn't remove — e.g. if a
  // worker died between add and the fixture teardown. afterAll has no `page`
  // fixture, so open a throwaway context from the setup project's saved
  // storageState, land on the app origin to hydrate its localStorage token, and
  // best-effort delete each ledgered id. Even if this net fails, the direct-DB
  // globalTeardown (playwright.config.ts) remains the final backstop.
  test.afterAll(async ({ browser }) => {
    if (allCreatedEntryIds.size === 0) return;
    const context = await browser.newContext({
      storageState: "e2e/.auth/user.json",
    });
    const page = await context.newPage();
    try {
      await page.goto("/cabinet");
      for (const id of allCreatedEntryIds) {
        await deleteEntryViaApi(page, id);
      }
    } finally {
      await context.close();
      allCreatedEntryIds.clear();
    }
  });

  test("increment then decrement the package count, then delete via the trash dialog (Risk #2, FR-005)", async ({
    page,
    createdEntryIds,
  }) => {
    const { productName, expiryDisplay } = await addFreshEntry(
      page,
      createdEntryIds,
    );

    const myRow = await findEntryRow(page, productName, expiryDisplay);
    const packageCell = myRow.getByRole("cell").nth(1); // "Opak." column

    // --- Increment (1 → 2): a real PATCH, and the user sees the new count ---
    const patchUp = page.waitForResponse(
      (res) =>
        res.url().includes("/quantity") && res.request().method() === "PATCH",
    );
    await myRow
      .getByRole("button", { name: "Zwiększ liczbę opakowań" })
      .click();
    expect((await patchUp).ok()).toBeTruthy();
    await expect(packageCell).toContainText("2");

    // --- Decrement (2 → 1): a real PATCH (not the zero-delete branch) ---
    const patchDown = page.waitForResponse(
      (res) =>
        res.url().includes("/quantity") && res.request().method() === "PATCH",
    );
    await myRow
      .getByRole("button", { name: "Zmniejsz liczbę opakowań" })
      .click();
    expect((await patchDown).ok()).toBeTruthy();
    await expect(packageCell).toContainText("1");

    // --- Plain delete via the trash affordance + confirm dialog ---
    await myRow.getByRole("button", { name: "Usuń lek" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("Czy na pewno chcesz usunąć");

    const deleteResponse = page.waitForResponse(
      (res) =>
        /\/cabinet\/entries\/[^/]+$/.test(res.url()) &&
        res.request().method() === "DELETE",
    );
    await dialog.getByRole("button", { name: "Usuń", exact: true }).click();
    expect((await deleteResponse).ok()).toBeTruthy();

    // Business outcome: the entry is gone from the user's cabinet.
    await expect(myRow).toHaveCount(0);
  });

  test("decrementing an uncategorised entry to zero deletes it after confirm (Risk #2, FR-005 zero rule)", async ({
    page,
    createdEntryIds,
  }) => {
    const { productName, expiryDisplay } = await addFreshEntry(
      page,
      createdEntryIds,
    );

    const myRow = await findEntryRow(page, productName, expiryDisplay);

    // Decrement from 1 on a fresh (uncategorised, count 1) entry: the client zero
    // rule must open the "will be deleted" confirm INSTEAD of PATCHing to 0.
    await myRow
      .getByRole("button", { name: "Zmniejsz liczbę opakowań" })
      .click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText(
      "Zmniejszenie liczby opakowań do zera usunie",
    );

    // Confirm: the decrement must resolve as a real DELETE (proving the row is
    // removed, not left sitting at 0).
    const deleteResponse = page.waitForResponse(
      (res) =>
        /\/cabinet\/entries\/[^/]+$/.test(res.url()) &&
        res.request().method() === "DELETE",
    );
    await dialog.getByRole("button", { name: "Usuń", exact: true }).click();
    expect((await deleteResponse).ok()).toBeTruthy();

    await expect(myRow).toHaveCount(0);
  });
});

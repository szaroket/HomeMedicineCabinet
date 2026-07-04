import { Client } from "pg";

import { TEST_EMAIL } from "../test-account";

/**
 * Global teardown — Phase 4 of context/changes/critical-path-e2e/plan.md.
 *
 * The cabinet API exposes no DELETE endpoint, so the Risk #2 journey spec
 * (seed.spec.ts) cannot tear down its own rows through the app. This teardown
 * connects directly to Postgres after the whole run and deletes ONLY the shared
 * test account's `cabinet_entries` — so repeated local/CI runs don't accumulate
 * data unboundedly and can't collide on `uq_cabinet_entries_user_med_expiry`.
 *
 * DELIBERATELY NARROW — the account itself must survive:
 * - Match the account by its EXACT fixed email (never the `e2e-*` prefix), so the
 *   `users` row is never a deletion target.
 * - Delete only `cabinet_entries` for that `user_id`. Do NOT touch `users`,
 *   `user_preferences`, or the Supabase `auth.users` row: Phase 2 pivoted to a
 *   single confirmed login (`e2e-hmc@example.com`) that email confirmation makes
 *   un-recreatable, so deleting it would break every subsequent run.
 * - If no `users` row matches the email, the subquery is NULL and the DELETE
 *   matches nothing — it can never mass-delete.
 *
 * Runs as Playwright's `globalTeardown` (wired in playwright.config.ts). Reads
 * `E2E_DATABASE_URL` (loaded from .env.local by the config's dotenv call). This
 * is a Node script — it uses the `pg` client and its own TLS, so it is not
 * subject to the uv-CPython L-001 applink trap; but the full `npx playwright
 * test` command still boots the backend (uv/uvicorn) and must be run from native
 * PowerShell per lessons.md L-001.
 */

// Resolve the connection string, normalizing the backend's SQLAlchemy dialect
// URL (`postgresql+asyncpg://…`) to the plain form the `pg` client parses, so the
// same value the backend uses in DATABASE_URL can be pasted verbatim.
function requireConnectionString(): string {
  const raw = process.env.E2E_DATABASE_URL;
  if (!raw) {
    throw new Error(
      "E2E_DATABASE_URL is not set. The e2e teardown needs a direct Postgres " +
        "connection string to sweep the test account's cabinet entries. Set it " +
        "in frontend/.env.local (or the shell) — you can paste the backend's " +
        "DATABASE_URL value as-is.",
    );
  }
  return raw
    .replace(/^postgresql\+asyncpg:\/\//, "postgresql://")
    .replace(/^postgres\+asyncpg:\/\//, "postgres://");
}

async function globalTeardown(): Promise<void> {
  // Supabase requires TLS for Postgres; `pg` does not enable SSL by default and
  // the pooler serves a cert `pg` can't chain to the system store, so relax
  // verification (this is a test-only cleanup connection, not app traffic).
  const client = new Client({
    connectionString: requireConnectionString(),
    ssl: { rejectUnauthorized: false },
  });

  await client.connect();
  try {
    // Delete ONLY this account's cabinet entries. The email-scoped subquery keeps
    // the account row itself out of the deletion set; a missing account yields a
    // NULL user_id that matches no rows.
    const result = await client.query(
      `DELETE FROM cabinet_entries
       WHERE user_id = (SELECT id FROM users WHERE email = $1)`,
      [TEST_EMAIL],
    );
    console.log(
      `[e2e teardown] Cleared ${result.rowCount ?? 0} cabinet_entries row(s) ` +
        `for ${TEST_EMAIL}; account row left intact.`,
    );
  } finally {
    await client.end();
  }
}

export default globalTeardown;

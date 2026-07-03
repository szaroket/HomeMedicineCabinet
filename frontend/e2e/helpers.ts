/**
 * helpers.ts — shared, side-effect-free helpers for the cabinet e2e specs.
 *
 * Extracted from seed.spec.ts + manage-cabinet-entry.spec.ts (both protect
 * Risk #2, context/foundation/test-plan.md) once a second spec made the
 * duplication real. Only the genuinely-shared, order-independent pieces live
 * here — the structural API views and the two pure label/date builders.
 *
 * Deliberately NOT shared: each spec keeps its own `uniqueFutureExpiryIso()`.
 * The isolation axis for `uq_cabinet_entries_user_med_expiry` is a per-run
 * expiry, and the two specs run against the same account with the same default
 * product — so their expiry bands must stay disjoint (seed bases at 2035, manage
 * at 2060 with a module-scoped sequence). Centralising that generator would
 * couple the two bands and reintroduce the collision it exists to prevent.
 *
 * The structural views are decoupled from the app's own `@/…` types on purpose:
 * the e2e tsconfig need not resolve src paths.
 */

// Minimal view of a `/medicines/products` row — just the fields the specs read.
export interface ProductOut {
  name: string;
  strength: string | null;
  pharmaceutical_form: string | null;
}

// Superset view of a `/medicines/variants` row: seed asserts the detail fields,
// manage only needs `id`. A single shared shape serves both (each reads what it
// needs); the extra fields are harmless to a spec that ignores them.
export interface VariantOut {
  id: string;
  strength: string | null;
  pharmaceutical_form: string | null;
  active_ingredient: string | null;
  route_of_administration: string | null;
}

// Rebuild the ProductAutocomplete option label exactly as it renders, so a spec
// can click the right catalog row by its user-visible text.
export function productLabel(product: ProductOut): string {
  return [
    product.name,
    product.strength,
    product.pharmaceutical_form ? `· ${product.pharmaceutical_form}` : null,
  ]
    .filter(Boolean)
    .join(" ");
}

// The cabinet renders dates with pl-PL `dd.MM.yyyy`; rebuild the same string
// deterministically from the ISO parts (locale-independent) so a spec can locate
// its specific row by that unique expiry without depending on the runner's ICU
// locale data.
export function toDisplayDate(expiryIso: string): string {
  const [year, month, day] = expiryIso.split("-");
  return `${day}.${month}.${year}`;
}

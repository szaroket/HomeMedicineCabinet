"""Raw SQL queries for the medicines module."""

from sqlalchemy import text

# Group case-insensitively on (name, strength, form): the source registry holds
# the same product under inconsistent casing (e.g. "Apap" vs "APAP"), and a
# plain DISTINCT would surface each casing as a separate pick. DISTINCT ON keeps
# one representative row per case-folded group; the trailing ORDER BY columns
# make that representative deterministic. The variants lookup must match
# the same case-folded key so selecting a product still fetches every variant.
SEARCH_PRODUCTS = text(
    """
    SELECT DISTINCT ON (
            lower(name),
            lower(coalesce(strength, '')),
            lower(coalesce(pharmaceutical_form, ''))
        )
        name, strength, pharmaceutical_form, active_ingredient
    FROM medication_registry
    WHERE search_vector @@ to_tsquery('simple', :tsquery)
    ORDER BY
        lower(name),
        lower(coalesce(strength, '')),
        lower(coalesce(pharmaceutical_form, '')),
        name, strength, pharmaceutical_form
    LIMIT :limit
    """
)

# Case-insensitive, NULL-safe match on the product key.  /products folds casing
# via lower(name)/lower(coalesce(strength,''))/..., so variants must use the same
# fold or a product selected from the search results would miss rows stored under
# a different casing in the source registry.
LIST_VARIANTS = text(
    """
    SELECT id, name, strength, pharmaceutical_form,
           capacity, capacity_unit, is_tablet_based,
           active_ingredient, route_of_administration
    FROM medication_registry
    WHERE lower(name) = lower(:name)
      AND lower(coalesce(strength, '')) IS NOT DISTINCT FROM lower(coalesce(:strength, ''))
      AND lower(coalesce(pharmaceutical_form, '')) IS NOT DISTINCT FROM
          lower(coalesce(:pharmaceutical_form, ''))
    ORDER BY capacity NULLS LAST
    """
)

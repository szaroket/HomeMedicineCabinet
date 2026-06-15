"""Pure XML parsing for the Polish medicines registry import.

Stream-parses the official ``produktyLecznicze`` export and yields one
normalized row dict per distinct package size (``capacity`` + ``capacity_unit``)
of each human, non-withdrawn product. Package units that differ only by GTIN /
wrapping (e.g. the same tablet count in a sachet vs. a blister) collapse to a
single row — GTIN is informational for the MVP. Nothing here touches the DB or
the network; every function is unit-testable against a committed XML fixture.
"""

import logging
import os
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from decimal import Decimal, InvalidOperation
from xml.etree.ElementTree import Element

logger = logging.getLogger(__name__)

# The export's default namespace; ElementTree reports tags fully qualified.
NS = "{http://rejestry.ezdrowie.gov.pl/rpl/eksport-danych-v6.0.0}"

# Countable, discrete dosage units → is_tablet_based True. Volume/mass units
# (ml, g, …) and unknown units stay False. Centralized so downstream query code
# (S-01/S-05) never re-derives pill-ness; extend conservatively.
TABLET_UNITS: frozenset[str] = frozenset(
    {"tabl.", "kaps.", "draż.", "past.", "czopki", "globulki"}
)


_SENTINEL_VALUES: frozenset[str] = frozenset({"-"})


def _clean(value: str | None) -> str | None:
    """Trim a raw attribute; treat empty, whitespace, or sentinel values as missing (None)."""
    if value is None:
        return None
    value = value.strip()
    if not value or value in _SENTINEL_VALUES:
        return None
    return value


def _distinct_attr(product: Element, path: str, attr: str) -> list[str]:
    """Collect distinct non-empty attribute values in document order."""
    seen: dict[str, None] = {}
    for el in product.findall(path):
        value = _clean(el.get(attr))
        if value is not None:
            seen.setdefault(value, None)
    return list(seen)


def _join_routes(product: Element) -> str | None:
    routes = _distinct_attr(
        product, f"{NS}drogiPodania/{NS}drogaPodania", "drogaPodaniaNazwa"
    )
    return ", ".join(routes) if routes else None


def _join_substances(product: Element) -> str | None:
    substances = _distinct_attr(
        product, f"{NS}substancjeCzynne/{NS}substancjaCzynna", "nazwaSubstancji"
    )
    return " + ".join(substances) if substances else None


def _join_manufacturers(product: Element) -> str | None:
    manufacturers = _distinct_attr(
        product, f"{NS}daneOWytworcy/{NS}wytworcy", "nazwaWytworcyImportera"
    )
    return ", ".join(manufacturers) if manufacturers else None


def _first_atc(product: Element) -> str | None:
    el = product.find(f"{NS}kodyATC/{NS}kodATC")
    return _clean(el.text) if el is not None else None


def _parse_capacity(pojemnosc: str | None) -> Decimal | None:
    """Parse ``pojemnosc`` into a Decimal; accept comma or dot decimals.

    Returns None for empty/whitespace/non-numeric values (e.g. FANHDI's
    powder vial has an empty capacity) so the parser never crashes on them.
    """
    raw = _clean(pojemnosc)
    if raw is None:
        return None
    try:
        return Decimal(raw.replace(",", "."))
    except InvalidOperation:
        return None


def _is_tablet_based(unit: str | None) -> bool:
    return unit in TABLET_UNITS


def _variant_key(row: dict) -> tuple:
    """Return the case-folded dedup key for a parsed row."""
    return (
        (row["name"] or "").lower(),
        (row["strength"] or "").lower(),
        (row["pharmaceutical_form"] or "").lower(),
        row["capacity"],
        row["capacity_unit"],
    )


def _scan_original_keys(source) -> frozenset[tuple]:
    """First-pass scan: return variant keys that have an original authorization.

    The registry export lists the same logical pack under multiple
    ``produktLeczniczy`` entries — one original authorization (NAR, MRP, DCP,
    or CEN) plus any number of parallel imports (IR). This pass identifies which
    variant keys have an original authorization so the second pass can suppress
    IR duplicates for those keys, regardless of document order.

    Procedure types:
    - NAR — Polish national authorization
    - MRP — Mutual Recognition Procedure (EU)
    - DCP — Decentralised Procedure (EU)
    - CEN — Centralised Procedure (EMA)
    - IR  — Parallel Import (not original; suppressed when any of the above exists)

    Args:
        source: Path or seekable file object for the registry XML export.

    Returns:
        Frozenset of ``(name_lc, strength_lc, form_lc, capacity, unit)`` tuples
        that appear under at least one non-IR ``produktLeczniczy`` entry.
    """
    original_keys: set[tuple] = set()
    context = ET.iterparse(source, events=("start", "end"))
    _event, root = next(context)
    for event, elem in context:
        if event != "end" or elem.tag != f"{NS}produktLeczniczy":
            continue
        if elem.get("rodzajPreparatu") == "ludzki" and elem.get("typProcedury") != "IR":
            for row in _rows_for_product(elem):
                original_keys.add(_variant_key(row))
        elem.clear()
        root.clear()
    return frozenset(original_keys)


def _rows_for_product(product: Element) -> Iterator[dict]:
    """Yield one row dict per distinct package size of a single (human) product.

    Rows are deduped on ``(capacity, capacity_unit)`` within the product: GTINs
    that differ only by package wrapping collapse to a single row (the first one
    seen wins). FANHDI-style composite packs keep both units because their
    ``(capacity, capacity_unit)`` keys differ.
    """
    base = {
        "source_product_id": _clean(product.get("id")),
        "name": _clean(product.get("nazwaProduktu")),
        "active_ingredient": _join_substances(product),
        "strength": _clean(product.get("moc")),
        "pharmaceutical_form": _clean(product.get("nazwaPostaciFarmaceutycznej")),
        "marketing_authorization_holder": _clean(product.get("podmiotOdpowiedzialny")),
        "manufacturer": _join_manufacturers(product),
        "route_of_administration": _join_routes(product),
        "atc_code": _first_atc(product),
        "leaflet_url": _clean(product.get("ulotka")),
        "specification_url": _clean(product.get("charakterystyka")),
    }
    if base["name"] is None:
        logger.warning(
            "Skipping product %s: missing nazwaProduktu (name)",
            base["source_product_id"],
        )
        return
    seen: set[tuple[Decimal | None, str | None]] = set()
    for opakowanie in product.findall(f"{NS}opakowania/{NS}opakowanie"):
        if opakowanie.get("skasowane") == "TAK":
            continue
        gtin = _clean(opakowanie.get("kodGTIN"))
        availability = _clean(opakowanie.get("kategoriaDostepnosci"))
        for unit in opakowanie.findall(
            f"{NS}jednostkiOpakowania/{NS}jednostkaOpakowania"
        ):
            capacity = _parse_capacity(unit.get("pojemnosc"))
            capacity_unit = _clean(unit.get("jednostkaPojemnosci"))
            key = (capacity, capacity_unit)
            if key in seen:
                continue  # same size, different GTIN/wrapping → drop the dup
            seen.add(key)
            yield {
                **base,
                "gtin": gtin,
                "availability_category": availability,
                "capacity": capacity,
                "capacity_unit": capacity_unit,
                "is_tablet_based": _is_tablet_based(capacity_unit),
            }


def _rewind_for_pass_two(source) -> None:
    """Rewind a file-object source before pass 2; reject non-seekable streams.

    A path source is left untouched because ``iterparse`` re-opens it for each
    pass. A file object is rewound with ``seek(0)``. A non-seekable stream (e.g.
    a live HTTP response) would be exhausted by pass 1 and silently yield zero
    rows in pass 2, so it is rejected loudly instead.

    Args:
        source: Path or file object passed to ``parse_registry``.

    Raises:
        ValueError: When ``source`` is a non-seekable stream that cannot be
            re-read for the second pass.
    """
    if isinstance(source, (str, bytes, os.PathLike)):
        return  # iterparse re-opens the path each pass
    if not hasattr(source, "seek") or (
        hasattr(source, "seekable") and not source.seekable()
    ):
        raise ValueError(
            "parse_registry requires a path or a seekable file object; the given "
            "stream cannot be rewound for the second (yield) pass."
        )
    source.seek(0)


def parse_registry(source) -> Iterator[dict]:
    """Stream-parse the registry export, yielding one dict per package unit.

    ``source`` is a path or a **seekable** file object: parsing runs two passes
    over the source. A non-seekable stream cannot be rewound for pass 2 and is
    rejected with a ``ValueError`` rather than silently importing nothing. Uses
    namespace-aware ``iterparse``
    and clears each processed element (and the root) so memory stays flat over
    the hundreds-of-MB production file. Products whose ``rodzajPreparatu`` is
    not ``ludzki`` (human) are skipped; withdrawn packages (``skasowane="TAK"``)
    are skipped inside ``_rows_for_product``.

    Cross-product deduplication: the registry export includes multiple
    ``produktLeczniczy`` entries for the same logical product (one per parallel
    importer / marketing-authorization holder). Entries are deduped on
    ``(lower(name), lower(strength), lower(form), capacity, capacity_unit)``
    across the whole file — first occurrence wins (document order). Original
    (NAR) authorizations appear before parallel imports (IR) in the standard
    government export, so they naturally win the race.

    Security note: stdlib ElementTree never resolves external entities, so there
    is no XXE file-read/SSRF here. The only residual XML risk is an internal
    entity-expansion (billion-laughs) DoS, which we accept: the source is a
    trusted government HTTPS endpoint and this script is hand-run by an operator
    on a one-off basis. Swap to ``defusedxml.ElementTree.iterparse`` if this ever
    parses untrusted input.
    """
    # Pass 1 — find all variant keys that have an original authorization
    # (NAR / MRP / DCP / CEN). IR (parallel import) entries are suppressed
    # whenever an original entry exists for the same variant, regardless of
    # document order.
    original_keys = _scan_original_keys(source)
    _rewind_for_pass_two(source)

    # Pass 2 — stream and yield, skipping IR rows shadowed by an original row
    # and deduplicating any remaining same-procedure duplicates (first-seen wins).
    seen_variants: set[tuple] = set()
    context = ET.iterparse(source, events=("start", "end"))
    _event, root = next(context)  # capture the <produktyLecznicze> root
    for event, elem in context:
        if event != "end" or elem.tag != f"{NS}produktLeczniczy":
            continue
        if elem.get("rodzajPreparatu") == "ludzki":
            is_ir = elem.get("typProcedury") == "IR"
            for row in _rows_for_product(elem):
                key = _variant_key(row)
                if key in original_keys and is_ir:
                    logger.debug(
                        "Skipping IR variant '%s' %s %s cap=%s %s "
                        "(product id %s; original authorization exists)",
                        row["name"],
                        row["strength"],
                        row["pharmaceutical_form"],
                        row["capacity"],
                        row["capacity_unit"],
                        row["source_product_id"],
                    )
                    continue
                if key in seen_variants:
                    logger.debug(
                        "Skipping duplicate variant '%s' %s %s cap=%s %s "
                        "(product id %s)",
                        row["name"],
                        row["strength"],
                        row["pharmaceutical_form"],
                        row["capacity"],
                        row["capacity_unit"],
                        row["source_product_id"],
                    )
                    continue
                seen_variants.add(key)
                yield row
        elem.clear()
        root.clear()  # drop the processed product from root so memory stays flat

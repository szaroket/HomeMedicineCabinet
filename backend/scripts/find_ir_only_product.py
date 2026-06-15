"""Find products in the registry that have only IR (parallel import) entries.

These are products with no original authorization (NAR/MRP/DCP/CEN) — the
import parser keeps IR rows for them since there is no canonical row to prefer.
Useful for manual verification that IR-only products still appear after import.

Usage:
    uv run python -m scripts.find_ir_only_product
    uv run python -m scripts.find_ir_only_product --limit 5
    uv run python -m scripts.find_ir_only_product --url <custom-url>
"""

import argparse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict

REGISTRY_URL = (
    "https://rejestry.ezdrowie.gov.pl/api/rpl/medicinal-products/"
    "public-pl-report/6.0.0/overall.xml"
)
NS = "{http://rejestry.ezdrowie.gov.pl/rpl/eksport-danych-v6.0.0}"


def find_ir_only_products(source, limit: int = 3) -> list[dict]:
    """Stream-parse ``source`` and return up to ``limit`` IR-only product groups.

    A product group is IR-only when every ``produktLeczniczy`` entry sharing the
    same case-folded ``(name, strength, form)`` key has ``typProcedury="IR"``.

    Args:
        source: URL string or file path accepted by ``urllib.request.urlopen`` /
            ``ET.iterparse``.
        limit: Maximum number of IR-only groups to return.

    Returns:
        List of dicts with keys ``name``, ``strength``, ``form``, ``procedures``
        (set of procedure types seen for the group), and ``product_ids``.
    """
    # procedures_by_group: group_key → set of typProcedury values
    procedures: dict[tuple, set[str]] = defaultdict(set)
    # Keep one representative (name, strength, form) per group for display
    display: dict[tuple, tuple] = {}
    product_ids: dict[tuple, list[str]] = defaultdict(list)

    context = ET.iterparse(source, events=("start", "end"))
    _event, root = next(context)
    for event, elem in context:
        if event != "end" or elem.tag != f"{NS}produktLeczniczy":
            continue
        if elem.get("rodzajPreparatu") != "ludzki":
            elem.clear()
            root.clear()
            continue

        name = (elem.get("nazwaProduktu") or "").strip()
        strength = (elem.get("moc") or "").strip()
        form = (elem.get("nazwaPostaciFarmaceutycznej") or "").strip()
        proc = (elem.get("typProcedury") or "").strip()
        pid = elem.get("id") or ""

        if not name:
            elem.clear()
            root.clear()
            continue

        group = (name.lower(), strength.lower(), form.lower())
        procedures[group].add(proc)
        product_ids[group].append(pid)
        if group not in display:
            display[group] = (name, strength, form)

        elem.clear()
        root.clear()

    results = []
    for group, procs in procedures.items():
        if procs == {"IR"}:
            name, strength, form = display[group]
            results.append(
                {
                    "name": name,
                    "strength": strength,
                    "form": form,
                    "procedures": procs,
                    "product_ids": product_ids[group],
                }
            )
        if len(results) >= limit:
            break

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=REGISTRY_URL, help="Registry XML URL or path")
    parser.add_argument(
        "--limit", type=int, default=3, help="Number of IR-only products to show"
    )
    args = parser.parse_args()

    print(f"Fetching registry from:\n  {args.url}\n")
    print("Scanning for IR-only products (this may take a minute)...\n")

    source = args.url
    if source.startswith("http"):
        req = urllib.request.Request(source, headers={"Accept-Encoding": "identity"})
        with urllib.request.urlopen(req) as response:
            results = find_ir_only_products(response, limit=args.limit)
    else:
        results = find_ir_only_products(source, limit=args.limit)

    if not results:
        print("No IR-only products found.")
        return

    print(f"Found {len(results)} IR-only product group(s):\n")
    for r in results:
        print(f"  Name:       {r['name']}")
        print(f"  Strength:   {r['strength'] or '(none)'}")
        print(f"  Form:       {r['form'] or '(none)'}")
        print(f"  Procedures: {', '.join(sorted(r['procedures']))}")
        print(f"  Product IDs: {', '.join(r['product_ids'])}")
        print()

    print("Use one of these to verify the variants endpoint still returns results:")
    r = results[0]
    qs = f"name={r['name']}"
    if r["strength"]:
        qs += f"&strength={r['strength']}"
    if r["form"]:
        qs += f"&form={r['form']}"
    print(f"  GET /api/v1/medicines/variants?{qs}")


if __name__ == "__main__":
    main()

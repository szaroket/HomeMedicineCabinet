"""CLI entrypoint: download → parse → load the Polish medicines registry.

Run from ``backend/``::

    uv run python -m scripts.registry_import                 # full import
    uv run python -m scripts.registry_import --dry-run       # parse + count only
    uv run python -m scripts.registry_import --source FILE   # local XML instead

Note: a real load opens a TLS connection to the database. On Windows run it from
a native PowerShell terminal (see context/foundation/lessons.md, L-001).
"""

import argparse
import asyncio
import logging
import tempfile
import time
from pathlib import Path

import httpx

from scripts.registry_import.loader import load_registry
from scripts.registry_import.parser import parse_registry

DEFAULT_SOURCE = (
    "https://rejestry.ezdrowie.gov.pl/api/rpl/medicinal-products/"
    "public-pl-report/6.0.0/overall.xml"
)

logger = logging.getLogger("registry_import")

# Keys surfaced in --dry-run sample output (the most telling fields).
_SAMPLE_KEYS = ("name", "capacity", "capacity_unit", "is_tablet_based", "gtin")

# Download is the long network-bound step. A finite timeout prevents an
# indefinite hang on a stalled server; a few retries ride out transient stalls
# so the operator need not re-run the whole command.
_DOWNLOAD_TIMEOUT = httpx.Timeout(connect=30, read=300, write=30, pool=30)
_DOWNLOAD_MAX_ATTEMPTS = 3
_DOWNLOAD_RETRY_DELAY = 5  # seconds


def _is_url(source: str) -> bool:
    return source.startswith(("http://", "https://"))


def _download(url: str) -> str:
    """Stream-download ``url`` to a temp file and return its path.

    Uses ``delete=False`` and closes the handle before returning so the file can
    be reopened by path on Windows (a still-open NamedTemporaryFile cannot be
    reopened there). The caller is responsible for unlinking the returned path.
    """
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xml")
    try:
        for attempt in range(1, _DOWNLOAD_MAX_ATTEMPTS + 1):
            try:
                # Discard any partial bytes from a failed earlier attempt.
                tmp.seek(0)
                tmp.truncate()
                with httpx.stream(
                    "GET", url, timeout=_DOWNLOAD_TIMEOUT, follow_redirects=True
                ) as resp:
                    resp.raise_for_status()
                    for chunk in resp.iter_bytes():
                        tmp.write(chunk)
                break
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt == _DOWNLOAD_MAX_ATTEMPTS:
                    raise
                logger.warning(
                    "Download attempt %d/%d failed: %s — retrying in %ds",
                    attempt,
                    _DOWNLOAD_MAX_ATTEMPTS,
                    exc,
                    _DOWNLOAD_RETRY_DELAY,
                )
                time.sleep(_DOWNLOAD_RETRY_DELAY)
    finally:
        tmp.close()
    return tmp.name


def _dry_run(source: str) -> int:
    """Parse only: log the row count and a few sample rows. No DB writes."""
    count = 0
    samples: list[dict] = []
    for row in parse_registry(source):
        if len(samples) < 3:
            samples.append(row)
        count += 1
    logger.info("Parsed %d rows (dry-run, no DB writes)", count)
    for row in samples:
        logger.info("  sample: %s", {key: row[key] for key in _SAMPLE_KEYS})
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.registry_import",
        description="Download, parse and bulk-load the Polish medicines registry.",
    )
    parser.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help="Dataset URL (default) or a local XML file path.",
    )
    parser.add_argument(
        "--batch-size", type=int, default=1000, help="Rows per insert batch."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reload even when cabinet_entries references the registry.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and count only; do not touch the database.",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    tmp_path: str | None = None
    try:
        if _is_url(args.source):
            logger.info("Downloading %s ...", args.source)
            source = tmp_path = _download(args.source)
        else:
            source = args.source

        if args.dry_run:
            return _dry_run(source)

        inserted = asyncio.run(
            load_registry(
                parse_registry(source),
                batch_size=args.batch_size,
                force=args.force,
            )
        )
        logger.info("Done. Inserted %d rows into medication_registry.", inserted)
        return 0
    finally:
        if tmp_path is not None:
            # Best-effort cleanup: never let a cleanup error mask an in-flight
            # exception from the import body above.
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("Could not remove temp file %s: %s", tmp_path, exc)


if __name__ == "__main__":
    raise SystemExit(main())

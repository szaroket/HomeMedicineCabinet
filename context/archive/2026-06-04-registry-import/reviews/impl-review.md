<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Registry Import (F-03)

- **Plan**: context/changes/registry-import/plan.md
- **Scope**: All 4 phases
- **Date**: 2026-06-04
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 4 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

Plan adherence is clean: every planned file matches intent, no missing/extra
source, the "What We're NOT Doing" list is fully respected, and the
user-approved `(capacity, capacity_unit)` dedup deviation is implemented
consistently across parser + fixture + tests with first-GTIN-wins semantics.
All automated success criteria pass (offline checks re-run during review; the
TLS-DB-bound checks 1.1–1.3 and 4.1 verified manually in PowerShell per L-001).
Findings are reliability/hardening nits on the one-off operator script.

## Findings

### F1 — A row with missing `name` aborts the entire import

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality (reliability)
- **Location**: backend/scripts/registry_import/parser.py:100
- **Detail**: `_rows_for_product` sets `"name": _clean(...)`, which is `None` when `nazwaProduktu` is missing/blank. `MedicationRegistry.name` is NOT NULL, so a single bad source record would fail the whole all-or-none transaction at COMMIT — after downloading/parsing the full dataset. Unlikely in the real RPL data, but cheap insurance for a one-off import.
- **Fix**: In `_rows_for_product`, skip + `logger.warning` rows whose `name` is `None` (continue before yielding), turning a hard abort into an observable skip.
- **Decision**: FIXED — added module `logger` and a `name is None` guard that warns + returns before yielding rows.

### F2 — httpx download has no timeout (can hang forever)

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality (reliability)
- **Location**: backend/scripts/registry_import/__main__.py:48
- **Detail**: `httpx.stream("GET", url, timeout=None, ...)` disables all timeouts; a stalled server hangs the import indefinitely with no feedback. `raise_for_status()` + `follow_redirects` are correctly handled.
- **Fix**: Use a finite read timeout, e.g. `httpx.Timeout(connect=30, read=300, write=30, pool=30)`.
- **Decision**: FIXED (extended) — finite `httpx.Timeout` + retry loop (3 attempts, 5s backoff) that truncates the temp file between attempts so partial bytes are discarded.

### F3 — XML internal-entity expansion (billion-laughs) DoS exposure

- **Severity**: ⚠️ WARNING (CRITICAL-by-category, downgraded — see detail)
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality (security)
- **Location**: backend/scripts/registry_import/parser.py:11,145
- **Detail**: `xml.etree.ElementTree` parses a downloadable source. Stdlib ET does NOT fetch external entities (no classic XXE file-read/SSRF), so the realistic risk is only an internal-entity / quadratic-blowup DoS on a malicious file. Source is a trusted gov HTTPS endpoint and the script is hand-run by an operator → low likelihood, self-inflicted. Hence downgraded from CRITICAL to WARNING/LOW.
- **Fix**: Either accept-as-risk with a one-line trust-assumption comment in `parse_registry`, or swap to `defusedxml.ElementTree.iterparse` (drop-in, keeps the streaming API) for defense-in-depth.
- **Decision**: ACCEPTED (risk) — documented the trust assumption (trusted gov HTTPS source, hand-run operator) and the defusedxml escape hatch in `parse_registry`'s docstring. No code/dep change.

### F4 — os.unlink in finally can mask the real exception

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality (reliability)
- **Location**: backend/scripts/registry_import/__main__.py:117-119
- **Detail**: The `finally` block calls `os.unlink(tmp_path)` unconditionally. If the file is already gone or locked (Windows), `unlink` raises inside `finally` and masks any in-flight exception from the import body.
- **Fix**: `pathlib.Path(tmp_path).unlink(missing_ok=True)` wrapped in `try/except OSError: logger.warning(...)`.
- **Decision**: FIXED — switched `os` import to `pathlib.Path`; cleanup now `Path(tmp_path).unlink(missing_ok=True)` guarded by `try/except OSError` + warning.

### F5 — `--force` guard message slightly overstates orphan risk

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/scripts/registry_import/loader.py:37-48
- **Detail**: The count-then-delete guard is a (benign) check-then-act, and the cabinet FK is restrict-default (no cascade) — so with `--force` the DELETE would error at the DB, never silently orphan. The message says "would orphan those FKs", which overstates it. Behaviorally safe.
- **Fix**: Reword the message to "cannot delete; the cabinet FK would reject it" (or note `--force` will fail loudly at the DB).
- **Decision**: FIXED — reworded the guard message: the restrict-default FK rejects the DELETE so `force=True` fails loudly at the DB; advises clearing `cabinet_entries` first.

### F6 — `is_tablet_based` server_default persists on the column

- **Severity**: 🔭 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/migrations/versions/dc9619b00abd_reshape_medication_registry.py:51-59
- **Detail**: `add_column` sets `server_default=sa.false()` (needed to back-fill the NOT NULL column) and never drops it, while the model declares its own client-side `default=False`. Harmless; minor "model-as-sole-default" divergence. Sibling migrations don't set server defaults on existing columns.
- **Fix**: Optional — drop the server_default in a follow-up `alter_column` if you want the model to be the only default authority.
- **Decision**: SKIPPED — harmless; the persisted server_default is accepted as-is.

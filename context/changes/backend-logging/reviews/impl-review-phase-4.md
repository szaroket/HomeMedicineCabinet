<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Backend Logging Implementation Plan

- **Plan**: context/changes/backend-logging/plan.md
- **Scope**: Phase 4 of 4
- **Date**: 2026-06-29
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 1 warning, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | WARNING |

## Verification run

- `ruff check .` — All checks passed
- `ruff format --check .` — 82 files already formatted
- `pytest` excluding `tests/db` — 349 passed
- `pytest` (full suite) — aborts at `tests/db/test_connection.py` with the OpenSSL/applink
  crash under the Bash tool (lessons L-001); environment quirk, **not** a Phase 4 regression.
  Run from PowerShell / CI to confirm criterion 4.2.

## Findings

### F1 — registry_import central-config step skipped, but Progress marks it done

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Plan Adherence / Success Criteria
- **Location**: backend/scripts/registry_import/__main__.py:122
- **Detail**: Phase 4 Change #1 (route registry_import through `configure_logging()` + redaction)
  was not implemented. Line 122 still calls `logging.basicConfig(level=logging.INFO,
  format="%(message)s")` — no central format, no redaction filter on the script's loggers.
  Commit 656bdd7 says "registry_import step skipped per user decision," a legitimate scope cut.
  The problem is the record contradicts reality: (a) Progress 4.3 "registry_import emits central
  format with redaction" is checked `[x]`, asserting a behavior that does not exist; (b) the
  plan's Changes Required #1 and Manual Verification bullet still describe the routing with no
  addendum recording the skip — unlike Phase 1, which documented its scope change via an addendum.
  A future review reading the plan as ground truth will believe the import script is redacted.
  Actual security risk is low (the script logs medicine sample rows, URLs, counts — no
  email/token/password), so this is a record-integrity issue, not a live leak.
- **Fix A ⭐ Recommended**: Make the record honest — keep the skip. Add a Phase 4 addendum noting
  registry_import was intentionally deferred per user decision; flip 4.3 to `[ ]` (or strike with
  a note); move the registry_import item under "What We're NOT Doing" / follow-up.
  - Strength: Respects the explicit user decision; the real defect is the false checkbox, and this
    fixes exactly that. Matches the Phase 1 addendum precedent already in this plan.
  - Tradeoff: registry_import stays outside central format/redaction.
  - Confidence: HIGH — skip is confirmed in the commit message and code.
  - Blind spot: None significant.
- **Fix B**: Actually implement the routing. Replace `logging.basicConfig(...)` at line 122 with
  `configure_logging()` (import from app.core.logging_config) so the script's loggers inherit the
  central handler + redaction.
  - Strength: Fulfils the original scope; brings the script behind redaction.
  - Tradeoff: Reverses an explicit user decision; configure_logging() reads Settings (env-driven
    JSON/level), which a standalone CLI may not want imposed.
  - Confidence: MED — 3-line change, but contradicts the stated decision.
  - Blind spot: Whether the script is ever run in an env that sets log_format=json.
- **Decision**: FIXED via Fix A — flipped Progress 4.3 to [ ], added Phase 4 addendum, listed routing under "What We're NOT Doing" as follow-up.

### F2 — alembic change adjusted the formatter, not the levels the contract named

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: backend/alembic.ini:147-149
- **Detail**: Phase 4 Change #2 Contract said: "Adjust the [loggers]/[handlers] levels in
  alembic.ini to match the app's level convention." The implementation instead rewrote
  `[formatter_generic]` format/datefmt to mirror the app console layout
  (`[asctime][level-8] name | message`) and left the levels (root=WARNING, sqlalchemy=WARNING,
  alembic=INFO) untouched. This satisfies the broader Intent ("make alembic logging consistent
  with the app convention") and is arguably more useful than re-leveling, but deviates from the
  literal contract; the levels were never reviewed/aligned.
- **Fix**: Accept as-is — the format alignment matches the Intent and the existing levels
  (operational alembic at INFO, SQL echo at WARNING) are sensible. Optionally note in the plan
  that levels were left intentionally.
- **Decision**: ACCEPTED as-is — format alignment matches Intent; levels are sensible. Recorded in the Phase 4 addendum (levels left intentionally).

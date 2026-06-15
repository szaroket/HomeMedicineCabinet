<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Registry Import (F-03)

- **Plan**: context/changes/registry-import/plan.md
- **Mode**: Deep
- **Date**: 2026-06-04
- **Verdict**: REVISE → SOUND (all 7 findings fixed in triage)
- **Findings**: 2 critical, 3 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | WARNING |
| Plan Completeness | FAIL |

## Grounding

5/5 code paths ✓ (model, migration head 2c7067ce3f56, connector, conftest, backend-structure),
5/5 symbols ✓ (MedicationRegistry, cabinet_entries FK, async_session_factory, database_url, asyncio_mode),
brief↔plan ✓.
Fixture path ✗ — plan references repo-root `rejestr_lekow_20260603.xml`, which does not exist; the
committed sample is `docs/reference/rejestr_lekow_sample_20260603.xml` (see F1).

## Findings

### F1 — Plan points at a fixture file that doesn't exist

- **Severity**: ❌ CRITICAL
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Current State (l.32), Phase 2 §3 (l.299), References (l.493)
- **Detail**: The plan names the sample as repo-root `rejestr_lekow_20260603.xml` and Phase 2 §3 says "Copy of the repo-root rejestr_lekow_20260603.xml". That file does not exist. The committed sample is `docs/reference/rejestr_lekow_sample_20260603.xml` (which change.md correctly references). An implementer will look in the wrong place and the fixture-copy instruction is wrong.
- **Fix**: Update all three plan references to `docs/reference/rejestr_lekow_sample_20260603.xml` to match change.md and the actual committed file.
- **Decision**: FIXED (Fix in plan)

### F2 — Phase 2 title mismatch between body and Progress

- **Severity**: ❌ CRITICAL
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 2 header (l.232) vs Progress (l.516)
- **Detail**: Body heading is `## Phase 2: XML Parser (pure, fixture-tested)`; Progress heading is `### Phase 2: XML Parser`. The Progress-format contract requires each `## Phase N: <name>` to have a matching `### Phase N: <name>`. A mismatched name can break `/10x-implement`'s phase-to-progress matching. Phases 1, 3, 4 match correctly.
- **Fix**: Rename the Progress heading to `### Phase 2: XML Parser (pure, fixture-tested)` (or trim the body heading) so the two strings are identical.
- **Decision**: FIXED (Fix in plan)

### F3 — iterparse snippet leaks the root's children; memory won't stay flat

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Critical Impl Details (l.114-126), Phase 2 snippet (l.282-291)
- **Detail**: The prose says "call elem.clear() (and drop processed siblings from the root) so memory stays flat", but both code snippets only call `elem.clear()`. In ElementTree, clearing an element empties its children, yet the root keeps a reference to every cleared (now-empty) element, so the root's child list grows unbounded across the file. On the stated "hundreds of MB" dataset this defeats the reason for streaming. The snippet is what an implementer copies verbatim, so the documented technique gets silently dropped.
- **Fix**: Capture the root element and prune processed siblings — grab `root` from the first event (or `ET.iterparse(...).root`) and call `root.clear()` (or `root.remove(elem)`) after each `produktLeczniczy` end-event. Update both snippets so code matches prose.
  - Strength: Restores true flat memory; matches the documented intent and the canonical ElementTree streaming idiom.
  - Tradeoff: Snippet is slightly less minimal; must hold a root ref.
  - Confidence: HIGH — this is the well-known iterparse memory pitfall.
  - Blind spot: Real peak memory at full-file scale is unmeasured; only Phase 4 confirms.
- **Decision**: FIXED (Fix in plan — both snippets now capture root and call root.clear())

### F4 — TRUNCATE on medication_registry fails due to the cabinet FK

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 3 loader (l.361), Migration Notes (l.483)
- **Detail**: The approach is named "truncate-and-reload" and the loader contract says "TRUNCATE/DELETE FROM medication_registry". Postgres refuses to TRUNCATE a table referenced by a foreign key from another table — `cabinet_entries.medication_registry_id` (cabinet/models.py:21) — even when the referencing table is empty ("cannot truncate a table referenced in a foreign key constraint"). The cabinet-empty guard does not prevent this; only DELETE (which checks actual rows) works. Dry-run won't catch it (no DB); it fails for the first time at the Phase 4 production run.
- **Fix**: Specify `DELETE FROM medication_registry` (not TRUNCATE) in the loader contract and Migration Notes; reserve TRUNCATE … CASCADE only if intentionally cascading, which here would delete cabinet rows and is undesirable.
- **Decision**: FIXED (Fix in plan)

### F5 — "within a transaction" vs "commit per batch" contradiction

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 3 loader overview (l.352) vs contract (l.363)
- **Detail**: The overview says inserts run "in batches within a transaction"; the contract says "commit per batch". These are mutually exclusive. It matters because the delete+reload isn't atomic under per-batch commit: a mid-load failure leaves the registry partially populated. Acceptable for a guarded one-off (re-run truncates and reloads), but the plan should state which it is so the implementer doesn't guess.
- **Fix**: Pick one and state the failure behavior. Recommended: delete + per-batch commit, explicitly noting "a failed run leaves a partial registry; just re-run" — consistent with the truncate-and-reload, re-runnable design.
- **Decision**: FIXED (Fix differently — chose single all-or-none transaction: batched executes of 1000 rows, one commit at the end, rollback-on-failure leaves prior registry intact)

### F6 — NamedTemporaryFile reopen-by-name fails on Windows

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 3 __main__ (l.377-379)
- **Detail**: Plan streams the URL into a NamedTemporaryFile then parses it. On Windows (this project's dev OS), a NamedTemporaryFile cannot be reopened by path while still open, so passing `.name` to iterparse raises PermissionError. The Phase 4 run will likely be launched from Windows.
- **Fix**: Pass the open file object to iterparse, or use `NamedTemporaryFile(delete=False)`, close it, parse by path, then unlink in a finally block.
- **Decision**: FIXED (Fix in plan)

### F7 — "distinct" joins vs exact-string test assertions

- **Severity**: 🔍 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 2 helpers (l.270-275) & tests (l.316)
- **Detail**: `_join_routes/_join_substances/_join_manufacturers` are specified as "distinct … joined", while the tests assert exact strings (e.g. Gensulin R == "domięśniowa, dożylna, podskórna"). A set-based distinct would make ordering non-deterministic and the test flaky.
- **Fix**: Specify order-preserving dedup (e.g. dict.fromkeys) so joins follow XML document order deterministically.
- **Decision**: FIXED (Fix in plan)

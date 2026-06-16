<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Important Category

- **Plan**: context/changes/important-category/plan.md
- **Scope**: Phase 5 of 7
- **Date**: 2026-06-16
- **Verdict**: APPROVED
- **Findings**: 0 critical, 0 warnings, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

## Findings

### F1 — Untracked reference/asset files in working tree

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: reference/*.png, docs/reference/aspirin.xml
- **Detail**: git status shows untracked files (PNG/JPG mockups under `reference/`, `aspirin.xml` under `docs/reference/`). They are NOT part of the Phase 5 commit (42cbb9c) and predate it (dated Jun 12–15) — design assets likely for the Phase 6–7 frontend work, not Phase 5 scope creep. Flagged only for housekeeping awareness.
- **Fix**: Either commit them where appropriate or add to `.gitignore`. Out of scope for this phase.
- **Decision**: SKIPPED (out of phase scope)

## Notes

- All 5 planned changes MATCH: `AddEntryRequest.is_important`/`AddEntryOut.is_important` schemas; `crud.insert_entry` + `update_entry_counts` (single-write merge, no second flush — the plan's stated preference); `service.add_entry` threading with OR semantics `merged_important = existing.is_important or is_important`; `router` pass-through; updated/added tests.
- Subtle correctness point handled: the race-loss re-merge path also carries `is_important` via `merge_kwargs` (service.py:479-486, 511), so a concurrent-insert merge still applies OR semantics.
- `update_entry_counts(..., is_important: bool | None = None)` correctly leaves importance untouched when omitted — safe for future count-only callers (e.g. S-03 decrement).
- Automated success criteria verified passing on 2026-06-16: `uv run pytest tests/cabinet/test_service.py tests/cabinet/test_router.py` (107 passed), `uv run ruff check app/api/v1/cabinet/` (all checks passed), `uv run ruff format --check` (7 files formatted).
- Tests cover OR-merge in both directions plus both-true/both-false (parametrized), fresh-insert-important, and default-false — matches Success Criteria 5.3.
- Lessons compliance: Google-style docstrings updated on every touched signature; no single-letter names (L-005); no new `session.execute`/`flush` introduced (L-004 N/A — reuses existing wrapped `persist`).

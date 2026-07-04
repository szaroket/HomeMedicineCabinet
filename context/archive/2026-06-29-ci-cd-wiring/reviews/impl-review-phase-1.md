<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: CI/CD Wiring (F04)

- **Plan**: context/changes/ci-cd-wiring/plan.md
- **Scope**: Phase 1 of 4 (Backend gate config)
- **Date**: 2026-06-29
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 1 warning, 1 observation

## Verified green locally

- `uv run coverage run -m pytest` → 357 passed; `coverage report` TOTAL 86% (floor 60)
- `uv run ruff check .` / `uv run ruff format --check .` → clean (82 files formatted)
- `pre-commit run check-toml --all-files` → Passed

The `[tool.coverage.run]`, `[tool.coverage.report]`, and `[tool.pyright]` blocks match the Phase 1 contract field-for-field.

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS (N/A — config only) |
| Pattern Consistency | PASS |
| Success Criteria | WARNING |

## Findings

### F1 — pyright gate unverifiable locally; criteria 1.2 / 1.6 not reproducible

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Success Criteria
- **Location**: backend/pyproject.toml:52-56 (verification, not the config)
- **Detail**: `uv run pyright` does not run on this Windows machine. Even `uv run pyright --version` exits 1 producing no output except `OPENSSL_Uplink(...): no OPENSSL_Applink` on stderr — the node binary from `nodejs-wheel-binaries` crashes before pyright starts (a Windows OpenSSL DLL conflict, not a type error). Plan criteria 1.2 ("uv run pyright passes") and 1.6 ("strictest passing typeCheckingMode chosen") are both marked [x] @ ca1ce29 but neither is reproducible here. A piped `... | tail; echo $?` reports 0 (tail's status), the likely trap that made the crash look like a pass. The `[tool.pyright]` config itself is correct and will be genuinely exercised by Phase 2 CI on ubuntu-latest, where this crash won't occur.
- **Fix A ⭐ Recommended**: Treat CI (Phase 2, Linux) as the authoritative pyright gate; note in the plan that local pyright is non-functional on this Windows env and leave 1.2/1.6 to be confirmed by the first Actions run.
  - Strength: Config matches the plan and Linux CI is the real gate; avoids an out-of-scope env fix inside a CI-config change. "basic" mode validated for real on first green Actions run.
  - Tradeoff: No local pre-push type safety net on Windows; "strictest passing mode" (1.6) stays an assumption until CI proves it.
  - Confidence: HIGH — coverage/ruff/toml all verify green; only the node binary is broken, not the config.
  - Blind spot: Haven't confirmed pyright is green on Linux yet (Phase 2).
- **Fix B**: Fix the local crash (use a system Node for pyright instead of the wheel binary, or resolve the OpenSSL Applink) so local verification works.
  - Strength: Restores the local gate the plan's "make gates locally green first" approach assumes.
  - Tradeoff: Environment-specific, may not reproduce across devs, scope creep for a config change.
  - Confidence: MEDIUM — root cause is an env/DLL issue, fix may be fiddly.
  - Blind spot: Whether other contributors hit the same crash.
- **Decision**: DISMISSED — premise is a Git-Bash-nesting artifact. The OpenSSL Applink crash reproduces only when the node wheel binary inherits Git Bash's polluted PATH (its bundled OpenSSL DLLs shadow the required one); it reproduces even via `powershell.exe` launched from the Bash tool. In the user's native PowerShell session (clean PATH) `uv run pyright` runs and passes. Criteria 1.2/1.6 confirmed verified by the user.

### F2 — pyright pythonVersion 3.13 vs project requires-python >=3.12

- **Severity**: 📝 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/pyproject.toml:55 vs :6
- **Detail**: `pythonVersion = "3.13"` while `requires-python = ">=3.12"`. Pyright type-checks assuming 3.13 semantics, so 3.12-incompatible syntax wouldn't be caught for a contributor on 3.12. Plan-conformant (the contract specified "3.13") and CI uses 3.13, so harmless today — just a latent floor/target mismatch.
- **Fix**: Either bump `requires-python` to ">=3.13" to match the real target, or set pyright `pythonVersion` to "3.12" to match the declared floor. Not required for Phase 1.
- **Decision**: FIXED — bumped `requires-python` to ">=3.13" (backend/pyproject.toml:6) to match the real 3.13 target (CI + pyright pythonVersion). No remaining 3.12 references in pyproject.toml.

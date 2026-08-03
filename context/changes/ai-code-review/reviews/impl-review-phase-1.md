<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: AI Code Review Workflow

- **Plan**: `context/changes/ai-code-review/plan.md`
- **Scope**: Phase 1 of 4 — Author the Review Criteria
- **Date**: 2026-08-03
- **Verdict**: APPROVED
- **Findings**: 0 critical, 2 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | PASS |
| Safety & Quality | PASS |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | WARNING |

## Automated verification

| Check | Result |
|---|---|
| 1.1 `.github/review-criteria.md` exists | PASS |
| 1.2 `grep -c '^## '` → 9 (≥5 required) | PASS |
| 1.3 `pre-commit run --files .github/review-criteria.md` | PASS |

Repo-specific claims in the criteria file were spot-checked and all hold:
pyright basic mode (`backend/pyproject.toml:60`), coverage `fail_under = 60`
(`backend/pyproject.toml:52-53`), nullable registry fields
(`backend/app/api/v1/medicines/models.py:12-22`), merge-vs-insert branching
(`backend/app/api/v1/cabinet/service.py:766`), mutating `GET /auth/refresh`
(`backend/app/api/v1/auth/router.py:113`). `rule_reference` is a real `Finding`
field in the action (`src/pr_review_agent/models.py:51`), so that instruction is
valid.

Review was conducted inline rather than via sub-agents: the phase touches one
prose file in one commit, under the skill's ≤3-file budgeting threshold.

## Findings

### F1 — Criteria bodies are ~5× the contracted length

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Plan Adherence
- **Location**: `.github/review-criteria.md` (whole file)
- **Detail**: `plan.md:112` contracts "Keep each body to two or three sentences
  — it is prompt input, not documentation." Actual bodies run 83–230 words each
  (Python Craft 230, Test Quality 203, REST API 199), 1520 words total. The
  action injects this verbatim into the system prompt on every run
  (`agents_context.py:180-203`), so the overrun is a recurring per-PR token cost
  — and `plan.md:62` explicitly declines to tune `model`, `max-turns`, or
  `max-findings` in this change, leaving no compensating lever. `plan.md:328`
  already names per-run spend as the open risk. The content itself is good:
  principle-first, repo specifics used as illustration, and it actively avoids
  restating what CI enforces. The deviation is real but arguably an improvement
  — it needs a recorded decision, not necessarily a rewrite.
- **Fix A ⭐ Recommended**: Amend `plan.md:112` to reflect the length actually
  chosen, with a one-line rationale.
  - Strength: Preserves guidance the user reviewed and approved (1.6 `[x]`);
    keeps the plan usable as ground truth for the Phase 2–4 reviews that follow.
  - Tradeoff: Phase 2 inherits an untested cost assumption; the first real runs
    become the measurement.
  - Confidence: HIGH — content quality verified against the repo; every specific
    claim checks out.
  - Blind spot: No token count or cost estimate for a real PR has been taken, so
    "affordable" is assumed, not measured.
- **Fix B**: Trim each body to the contracted 2–3 sentences.
  - Strength: Honors the plan as written; smallest prompt.
  - Tradeoff: Discards the "why" that makes several criteria actionable (e.g.
    why a spec-less mock keeps passing). Terse criteria produce generic findings
    — the exact failure `plan.md:296` says to watch for.
  - Confidence: MEDIUM — the smoke fixture is terse, but it is a smoke test, not
    a quality benchmark.
  - Blind spot: Haven't measured whether terse criteria actually degrade output
    on this action.
- **Decision**: FIXED via Fix A — `plan.md:112` now contracts "a short paragraph
  — principle first, repo specifics only as illustration", and records that the
  length is deliberate with per-run prompt cost accepted as the trade.

### F2 — Progress annotations cite a commit not on this branch

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: `context/changes/ai-code-review/plan.md:354-362`
- **Detail**: All six Phase 1 items are annotated `— 40ffc62`, but
  `git merge-base --is-ancestor 40ffc62 HEAD` fails: 40ffc62 was amended away
  and the surviving commit is `5678f46`. The annotations are also still
  uncommitted in the working tree, so the sha will not survive to the bootstrap
  PR. The plan convention at `:348` exists so a future reader can find the
  landing commit — as written, they cannot.
- **Fix**: Replace `40ffc62` with `5678f46` on lines 354-362 and commit the plan
  update.
- **Decision**: FIXED — all six Phase 1 annotations now read `5678f46`. Still
  needs to be committed alongside the other plan edits.

### F3 — Nine criteria, each needing a score under default max-turns

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: `.github/review-criteria.md` — 9 `##` headings
- **Detail**: `agents_context.py:206-224` requires one `CriterionScore` per
  criterion, by exact name, in a single `submit_review_verdict` call. Nine axes
  is nearly double the plan's stated minimum of five, and Phase 2 keeps
  `max-turns` at its default of 5. Not a defect — just the concrete thing to
  watch in the Phase 4 live run: a verdict missing scores, or thin scores on the
  later criteria, points here.
- **Fix**: No change now. Add it to what Phase 4 checks in the first post-merge
  run log.
- **Decision**: FIXED — Phase 4 gained a Manual Verification bullet and Progress
  item `4.7` ("The verdict carries all nine criterion scores, none visibly
  thin"); the old `4.7` shifted to `4.8`.

### F4 — Test Quality paraphrases rules already injected verbatim

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: `.github/review-criteria.md:139-140`
- **Detail**: Manual check 1.5 ("no criterion restates the rules-file verbatim")
  is marked `[x]`. The strict verbatim bar is met, but "Reuse the shared
  fixtures rather than rebuilding them inline" sits very close to
  `AGENTS.md:118` "Reuse shared fixtures; never duplicate mocks", and the
  spec-less-mock line shadows `AGENTS.md:119` — both of which the action already
  injects in full as `rules-file`. The criteria file adds rationale AGENTS.md
  lacks, which is the justification for keeping it; flagged so the call is
  deliberate rather than assumed.
- **Fix**: Leave as-is, or cut the two overlapping clauses and let the
  "Repository Rules & Lessons Compliance" criterion carry them.
- **Decision**: SKIPPED — overlap kept deliberately; the added rationale is what
  the criteria file contributes over the injected `rules-file`.

## Note (not a finding)

Untracked `reference/` (12 image files) sits at repo root, unrelated to this
change. Not a Phase 1 artifact, so not a finding — but a `git add -A` before the
bootstrap PR would sweep it in, and `AGENTS.md`'s project tree has no root
`reference/`.

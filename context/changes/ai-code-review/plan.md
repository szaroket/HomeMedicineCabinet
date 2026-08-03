# AI Code Review Workflow Implementation Plan

## Overview

Wire the reusable `szaroket/ai-code-review-action` GitHub Action into this repository so that every pull request targeting `main` or `develop` receives an automated Claude-powered code review, judged against this project's own rules (`AGENTS.md`), standing lessons (`context/foundation/lessons.md`), and a new project-specific criteria file.

The review is **advisory**: it publishes inline PR comments and uploads artifacts, but never blocks a merge and never gates the Render deploy.

## Current State Analysis

**What exists:**

- A single CI workflow, `.github/workflows/ci-cd.yml` (309 lines, 9 jobs): `vulnerability-scan`, `pre-commit`, `backend-tests`, `frontend-build`, `backend-typecheck`, `frontend-unit`, `frontend-typecheck`, `backend-integration`, `frontend-e2e` — all listed in the `deploy` job's `needs:` (`ci-cd.yml:288-297`). Triggers: `push [main, develop]`, `pull_request [main, develop]`, `release [published]`.
- `AGENTS.md` at repo root — hard rules, backend layer rules, frontend structure rules, coding style, testing guidelines. This is exactly the shape the action's `rules-file` input expects, and it is already the input's default value.
- `context/foundation/lessons.md` — seven standing constraints (L-001…L-007) written as "treat as a standing constraint, not a one-off note". A natural fit for the optional `lessons-file` input.
- Repo secrets (via `gh secret list`): `DATABASE_URL`, `E2E_DATABASE_URL`, `E2E_TEST_PASSWORD`, `RENDER_DEPLOY_HOOK_BACKEND`, `RENDER_DEPLOY_HOOK_FRONTEND`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_URL`.

**What's missing:**

- No `.github/review-criteria.md`. The action's `criteria-file` input is **required with no default**; a missing or heading-less file exits `3`.
- No `OPENROUTER_API_KEY` secret. Without it the agent cannot authenticate.
- No workflow references the action at all.

**Key constraints discovered:**

- The GitHub default branch is `develop` (`gh repo view` → `defaultBranchRef.name = "develop"`). The local `origin/HEAD` symbolic ref points at `main` and is stale — do not trust it when choosing a merge target.
- The action repo `szaroket/ai-code-review-action` is PUBLIC and has **no tags**; `origin/main` is at `6e89cd450e9921fed50e5e0c62083c46e6e96084`. SHA-pinning is the only pinning available.
- This repository is PUBLIC, so any published review comment is world-visible.

## Desired End State

A pull request opened against `main` or `develop`:

1. Triggers a new `AI Code Review` workflow run, independent of `CI/CD`.
2. The action reads `.github/review-criteria.md`, `AGENTS.md`, and `context/foundation/lessons.md` **from the PR's base ref**, reviews only changed files under `backend/` and `frontend/` (minus excluded noise), and posts a GitHub review with inline comments.
3. A `review-output` artifact containing the JSON and markdown review is attached to the run, whether or not publishing succeeded.
4. If the review errors for any reason — API outage, rate limit, no verdict — the workflow run still reports success and the PR shows no red X.

Verified by: opening a real PR after this change is merged to `develop` and observing inline comments plus a downloadable artifact.

### Key Discoveries:

- `action.yml:13` — `rules-file` already defaults to `AGENTS.md`, so this repo's root rules file is picked up with no configuration.
- `README.md:30-41` — criteria, rules, and lessons files are read from the **PR's base ref**, not the checkout, so a PR cannot rewrite the rules it is judged by. The practical consequence drives Phase 4: the criteria file must land on `develop` before it can ever be used.
- `README.md:124-129` — a non-empty `ANTHROPIC_API_KEY` **silently takes precedence** over `ANTHROPIC_AUTH_TOKEN`, bypassing the gateway with no error and billing Anthropic directly. Nothing in the action can detect this. This is why Phase 3 includes an explicit check that no `ANTHROPIC_API_KEY` secret exists.
- `action.yml:72` — the composite action runs `astral-sh/setup-uv` itself and `uv sync`s its own project; the consuming workflow needs only `actions/checkout`, no Python/uv setup.
- `README.md:78-80` — `actions/checkout` is **required**; the action resolves file paths relative to the checkout and uses it to decide whether the agent may explore the repository.
- `README.md:150-151` — with the default `GITHUB_TOKEN`, an `APPROVE` verdict is downgraded to a plain `COMMENT`. Expected behavior, not a bug to chase.
- `README.md:153-161` — `pull_request` runs from forks get a read-only token and no secrets, so they cannot publish and have no API key. Documented limitation, not worked around.
- `ci-cd.yml:24` — established repo convention: third-party actions are SHA-pinned with the trailing comment `# SHA-pinned: 3rd-party action (supply-chain); GitHub-owned actions use major tags`. Follow it exactly.
- `ci-cd.yml:274-282` — existing artifact-upload pattern uses `actions/upload-artifact@v4` with `retention-days: 7`. Match it.

## What We're NOT Doing

- **Not** adding the review to `ci-cd.yml` or to the `deploy` job's `needs:` list. The deploy gate stays exactly as it is.
- **Not** setting up direct Anthropic auth (`anthropic-api-key`). Gateway only.
- **Not** using `trust-head-files`. On a public repo it would hand fork authors control of the system prompt.
- **Not** working around the fork-PR secret restriction with `pull_request_target` or a PAT.
- **Not** reviewing `context/`, `docs/`, `.github/`, or root config files — out of `scope-dirs` by decision.
- **Not** adding `workflow_dispatch`. Re-review happens by pushing to the PR branch.
- **Not** modifying the action repo itself. It is consumed as-is at a pinned SHA.
- **Not** tuning `model`, `max-turns`, or `max-findings` away from their defaults (`claude-sonnet-5`, `5`, `30`) in this change. Revisit after real-world runs.

## Implementation Approach

Four sequential phases, ordered so that nothing is committed before the thing it depends on exists:

1. Author the criteria file interactively — it is the only genuinely bespoke artifact, and the workflow is useless without it.
2. Write the workflow that consumes it, plus a discoverability note in `AGENTS.md`.
3. Provision the secret and statically validate the YAML — everything that can be checked without merging.
4. Merge to `develop`, then verify live on the next real PR.

Phases 1–3 are all local file/config work and could in principle be squashed, but keeping the criteria authoring separate is deliberate: it is a judgment-heavy discussion, not a mechanical edit, and it should not be rushed alongside YAML plumbing.

## Critical Implementation Details

**Auth mutual exclusion.** The workflow must pass `anthropic-base-url` and `anthropic-auth-token` and must **not** pass `anthropic-api-key` at all — not even as an empty string with a `${{ secrets.ANTHROPIC_API_KEY }}` expression that resolves to empty. Leaving the input out entirely is the safe form. If an `ANTHROPIC_API_KEY` secret is ever added to this repo for another purpose, this workflow is unaffected only because it never references it.

**Base-ref sequencing.** Because criteria/rules/lessons are read from the base ref, the PR that introduces `.github/review-criteria.md` will itself report the file as missing (exit `3`). This is expected and is precisely why the run is advisory — the red X that would otherwise appear on the bootstrap PR is suppressed. Do not "fix" this by reaching for `trust-head-files`.

**`continue-on-error` placement.** It belongs on the action step, not on the job. Placing it at job level would also swallow a genuine `actions/checkout` failure and would still let the artifact-upload step run against an empty directory.

## Phase 1: Author the Review Criteria

### Overview

Produce `.github/review-criteria.md` with at least five criteria tailored to this project, arrived at through discussion rather than pre-decided. Headings become criterion names; the prose under each becomes the guidance the model receives alongside `AGENTS.md`.

### Changes Required:

#### 1. Criteria discussion

**File**: none (working session)

**Intent**: Before writing anything, walk through candidate criteria with the user and agree on the final set. Ground each candidate in something concrete from this repository — `AGENTS.md`'s hard rules, the backend layer rules, the frontend structure rules, the testing guidelines, and `context/foundation/lessons.md`'s L-001…L-007. Present at least six or seven candidates so there is something to cut, and settle on a minimum of five.

**Contract**: Agreement on the exact `##` heading names and the intent of each, recorded in the conversation before any file is written. Candidate seeds worth putting on the table, each traceable to an existing rule:

- Correctness — does the change do what it claims (universal baseline).
- Repository rules compliance — Polish-only user-facing text (`AGENTS.md` Hard Rules), backend layer boundaries (router → facade → service → crud, no cross-domain service calls), frontend feature-based layout and no barrel files.
- Test coverage & fixture discipline — shared fixtures from `backend/tests/conftest.py` reused rather than duplicated, `spec=`/`autospec=` on every mock (`AGENTS.md` Testing Guidelines).
- Lessons compliance — the standing constraints in `context/foundation/lessons.md`, notably imports at top of file (L-006), no single-letter names (L-005), `SQLAlchemyError` wrapping in crud (L-004).
- Scope discipline — no unrelated drive-by edits.
- Documentation — Google-style docstrings with typed `Args:`/`Returns:`, present where the change needs them.

#### 2. Criteria file

**File**: `.github/review-criteria.md`

**Intent**: Write the agreed criteria to disk in the format the action parses.

**Contract**: A markdown file whose top-level structure is a single `#` title followed by at least five `##` headings, each with a short prose body. Heading text is the criterion name; the body is model guidance. A file with zero `##` headings causes exit `3`. Keep each body to a short paragraph — principle first, repo specifics only as illustration. Bodies run longer than a bare one-liner on purpose: the rationale is what makes a criterion yield a specific finding instead of generic advice, and per-run prompt cost is accepted as the trade (see Performance Considerations).

### Success Criteria:

#### Automated Verification:

- `.github/review-criteria.md` exists
- The file contains at least five `##` headings: `grep -c '^## ' .github/review-criteria.md` returns 5 or more
- Pre-commit passes on the new file: `pre-commit run --files .github/review-criteria.md`

#### Manual Verification:

- Each criterion is traceable to a concrete rule in `AGENTS.md` or `context/foundation/lessons.md`, not generic advice
- No criterion restates something the injected `rules-file` already says verbatim — criteria point at rules, they do not duplicate them
- The user has explicitly approved the final set of headings

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the criteria set is right before proceeding to the next phase. This phase is the one with real judgment in it; do not roll straight into YAML.

---

## Phase 2: Write the Review Workflow

### Overview

Add a standalone workflow that runs the action on pull requests, plus a one-line note in `AGENTS.md` so the workflow is discoverable by future contributors and agents.

### Changes Required:

#### 1. Workflow file

**File**: `.github/workflows/ai-review.yml`

**Intent**: Define a single-job workflow that checks out the repo, runs the pinned action against the PR, and uploads the review artifacts unconditionally.

**Contract**: The workflow's shape, each element decided during planning:

- `name: AI Code Review`
- `on: pull_request: branches: [main, develop]` — default types (`opened`, `synchronize`, `reopened`), mirroring `ci-cd.yml:6-7`
- `permissions: contents: read`, `pull-requests: write` — write is required by `publish`
- One job, `runs-on: ubuntu-latest`
- Step 1: `actions/checkout@v7` — matches the version used throughout `ci-cd.yml`; GitHub-owned, so a major tag is correct per repo convention
- Step 2: `szaroket/ai-code-review-action@6e89cd450e9921fed50e5e0c62083c46e6e96084`, with `continue-on-error: true`, and the trailing pin comment matching `ci-cd.yml:24`'s wording
- Step 3: `actions/upload-artifact@v4` with `if: always()`, `name: review-output`, `path: review-output/`, `retention-days: 7` — matching the pattern at `ci-cd.yml:274-282`

Action inputs:

| Input | Value | Why |
|---|---|---|
| `pr-number` | `${{ github.event.pull_request.number }}` | Required |
| `criteria-file` | `.github/review-criteria.md` | From Phase 1 |
| `rules-file` | `AGENTS.md` | Explicit, though it is also the default |
| `lessons-file` | `context/foundation/lessons.md` | L-001…L-007 as pitfalls input |
| `scope-dirs` | `backend,frontend` | Code only; skips `context/`, `docs/`, `.github/` |
| `exclude` | lockfiles, migrations, generated assets (see below) | Token spend on reviewable code |
| `anthropic-base-url` | `https://openrouter.ai/api` | Gateway route |
| `anthropic-auth-token` | `${{ secrets.OPENROUTER_API_KEY }}` | Gateway route |
| `github-token` | `${{ github.token }}` | Required |
| `publish` | `"true"` | Inline comments |
| `format` | `all` | JSON + markdown artifacts |

`anthropic-api-key` is **omitted entirely** — see Critical Implementation Details.

The `exclude` value is a comma-separated glob list. It must cover at minimum the lockfiles (`**/uv.lock`, `**/package-lock.json`) and Alembic migrations (`backend/migrations/**`, which `AGENTS.md:110` already exempts from docstring rules). Confirm against the repo's actual generated-file set before finalizing.

#### 2. Discoverability note

**File**: `AGENTS.md`

**Intent**: The "Commit & Pull Request Guidelines" section enumerates what CI runs on every PR. Add a sentence noting that a separate advisory AI review workflow also runs and does not gate the deploy, so nobody mistakes its comments for a required check.

**Contract**: One or two sentences appended to the existing CI paragraph in the "Commit & Pull Request Guidelines" section (`AGENTS.md:125`). Do not restructure the section.

### Success Criteria:

#### Automated Verification:

- Workflow file parses as valid YAML: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ai-review.yml'))"`
- The workflow does not reference an Anthropic API key: `grep -i 'anthropic-api-key' .github/workflows/ai-review.yml` returns no match
- The action reference is SHA-pinned, not a branch: `grep 'ai-code-review-action@' .github/workflows/ai-review.yml` shows a 40-character SHA
- Pre-commit passes: `pre-commit run --files .github/workflows/ai-review.yml AGENTS.md`

#### Manual Verification:

- `ci-cd.yml` is untouched — `git diff` shows no changes to it, and the `deploy` job's `needs:` list is unchanged
- `continue-on-error: true` sits on the action step, not on the job
- The `exclude` globs match real paths in this repo (spot-check against `git ls-files`)
- The pin comment matches the wording convention at `ci-cd.yml:24`

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human before proceeding to the next phase.

---

## Phase 3: Provision the Secret and Validate

### Overview

Everything that can be verified without merging: the API secret exists, no conflicting secret exists, and the workflow YAML passes a real Actions linter.

### Changes Required:

#### 1. Repository secret

**File**: none (GitHub repository settings)

**Intent**: Add the OpenRouter API key as a repository secret so the action can authenticate. **This is the user's action, not the agent's** — the key must never pass through a tool call, a file, or the conversation. `AGENTS.md:8` forbids committing secrets, and this rule extends to transcripts.

**Contract**: A repository secret named `OPENROUTER_API_KEY`, matching the `secrets.OPENROUTER_API_KEY` reference in the workflow. The user sets it via the GitHub UI (Settings → Secrets and variables → Actions), or by running `gh secret set OPENROUTER_API_KEY` themselves in their own terminal and pasting the value at the prompt.

#### 2. Auth-conflict check

**File**: none (verification step)

**Intent**: Confirm that no `ANTHROPIC_API_KEY` secret exists in the repository. If one is ever added, it does not affect this workflow — which never references it — but confirming its absence now documents the intent and guards against a future contributor "helpfully" wiring it in.

**Contract**: `gh secret list` output contains `OPENROUTER_API_KEY` and does not contain `ANTHROPIC_API_KEY`.

#### 3. Static workflow lint

**File**: none (verification step)

**Intent**: Catch Actions-specific errors — unknown inputs, bad expression syntax, invalid `permissions` keys — that a plain YAML parse cannot see.

**Contract**: `actionlint` run over `.github/workflows/ai-review.yml` reports no errors. Available via `npx` or as a standalone binary; no repo dependency needs to be added for a one-off run.

### Success Criteria:

#### Automated Verification:

- Secret is present: `gh secret list` includes `OPENROUTER_API_KEY`
- No conflicting secret: `gh secret list` does not include `ANTHROPIC_API_KEY`
- Workflow passes Actions linting: `actionlint .github/workflows/ai-review.yml`

#### Manual Verification:

- The OpenRouter key has credit/quota available and is scoped appropriately
- The secret value was never written to a file, a command line, or this conversation

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human before proceeding to the next phase.

---

## Phase 4: Merge and Verify Live

### Overview

Land the change on `develop`, then confirm end-to-end behavior on the next real pull request. The bootstrap PR itself cannot be reviewed — its criteria file does not yet exist on the base ref.

### Changes Required:

#### 1. Bootstrap PR

**File**: none (git/GitHub workflow)

**Intent**: Open a PR from `feature/ai-code-review` to `develop` carrying the criteria file, the workflow, and the `AGENTS.md` note, and merge it once the existing CI is green.

**Contract**: Target branch is `develop` — GitHub's actual default branch. The `AI Code Review` workflow will trigger on this PR and is expected to fail internally with exit `3` (criteria file not found on base ref); `continue-on-error` renders the job green regardless. Confirm this by reading the run log, not by assuming it. Commit messages follow Conventional Commits per `AGENTS.md:125` — `feat:` or `ci:` prefix.

#### 2. Live verification

**File**: none (observation on the next PR)

**Intent**: On the first PR opened after the merge, confirm every part of the chain actually works.

**Contract**: On that PR's `AI Code Review` run, all of the following hold:

- The run is triggered and completes
- The log shows the criteria file resolved from the base ref (no exit `3`)
- Inline review comments appear on the PR diff, posted under the `github-actions` bot
- A `review-output` artifact is attached, containing `pr-<n>-<timestamp>.json` and `pr-<n>-<timestamp>.md`
- Findings reference files under `backend/`/`frontend/` only — no `context/` or lockfile commentary
- The verdict appears as a `COMMENT`, not `APPROVE` (expected token restriction, `README.md:150-151`)

### Success Criteria:

#### Automated Verification:

- Branch merged to `develop`: `git log origin/develop --oneline` includes the change
- Workflow is registered with GitHub: `gh workflow list` includes `AI Code Review`
- The bootstrap run did not fail the check: `gh run list --workflow=ai-review.yml` shows a success conclusion

#### Manual Verification:

- On the first post-merge PR, inline comments are published on the diff
- The `review-output` artifact downloads and contains both JSON and markdown
- Findings are scoped to `backend/`/`frontend/` and are substantive rather than generic
- The verdict carries one score per criterion — all nine, by exact heading name. Nine axes against a default `max-turns` of `5` is the pressure point: a verdict missing scores, or visibly thin scores on the later criteria, means the budget is too tight and `max-turns` needs revisiting
- The review quality justifies keeping `publish: "true"` on a public repo — if it does not, opening a follow-up change to revert to artifacts-only is the correct response

---

## Testing Strategy

There is no application code in this change, so testing is configuration validation plus one live end-to-end observation.

### Static validation:

- YAML parses (`yaml.safe_load`)
- `actionlint` passes — catches unknown action inputs and bad expressions
- Criteria file has ≥5 `##` headings, the action's own parse requirement
- `grep` assertions that `anthropic-api-key` is absent and the action SHA is pinned

### Integration:

- The bootstrap PR proves the workflow triggers, the secret resolves, and `continue-on-error` suppresses the expected exit `3`.
- The first post-merge PR proves criteria resolution from the base ref, publishing, scoping, and artifact upload.

### Manual testing steps:

1. Open the bootstrap PR against `develop`; confirm `AI Code Review` appears in the checks list and reports success.
2. Open its run log; confirm the failure reason is the missing criteria file on the base ref, not an auth error. An auth error here means the secret is wrong and must be fixed before merging.
3. Merge to `develop`.
4. Open any subsequent PR touching a `backend/` or `frontend/` file; confirm inline comments appear.
5. Download the `review-output` artifact; confirm both JSON and markdown are present.
6. Confirm no findings reference `context/`, `docs/`, or a lockfile.

## Performance Considerations

Each PR push triggers a run, and each run is a paid model call. A 10-commit PR is roughly 10 reviews. Cost levers, in order of bluntness: narrow `scope-dirs`, drop `synchronize` from the trigger types, lower `max-turns` from its default of `5`. None are applied in this change — revisit once real spend is observable.

Runtime is dominated by `uv sync` of the action's own project plus the agent loop; expect a few minutes. Because the workflow is independent of `ci-cd.yml`, it adds nothing to the critical path of the deploy gate.

## Migration Notes

No data or schema changes. Rollback is deleting `.github/workflows/ai-review.yml` — the workflow disappears from the checks list on the next PR, and nothing else in CI is affected. `.github/review-criteria.md` is inert on its own and can be left in place.

## References

- Action README: `D:\szkolenia\10xdevs\ai-code-review-action\README.md`
- Action interface: `D:\szkolenia\10xdevs\ai-code-review-action\action.yml`
- Example criteria file: `D:\szkolenia\10xdevs\ai-code-review-action\tests\fixtures\smoke-criteria.md`
- Existing CI conventions: `.github/workflows/ci-cd.yml:24` (SHA-pinning), `:274-282` (artifact upload)
- Repository rules injected as `rules-file`: `AGENTS.md`
- Standing constraints injected as `lessons-file`: `context/foundation/lessons.md`
- Plan brief: `context/changes/ai-code-review/plan-brief.md`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles.

### Phase 1: Author the Review Criteria

#### Automated

- [x] 1.1 `.github/review-criteria.md` exists — 5678f46
- [x] 1.2 The file contains at least five `##` headings — 5678f46
- [x] 1.3 Pre-commit passes on the new file — 5678f46

#### Manual

- [x] 1.4 Each criterion is traceable to a concrete rule in `AGENTS.md` or `lessons.md` — 5678f46
- [x] 1.5 No criterion duplicates the injected rules-file verbatim — 5678f46
- [x] 1.6 The user has explicitly approved the final set of headings — 5678f46

### Phase 2: Write the Review Workflow

#### Automated

- [x] 2.1 Workflow file parses as valid YAML — db60770
- [x] 2.2 The workflow does not reference an Anthropic API key — db60770
- [x] 2.3 The action reference is SHA-pinned, not a branch — db60770
- [x] 2.4 Pre-commit passes on the workflow and `AGENTS.md` — db60770

#### Manual

- [x] 2.5 `ci-cd.yml` is untouched and the deploy gate is unchanged — db60770
- [x] 2.6 `continue-on-error: true` sits on the action step, not the job — db60770
- [x] 2.7 The `exclude` globs match real paths in this repo — db60770
- [x] 2.8 The pin comment matches the convention at `ci-cd.yml:24` — db60770

### Phase 3: Provision the Secret and Validate

#### Automated

- [x] 3.1 `gh secret list` includes `OPENROUTER_API_KEY` — 892218e
- [x] 3.2 `gh secret list` does not include `ANTHROPIC_API_KEY` — 892218e
- [x] 3.3 `actionlint` passes on the workflow — 892218e

#### Manual

- [x] 3.4 The OpenRouter key has credit/quota available — 892218e
- [x] 3.5 The secret value was never written to a file, command line, or conversation — 892218e

### Phase 4: Merge and Verify Live

#### Automated

- [x] 4.1 Branch merged to `develop` — 6efba5f
- [x] 4.2 `gh workflow list` includes `AI Code Review`
- [x] 4.3 The bootstrap run shows a success conclusion

#### Manual

- [ ] 4.4 Inline comments are published on the first post-merge PR
- [ ] 4.5 The `review-output` artifact contains both JSON and markdown
- [ ] 4.6 Findings are scoped to `backend/`/`frontend/` and are substantive
- [ ] 4.7 The verdict carries all nine criterion scores, none visibly thin
- [ ] 4.8 Review quality justifies keeping `publish: "true"` on a public repo

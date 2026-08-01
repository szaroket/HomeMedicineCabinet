# AI Code Review Workflow — Plan Brief

> Full plan: `context/changes/ai-code-review/plan.md`

## What & Why

Wire the reusable `szaroket/ai-code-review-action` into this repository so every PR targeting `main` or `develop` gets an automated Claude review judged against this project's own rules. The action supplies the diff, agent loop, deduplication, and publishing; we supply the criteria and the wiring. `AGENTS.md` and `context/foundation/lessons.md` already exist in exactly the shape the action wants — they become the rules and lessons inputs with no rewriting.

## Starting Point

CI today is one file, `.github/workflows/ci-cd.yml` — nine jobs, all gating a Render deploy on release. Nothing references the action. Three prerequisites are missing: `.github/review-criteria.md` (the action's `criteria-file` input is required with no default), an `OPENROUTER_API_KEY` repository secret, and the workflow itself. The action repo has no tags, so pinning means pinning `origin/main`'s SHA.

## Desired End State

A PR against `main`/`develop` triggers a standalone `AI Code Review` run that reviews only changed files under `backend/` and `frontend/`, posts inline comments on the diff, and attaches a `review-output` artifact containing JSON and markdown. If the review errors — API outage, rate limit, no verdict — the run still reports success and the PR shows no red X. The existing deploy gate is untouched.

## Key Decisions Made

| Decision | Choice | Why |
|---|---|---|
| Placement | Separate `ai-review.yml`, not a job in `ci-cd.yml` | A flaky or expensive AI review can never block a release |
| Auth route | OpenRouter gateway (`base-url` + `auth-token`) | Reuses an existing OpenRouter balance; `anthropic-api-key` omitted entirely |
| Publishing | `publish: "true"` **and** artifacts with `if: always()` | Comments land where they're read; artifacts survive a failed publish (exit 6) |
| Scope | `scope-dirs: backend,frontend` + exclude lockfiles/migrations | Spends tokens on reviewable code, not `context/` planning prose |
| Trigger | `pull_request` on `[main, develop]`, default types | Mirrors `ci-cd.yml`'s existing filter exactly |
| Failure handling | `continue-on-error: true` on the action step | Upstream API flakiness must not train the team to ignore red checks |
| Bootstrap | Merge to `develop` first, verify on the next real PR | No trust-model compromise; `trust-head-files` is unsafe on a public repo |
| Criteria authoring | Its own phase, decided interactively | Judgment-heavy; should not be rushed alongside YAML plumbing |
| Pinning | SHA `6e89cd45…` with the repo's standard pin comment | Follows the convention established at `ci-cd.yml:24` |

## Scope

**In scope:** `.github/review-criteria.md` (≥5 project-specific criteria), `.github/workflows/ai-review.yml`, a discoverability note in `AGENTS.md`, the `OPENROUTER_API_KEY` secret, and live verification on the first post-merge PR.

**Out of scope:** touching `ci-cd.yml` or the deploy gate; direct Anthropic auth; `trust-head-files`; fork-PR workarounds (`pull_request_target`, PATs); reviewing `context/`, `docs/`, or `.github/`; `workflow_dispatch`; tuning `model`/`max-turns`/`max-findings`; any change to the action repo.

## Architecture / Approach

One job: `actions/checkout@v7` → the pinned action (`continue-on-error: true`) → `actions/upload-artifact@v4` (`if: always()`). Permissions are `contents: read` + `pull-requests: write`. The action runs `setup-uv` and installs its own project internally, so the consuming workflow needs no Python or Node setup. Critically, the action reads criteria/rules/lessons from the **PR's base ref**, not the checkout — a PR cannot rewrite the rules it is judged by, which is what drives the merge-first sequencing.

## Phases at a Glance

| Phase | What it delivers | Key risk |
|---|---|---|
| 1. Author criteria | `.github/review-criteria.md`, ≥5 criteria agreed interactively | Generic criteria that duplicate `AGENTS.md` instead of pointing at it |
| 2. Write workflow | `ai-review.yml` + `AGENTS.md` note | Accidentally passing `anthropic-api-key`, which silently bypasses the gateway |
| 3. Secret & validate | `OPENROUTER_API_KEY` set; `actionlint` clean | Secret leaking into a file, command line, or transcript |
| 4. Merge & verify | Live proof on the first post-merge PR | Review quality too noisy to justify publishing on a public repo |

**Prerequisites:** an OpenRouter account with credit; repo admin rights to add a secret; the action repo staying public at the pinned SHA.
**Estimated effort:** ~1 session for phases 1–3, plus one calendar wait for a real PR to verify phase 4.

## Open Risks & Assumptions

- **The gateway precedence trap is undetectable at runtime.** A non-empty `ANTHROPIC_API_KEY` silently overrides `ANTHROPIC_AUTH_TOKEN` — no error, and the bill goes to Anthropic. Mitigated by omitting the input entirely, not by setting it empty.
- **This is a public repo, so every published finding is world-visible** under the `github-actions` bot identity, including wrong ones. Phase 4 explicitly re-evaluates whether `publish: "true"` earns its keep.
- **The bootstrap PR cannot review itself** — its criteria file is not on the base ref, so it exits `3`. Expected, and suppressed by `continue-on-error`. Do not mistake this for a broken config, and do not "fix" it with `trust-head-files`.
- **Fork PRs get a read-only token and no secrets**, so they cannot be reviewed at all. A GitHub restriction, documented rather than worked around.
- **Cost scales with pushes, not PRs** — `synchronize` means a 10-commit PR is ~10 paid runs. Left unaddressed until real spend is observable.
- **GitHub's default branch is `develop`**, though local `origin/HEAD` still points at `main`. The stale ref must not drive the merge target.

## Success Criteria (Summary)

- A PR against `main`/`develop` gets inline AI review comments citing this project's actual conventions, not generic advice.
- A `review-output` artifact with JSON and markdown is attached to every run, including failed ones.
- No AI-review failure has ever blocked a merge or a deploy.

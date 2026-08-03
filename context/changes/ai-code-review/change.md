---
change_id: ai-code-review
title: AI code review
status: implementing
created: 2026-08-01
updated: 2026-08-03
archived_at: null
---

## Notes

<!-- Free-form notes for this change: links, ad-hoc context, decisions that don't belong in research/frame/plan. -->

**2026-08-03 — Design deviation from Phase 4's `continue-on-error` rationale.** PR #58
(https://github.com/szaroket/HomeMedicineCabinet/pull/58) hit a genuine action failure
(`Reached maximum number of turns (5)`, exit 1, no review produced, no artifact
uploaded) and the `AI Code Review` check still reported SUCCESS because
`continue-on-error: true` sat on the action step. The plan's "Critical Implementation
Details" section designed that flag specifically so a genuine error would still show
green — intended to cover the one-time bootstrap-PR exit-3 case (missing criteria file
on base ref), but it also silently swallowed real crashes going forward, which is worse
than no review: a hidden failure looks identical to a clean pass.

Decision (user-directed): removed `continue-on-error: true` from
`.github/workflows/ai-review.yml`. The action step now fails the `AI Code Review` check
on any error; `actions/upload-artifact` still runs via `if: always()`. This workflow is
still not in `ci-cd.yml`'s `deploy` job `needs:`, so it cannot block merge/deploy — it
only makes failures visible on the PR instead of hiding them.

Also bumped `max-turns` from the action's default of `5` to `15` in the same workflow —
PR #58's 57-file diff exhausted the 5-turn budget in ~5 minutes. This deliberately
revisits the "Not tuning `max-turns`... in this change" note in the plan's "What We're
NOT Doing" section, now that real-world spend/behavior is observable (Performance
Considerations already anticipated this revisit).

Separately, filed and fixed the root cause upstream in `ai-code-review-action`
(PR #11, https://github.com/szaroket/AICodeReviewAction/pull/11, branch
`fix/publish-on-mid-run-sdk-failure`, targets `main`): the SDK's control loop raises a
bare `Exception` for an in-run error result (max-turns, etc.) rather than a
`ClaudeSDKError` subclass, which crashed `run_review` before `cli.py`'s exit-code
contract ever saw the failure. Fixed in `run_review` (commit 2dae104): the mid-loop
exception is now caught and returned as `sdk_success=False` with whatever the collector
gathered, instead of propagating and crashing the whole CLI.

The first version of this fix also made the failure branch of `cli.py` best-effort
`post_review` an "incomplete-run" summary. Reverted that part (commit 0d4bc45) after
seeing it live on PR #11's own dogfood self-test: an `=== INCOMPLETE — NO VERDICT
PRODUCED === / No findings.` comment reads ambiguously next to a genuine clean-pass
comment (which also says "No findings." when nothing needs fixing, just with a `##
Review Criteria` block above it). Decision (user-directed): a PR comment is only ever
one of two shapes — clean pass (verdict + per-criterion scores) or one with findings to
fix. A crashed/incomplete run is neither and must never publish; it only fails the check
(exit 4/5), with the JSON artifact already written for debugging. Also bumped
`self-test.yml`'s dogfood job to `max-turns: 15` (same value as the consuming workflow)
so PR #11 stops tripping the same max-turns wall reviewing its own diff.

Once PR #11 merges and the consuming workflow's pinned SHA is bumped, a future max-turns
exhaustion will fail the check cleanly (no uncaught traceback, no PR comment) instead of
silently reporting green like PR #58 did.

# Backend Logging — Plan Brief

> Full plan: `context/changes/backend-logging/plan.md`

## What & Why

Complete and harden the backend logging foundation (roadmap slice F-05) so the FastAPI app has consistent, structured, secret-safe logs. The motivation is observability — faster debugging across every slice — and closing a real security gap: a live PII leak that logs user emails. Output stays terminal-only (no files).

## Starting Point

A partial base already exists: `app/core/logging_config.py` has a correlation-id filter, UTC timestamps, a `module:func:line` format, and `dictConfig` wiring; CRUD-layer error logging is consistent (lesson L-004); there are no `print()` calls in the app. What's missing: env-switchable JSON/console output, log config in `Settings`, request duration in access logs, redaction of secrets/PII, and a fix for the email leak at `supabase_auth.py:101`.

## Desired End State

`configure_logging()` emits readable console logs in dev and JSON in deployed envs (selected from `Settings`), terminal-only. A central redaction filter scrubs emails, tokens, and password values from every record. Each request logs one INFO access line with method, path, status, and `duration_ms`. Service-layer levels are consistent, and the standalone scripts + alembic share the same config.

## Key Decisions Made

| Decision               | Choice                                              | Why (1 sentence)                                                        | Source |
| ---------------------- | -------------------------------------------------- | ---------------------------------------------------------------------- | ------ |
| Library                | Extend stdlib `logging`, terminal-only (no file)   | Zero new deps; builds on a working base the team knows.                | Plan   |
| Output format          | JSON in deployed, console in dev (switchable)       | Readable locally, machine-parseable on Render; matches roadmap default. | Plan   |
| Secrets/PII            | Redaction filter + convention + fix offenders       | Defense-in-depth, testable, fixes the known email leak.                | Plan   |
| Config wiring          | Add log fields to `Settings` in `config.py`         | Honors the documented single-source-of-truth rule.                     | Plan   |
| Access logging         | One INFO line per request with `duration_ms`        | Meets the observability outcome; visible at the INFO default.          | Plan   |
| Service/CRUD coverage  | Standardize levels + fill obvious gaps              | Consistency without entry/exit log spam; CRUD already covered (L-004).  | Plan   |
| Testing                | Redaction unit test only                            | The one security gate (test-plan §4); rest is brittle/framework.       | Plan   |
| Scripts/alembic        | Include them in the standardization                 | Uniform logging across the whole backend.                             | Plan   |

## Scope

**In scope:** env-switchable JSON/console output, log config in `Settings`, redaction filter + unit test, email-leak fix, timed INFO access line, service-layer level consistency, scripts + alembic alignment.

**Out of scope:** Sentry/error tracking, log shipping/file handlers, `structlog`, middleware/format/level tests, full per-domain entry/exit audit, frontend logging, changes to the test/risk strategy.

## Architecture / Approach

Extend the existing `dictConfig` setup: add a JSON formatter beside the console one and select between them in `configure_logging()` from a `Settings` flag (single StreamHandler, terminal-only). Add a `_RedactionFilter` next to `_CorrelationIdFilter`, attached to the handler so redaction is centralized and unavoidable — it renders the final message (covering `%s` args) and scrubs email/token/password patterns. Fix the known leak at the call site. Replace the DEBUG request/response pair with one timed INFO access line. Finally point scripts + alembic at the same config.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Central foundation + redaction | Config fields, JSON/console switch, redaction filter + its unit test | Import-time ordering of `Settings` vs `configure_logging()` |
| 2. Access logging | One timed INFO line per request | Middleware timing/regression on existing tests |
| 3. Apply + fix PII | Email-leak fix, redaction wired, service-level consistency | Avoiding log spam while filling gaps |
| 4. Scripts + alembic | Uniform config across tooling | DB-touching script runs need PowerShell (L-001) |

**Prerequisites:** F-01 (app factory/middleware seam) and F-02 (DB/session layer) — both done.
**Estimated effort:** ~2 sessions across 4 phases; small, centralised, additive diff.

## Open Risks & Assumptions

- Redaction patterns can't guarantee 100% coverage; the filter is defense-in-depth on top of the "never log PII" convention.
- `configure_logging()` runs at import time — `Settings` must be readable then (it is; `settings` is a module-level singleton with no circular dependency).
- DB-touching script/alembic verification must run from native PowerShell, not the Bash tool (lesson L-001).

## Success Criteria (Summary)

- `uv run pytest` green, including the redaction unit test.
- Dev server shows readable console + one INFO access line per request; deployed selector emits JSON; no email/token/password appears in any line.
- A failed sign-in logs a warning with no email present.

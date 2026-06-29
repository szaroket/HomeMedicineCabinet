# Backend Logging Implementation Plan

## Overview

Complete and harden the backend logging foundation for the FastAPI app. A partial base already exists (central `dictConfig`, correlation-id filter, UTC timestamps, consistent CRUD-level error logging). This change closes the gaps required by roadmap slice **F-05**: env-switchable JSON/console output, log-level config wired through `Settings`, a central redaction filter for secrets/PII (and a fix for the live email leak), one structured access-log line per request with duration, consistent service-layer levels, and bringing the standalone scripts + alembic onto the same config. Output is **terminal/StreamHandler only — no file logging**.

## Current State Analysis

What exists today:

- **Central config** — `backend/app/core/logging_config.py` defines `_CorrelationIdFilter`, a `module:func:line | message` format, `LOGGING_CONFIG` (`dictConfig`), and `configure_logging()` which also forces UTC (`logging.Formatter.converter = gmtime`). A single `console` StreamHandler is wired.
- **Startup wiring** — `configure_logging()` runs at import time in `backend/app/main.py:18`; `correlation_id_var` / `generate_correlation_id` live in `logging_config.py`.
- **Correlation-id middleware** — `main.py:47-58` reads/sets `X-Correlation-ID` and logs request + response, but **only at `DEBUG`** (invisible at the `INFO` root default) and **without request duration**.
- **CRUD error logging** — `cabinet/crud.py`, `users/crud.py`, `medicines/crud.py` all `logger.error(..., exc_info=True)` and raise domain errors, per lesson **L-004**. This is consistent and does not need rework.
- **Service-layer logging** — thin: `auth/service.py` (7 calls), `cabinet/service.py` (1). Other services have none.
- **No `print()`** anywhere in `backend/app/` — the "remove ad-hoc output" goal is already met for the app.
- **Standalone scripts** — `scripts/registry_import/__main__.py:122` calls its own `logging.basicConfig(level=INFO, format="%(message)s")`; `parser.py`/`loader.py` use module loggers. `alembic.ini` carries its own `[loggers]` config and `migrations/env.py` uses `fileConfig`.
- **Config** — `backend/app/core/config.py` `Settings` has **no** logging fields (no level, no format/environment switch).

Key gaps vs. the F-05 outcome:

1. **PII leak (live):** `backend/app/db/supabase_auth.py:101` logs the user's `email` directly (`logger.warning("Supabase sign_in failed for %s: %s", email, e)`). No redaction exists.
2. **No format switch:** console-only; roadmap wants JSON in deployed envs, console in dev, switchable via config.
3. **No log config in `Settings`:** level and format are not env-driven.
4. **Access logging weak:** DEBUG-only, no duration.

## Desired End State

Structured logging is configured end-to-end across the FastAPI backend, terminal-only:

- `configure_logging()` emits **human-readable console** logs in local dev and **JSON** logs in deployed environments, selected from `Settings`. Log level is also config-driven.
- A central **redaction filter** scrubs secrets/PII (email addresses, bearer/JWT tokens, password-like values) from every emitted record on both console and JSON handlers; it has a parametrized unit test.
- The `supabase_auth.py` email leak is fixed at the call site (defense-in-depth: filter also catches it).
- Each request produces **one INFO access line** with method, path, status, `duration_ms`, and correlation id.
- Service-layer logging uses consistent levels (DEBUG/INFO/WARNING/ERROR); obvious gaps are filled without entry/exit spam.
- `scripts/registry_import` and `alembic` logging route through the same central configuration/redaction (scripts run outside the request lifecycle — no correlation id required there).

Verify: `uv run pytest` green (incl. the redaction test); running the dev server emits readable console lines with a per-request INFO access line; setting the environment to a deployed value emits JSON; no email/token/password appears in any emitted line.

### Key Discoveries:

- Central config already exists — extend it, don't rebuild: `backend/app/core/logging_config.py:32` (`LOGGING_CONFIG`).
- Live PII leak to fix: `backend/app/db/supabase_auth.py:101`.
- `configure_logging()` runs at **import time** (`main.py:18`), so `Settings` must be importable/instantiated before it — `settings` is already a module-level singleton in `config.py:45`, imported lazily elsewhere; importing it at the top of `logging_config.py` is safe (no circular dependency: `config.py` imports only `pydantic_settings`).
- Existing spy-logger test pattern to mirror: `backend/tests/cabinet/test_service.py:820` (`mocker.patch(..., autospec=True)`).
- Test fixtures available: `mock_session`, `fake_user`, `client`, `authed_client` in `backend/tests/conftest.py`.
- Lessons that constrain this change: **L-004** (CRUD `try/except SQLAlchemyError` + `logger.error(exc_info=True)` — already satisfied, don't disturb), **L-005** (no single-letter names — note `supabase_auth.py` uses `e`; when touching line 101, do not propagate `e`, but renaming all `e`→`exc` in that file is out of scope unless trivially local to the edited block), **L-006** (all imports at top of file).

## What We're NOT Doing

- No error-tracking integration (Sentry) — parked per roadmap F-05.
- No log shipping / drains / file handlers — terminal output only (explicit user decision).
- No `structlog` or other logging library — extend the existing stdlib `logging` setup (user decision).
- No middleware/format/level unit tests and no manual-only sign-off as the gate — the **only** automated logging test is the redaction filter unit test (user decision: "redaction tests only").
- No full per-domain entry/exit logging audit — standardize levels and fill obvious gaps only.
- No frontend logging changes.
- No change to the risk strategy or quality-gate definitions (that is `/10x-test-plan`).

## Implementation Approach

Extend the existing `dictConfig`-based setup rather than introducing a new library. Add two formatters (`console`, `json`) and select between them in `configure_logging()` based on a `Settings`-driven environment/format flag; keep the single StreamHandler (terminal-only). Add a `_RedactionFilter` alongside the existing `_CorrelationIdFilter` and attach both to the handler so redaction is centralized and unavoidable. Fix the known PII call site directly. Replace the request/response DEBUG pair with a single timed INFO access line. Finally, point the standalone scripts and alembic at the same configuration.

## Critical Implementation Details

- **Redaction must operate on the final rendered message.** Log calls pass PII via `%s` args (e.g. `"...for %s", email`), so a filter that only inspects `record.msg` misses the args. The filter should render `record.getMessage()`, regex-scrub it, assign the scrubbed string to `record.msg`, and clear `record.args` — so both console and JSON handlers receive already-redacted text. Cover email, `Bearer <token>` / JWT-shaped strings, and `password`-keyed values.
- **Import-time ordering.** `configure_logging()` is called at module import in `main.py`. Reading `settings` inside `configure_logging()` (not at `logging_config` import top, to avoid forcing settings instantiation on every import of the module) keeps startup robust; `settings` is already instantiated at `config.py` import.

## Phase 1: Central logging foundation + redaction

### Overview

Make output format and level config-driven, add the redaction filter as the security gate, and cover it with the one unit test. Terminal-only.

### Changes Required:

#### 1. Settings — logging configuration fields

**File**: `backend/app/core/config.py`

**Intent**: Make log level and output format env-driven, honoring the "config.py is the single source of truth" rule.

**Contract**: Add fields to `Settings`: `log_level: str = "INFO"` and an environment/format selector (e.g. `environment: str = "local"` or `log_format: Literal["console", "json"] = "console"`). Document them in the class docstring (Google style, parenthesised types, per AGENTS.md). Deployed environments set the env var to produce JSON.

#### 2. JSON formatter + redaction filter + env switch

**File**: `backend/app/core/logging_config.py`

**Intent**: Add a JSON formatter, a redaction filter, and select console-vs-JSON from settings — without adding a file handler.

**Contract**:
- Add a `_JsonFormatter(logging.Formatter)` (or a `format`-style JSON dict serialization) emitting at minimum `timestamp` (UTC), `level`, `correlation_id`, `logger`/`module:func:line`, and `message`.
- Add `_RedactionFilter(logging.Filter)` that renders `record.getMessage()`, scrubs email/token/password patterns, sets `record.msg` to the scrubbed text, and clears `record.args`. Returns `True` always.
- Register both formatters in `LOGGING_CONFIG["formatters"]` and add `redaction` to `LOGGING_CONFIG["filters"]`; attach `["correlation_id", "redaction"]` to the `console` handler. Keep a single StreamHandler.
- In `configure_logging()`, read `settings.log_level` and the format selector; set the handler/root level and pick the active formatter before `dictConfig`. Keep the existing UTC `converter` line.

**Contract (redaction filter — non-obvious patterns)**:

```python
# email, bearer/JWT tokens, password-keyed values — illustrative, refine in impl
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_TOKEN = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+")
_PASSWORD = re.compile(r"(?i)(password['\"]?\s*[:=]\s*)\S+")
```

#### 3. Redaction filter unit test

**File**: `backend/tests/core/test_logging_config.py` (new; create `backend/tests/core/__init__.py` if absent)

**Intent**: Lock the security-critical redaction behavior — the one logging test we keep (test-plan §4 gate).

**Contract**: `pytest.mark.parametrize` over inputs containing an email, a `Bearer <token>`, and a `password=...` value (passed both inline in the message and via `%s` args), asserting the scrubbed output contains no raw secret and preserves surrounding text. Use named args when calling with 3+ arguments (test-style conventions). Mirror imports-at-top (L-006).

### Success Criteria:

#### Automated Verification:

- Linting passes: `cd backend && uv run ruff check . && uv run ruff format --check .`
- Redaction unit test passes: `cd backend && uv run pytest tests/core/test_logging_config.py`
- Full backend suite passes: `cd backend && uv run pytest`

#### Manual Verification:

- With local settings, console output is human-readable and unchanged in spirit (format + correlation id).
- Setting the environment/format selector to the deployed value produces JSON lines on stdout.
- A log line containing an email or `Bearer <token>` is emitted with the secret scrubbed.

**Implementation Note**: After this phase and all automated verification passes, pause for manual confirmation before Phase 2.

**Addendum (2026-06-29, impl-review F1)**: Phase 1 also rerouted the `uvicorn.access` logger onto the central console handler (own handler, level INFO, `propagate: False`) so uvicorn's access lines pass through the same format + redaction. This was not in the original Phase 1 contract — kept because it puts access lines behind redaction, which the security goal wants. **Phase 2 must account for this**: when adding the access-logging middleware, ensure app middleware and `uvicorn.access` do not both emit a line per request (avoid duplicate access logging).

---

## Phase 2: Request/response access logging

### Overview

Replace the DEBUG request/response pair with a single INFO access line that includes request duration, so deployed (INFO-default) environments get one structured access record per request.

### Changes Required:

#### 1. Access-logging middleware

**File**: `backend/app/main.py`

**Intent**: Emit one timed INFO line per request, preserving correlation-id propagation.

**Contract**: In `correlation_id_middleware`, time around `await call_next(request)` (use `time.perf_counter()`), then `logger.info` a single line with method, path, `response.status_code`, and `duration_ms`. Keep setting/resetting `correlation_id_var` and the `X-Correlation-ID` response header. Remove the two `logger.debug` request/response lines. Consider leaving health-check noise at DEBUG only if it proves noisy (optional, not required).

### Success Criteria:

#### Automated Verification:

- Linting passes: `cd backend && uv run ruff check . && uv run ruff format --check .`
- Full backend suite passes (no regressions from middleware change): `cd backend && uv run pytest`

#### Manual Verification:

- Each request to the running dev server logs exactly one INFO access line with method, path, status, and a plausible `duration_ms`.
- The `X-Correlation-ID` response header is still present and matches the logged correlation id.

**Implementation Note**: Pause for manual confirmation before Phase 3.

---

## Phase 3: Apply across the app + fix PII leak

### Overview

Fix the live email leak, confirm the redaction filter covers the auth handlers, and standardize service-layer log levels, filling obvious gaps without entry/exit spam. CRUD layer already satisfies L-004 and is left as-is.

### Changes Required:

#### 1. Fix the Supabase sign-in PII leak

**File**: `backend/app/db/supabase_auth.py`

**Intent**: Stop logging the raw user email; rely on the error context instead.

**Contract**: At line 101, remove `email` from the log args (log the failure without the address, e.g. include `e.code`/status as in `sign_up`). Do not introduce single-letter names in the edited block (L-005); the broader `e`→`exc` rename across the file is out of scope.

#### 2. Standardize service-layer logging

**Files**: `backend/app/api/v1/<domain>/service.py` (cabinet, users, medicines, auth as needed)

**Intent**: Apply consistent levels at service boundaries and fill obvious gaps (key business events at INFO, recoverable anomalies at WARNING), without logging every function entry/exit.

**Contract**: Where a service already logs, normalize the level to the convention. Add a small number of meaningful INFO/WARNING logs where a domain currently has none and a notable event occurs. No new dependencies; reuse the module `logger = logging.getLogger("app.<domain>.service")` pattern already used elsewhere.

### Success Criteria:

#### Automated Verification:

- Linting passes: `cd backend && uv run ruff check . && uv run ruff format --check .`
- Full backend suite passes: `cd backend && uv run pytest`
- No `email`/token logged in auth path: grep shows `supabase_auth.py` no longer passes `email` to a log call.

#### Manual Verification:

- A failed sign-in logs a warning with no email address present.
- Service-layer logs read consistently across domains at the expected levels.

**Implementation Note**: Pause for manual confirmation before Phase 4.

---

## Phase 4: Scripts + alembic alignment

### Overview

Bring the standalone tooling onto the same central configuration so logging is uniform across the backend (user decision: include scripts + alembic).

### Changes Required:

#### 1. Route registry_import through central config

**File**: `backend/scripts/registry_import/__main__.py`

**Intent**: Replace the script's ad-hoc `basicConfig` with the app's `configure_logging()` + redaction, while accepting that correlation ids are request-scoped and won't apply here.

**Contract**: At `main()` startup (line ~122), call `configure_logging()` instead of `logging.basicConfig(...)`. The script's module loggers (`registry_import`, `parser`, `loader`) then inherit the central handler/format/redaction. Verify the script still runs as `python -m scripts.registry_import` and that DB-touching runs follow L-001 (PowerShell, not the Bash tool).

#### 2. Align alembic logging

**Files**: `backend/alembic.ini`, `backend/migrations/env.py`

**Intent**: Make alembic logging consistent with the app convention (level/handler), without forcing JSON on migration tooling.

**Contract**: Adjust the `[loggers]`/`[handlers]` levels in `alembic.ini` to match the app's level convention; leave `fileConfig(config.config_file_name)` wiring in `env.py` intact unless a conflict surfaces. Keep migrations exempt from docstring rules (AGENTS.md).

### Success Criteria:

#### Automated Verification:

- Linting passes: `cd backend && uv run ruff check . && uv run ruff format --check .`
- Full backend suite passes: `cd backend && uv run pytest`

#### Manual Verification:

- `python -m scripts.registry_import --dry-run <source>` emits logs in the central format with secrets redacted (run from PowerShell if it touches the DB, per L-001).
- An `alembic` invocation (e.g. `alembic history`) logs at the aligned level without errors.

**Implementation Note**: Final phase — confirm full manual verification before closing the change.

---

## Testing Strategy

### Unit Tests:

- Redaction filter (`tests/core/test_logging_config.py`): parametrized over email, bearer/JWT token, and password-keyed inputs — supplied both inline and via `%s` args — asserting secrets are scrubbed and surrounding text preserved. This is the sole automated logging test (test-plan §4 gate).

### Integration Tests:

- None added for logging (user decision). Existing suite must stay green after the middleware and service-layer changes.

### Manual Testing Steps:

1. Run the dev server locally; confirm console format + one INFO access line per request with `duration_ms`.
2. Flip the environment/format selector to the deployed value; confirm JSON output on stdout, terminal-only (no file created).
3. Trigger a failed sign-in; confirm the warning contains no email.
4. Emit a line containing `Bearer <token>`; confirm it is redacted.
5. Run `scripts/registry_import --dry-run`; confirm central format + redaction.

## Performance Considerations

Redaction runs a few precompiled regexes per emitted record — negligible at expected log volume. The access-log timer uses `time.perf_counter()` around `call_next` (already in the request path). No file I/O (terminal-only) keeps overhead minimal.

## Migration Notes

No data or schema migration. Deployed environments must set the environment/format env var (and optionally `LOG_LEVEL`) to switch from console to JSON; document the variable names in the env config. Default (unset) behavior remains human-readable console at INFO, matching current local dev.

## References

- Roadmap slice: `context/foundation/roadmap.md` F-05 (lines 127-140)
- Quality gate: `context/foundation/test-plan.md` §4 (no secrets/PII in logs)
- Lessons: `context/foundation/lessons.md` L-004 (CRUD logging), L-005 (no single-letter names), L-006 (imports at top), L-001 (TLS DB commands via PowerShell)
- Existing config: `backend/app/core/logging_config.py`, `backend/app/main.py:47-58`
- PII leak: `backend/app/db/supabase_auth.py:101`
- Test patterns: `backend/tests/conftest.py`, `backend/tests/cabinet/test_service.py:820`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Central logging foundation + redaction

#### Automated

- [x] 1.1 Linting passes (`ruff check` + `ruff format --check`) — bc6dcc5
- [x] 1.2 Redaction unit test passes (`pytest tests/core/test_logging_config.py`) — bc6dcc5
- [x] 1.3 Full backend suite passes (`uv run pytest`) — bc6dcc5

#### Manual

- [x] 1.4 Local console output readable with correlation id — bc6dcc5
- [x] 1.5 Deployed selector produces JSON on stdout — bc6dcc5
- [x] 1.6 Email / Bearer token line emitted with secret scrubbed — bc6dcc5

### Phase 2: Request/response access logging

#### Automated

- [x] 2.1 Linting passes — 818de58
- [x] 2.2 Full backend suite passes (no middleware regressions) — 818de58

#### Manual

- [x] 2.3 One INFO access line per request with method/path/status/duration_ms — 818de58
- [x] 2.4 X-Correlation-ID header present and matches logged id — 818de58

### Phase 3: Apply across the app + fix PII leak

#### Automated

- [x] 3.1 Linting passes
- [x] 3.2 Full backend suite passes
- [x] 3.3 `supabase_auth.py` no longer passes email to a log call

#### Manual

- [ ] 3.4 Failed sign-in logs a warning with no email present
- [ ] 3.5 Service-layer logs consistent across domains

### Phase 4: Scripts + alembic alignment

#### Automated

- [ ] 4.1 Linting passes
- [ ] 4.2 Full backend suite passes

#### Manual

- [ ] 4.3 registry_import emits central format with redaction
- [ ] 4.4 alembic invocation logs at aligned level without errors

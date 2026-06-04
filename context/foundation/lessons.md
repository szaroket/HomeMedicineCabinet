# Lessons

Recurring project rules and agent failure patterns. Each entry is something an
implementation or review should treat as a standing constraint, not a one-off
note. Newest first.

---

## L-001 — Run TLS database commands from native PowerShell, not the Git Bash tool

**Context**: Discovered during `registry-import` Phase 1 (2026-06-04) while trying
to run `uv run alembic upgrade head` against Supabase.

**Symptom**: Any TLS connection to the database from the agent's Bash tool
(Git Bash / MSYS2) hard-aborts the Python process with:

```
OPENSSL_Uplink(...): no OPENSSL_Applink
```

The crash fires the moment `ssl.create_default_context()` runs — so it hits
`alembic`, the app's `app/db/connector.py`, and the Phase 3/4 import loader
equally. It is a hard `abort()`, so buffered stdout is lost (use `python -u` when
diagnosing).

**Root cause**: uv's bundled CPython 3.13 ships an OpenSSL build without applink
support. Under Git Bash, OpenSSL's default cert-file path resolves (via MSYS path
translation) to a real file that gets opened across the DLL boundary, which
requires applink → abort. Native Windows PowerShell does **not** set up that
environment, so OpenSSL skips the file read and TLS works normally. The same uv
Python, same DB URL, runs cleanly from PowerShell.

**The rule**:

- Do **not** run database-touching commands (`uv run alembic ...`, the registry
  import script, anything that opens a TLS DB connection) from the agent's Bash
  tool. They will abort with the applink error.
- Run them from a **native Windows PowerShell** terminal. The user can do this
  directly, or the agent should hand the exact commands to the user to run.
- This is an environment/shell quirk, **not** a code defect. Do **not** "fix" it
  by weakening SSL (`CERT_NONE`) or adding workaround SSL contexts to
  `connector.py` / `migrations/env.py` — that would commit a security regression
  to solve a problem that does not exist outside the Bash tool.
- Code-level checks that need no DB (`ruff`, model imports, `pytest` on
  pure/fixture tests) run fine from the Bash tool; only TLS-DB work must move to
  PowerShell.

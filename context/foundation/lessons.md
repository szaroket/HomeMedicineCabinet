# Lessons

Recurring project rules and agent failure patterns. Each entry is something an
implementation or review should treat as a standing constraint, not a one-off
note. Newest first.

---

## L-004 — Wrap every `session.execute` / `session.flush` in `try/except SQLAlchemyError`

**Context**: Applied consistently starting with `cabinet/crud.py` (S-01 Phase 4, 2026-06-10); the pattern was already present in `medicines/crud.py`.

**The rule**:

- Every `await session.execute(...)`, `await session.flush()`, and `await session.refresh(...)` in a `crud.py` module must be wrapped in `try/except SQLAlchemyError`.
- On catch: log with `logger.error(..., exc_info=True)` and raise the domain-specific database error (e.g. `CabinetDatabaseError`, `MedicineSearchError`) chained with `from exc`.
- Each domain must define its own `<Domain>DatabaseError(BaseDomainError)` in `app/utilities/errors.py` — do not reuse another domain's error class.
- The router maps `<Domain>DatabaseError` → HTTP 503; never let a raw `SQLAlchemyError` propagate to the client.
- For `insert_entry` / `update_entry_counts` patterns where `session.add()` precedes the flush, the `session.add()` call itself doesn't need the try block — only the `await` calls do.

---

## L-003 — Keep FastAPI `Query()`/`Path()` inside `Annotated`, never as a default value, when the type carries Pydantic constraints

**Context**: Surfaced in `medicines/router.py` (S-01 Phase 2, 2026-06-09) while
adding a `StringConstraints(strip_whitespace=True, min_length=1)` to reject
blank/whitespace-only search queries.

**Symptom**: The validation silently did nothing — a whitespace-only `query`
returned `200 []` instead of `422`. The constraint was declared on a type alias
but applied via a `Query()` *default value*:

```python
SearchQuery = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# BROKEN: StringConstraints is silently dropped
async def search_products(query: SearchQuery = Query(description="...")): ...
```

**Root cause**: When `Query()` (or `Path()`, `Header()`, ...) is supplied as the
parameter's **default value** while the Pydantic metadata lives on the
`Annotated` type, FastAPI builds the field from the `Query()` FieldInfo and does
**not** merge in the `Annotated` `StringConstraints`. The constraint is silently
ignored — no error, no warning. Putting `Query()` *inside* the `Annotated`
metadata makes FastAPI combine both.

**The rule**:

- Declare query/path/header params in the **all-in-`Annotated`** style; put
  `Query()`/`Path()`/etc. as Annotated metadata, not as the default value:

  ```python
  SearchQuery = Annotated[
      str,
      StringConstraints(strip_whitespace=True, min_length=1),
      Query(description="..."),
  ]

  async def search_products(query: SearchQuery): ...          # required
  async def search_products(query: SearchQuery = "default"): ...  # optional, real default
  ```

- A plain `param: int = Query(20, ge=1, le=50)` is fine **when all constraints
  live on the `Query()` itself** (no separate `Annotated`/`StringConstraints`).
  The trap is specifically: Pydantic constraints on the type **+** `Query()` as a
  default value — then the type's constraints vanish.
- When validation "does nothing", suspect this before suspecting the constraint
  values; it fails silently, so cover it with an explicit test/manual check.

---

## L-002 — Type `crud.py` sessions as `sqlalchemy.ext.asyncio.AsyncSession`, not the SQLModel one

**Context**: Surfaced in `auth/crud.py` and again in `medicines/crud.py` (S-01
Phase 2, 2026-06-09) when running raw `text()` / Core `insert()` statements.

**Symptom**: When the session parameter is annotated with
`sqlmodel.ext.asyncio.session.AsyncSession`, the type checker / IDE flags
`session.execute(...)` as deprecated and nudges toward `session.exec()`:

```
The method "execute" in class "AsyncSession" is deprecated.
You probably want to use `session.exec()` instead of `session.execute()`.
```

**Root cause**: SQLModel subclasses SQLAlchemy's `AsyncSession` and marks
`execute()` deprecated to push its own `exec()` — but `exec()` only accepts
`select()`-style statements. For a raw `text()` query (e.g. the full-text
`to_tsquery` search) or a Core `insert(...)`, `exec()` does not fit and
`execute()` is the correct call. Crucially, `get_session` in
`app/db/connector.py` yields a **plain** `sqlalchemy.ext.asyncio.AsyncSession`,
so the deprecation is a false positive caused only by the annotation.

**The rule**:

- In `crud.py` modules, annotate the session as
  `from sqlalchemy.ext.asyncio import AsyncSession` (matches the real runtime
  object from `get_session`); `session.execute(...)` is then correct and
  un-deprecated. This is the pattern in `auth/crud.py`.
- Do **not** "fix" the warning by forcing `session.exec()` on a `text()` or
  Core statement — that is the wrong API for non-`select` work.
- `router.py` / `service.py` may keep the SQLModel `AsyncSession` annotation
  (as `auth/` does) since they don't call `.execute()` directly; the rule is
  specifically about the crud layer that issues raw/Core statements.

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

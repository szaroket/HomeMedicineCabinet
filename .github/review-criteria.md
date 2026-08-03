# Review Criteria

## Correctness & Edge Cases

Does the change do what its description, docstring, and name claim, including the
paths nobody exercises by hand? Work through boundary values, empty and `None`
inputs, off-by-one limits, the failure branch of every call that can fail, and
any case where two operations can interleave. Watch for silent wrongness rather
than crashes: integer division and rounding, truncation, timezone- and
date-arithmetic mistakes, mutation of a caller's argument, and a default that
quietly substitutes for a missing value. In this codebase the nullable registry
fields, the expiry-threshold comparisons, and the merge-vs-insert branching are
where such bugs have room to hide. A finding belongs here when the code would
produce a wrong result — not when it is merely untidy.

## Backend Architecture

Separation of concerns and dependency direction: each layer does its own job,
depends only inward, and exposes a contract that hides what sits behind it.
Persistence models are not transport models — a table model is never returned
from an endpoint, every route declares an explicit response schema, and read and
write schemas stay separate so they can diverge as the API requires. Errors are a
designed taxonomy, not an afterthought: each domain owns its exception
hierarchy, a new failure mode gets a typed error rather than a reused generic
one, domains do not borrow each other's error types, and translating a domain
error into a transport error happens in exactly one layer. Business logic belongs
in the service layer — flag it when it drifts up into routing or down into data
access, and flag cross-domain orchestration that bypasses the facade. Shared
behavior belongs in a shared module rather than being copied between domains.

## REST API Design

Design the API around resources, not procedures: paths name plural resource
collections, nest to express containment, live under an explicit version prefix,
and mirror the domain structure behind them. A narrow partial update earns its
own sub-resource path rather than a verb or a mode flag on the parent. HTTP verbs
carry their standard contract — `GET` is safe and free of side effects, `PUT`,
`PATCH`, and `DELETE` are idempotent, `POST` creates. Status codes are part of
the contract and must be consistent across the API: created, no-content on
delete, not-found for a missing or inaccessible resource, unprocessable for
domain validation failures, service-unavailable for a downstream outage, and a
generic server error that leaks no internals for anything unexpected. Collections
express filtering, sorting, and pagination through query parameters rather than
bespoke endpoints, and a new paginated response reuses the established envelope
instead of inventing another shape. Credentials, tokens, and personal identifiers
never travel in a path or query string, where access logs and proxies will retain
them. This repo's verb-shaped session endpoints and its mutating `GET
/auth/refresh` are inherited exceptions in the auth domain — do not report them,
and do not treat them as precedent for new endpoints.

## Python Craft & Type Safety

Modern, idiomatic Python 3.13 that a reader can follow on the first pass. Prefer
guard clauses to deep nesting, small functions with one responsibility, named
constants over magic values, comprehensions and standard-library idioms over
hand-rolled loops, and context managers for anything that must be released.
Classic defects to flag on sight: a mutable default argument, a bare `except`, an
exception swallowed or re-raised without `from`, a broad `except Exception` that
hides a specific failure, dead or commented-out code, and duplicated logic that
belongs in a shared helper. Async code has its own failure modes — blocking I/O
inside a coroutine, a missing `await`, a database session shared across
concurrent tasks, and unbounded concurrency all pass review by eye and fail in
production. On typing: CI runs `pyright` in `basic` mode, so it is *already*
enforcing what it can catch and you should not restate its errors; judge the
precision it permits. An unannotated signature, a value typed `Any` when a real
type exists, a `cast` or `# type: ignore` with no stated reason, a closed value
set typed as `str` instead of an enum, and an optional-heavy structure that a
discriminated union would model exactly are all defects basic mode will happily
accept. Logging is structured through a module-level logger, never `print`, and a
credential, token, or personal identifier must never reach a log line or a client
error message.

## Data Access, Migrations & Query Efficiency

Authorization is enforced at the data-access boundary: every query that reads or
writes user-owned data is scoped by the authenticated user's identity, and a
resource belonging to another user answers as if it does not exist rather than
revealing that it does. Values reach SQL as bind parameters — building a
statement through string formatting is an injection defect regardless of how
trustworthy the value looks. Query efficiency is part of correctness at scale:
flag N+1 access patterns, queries inside loops, unbounded result sets, a filter
or sort on an unindexed column, and fetching whole rows when a projection or
aggregate would do. Transaction boundaries are deliberate — one unit of work
commits or rolls back together, and partial writes must not survive a failure.
Any change to a persisted schema ships its migration in the same pull request,
and a destructive or non-reversible migration needs explicit justification.

## Frontend Architecture & State Ownership

Every piece of state has exactly one owner, and the boundary between server state
and client state is the one that matters most: data owned by the server lives in
the query cache and is never copied into local component state, where the copy
immediately begins to go stale. State derived from other state is computed, not
stored. Session and persistence concerns live behind a single module that owns
the storage key and its accessors, so no other file reaches into browser storage
directly. Modules respect their boundaries: a feature owns its slice, features do
not import each other, shared code earns promotion by having a second consumer,
and composition happens at the application root. Watch for a component that has
accumulated data fetching, form state, and presentation at once, and for props
threaded through several layers that neither reads — both mean a hook, a context,
or a split is missing. Data crossing the network boundary is validated into typed
values rather than asserted into them.

## React & TypeScript Craft

Components follow the rules of hooks with honest dependency arrays; a suppressed
dependency warning needs a stated reason. Effects synchronize with something
outside React — they are not the place to fetch data that a query hook should
own, nor to recompute values that could simply be derived during render. Server
mutations invalidate the affected cache entries through a shared key definition
rather than ad-hoc strings, so two call sites cannot drift apart. Every
asynchronous view distinguishes loading, error, and empty as three separate
states, and lists carry stable keys rather than array indices. On TypeScript:
`any`, a non-null assertion, and an unchecked type assertion each discard the
guarantee the type system exists to provide, so each needs justification; model
mutually exclusive states as a discriminated union rather than a record of
optional fields. Interactive markup needs accessible names, labels bound to their
inputs, and keyboard operability — this is a correctness requirement for users
and, because the E2E suite locates elements by role and label, a prerequisite for
testability.

## Test Quality

Name the tests that are missing. CI already enforces a coverage threshold, so a
percentage is not your concern — but a green bar says nothing about whether the
*right* cases exist, and identifying a specific untested case is one of the most
valuable findings you can make. For each behavior the diff changes, ask whether a
test would fail if that behavior regressed; if not, say which case is absent —
the boundary value, the error branch, the permission denial, the empty result,
the concurrent path. When a change touches a critical user journey end to end
(authentication, creating or destroying user data, anything irreversible),
recommend browser-level coverage if none exists. Existing tests are judged on
whether they can actually fail: a mock built without a spec accepts any signature
and keeps passing after the real function changes, an assertion on which mock
received which argument tests the implementation rather than the behavior, and
covering an error branch without asserting the response it produces leaves the
mapping unverified. Tests must be independent and repeatable — shared mutable
state between tests, order dependence, and fixed sleeps instead of waiting on a
condition are defects. Reuse the shared fixtures rather than rebuilding them
inline.

## Repository Rules & Lessons Compliance

The full text of `AGENTS.md` and `context/foundation/lessons.md` is already in
your prompt under "Repository Rules" and "Additional Lessons / Pitfalls" — read
them there rather than assuming what they contain. Score this criterion on
whether the diff honors them, and cite the specific rule or lesson id (for
example `L-004`) in `rule_reference` on every finding that relates to one. Do not
raise a finding restating a rule the code already complies with, and do not
invent a convention that neither file actually states.

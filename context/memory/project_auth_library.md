---
name: project-auth-library
description: Auth library decision — supabase Python library for auth, SQLModel+asyncpg for data layer
metadata:
  type: project
---

Use the `supabase` Python library exclusively for auth in F-01 (`supabase.auth` — sign_up, sign_in_with_password, sign_out, get_user JWT validation). Do NOT use its PostgREST database client.

**Why:** User explicitly confirmed this split. The data layer (F-02+) uses SQLModel + asyncpg + Alembic for direct PostgreSQL access — better fit for full-text search, transactions, and Alembic migrations.

**How to apply:** When implementing F-01, add `supabase` to pyproject.toml and wire only `supabase.auth`. When implementing F-02+, use SQLModel sessions — never the supabase DB client.

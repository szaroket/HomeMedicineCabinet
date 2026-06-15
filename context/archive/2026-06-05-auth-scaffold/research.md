---
change_id: auth-scaffold
doc: research
created: 2026-06-05
updated: 2026-06-05
sources: web (exa) — FastAPI docs, Supabase docs, supabase-py issues, 2026 best-practice writeups
---

# Auth scaffold — library research (F-01)

Research into auth-flow libraries compatible with the project stack
(FastAPI + Supabase Auth + SQLModel; FastAPI is the sole Supabase/DB client,
the frontend never calls Supabase directly).

The stack constrains the choice to two concerns:

1. A client to talk to **Supabase Auth** for register / login / logout.
2. A **JWT verification** library for the FastAPI route guard.

Everything else is boilerplate around those two.

## Recommended libraries

| Concern | Library | Why |
|---|---|---|
| Supabase Auth client (signup/login/logout) | **`supabase-py`** (v2.15+) | Official SDK. `supabase.auth.sign_up`, `sign_in_with_password`, `sign_out`, `get_claims`. Wraps `auth-py` (formerly gotrue-py). Sync + async. |
| JWT verification on protected routes | **`PyJWT`** (2.x) + `cryptography` extra | FastAPI-recommended choice. Ships `PyJWKClient` for JWKS with built-in `kid` lookup and key caching. |
| (transitive) crypto backend | **`cryptography`** | Required for asymmetric algos (ES256/RS256) used by new Supabase projects. Pulled in via `pyjwt[crypto]`. |

Install: `uv add "supabase>=2.15" "pyjwt[crypto]"`

## Key decision: how to verify the token

Two viable patterns; the right one depends on **when the Supabase project was created**:

1. **JWKS / asymmetric (ES256 or RS256)** — fetch public keys from
   `https://<project>.supabase.co/auth/v1/.well-known/jwks.json`, verify locally
   with `PyJWKClient`. **No network call to Supabase per request.** Default for
   projects created after **2025-10-01**; Supabase is forcing all projects here by
   late 2026.
2. **Static secret / symmetric (HS256)** — verify with `SUPABASE_JWT_SECRET` from
   project settings. Legacy path; being deprecated.

**Recommendation: build on the JWKS / `PyJWKClient` path from the start** — it is the
direction Supabase is mandating, avoids a forced migration mid-build, and keeps
verification local (relevant to performance NFRs).

Reference pattern (from supabase-py issue #1183):

```python
from jwt import PyJWKClient, decode as jwt_decode

ISSUER = f"{settings.supabase_url}/auth/v1"
jwks = PyJWKClient(f"{ISSUER}/.well-known/jwks.json")

key = jwks.get_signing_key_from_jwt(token).key
claims = jwt_decode(
    token, key,
    algorithms=["ES256", "RS256"],
    issuer=ISSUER,
    audience="authenticated",
)
```

## What to avoid

- **`python-jose`** — many older Supabase+FastAPI tutorials use it, but it is
  effectively abandoned (last release ~3 years ago) and **FastAPI officially dropped
  its recommendation** in favor of PyJWT (fastapi/fastapi discussion #11345). Do not
  pull it into a greenfield scaffold.
- **`supabase.auth.get_user(token)` on every request** — makes a network round-trip
  to Supabase per call and broke under the new signing keys. Use local JWKS
  verification instead.

## Non-negotiable security settings

These map directly to F-01's "reject unauthenticated requests" outcome and the PRD
Access Control section:

- **Pin `algorithms` explicitly** — never trust the token's own `alg` header
  (algorithm-confusion / `alg=none` attacks, RFC 8725).
- **Validate `audience` (`"authenticated"`) and `issuer`**, and verify expiry — all
  four checks, every time.
- **Layer the FastAPI dependencies**: low-level dep extracts + validates the token →
  mid-level loads the user from claims → route-level enforces access. Avoid the
  "god dependency" that does everything (most common source of auth bugs).
- Keep `SUPABASE_JWT_SECRET` / keys in env vars (pre-commit secret rule per AGENTS.md).

## Architecture fit

Consistent with the tech-stack constraint that **FastAPI is the sole Supabase client**:
frontend POSTs credentials to FastAPI → FastAPI calls `supabase-py` to authenticate →
returns the access/refresh JWTs → frontend sends `Authorization: Bearer <jwt>` on
subsequent calls → a `PyJWT` dependency guard validates locally. The frontend never
holds a service key or calls Supabase directly. RLS stays as the defence-in-depth net.

## Reference links

- Supabase Python API reference — https://supabase.com/docs/reference/python/introduction
- supabase/auth-py (formerly gotrue-py) — https://github.com/supabase/auth-py
- supabase-py issue #1183 (JWKS / `get_claims` migration, FastAPI dep pattern) — https://github.com/supabase/supabase-py/issues/1183
- FastAPI: drop python-jose recommendation — https://github.com/fastapi/fastapi/discussions/11345
- FastAPI OAuth2 + JWT tutorial (PyJWT) — https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
- PyJWT API reference (`PyJWKClient`, `decode`) — https://pyjwt.readthedocs.io/en/latest/api.html
- Migrating Supabase JWT to JWKS — https://objectgraph.com/blog/migrating-supabase-jwt-jwks/
- FastAPI auth best practices 2026 — https://safeguard.sh/resources/blog/fastapi-authentication-best-practices-2026
- Scaffolding template (email/password + JWT + layered deps) — https://github.com/hpohlmann/supabase-api-scaffolding-template

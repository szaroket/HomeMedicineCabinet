# Backend Structure

## Directory layout

```
backend/
└── app/
    ├── main.py           # Sole entry point: FastAPI app factory (create_app) + middleware + uvicorn __main__
    └── v1/
        ├── router.py     # Aggregates all domain routers under prefix /v1
        ├── health/
        │   └── router.py   # GET /v1/health/ — router layer only (no service/crud needed)
        ├── auth/
        │   ├── router.py   # Route definitions only (no logic)
        │   ├── service.py  # Business logic
        │   └── crud.py     # Database operations
        └── medicines/
            ├── router.py
            ├── service.py
            └── crud.py
```

## Rules

- **`app/main.py`** — sole entry point: `create_app()` factory registers middleware and includes `v1_router`; `if __name__ == "__main__"` block runs uvicorn. No domain routes here.
- There is **no** `backend/main.py`.
- **`app/v1/router.py`** — imports and includes every domain router. Prefix: `/v1`.
- **Domain directories** (`auth/`, `medicines/`, …) live under `app/v1/`. Each new domain gets its own directory.
- **Layer separation** inside each domain:
  - `router.py` — only FastAPI `APIRouter` and endpoint decorators. Calls service functions.
  - `service.py` — business logic, validation, orchestration. Calls crud functions.
  - `crud.py` — raw database read/write operations. No business logic.
- **URL paths** mirror the directory path: `app/v1/<domain>/<endpoint>` → `/v1/<domain>/<endpoint>`.
- **`health/`** is an exception: it has only `router.py` (no service/crud) because it returns a static response with no business logic or DB access.
- **Adding a new domain**: create `app/v1/<domain>/` with `__init__.py`, `router.py`, `service.py`, `crud.py`; import and include the router in `app/v1/router.py`.
- **Adding a new API version**: create `app/v2/` following the same pattern; register in `app/main.py`.

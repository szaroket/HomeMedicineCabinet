import logging
import os
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging_config import (
    configure_logging,
    correlation_id_var,
    generate_correlation_id,
)
from app.db.connector import engine, init_db
from app.api.v1.router import router as v1_router

configure_logging()
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="Home Medicine Cabinet API", version="0.4.0", lifespan=lifespan)

    _frontend_url = os.getenv("FRONTEND_URL")
    _allowed_origins = (
        [_frontend_url, "http://localhost:5173"]
        if _frontend_url
        else ["http://localhost:5173"]
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next):
        cid = request.headers.get("X-Correlation-ID") or generate_correlation_id()
        token = correlation_id_var.set(cid)
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        response.headers["X-Correlation-ID"] = cid
        logger.info(
            "%s %s %d %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        correlation_id_var.reset(token)
        return response

    app.include_router(v1_router)

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )

import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.v1.router import router as v1_router


def create_app() -> FastAPI:
    app = FastAPI(title="Home Medicine Cabinet API")

    _frontend_url = os.getenv("FRONTEND_URL")
    _allowed_origins = (
        [_frontend_url, "http://localhost:5173"]
        if _frontend_url
        else ["http://localhost:5173"]
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

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

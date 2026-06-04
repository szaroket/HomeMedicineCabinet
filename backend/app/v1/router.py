from fastapi import APIRouter

from app.v1.auth.router import router as auth_router
from app.v1.health.router import router as health_router
from app.v1.medicines.router import router as medicines_router

router = APIRouter(prefix="/v1")

router.include_router(health_router)
router.include_router(auth_router)
router.include_router(medicines_router)

from fastapi import APIRouter

from app.api.v1.auth.router import router as auth_router
from app.api.v1.cabinet.router import router as cabinet_router
from app.api.v1.health.router import router as health_router
from app.api.v1.medicines.router import router as medicines_router
from app.api.v1.notifications.router import router as notifications_router
from app.api.v1.users.router import router as users_router

router = APIRouter(prefix="/api/v1")

router.include_router(health_router)
router.include_router(auth_router)
router.include_router(medicines_router)
router.include_router(cabinet_router)
router.include_router(users_router)
router.include_router(notifications_router)

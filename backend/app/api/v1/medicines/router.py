from fastapi import APIRouter, Security

from app.core.jwt_security import get_current_user

router = APIRouter(
    prefix="/medicines", tags=["medicines"], dependencies=[Security(get_current_user)]
)


# Example: GET /api/v1/medicines
# @router.get("/")
# async def get_medicines():
#     return await medicines_service.get_all()

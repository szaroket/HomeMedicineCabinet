from fastapi import APIRouter

router = APIRouter(prefix="/medicines", tags=["medicines"])


# Example: GET /v1/medicines
# @router.get("/")
# async def get_medicines():
#     return await medicines_service.get_all()

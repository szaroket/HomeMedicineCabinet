from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])


# Example: POST /api/v1/auth/login
# @router.post("/login")
# async def login(credentials: LoginRequest):
#     return await auth_service.login(credentials)

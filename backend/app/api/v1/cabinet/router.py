from fastapi import APIRouter, Security

from app.core.jwt_security import get_current_user

router = APIRouter(
    prefix="/cabinet", tags=["cabinet"], dependencies=[Security(get_current_user)]
)

"""Auth endpoints: register, login, logout, refresh, me."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import service as auth_service
from app.api.v1.auth.schemas import AuthResponse, LoginRequest, RegisterRequest, UserOut
from app.api.v1.auth.types import CurrentUser
from app.core.config import settings
from app.core.jwt_security import get_current_user
from app.db.connector import get_session
from app.utilities.errors import (
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidEmailError,
    RateLimitError,
    RegistrationError,
    SessionExpiredError,
    WeakPasswordError,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        path=settings.auth_cookie_path,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.auth_cookie_name, path=settings.auth_cookie_path
    )


@router.post(
    "/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    data: RegisterRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    """Register a new user and return an access token."""
    try:
        auth_response, refresh_token = await auth_service.register(session, data)
    except RateLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e)
        ) from e
    except DuplicateEmailError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except WeakPasswordError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)
        ) from e
    except InvalidEmailError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)
        ) from e
    except RegistrationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    _set_refresh_cookie(response, refresh_token)
    return auth_response


@router.post("/login", response_model=AuthResponse)
async def login(
    data: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    """Authenticate an existing user and return an access token."""
    try:
        auth_response, refresh_token = await auth_service.login(session, data)
    except RateLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e)
        ) from e
    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)
        ) from e
    _set_refresh_cookie(response, refresh_token)
    return auth_response


@router.get("/refresh", response_model=AuthResponse)
def refresh(request: Request, response: Response) -> AuthResponse:
    """Exchange the refresh cookie for a new access token."""
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token cookie is missing.",
        )
    try:
        auth_response, new_refresh_token = auth_service.refresh(token)
    except RateLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e)
        ) from e
    except SessionExpiredError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)
        ) from e
    _set_refresh_cookie(response, new_refresh_token)
    return auth_response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Sign out the current user and clear the refresh cookie."""
    _clear_refresh_cookie(response)
    auth_service.logout(access_token="")


@router.get("/me", response_model=UserOut)
def me(current_user: CurrentUser = Depends(get_current_user)) -> UserOut:
    """Return the authenticated user's identity."""
    return UserOut(id=current_user.id, email=current_user.email)

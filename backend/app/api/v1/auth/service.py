"""Auth business logic."""

import logging
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import crud
from app.api.v1.auth.schemas import AuthResponse, LoginRequest, RegisterRequest, UserOut
from app.db import supabase_auth
from app.utilities.errors import (
    DuplicateEmailError,
    InvalidCredentialsError,
    RegistrationError,
    SessionExpiredError,
)

logger = logging.getLogger("app.auth.service")


async def register(
    session: AsyncSession, data: RegisterRequest
) -> tuple[AuthResponse, str]:
    """Register a new user via Supabase Auth and provision local rows.

    Args:
        session (AsyncSession): Active async database session.
        data (RegisterRequest): Registration payload (email + password).

    Returns:
        tuple[AuthResponse, str]: Tuple of (AuthResponse, refresh_token).

    Raises:
        DuplicateEmailError: If the email is already registered.
        RegistrationError: If Supabase rejects the sign-up for any other reason.
    """
    result = supabase_auth.sign_up(data.email, data.password)

    if result.user is None:
        logger.warning("sign_up returned no user — duplicate email")
        raise DuplicateEmailError()

    if result.session is None:
        logger.error(
            "sign_up returned no session — enable auto-confirm in Supabase Auth settings",
        )
        raise RegistrationError()

    user_id = UUID(str(result.user.id))
    email = result.user.email or data.email
    await crud.provision_user(session, user_id, email)
    logger.info("Registered and provisioned user %s", user_id)

    return (
        AuthResponse(
            access_token=result.session.access_token,
            user=UserOut(id=user_id, email=email),
        ),
        result.session.refresh_token,
    )


async def login(session: AsyncSession, data: LoginRequest) -> tuple[AuthResponse, str]:
    """Authenticate an existing user via Supabase Auth.

    Args:
        session (AsyncSession): Active async database session.
        data (LoginRequest): Login payload (email + password).

    Returns:
        tuple[AuthResponse, str]: Tuple of (AuthResponse, refresh_token).

    Raises:
        InvalidCredentialsError: If the email/password combination is incorrect.
    """
    result = supabase_auth.sign_in_with_password(data.email, data.password)

    if result.user is None or result.session is None:
        logger.warning("sign_in returned no user/session")
        raise InvalidCredentialsError()

    user_id = UUID(str(result.user.id))
    email = result.user.email or data.email
    await crud.provision_user(session, user_id, email)
    logger.info("Logged in user %s", user_id)

    return (
        AuthResponse(
            access_token=result.session.access_token,
            user=UserOut(id=user_id, email=email),
        ),
        result.session.refresh_token,
    )


def refresh(refresh_token: str) -> tuple[AuthResponse, str]:
    """Exchange a refresh token for a new access token.

    Args:
        refresh_token (str): The httpOnly cookie refresh token.

    Returns:
        tuple[AuthResponse, str]: Tuple of (AuthResponse, new_refresh_token).

    Raises:
        SessionExpiredError: If the refresh token is invalid or expired.
    """
    result = supabase_auth.refresh_session(refresh_token)

    if result.user is None or result.session is None:
        logger.warning("refresh_session returned no user/session")
        raise SessionExpiredError()

    user_id = UUID(str(result.user.id))
    email = result.user.email or ""
    logger.info("Refreshed session for user %s", user_id)

    return (
        AuthResponse(
            access_token=result.session.access_token,
            user=UserOut(id=user_id, email=email),
        ),
        result.session.refresh_token,
    )

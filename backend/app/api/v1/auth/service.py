"""Auth business logic."""

import logging
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession
from supabase import AuthApiError

from app.api.v1.auth.crud import provision_user
from app.api.v1.auth.schemas import AuthResponse, LoginRequest, RegisterRequest, UserOut
from app.db.supabase_client import get_supabase
from app.utilities.errors import (
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidEmailError,
    RateLimitError,
    RegistrationError,
    SessionExpiredError,
    WeakPasswordError,
)

logger = logging.getLogger("app.auth.service")


async def register(
    session: AsyncSession, data: RegisterRequest
) -> tuple[AuthResponse, str]:
    """Register a new user via Supabase Auth and provision local rows.

    Args:
        session: Active async database session.
        data: Registration payload (email + password).

    Returns:
        Tuple of (AuthResponse, refresh_token).

    Raises:
        DuplicateEmailError: If the email is already registered.
        RegistrationError: If Supabase rejects the sign-up for any other reason.
    """
    try:
        result = get_supabase().auth.sign_up(
            {"email": data.email, "password": data.password}
        )
    except AuthApiError as e:
        logger.error("Supabase sign_up failed (code=%s): %s", e.code, e)
        if e.status == 429:
            raise RateLimitError() from e
        if e.code == "user_already_exists":
            raise DuplicateEmailError() from e
        if e.code == "weak_password":
            raise WeakPasswordError() from e
        if e.code in ("email_address_invalid", "email_address_not_authorized"):
            raise InvalidEmailError() from e
        raise RegistrationError() from e
    except Exception as e:
        logger.error("Unexpected error during sign_up: %s", e, exc_info=True)
        raise RegistrationError() from e

    if result.user is None:
        logger.warning("sign_up returned no user for %s — duplicate email", data.email)
        raise DuplicateEmailError()

    if result.session is None:
        logger.error(
            "sign_up returned no session for %s — enable auto-confirm in Supabase Auth settings",
            data.email,
        )
        raise RegistrationError()

    user_id = UUID(str(result.user.id))
    email = result.user.email or data.email
    await provision_user(session, user_id, email)
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
        session: Active async database session.
        data: Login payload (email + password).

    Returns:
        Tuple of (AuthResponse, refresh_token).

    Raises:
        InvalidCredentialsError: If the email/password combination is incorrect.
    """
    try:
        result = get_supabase().auth.sign_in_with_password(
            {"email": data.email, "password": data.password}
        )
    except AuthApiError as e:
        logger.warning("Supabase sign_in failed for %s: %s", data.email, e)
        if e.status == 429:
            raise RateLimitError() from e
        raise InvalidCredentialsError() from e
    except Exception as e:
        logger.error("Unexpected error during sign_in: %s", e, exc_info=True)
        raise InvalidCredentialsError() from e

    if result.user is None or result.session is None:
        logger.warning("sign_in returned no user/session for %s", data.email)
        raise InvalidCredentialsError()

    user_id = UUID(str(result.user.id))
    email = result.user.email or data.email
    await provision_user(session, user_id, email)
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
        refresh_token: The httpOnly cookie refresh token.

    Returns:
        Tuple of (AuthResponse, new_refresh_token).

    Raises:
        SessionExpiredError: If the refresh token is invalid or expired.
    """
    try:
        result = get_supabase().auth.refresh_session(refresh_token)
    except AuthApiError as e:
        logger.warning("Supabase refresh_session failed: %s", e)
        if e.status == 429:
            raise RateLimitError() from e
        raise SessionExpiredError() from e
    except Exception as e:
        logger.error("Unexpected error during refresh_session: %s", e, exc_info=True)
        raise SessionExpiredError() from e

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


def logout(access_token: str) -> None:
    """Sign out the user from Supabase Auth.

    Args:
        access_token: The user's current access JWT.
    """
    try:
        get_supabase().auth.sign_out()
        logger.info("User signed out")
    except Exception as e:
        logger.warning("Supabase sign_out failed (ignored): %s", e)

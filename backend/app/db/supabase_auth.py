"""Configured supabase-py client and Supabase Auth operations with domain error mapping."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from supabase import Client
    from supabase_auth.types import AuthResponse

from app.utilities.errors import (
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidEmailError,
    RateLimitError,
    RegistrationError,
    SessionExpiredError,
    WeakPasswordError,
)

logger = logging.getLogger("app.db.supabase_auth")

_client: "Client | None" = None


def get_supabase() -> "Client":
    """Return the module-level Supabase client, initialising it on first call.

    Returns:
        Client: The shared, lazily created ``supabase-py`` client instance.
    """
    global _client
    if _client is None:
        from supabase import create_client

        from app.core.config import settings

        _client = create_client(settings.supabase_url, settings.supabase_anon_key)
    return _client


def sign_up(email: str, password: str) -> "AuthResponse":
    """Register a new user via Supabase Auth, mapping failures to domain errors.

    Args:
        email (str): New user's email address.
        password (str): New user's plaintext password.

    Returns:
        AuthResponse: The Supabase ``AuthResponse`` carrying the created ``user`` and ``session``.

    Raises:
        RateLimitError: If Supabase rate-limits the request.
        DuplicateEmailError: If the email is already registered.
        WeakPasswordError: If the password is too weak.
        InvalidEmailError: If the email is invalid or not authorised.
        RegistrationError: If Supabase rejects the sign-up for any other reason.
    """
    from supabase import AuthApiError

    try:
        return get_supabase().auth.sign_up({"email": email, "password": password})
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


def sign_in_with_password(email: str, password: str) -> "AuthResponse":
    """Authenticate an existing user via Supabase Auth, mapping failures to domain errors.

    Args:
        email (str): User's email address.
        password (str): User's plaintext password.

    Returns:
        AuthResponse: The Supabase ``AuthResponse`` carrying the ``user`` and ``session``.

    Raises:
        RateLimitError: If Supabase rate-limits the request.
        InvalidCredentialsError: If the email/password combination is incorrect.
    """
    from supabase import AuthApiError

    try:
        return get_supabase().auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except AuthApiError as e:
        logger.warning("Supabase sign_in failed (code=%s): %s", e.code, e)
        if e.status == 429:
            raise RateLimitError() from e
        raise InvalidCredentialsError() from e
    except Exception as e:
        logger.error("Unexpected error during sign_in: %s", e, exc_info=True)
        raise InvalidCredentialsError() from e


def refresh_session(refresh_token: str) -> "AuthResponse":
    """Exchange a refresh token for a new session via Supabase Auth, mapping failures to domain errors.

    Args:
        refresh_token (str): The refresh token to redeem.

    Returns:
        AuthResponse: The Supabase ``AuthResponse`` carrying the rotated ``user`` and ``session``.

    Raises:
        RateLimitError: If Supabase rate-limits the request.
        SessionExpiredError: If the refresh token is invalid or expired.
    """
    from supabase import AuthApiError

    try:
        return get_supabase().auth.refresh_session(refresh_token)
    except AuthApiError as e:
        logger.warning("Supabase refresh_session failed: %s", e)
        if e.status == 429:
            raise RateLimitError() from e
        raise SessionExpiredError() from e
    except Exception as e:
        logger.error("Unexpected error during refresh_session: %s", e, exc_info=True)
        raise SessionExpiredError() from e

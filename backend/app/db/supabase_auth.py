"""Configured supabase-py client and Supabase Auth operations with domain error mapping."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from supabase import AuthApiError, create_client

from app.core.config import settings
from app.utilities.errors import (
    AccountDeletionError,
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidEmailError,
    RateLimitError,
    RegistrationError,
    SessionExpiredError,
    WeakPasswordError,
)

if TYPE_CHECKING:
    from supabase import Client
    from supabase_auth.types import AuthResponse

logger = logging.getLogger("app.db.supabase_auth")

_client: "Client | None" = None
_admin_client: "Client | None" = None


def get_supabase() -> "Client":
    """Return the module-level Supabase client, initialising it on first call.

    Returns:
        Client: The shared, lazily created ``supabase-py`` client instance.
    """
    global _client
    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_anon_key)
    return _client


def get_supabase_admin() -> "Client":
    """Return the module-level Supabase admin client, initialising it on first call.

    The admin client is authenticated with the service-role key and can
    perform privileged operations (e.g. `auth.admin.delete_user`). It is kept
    separate from the anon client returned by `get_supabase` and must never be
    exposed to the frontend.

    Returns:
        Client: The shared, lazily created service-role ``supabase-py`` client instance.
    """
    global _admin_client
    if _admin_client is None:
        _admin_client = create_client(
            settings.supabase_url, settings.supabase_service_role_key
        )
    return _admin_client


def delete_user(user_id: str) -> None:
    """Delete a Supabase Auth user via the admin API, mapping failures to domain errors.

    A missing auth user (already deleted) is treated as a benign, idempotent
    no-op rather than an error.

    Args:
        user_id (str): The Supabase Auth user id to delete.

    Raises:
        AccountDeletionError: If Supabase rejects the deletion for any reason
            other than the user already being gone.
    """
    try:
        get_supabase_admin().auth.admin.delete_user(user_id)
    except AuthApiError as e:
        if e.status == 404:
            logger.warning(
                "Supabase delete_user: user %s already absent (treated as deleted)",
                user_id,
            )
            return
        logger.error("Supabase delete_user failed (code=%s): %s", e.code, e)
        raise AccountDeletionError() from e
    except Exception as e:
        logger.error("Unexpected error during delete_user: %s", e, exc_info=True)
        raise AccountDeletionError() from e


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

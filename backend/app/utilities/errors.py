"""Domain exceptions raised by service and CRUD layers.

Routers catch these and map them to HTTPException with the appropriate status code.
"""


class AuthError(Exception):
    """Base class for authentication/authorisation domain errors.

    Attributes:
        message: Human-readable description of the error (English).
    """

    def __init__(self, message: str) -> None:
        """Initialise the error with a message.

        Args:
            message: Description of what went wrong.
        """
        super().__init__(message)
        self.message = message


class InvalidCredentialsError(AuthError):
    """Raised when the supplied email/password combination is incorrect."""

    def __init__(self, message: str = "Invalid email address or password.") -> None:
        """Initialise with a default message.

        Args:
            message: Description of what went wrong.
        """
        super().__init__(message)


class DuplicateEmailError(AuthError):
    """Raised when attempting to register with an already-used email address."""

    def __init__(
        self, message: str = "A user with this email address already exists."
    ) -> None:
        """Initialise with a default message.

        Args:
            message: Description of what went wrong.
        """
        super().__init__(message)


class SessionExpiredError(AuthError):
    """Raised when a refresh token is missing, invalid, or expired."""

    def __init__(
        self, message: str = "Session has expired. Please log in again."
    ) -> None:
        """Initialise with a default message.

        Args:
            message: Description of what went wrong.
        """
        super().__init__(message)


class RegistrationError(AuthError):
    """Raised when Supabase Auth rejects a sign-up for any other reason."""

    def __init__(self, message: str = "Registration failed.") -> None:
        """Initialise with a default message.

        Args:
            message: Description of what went wrong.
        """
        super().__init__(message)


class WeakPasswordError(AuthError):
    """Raised when the supplied password does not meet Supabase's strength requirements."""

    def __init__(
        self, message: str = "Password is too weak. Please choose a stronger password."
    ) -> None:
        """Initialise with a default message.

        Args:
            message: Description of what went wrong.
        """
        super().__init__(message)


class InvalidEmailError(AuthError):
    """Raised when the supplied email address is invalid or not authorised."""

    def __init__(
        self, message: str = "The email address is invalid or not authorised."
    ) -> None:
        """Initialise with a default message.

        Args:
            message: Description of what went wrong.
        """
        super().__init__(message)


class ProvisioningError(AuthError):
    """Raised when local user provisioning fails after Supabase auth succeeds."""

    def __init__(self, message: str = "Failed to provision the user account.") -> None:
        """Initialise with a default message.

        Args:
            message: Description of what went wrong.
        """
        super().__init__(message)


class RateLimitError(AuthError):
    """Raised when Supabase Auth rejects a request due to rate limiting."""

    def __init__(
        self, message: str = "Too many attempts. Please try again later."
    ) -> None:
        """Initialise with a default message.

        Args:
            message: Description of what went wrong.
        """
        super().__init__(message)


class MedicinesError(Exception):
    """Base class for medicines domain errors.

    Kept separate from AuthError so the auth and medicines taxonomies do not
    bleed into each other.

    Attributes:
        message: Human-readable description of the error (English).
    """

    def __init__(self, message: str) -> None:
        """Initialise the error with a message.

        Args:
            message: Description of what went wrong.
        """
        super().__init__(message)
        self.message = message


class MedicineSearchError(MedicinesError):
    """Raised when the registry search fails at the database layer.

    Typically wraps a SQLAlchemy/connection error so the router can map it to a
    503 Service Unavailable rather than leaking a raw 500.
    """

    def __init__(
        self, message: str = "Failed to search the medicines registry."
    ) -> None:
        """Initialise with a default message.

        Args:
            message: Description of what went wrong.
        """
        super().__init__(message)

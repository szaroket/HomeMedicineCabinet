"""Domain exceptions raised by service and CRUD layers.

Routers catch these and map them to HTTPException with the appropriate status code.
"""


class AuthError(Exception):
    """Base class for authentication/authorisation domain errors.

    Attributes:
        message (str): Human-readable description of the error (English).
    """

    def __init__(self, message: str) -> None:
        """Initialise the error with a message.

        Args:
            message (str): Description of what went wrong.
        """
        super().__init__(message)
        self.message = message


class InvalidCredentialsError(AuthError):
    """Raised when the supplied email/password combination is incorrect."""

    def __init__(self, message: str = "Invalid email address or password.") -> None:
        """Initialise with a default message.

        Args:
            message (str): Description of what went wrong.
        """
        super().__init__(message)


class DuplicateEmailError(AuthError):
    """Raised when attempting to register with an already-used email address."""

    def __init__(
        self, message: str = "A user with this email address already exists."
    ) -> None:
        """Initialise with a default message.

        Args:
            message (str): Description of what went wrong.
        """
        super().__init__(message)


class SessionExpiredError(AuthError):
    """Raised when a refresh token is missing, invalid, or expired."""

    def __init__(
        self, message: str = "Session has expired. Please log in again."
    ) -> None:
        """Initialise with a default message.

        Args:
            message (str): Description of what went wrong.
        """
        super().__init__(message)


class RegistrationError(AuthError):
    """Raised when Supabase Auth rejects a sign-up for any other reason."""

    def __init__(self, message: str = "Registration failed.") -> None:
        """Initialise with a default message.

        Args:
            message (str): Description of what went wrong.
        """
        super().__init__(message)


class WeakPasswordError(AuthError):
    """Raised when the supplied password does not meet Supabase's strength requirements."""

    def __init__(
        self, message: str = "Password is too weak. Please choose a stronger password."
    ) -> None:
        """Initialise with a default message.

        Args:
            message (str): Description of what went wrong.
        """
        super().__init__(message)


class InvalidEmailError(AuthError):
    """Raised when the supplied email address is invalid or not authorised."""

    def __init__(
        self, message: str = "The email address is invalid or not authorised."
    ) -> None:
        """Initialise with a default message.

        Args:
            message (str): Description of what went wrong.
        """
        super().__init__(message)


class ProvisioningError(AuthError):
    """Raised when local user provisioning fails after Supabase auth succeeds."""

    def __init__(self, message: str = "Failed to provision the user account.") -> None:
        """Initialise with a default message.

        Args:
            message (str): Description of what went wrong.
        """
        super().__init__(message)


class RateLimitError(AuthError):
    """Raised when Supabase Auth rejects a request due to rate limiting."""

    def __init__(
        self, message: str = "Too many attempts. Please try again later."
    ) -> None:
        """Initialise with a default message.

        Args:
            message (str): Description of what went wrong.
        """
        super().__init__(message)


class UserError(Exception):
    """Base class for users domain errors.

    Attributes:
        message (str): Human-readable description of the error (English).
    """

    def __init__(self, message: str) -> None:
        """Initialise the error with a message.

        Args:
            message (str): Description of what went wrong.
        """
        super().__init__(message)
        self.message = message


class UserDatabaseError(UserError):
    """Raised when a users database query fails (e.g. connection unavailable).

    Wraps a SQLAlchemy error so callers can map it to 503 rather than leaking
    a raw 500.
    """

    def __init__(
        self,
        message: str = "A database error occurred in the users domain.",
    ) -> None:
        """Initialise with a default message.

        Args:
            message (str): Description of what went wrong.
        """
        super().__init__(message)


class AccountDeletionError(UserError):
    """Raised when the Supabase Auth admin user deletion fails.

    Signals an upstream failure distinct from `UserDatabaseError`, so the
    router can map it to 502 rather than 503.
    """

    def __init__(self, message: str = "Failed to delete account.") -> None:
        """Initialise with a default message.

        Args:
            message (str): Description of what went wrong.
        """
        super().__init__(message)


class MedicinesError(Exception):
    """Base class for medicines domain errors.

    Kept separate from AuthError so the auth and medicines taxonomies do not
    bleed into each other.

    Attributes:
        message (str): Human-readable description of the error (English).
    """

    def __init__(self, message: str) -> None:
        """Initialise the error with a message.

        Args:
            message (str): Description of what went wrong.
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
            message (str): Description of what went wrong.
        """
        super().__init__(message)


class CabinetError(Exception):
    """Base class for cabinet domain errors.

    Kept separate from AuthError and MedicinesError so the cabinet taxonomy
    remains independent.

    Attributes:
        message (str): Human-readable description of the error (English).
    """

    def __init__(self, message: str) -> None:
        """Initialise the error with a message.

        Args:
            message (str): Description of what went wrong.
        """
        super().__init__(message)
        self.message = message


class MedicationNotFoundError(CabinetError):
    """Raised when the requested medication registry entry does not exist."""

    def __init__(self, message: str = "Medication not found.") -> None:
        """Initialise with a default message.

        Args:
            message (str): Description of what went wrong.
        """
        super().__init__(message)


class InvalidPackageCountError(CabinetError):
    """Raised when the supplied package_count is below the minimum (1)."""

    def __init__(self, message: str = "Package count must be at least 1.") -> None:
        """Initialise with a default message.

        Args:
            message (str): Description of what went wrong.
        """
        super().__init__(message)


class InvalidPartialTabletCountError(CabinetError):
    """Raised when partial_tablet_count is invalid for the selected variant.

    This covers two cases: a partial count supplied for a non-tablet variant,
    and a partial count outside the valid range (1 … tablets_per_package − 1).
    """

    def __init__(
        self,
        message: str = "Invalid partial tablet count for the selected variant.",
    ) -> None:
        """Initialise with a default message.

        Args:
            message (str): Description of what went wrong.
        """
        super().__init__(message)


class EntryNotFoundError(CabinetError):
    """Raised when a cabinet entry does not exist or does not belong to the user."""

    def __init__(self, message: str = "Cabinet entry not found.") -> None:
        """Initialise with a default message.

        Args:
            message (str): Description of what went wrong.
        """
        super().__init__(message)


class CabinetInvariantError(CabinetError):
    """Raised when an internal data invariant is violated in the cabinet domain.

    Signals a bug or corrupt data (e.g. a tablet-based registry row with NULL
    capacity), not a user mistake. The router maps this to 500.
    """

    def __init__(
        self,
        message: str = "An internal invariant was violated in the cabinet domain.",
    ) -> None:
        """Initialise with a default message.

        Args:
            message (str): Description of what went wrong.
        """
        super().__init__(message)


class InvalidDosageError(CabinetError):
    """Raised when the supplied usage/dosage fields are invalid for the selected variant."""

    def __init__(
        self,
        message: str = "Invalid dosage configuration for the selected variant.",
    ) -> None:
        """Initialise with a default message.

        Args:
            message (str): Description of what went wrong.
        """
        super().__init__(message)


class CabinetDatabaseError(CabinetError):
    """Raised when a cabinet database query fails (e.g. connection unavailable).

    Wraps a SQLAlchemy error so the router can map it to 503 rather than leaking
    a raw 500.
    """

    def __init__(
        self,
        message: str = "A database error occurred in the cabinet domain.",
    ) -> None:
        """Initialise with a default message.

        Args:
            message (str): Description of what went wrong.
        """
        super().__init__(message)


class NotificationsError(Exception):
    """Base class for notifications domain errors.

    Kept separate from the other domain taxonomies so notifications errors
    do not bleed into cabinet/users error handling.

    Attributes:
        message (str): Human-readable description of the error (English).
    """

    def __init__(self, message: str) -> None:
        """Initialise the error with a message.

        Args:
            message (str): Description of what went wrong.
        """
        super().__init__(message)
        self.message = message


class NotificationsDatabaseError(NotificationsError):
    """Raised when a notifications database query fails (e.g. connection unavailable).

    Wraps a SQLAlchemy error so the router can map it to 503 rather than leaking
    a raw 500.
    """

    def __init__(
        self,
        message: str = "A database error occurred in the notifications domain.",
    ) -> None:
        """Initialise with a default message.

        Args:
            message (str): Description of what went wrong.
        """
        super().__init__(message)


class DismissalEntryNotFoundError(NotificationsError):
    """Raised when a dismissal references a cabinet entry that does not exist.

    Distinguishes a genuine foreign-key violation (unknown ``cabinet_entry_id``)
    from the unique-constraint race — a duplicate dismissal, which is treated as
    success — so the router can map it to 404 rather than silently returning 204.
    """

    def __init__(self, message: str = "Cabinet entry not found.") -> None:
        """Initialise with a default message.

        Args:
            message (str): Description of what went wrong.
        """
        super().__init__(message)

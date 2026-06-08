"""Pydantic request/response schemas for the auth endpoints."""

from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    """Request body for POST /auth/register.

    Attributes:
        email: User's email address.
        password: Plain-text password (minimum 8 characters).
    """

    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        """Validate that the password meets the minimum length requirement.

        Args:
            v: The raw password value.

        Returns:
            The password unchanged if valid.

        Raises:
            ValueError: If the password is shorter than 8 characters.
        """
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        return v


class LoginRequest(BaseModel):
    """Request body for POST /auth/login.

    Attributes:
        email: User's email address.
        password: Plain-text password.
    """

    email: EmailStr
    password: str


class UserOut(BaseModel):
    """Public user representation returned in auth responses.

    Attributes:
        id: The user's UUID (equals the Supabase auth sub).
        email: The user's email address.
    """

    id: UUID
    email: str


class AuthResponse(BaseModel):
    """Response body for register and login endpoints.

    Attributes:
        access_token: Short-lived Supabase access JWT.
        token_type: Always "bearer".
        user: Basic user identity.
    """

    access_token: str
    token_type: str = "bearer"
    user: UserOut

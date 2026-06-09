"""JWT verification dependencies for FastAPI route protection."""

from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.api.v1.auth.types import CurrentUser
from app.core.config import settings

_jwks = PyJWKClient(settings.jwks_url)
_bearer = HTTPBearer()


def _get_signing_key(token: str) -> object:
    """Resolve the RSA/EC signing key for the given JWT from the JWKS endpoint.

    Args:
        token: The raw JWT string.

    Returns:
        The public signing key object.

    Raises:
        HTTPException: 503 if the JWKS endpoint is unreachable; 401 if the key
            cannot be resolved.
    """
    try:
        return _jwks.get_signing_key_from_jwt(token).key
    except jwt.PyJWKClientConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to reach the JWKS endpoint.",
        ) from e
    except (jwt.PyJWKClientError, jwt.DecodeError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to resolve signing key.",
        ) from e


def _decode_jwt(token: str, key: object) -> dict:
    """Decode and validate a JWT against the project's issuer/audience settings.

    Args:
        token: The raw JWT string.
        key: The signing key returned by `_get_signing_key`.

    Returns:
        The verified claims payload as a dictionary.

    Raises:
        HTTPException: 401 with a specific message for each validation failure.
    """
    try:
        return jwt.decode(
            token,
            key,
            algorithms=settings.jwt_algorithms,
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
        ) from e
    except jwt.MissingRequiredClaimError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token is missing required claim: {e}.",
        ) from e
    except jwt.InvalidAudienceError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token audience is invalid.",
        ) from e
    except jwt.InvalidIssuerError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token issuer is invalid.",
        ) from e
    except jwt.DecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token could not be decoded.",
        ) from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid.",
        ) from e


def get_token_claims(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """FastAPI dependency that extracts and validates the Bearer JWT from the request.

    Args:
        credentials: Bearer credentials extracted by `HTTPBearer`.

    Returns:
        The verified JWT claims payload.

    Raises:
        HTTPException: 401 if the token is invalid or cannot be verified.
    """
    token = credentials.credentials
    key = _get_signing_key(token)
    return _decode_jwt(token=token, key=key)


def get_current_user(claims: dict = Depends(get_token_claims)) -> CurrentUser:
    """FastAPI dependency that maps verified JWT claims to a CurrentUser.

    Args:
        claims: Verified JWT payload provided by `get_token_claims`.

    Returns:
        A `CurrentUser` with `id` (Supabase sub) and `email`.
    """
    return CurrentUser(id=UUID(claims["sub"]), email=claims.get("email", ""))

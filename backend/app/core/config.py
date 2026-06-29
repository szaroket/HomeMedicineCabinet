"""Application configuration loaded from environment variables."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Pydantic-settings singleton for all environment-backed configuration.

    Attributes:
        database_url (str): Async Postgres connection string (asyncpg).
        supabase_url (str): Base URL of the Supabase project (e.g. https://xxx.supabase.co).
        supabase_anon_key (str): Supabase anon/public API key.
        jwt_audience (str): Expected `aud` claim in Supabase JWTs.
        jwt_algorithms (list[str]): Allowed signing algorithms for JWT verification.
        auth_cookie_name (str): Name of the refresh-token cookie.
        auth_cookie_path (str): Path scope for the refresh-token cookie.
        auth_cookie_secure (bool): Whether the refresh cookie carries the `Secure`
            flag. Defaults to True (HTTPS-only); set False for localhost HTTP dev.
        log_level (str): Root log level (e.g. DEBUG, INFO, WARNING). Defaults to INFO.
        log_format (Literal["console", "json"]): Log output format. Use "console" for
            local development and "json" for deployed environments.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    supabase_url: str
    supabase_anon_key: str

    jwt_audience: str = "authenticated"
    jwt_algorithms: list[str] = ["ES256", "RS256"]

    auth_cookie_name: str = "refresh_token"
    auth_cookie_path: str = "/api/v1/auth"
    auth_cookie_secure: bool = True

    log_level: str = "INFO"
    log_format: Literal["console", "json"] = "console"

    @property
    def jwt_issuer(self) -> str:
        """Return the JWT issuer URL derived from the Supabase project URL."""
        return f"{self.supabase_url}/auth/v1"

    @property
    def jwks_url(self) -> str:
        """Return the JWKS endpoint URL used to fetch public signing keys."""
        return f"{self.jwt_issuer}/.well-known/jwks.json"


settings = Settings()  # pyright: ignore[reportCallIssue]

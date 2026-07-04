from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, sourced from environment variables / .env.

    Required fields have no defaults on purpose: if one is missing, Pydantic
    raises a ValidationError at import time and the app refuses to boot,
    instead of silently running with an undefined value.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["local", "development", "staging", "production"]
    app_port: int = 8000

    database_url: str = Field(min_length=1)
    redis_url: str = Field(min_length=1)

    # Auth / JWT. jwt_secret_key has no default on purpose (security-critical):
    # a missing value must fail fast at import time rather than boot with a
    # predictable secret. Use a long random value (>=32 chars) in every env.
    jwt_secret_key: str = Field(min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Auth cookies. Keep secure=True everywhere except plain-HTTP local dev.
    cookie_secure: bool = True
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_domain: str | None = None

    # Rate limiting (per minute).
    rate_limit_public_per_minute: int = 100
    rate_limit_authenticated_per_minute: int = 1000


settings = Settings()

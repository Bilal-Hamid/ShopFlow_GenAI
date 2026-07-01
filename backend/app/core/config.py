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


settings = Settings()

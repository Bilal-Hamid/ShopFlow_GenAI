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
    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Auth cookies. Keep secure=True everywhere except plain-HTTP local dev.
    cookie_secure: bool = True
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_domain: str | None = None

    # Rate limiting (per minute).
    rate_limit_public_per_minute: int = 100
    rate_limit_authenticated_per_minute: int = 1000

    # Stripe. Optional (default None) so the app still boots in environments
    # without payments configured (tests for other modules, frontend-only
    # deploys); the payment webhook returns a problem response if unset, and
    # checkout simply skips creating a hosted payment session.
    # - stripe_secret_key: the API key used to create Checkout Sessions. Prefer
    #   a restricted key (rk_...) scoped to Checkout Sessions over a raw sk_.
    # - stripe_webhook_secret: the endpoint's *signing secret* (whsec_...), used
    #   only to verify inbound webhook signatures — not an API key.
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    # Pinned Stripe API version for outbound calls (dynamic payment methods and
    # integration_identifier require a recent version).
    stripe_api_version: str = "2026-06-24.dahlia"
    # ISO currency for checkout amounts (the schema has no per-order currency).
    payment_currency: str = "usd"
    # Where Stripe redirects the customer after a hosted checkout completes or
    # is cancelled; the order id is appended as a query param.
    frontend_base_url: str = "http://localhost:3000"


settings = Settings()

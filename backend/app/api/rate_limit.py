"""Redis-backed fixed-window rate limiting, exposed as a FastAPI dependency.

Standards: 100 req/min per IP on public endpoints; 1000 req/min per
authenticated user on authenticated endpoints. This module provides the public
limiter (keyed by client IP); the authenticated limiter (keyed by user id) is
wired alongside ``get_current_user`` in ``deps.py`` for later endpoint groups.

The window is a coarse fixed window: a counter per (scope, identifier, minute)
that expires after the window. Simple, atomic (INCR), and sufficient for the
assignment's limits. A sliding-log/token-bucket algorithm would smooth burst
behaviour at the window boundary but is out of scope here.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from fastapi import Request

from app.api.errors import ProblemException
from app.core.config import settings
from app.db.redis import redis_client

WINDOW_SECONDS = 60


def _client_ip(request: Request) -> str:
    # request.client is None for some ASGI transports (e.g. test clients).
    return request.client.host if request.client else "unknown"


class RateLimiter:
    """A callable dependency enforcing ``limit`` requests per 60s per identifier."""

    def __init__(
        self,
        limit: int,
        scope: str,
        identifier: Callable[[Request], str | Awaitable[str]],
    ) -> None:
        self.limit = limit
        self.scope = scope
        self.identifier = identifier

    async def __call__(self, request: Request) -> None:
        ident = self.identifier(request)
        if isinstance(ident, Awaitable):
            ident = await ident

        # Bucket by wall-clock minute so the counter and its TTL align.
        key = f"ratelimit:{self.scope}:{ident}:{_minute_bucket()}"

        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, WINDOW_SECONDS)

        if count > self.limit:
            ttl = await redis_client.ttl(key)
            retry_after = str(ttl if ttl and ttl > 0 else WINDOW_SECONDS)
            raise ProblemException(
                status_code=429,
                detail=(
                    f"Rate limit exceeded: max {self.limit} requests per "
                    f"{WINDOW_SECONDS}s. Retry after {retry_after}s."
                ),
                title="Too Many Requests",
                headers={"Retry-After": retry_after},
            )


def _minute_bucket() -> int:
    return int(datetime.now(UTC).timestamp()) // WINDOW_SECONDS


# Public limiter: 100/min per client IP. Applied to all /auth routes.
public_rate_limiter = RateLimiter(
    limit=settings.rate_limit_public_per_minute,
    scope="public",
    identifier=_client_ip,
)
